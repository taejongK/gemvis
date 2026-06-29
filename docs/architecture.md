# Gemvis - 서비스 아키텍처 (v1, 초기 설계)

> ⚠️ **이 문서는 초기 설계 기록(v1)입니다.** 현재 구현은 [ARCHITECTURE_V2.md](ARCHITECTURE_V2.md)를 우선 참조하세요.
>
> - v2 변경점: `raw_insight` JSON을 KG file 노드에 직접 저장해 **GemInsight를 SSoT로 승격**, `analysis_status` 4-state 머신 도입, API 응답을 `FileRecord` 단일 타입으로 통합.
> - 이 문서의 "Kùzu", "4-레이어 다이어그램" 등은 초기 가정이며 실제 구현과 다를 수 있습니다 (예: 실제는 rdflib TTL).

## 시스템 개요

Gemvis는 온디바이스에서 동작하는 개인 지식그래프 비서로, 다음 4개의 핵심 레이어로 구성됩니다:

```
┌─────────────────────────────────────────────┐
│         User Interface Layer                │
│  (Chat UI, Graph Visualizer, File Browser)  │
└─────────────────────────────────────────────┘
                    ↕
┌─────────────────────────────────────────────┐
│         Agent & Orchestration Layer         │
│    (Gemma 4 Agent + Tool Calling)           │
└─────────────────────────────────────────────┘
                    ↕
┌─────────────────────────────────────────────┐
│      Knowledge Graph & Storage Layer        │
│  (Local Graph DB + Entity Manager)          │
└─────────────────────────────────────────────┘
                    ↕
┌─────────────────────────────────────────────┐
│         File Monitoring Layer               │
│  (File Watcher + Content Extractor)         │
└─────────────────────────────────────────────┘
```

---

## 레이어별 상세 설명

### 1. File Monitoring Layer (파일 감시 레이어)

**역할**: 사용자가 지정한 폴더들을 실시간으로 모니터링하고 변경사항을 감지

**컴포넌트**:
- **File Watcher**: 
  - 지정된 폴더 실시간 모니터링
  - 파일 생성/수정/삭제 이벤트 감지
  - 유휴 시간대 우선 처리 (PC 미사용 시간 적극 활용)
  
- **Content Extractor**:
  - 파일 형식별 내용 추출 (텍스트, 이미지, 음성, PDF 등)
  - 메타데이터 추출 (생성일, 수정일, 위치 정보 등)
  - 지원 확장자: `.txt`, `.md`, `.pdf`, `.jpg`, `.png`, `.mp3`, `.m4a`, `.docx` 등

**데이터 흐름**:
```
파일 변경 → 이벤트 감지 → 내용 추출 → Knowledge Graph Layer로 전달
```

---

### 2. Knowledge Graph & Storage Layer (지식그래프 & 저장 레이어)

**역할**: 추출된 데이터를 구조화하고 엔티티 간 관계를 그래프로 연결

**컴포넌트**:
- **Entity Extractor**: 
  - Gemma 4를 사용하여 엔티티 추출
  - 엔티티 타입: Person, Place, Project, Event, Concept, File
  
- **Relationship Builder**:
  - 엔티티 간 관계 생성
  - 관계 타입: `RELATED_TO`, `CREATED_BY`, `MENTIONED_IN`, `LOCATED_AT`, `PART_OF`, `HAPPENED_AT`
  
- **Graph Database**:
  - 경량 그래프 DB (sqlite-vec 또는 neo4j-lite)
  - 노드와 엣지로 구성된 지식그래프 저장
  - 벡터 임베딩 저장 (의미 기반 검색용)

**그래프 스키마 예시**:
```
[File: "meeting_notes.md"] 
  --MENTIONED--> [Person: "김과장"]
  --ABOUT--> [Project: "Gemvis 해커톤"]
  --CREATED_AT--> [Time: "2026-03-15"]
  --LOCATED_AT--> [Place: "강남역 근처 식당"]
```

---

### 3. Agent & Orchestration Layer (에이전트 & 오케스트레이션 레이어)

**역할**: Gemma 4를 활용하여 파일 분석, 정리, 질의응답 처리

**컴포넌트**:
- **Gemma 4 Agent**:
  - 모델: Gemma 4 E4B (모바일), Gemma 4 26B (데스크톱)
  - 멀티모달 입력 처리 (텍스트, 이미지, 음성)
  - Function calling을 통한 도구 호출
  
- **Tool Registry**:
  - `analyze_file`: 파일 내용 분석 및 엔티티 추출
  - `query_graph`: 지식그래프 쿼리 (Cypher/SPARQL)
  - `suggest_organization`: 파일 정리 제안
  - `create_link`: 파일 간 연결 생성
  - `search_similar`: 의미 기반 유사 파일 검색
  
- **Decision Engine**:
  - Auto-safe vs Review-first 분류
  - 신뢰도 기반 자동화 레벨 결정
  - 불확실한 경우 사용자 확인 요청

---

### 4. User Interface Layer (사용자 인터페이스 레이어)

**역할**: 사용자와의 상호작용 제공

**컴포넌트**:
- **Chat Interface**:
  - 자연어 질의 입력
  - 대화형 파일 검색
  - 에이전트 응답 표시
  
- **Graph Visualizer**:
  - 지식그래프 시각화 (D3.js 또는 Cytoscape.js)
  - 노드 클릭 시 상세 정보 표시
  - 관계 경로 하이라이트
  
- **File Browser**:
  - 기존 파일 시스템 뷰
  - Gemvis가 제안한 정리 구조 뷰 (심볼릭 링크 활용)
  - 검토 대기 파일 목록

---

## 데이터 흐름 시나리오

### 시나리오 1: 새 파일 자동 분석 및 정리

```
1. 사용자가 Downloads 폴더에 "meeting_notes.pdf" 저장
   ↓
2. File Watcher가 파일 생성 이벤트 감지
   ↓
3. Content Extractor가 PDF 내용 추출
   ↓
4. Gemma 4 Agent가 내용 분석:
   - 엔티티 추출: "김과장", "Gemvis 프로젝트", "강남역"
   - 관계 추출: 회의 관련, 2026-03-15 발생
   ↓
5. Knowledge Graph에 노드 및 관계 저장
   ↓
6. Decision Engine 판단: Review-first (회의록은 중요)
   ↓
7. UI에 알림: "새 회의록 발견. '프로젝트/Gemvis/회의록' 폴더에 정리할까요?"
   ↓
8. 사용자 승인 → 심볼릭 링크 생성
```

### 시나리오 2: 자연어 질의

```
사용자: "지난달 김과장이랑 같이 간 식당 어디였지?"
   ↓
Gemma 4 Agent가 질의 분석:
   - 엔티티: "김과장", "식당"
   - 시간: "지난달" (2026-03-01 ~ 2026-03-31)
   - 의도: 장소 검색
   ↓
Tool: query_graph 호출
   ```cypher
   MATCH (p:Person {name: "김과장"})-[:RELATED_TO]-(e:Event)-[:LOCATED_AT]->(place:Place)
   WHERE e.date >= "2026-03-01" AND e.date <= "2026-03-31"
   RETURN place
   ```
   ↓
결과: "강남역 근처 식당"
   ↓
추가 Tool: search_similar 호출
   - 해당 날짜의 사진, 음성메모 검색
   ↓
UI 응답:
   "강남역 근처 식당이에요. 
    관련 파일: meeting_notes.pdf, IMG_1234.jpg, voice_memo_031520.m4a"
   [그래프 시각화: 연결된 노드들 하이라이트]
```

---

## 기술 스택 상세

| 레이어 | 컴포넌트 | 기술 스택 |
|--------|----------|-----------|
| UI | Chat Interface | Electron + React |
| UI | Graph Visualizer | D3.js / Cytoscape.js |
| Agent | LLM | Gemma 4 (E4B/26B) |
| Agent | Orchestration | LangGraph / LlamaIndex |
| Graph | Database | Neo4j Lite / sqlite-vec |
| Graph | Vector Search | FAISS / ChromaDB |
| Monitoring | File Watcher | Chokidar (Node.js) / watchdog (Python) |
| Monitoring | Content Extraction | PyPDF2, Pillow, whisper-cpp |

---

## 배포 아키텍처

### MVP: Desktop-First

```
┌─────────────────────────────────────┐
│       User's Local Machine          │
│  ┌───────────────────────────────┐  │
│  │   Gemvis Desktop App          │  │
│  │   (Electron + Python Backend) │  │
│  └───────────────────────────────┘  │
│              ↕                      │
│  ┌───────────────────────────────┐  │
│  │   Gemma 4 26B Runtime         │  │
│  │   (llama.cpp)                 │  │
│  └───────────────────────────────┘  │
│              ↕                      │
│  ┌───────────────────────────────┐  │
│  │   Local Graph DB + Files      │  │
│  │   (~/.gemvis/)                │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
```

**최소 요구사항**:
- OS: macOS 12+, Windows 10+, Ubuntu 20.04+
- RAM: 16GB+ (Gemma 4 26B 실행용)
- Storage: 30GB+ (모델 + 그래프 DB)

---

## 확장 로드맵

### Phase 1 (해커톤 MVP)
- ✅ 로컬 파일 모니터링
- ✅ 텍스트/PDF 분석
- ✅ 경량 지식그래프 구축
- ✅ 자연어 질의응답
- ✅ 그래프 시각화

### Phase 2 (Post-해커톤)
- 이미지/음성 멀티모달 지원
- Mobile support (Gemma 4 E4B)
- 증분 학습 (사용자 피드백 반영)
- 고급 관계 추론

### Phase 3 (장기)
- Multi-device sync (E2E 암호화)
- Plugin ecosystem
- 외부 데이터 소스 연동 (선택적)

---

## 보안 및 프라이버시

### 핵심 원칙
1. **Zero Cloud Dependency**: 모든 데이터는 로컬에만 존재
2. **Opt-in Only**: 사용자가 명시적으로 지정한 폴더만 접근
3. **Audit Log**: 모든 파일 접근 및 변경 로그 기록
4. **Reversible**: 모든 정리 작업은 되돌릴 수 있음 (심볼릭 링크 활용)

### 보안 조치
- 그래프 DB 암호화 (SQLCipher)
- 민감한 엔티티 자동 감지 (비밀번호, API 키 등) → 경고
- 파일 이동 대신 심볼릭 링크 사용 (원본 보존)

---

## 성능 최적화

### 1. 지능형 스케줄링
- 유휴 시간 감지 (화면 잠금, 배터리 충전 중)
- 백그라운드 작업 우선순위 조정

### 2. 증분 처리
- 전체 재분석 대신 변경분만 처리
- 캐싱 전략: 이미 분석한 파일은 해시 기반 스킵

### 3. 모델 최적화
- Gemma 4 양자화 버전 사용 (4-bit quantization)
- Batch processing (여러 파일 한 번에 분석)

---

## 모니터링 및 디버깅

### 메트릭
- 파일 처리 속도 (files/minute)
- 그래프 크기 (nodes/edges count)
- 질의 응답 시간
- 모델 추론 시간

### 로깅
- 구조화된 로그 (JSON format)
- 레벨: DEBUG, INFO, WARNING, ERROR
- 로그 위치: `~/.gemvis/logs/`

---

## 요약

Gemvis 아키텍처의 핵심은:
1. **온디바이스 우선**: 모든 처리가 로컬에서 발생
2. **지식그래프 중심**: 단순 저장이 아닌 관계형 기억
3. **Gemma 4 활용**: 멀티모달 + tool calling + 프라이버시
4. **점진적 확장**: MVP → 멀티모달 → 모바일 → 동기화

이 구조는 프라이버시를 보장하면서도 강력한 개인 지식 관리를 가능하게 합니다.
