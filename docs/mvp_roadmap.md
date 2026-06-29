# Gemvis - MVP 개발 로드맵 (v1, 초기 일정)

> ⚠️ **이 문서는 초기 5주 로드맵(v1)입니다.** 실제 진행 상황 및 기술 선택은 [plan.md](../plan.md) · [ARCHITECTURE_V2.md](ARCHITECTURE_V2.md) · [FEATURES_SIDEBAR.md](FEATURES_SIDEBAR.md)를 참조하세요. 본문의 "Tauri / Kùzu" 등은 초기 가정입니다.

> 이 로드맵은 [user_scenarios.md](./user_scenarios.md) 의 6개 시나리오를 구현하기 위한 5주 일정이다. 모든 작업은 특정 시나리오를 만족해야 한다.

## MVP 정의

**MVP 목표**: 해커톤 제출용 작동하는 프로토타입으로, 핵심 가치를 입증할 수 있는 최소 기능 제품

**시나리오 커버리지 목표 (Week 5까지)**:
1. ✅ 시나리오 0 — 원클릭 설치 + 온보딩
2. ✅ 시나리오 1 — 첫 대규모 스캔 (관리 폴더 symlink 뷰 생성)
3. ✅ 시나리오 2 — 증분 감지 (신뢰도 기반 자동/리뷰)
4. ✅ 시나리오 3 — 자연어 질의 (NL → Cypher → 답변)
5. ✅ 시나리오 4 — 그래프 시각화 + 엔티티 편집
6. 🟡 시나리오 5 — 설정/관리 (기본 기능만)
7. 🟡 시나리오 6 — 엣지 케이스 복구 (주요 항목만)

---

## Phase 1: 기술 검증 + 인제스트 기반 (Week 1: 4/15 - 4/21)

### 목표
Gemma 4 추론, Kùzu 그래프 DB, 엔티티 추출 파이프라인의 백엔드 기반 완성.

### Tasks

#### 1.1 Gemma 4 로컬 실행 환경 ✅ (4/15 - 4/17 완료)
- [x] `./scripts/setup.sh` 원클릭 설치 (llama.cpp + CUDA 13.0 + Blackwell 지원)
- [x] `unsloth/gemma-4-E2B-it-GGUF` Q4_K_M 다운로드 (`scripts/models.yaml` 레지스트리)
- [x] RTX 5090에서 CUDA 추론 검증 (`"안녕, Gemvis"` 응답 성공)
- [x] 빌드 캐시 관리 + nvcc 자동 선택 + `-ngl 99` 오프로드

**검증 결과**: E2B Q4_K_M 생성 속도 ~30+ t/s, 첫 토큰 지연 <300ms

---

#### 1.2 llama.cpp 서버 + Async Client (Day 4 — 4/18)
- [ ] `scripts/start_server.sh` — llama-server 백그라운드 기동
  ```bash
  llama-server -m <model> -ngl 99 --host 127.0.0.1 --port 8080 \
               --ctx-size 8192 --parallel 2
  ```
- [ ] `backend/gemma_client.py` — async httpx 클라이언트
  - `complete(prompt, max_tokens, stop)` — 일반 생성
  - `complete_json(prompt, schema)` — JSON grammar 강제 출력
  - 재시도 (3회) + 타임아웃 (60초) + health check
- [ ] `tests/test_gemma_client.py` — 모의 없이 실제 서버로 테스트

**성공 기준**: Python에서 JSON 강제 출력이 스키마 어기지 않고 정확히 반환됨

---

#### 1.3 Kùzu 그래프 DB (Day 4 — 4/18)
- [ ] `pip install kuzu` 의존성 추가
- [ ] `backend/graph_db.py` — Kùzu 래퍼 (Repository 패턴)
  - 스키마 정의: Person / Place / Project / Event / Concept / File 노드
  - 관계: MENTIONED_IN / ATTENDED_BY / LOCATED_AT / PART_OF / HAPPENED_AT / TAGGED_AS / RELATED_TO
  - CRUD 메서드: `upsert_entity`, `add_relation`, `query`, `get_subgraph`
- [ ] `backend/schema.cypher` — 스키마 DDL 분리
- [ ] `tests/test_graph_db.py` — 1000 노드 / 5000 간선 CRUD 벤치

**성공 기준**: 1000 노드 insert < 1초, 2-hop 쿼리 < 100ms

---

#### 1.4 엔티티 추출 프롬프트 v1 (Day 5 — 4/19)
- [ ] `backend/prompts/entity_extraction.py` — 프롬프트 상수 + few-shot
- [ ] JSON 스키마 정의 (Pydantic 모델):
  ```python
  class ExtractionResult(BaseModel):
      entities: list[Entity]         # type, name, attributes
      relationships: list[Relation]  # from, to, type
      category: str                  # "업무/회의록" 등 경로형
      confidence: float              # 0-1
      summary: str                   # 1줄 요약
  ```
- [ ] 한국어 테스트 케이스 10개 (`tests/fixtures/` 에 txt/md 샘플)
- [ ] `tests/prompts/test_entity_extraction.py` — 실제 모델로 정확도 측정
  - 목표: F1 ≥ 0.8, 평균 지연 < 5초
- [ ] 결과를 프롬프트 파일 상단에 기록 (규칙: `.claude/rules/gemma-prompts.md`)

---

#### 1.5 인제스트 오케스트레이터 스켈레톤 (Day 6-7 — 4/20-4/21)
- [ ] `backend/ingest.py` — 파이프라인 오케스트레이터
  ```
  파일 경로 → extract_content() → gemma_client.complete_json() → graph_db.upsert()
           → symlink_manager.create_views()
  ```
- [ ] `backend/content_extractor.py` — txt/md 직접, pdf는 `pypdf`
- [ ] `backend/symlink_manager.py` — 관리 폴더 뷰 생성 (by-category, by-person, by-project, by-time)
- [ ] `backend/main.py` — FastAPI 최소: `POST /ingest`, `GET /health`

**엔드투엔드 검증**: 샘플 파일 1개 POST → 그래프 저장 + symlink 생성 확인

---

### Week 1 산출물
- [x] Gemma 4 로컬 실행 환경 ✅
- [ ] llama-server 상주 + Python async client
- [ ] Kùzu 그래프 DB + 스키마 + CRUD 테스트
- [ ] 엔티티 추출 프롬프트 v1 (F1 ≥ 0.8)
- [ ] 인제스트 파이프라인 스켈레톤 (파일 1개 → 그래프 + symlink)

---

## Phase 2: 시나리오 1·2 구현 (Week 2: 4/22 - 4/28)

### 목표
"첫 대규모 스캔"과 "증분 감지"를 백엔드만으로 완주. UI 없이 CLI로 검증 가능한 상태.

### Tasks

#### 2.1 파일 감시 + 증분 파이프라인 (시나리오 2)
- [ ] `backend/file_watcher.py` — watchdog 기반
  - 여러 폴더 동시 감시 (사용자 설정 리스트)
  - 생성/수정/이동 이벤트 구분
  - 디바운스 (동일 파일 중복 이벤트 방지)
- [ ] `backend/ingest_queue.py` — asyncio.Queue 기반 워커 풀
  - 최대 동시 처리 5개
  - 우선순위: 수동 추가 > 증분 감지 > 초기 스캔
  - 일시중지/재개/백그라운드 제어

**성공 기준:** `~/Downloads` 감시 → 새 txt 파일 드롭 후 30초 이내 그래프·symlink 반영

---

#### 2.2 초기 스캔 (시나리오 1)
- [ ] `backend/initial_scan.py` — 선택 폴더 전체를 워커 큐에 enqueue
  - 파일 개수 카운트 + 예상 시간 계산
  - 진행 상황 이벤트 스트림 (WebSocket or SSE)
  - 일시정지/재개 (체크포인트 파일)
- [ ] 중복 감지 (파일 해시 + 이미 분석된 건 스킵)

**성공 기준:** 100개 텍스트 파일 스캔 완료 + 모든 symlink 뷰 생성 확인

---

#### 2.3 Content Extractor 확장
- [ ] `.txt`, `.md` — 완료 (Week 1)
- [ ] `.pdf` — `pypdf` 기본, 암호화 감지 시 skip
- [ ] `.docx` — `python-docx`
- [ ] 손상 파일/권한 오류 → 에러 로그 + 스킵
- [ ] 100MB 초과 → 자동 skip + 플래그

---

#### 2.4 신뢰도 분기 + 리뷰 큐 (시나리오 2.2)
- [ ] `backend/classifier.py` — Gemma 응답의 `confidence` 파싱
  - ≥0.8 → 자동 symlink 생성
  - <0.8 → `_review/` symlink + SQLite 리뷰 테이블에 인큐
- [ ] `backend/review_queue.py` — CRUD (list/approve/reject)
- [ ] FastAPI: `GET /review`, `POST /review/{id}/decide`

---

#### 2.5 NL2Cypher + 답변 합성 (시나리오 3)
- [ ] `backend/prompts/nl2cypher.py` — 스키마 컨텍스트 포함
- [ ] `backend/prompts/answer_synthesis.py` — 쿼리 결과 + 원문 → 자연어
- [ ] `backend/query.py` — 파이프라인 오케스트레이터
- [ ] FastAPI: `POST /query`
- [ ] `tests/test_query.py` — 10개 자연어 질문, 정확도 ≥70%

**성공 기준:** CLI/HTTP 로 "김과장 관련 파일 찾아줘" 호출 시 올바른 파일 목록 반환

---

#### 2.6 엔티티 병합 API (시나리오 4 사전작업)
- [ ] `POST /entities/merge` — 두 노드를 하나로 합침 (관계 상속)
- [ ] `PATCH /entities/{id}` — 이름/속성 수정
- [ ] `DELETE /entities/{id}` — 삭제 + 연결 해제

---

### Week 2 산출물
- [ ] 파일 감시 + 인제스트 파이프라인 (시나리오 1, 2 동작)
- [ ] 신뢰도 기반 자동/리뷰 분기
- [ ] 자연어 질의 엔드포인트 (시나리오 3 백엔드)
- [ ] 엔티티 편집 API (시나리오 4 사전작업)
- [ ] 데모 데이터 10~20개 파일로 엔드투엔드 시연 (CLI/HTTP)

---

## Phase 3: 시나리오 0·4 UI 구현 (Week 3: 4/29 - 5/5)

### 목표
Tauri + React UI를 붙여서 온보딩 → 스캔 → 질의 → 그래프 탐색 전 과정이 **사용자 관점으로** 동작.

### Tasks

#### 3.1 Tauri 초기 구성
- [ ] `frontend/` — `cargo tauri init` + React + TypeScript
- [ ] Rust 사이드: 파일 시스템 권한 설정 (감시 폴더 접근)
- [ ] IPC commands: `pick_folder`, `open_file`, `get_file_count`
- [ ] Backend (FastAPI) 연결 — HTTP 프록시 또는 sidecar
- [ ] 개발 서버 실행 (`npm run tauri dev`) 확인

---

#### 3.2 온보딩 플로우 (시나리오 0.2, 5화면)
- [ ] 화면 1: 환영
- [ ] 화면 2: 프라이버시 동의
- [ ] 화면 3: 감시 폴더 선택 (멀티 선택, 파일 개수 미리 표시)
- [ ] 화면 4: 관리 폴더 위치 (기본 `~/Gemvis/`)
- [ ] 화면 5: 스캔 시작 버튼 + 예상 시간
- [ ] 온보딩 완료 상태 저장 (SQLite or JSON)

---

#### 3.3 Chat Interface (시나리오 3)
- [ ] `components/ChatInterface.tsx` — 메시지 리스트 + 입력
- [ ] 스트리밍 응답 (llama-server SSE or 폴링)
- [ ] 관련 파일 카드 (클릭 시 네이티브 앱으로 열기)
- [ ] "그래프에서 보기" 버튼 → Graph 탭 이동 + 해당 노드 하이라이트
- [ ] 모호한 질문에 되묻기 (시나리오 3.2)
- [ ] 제안 질문 (초기 화면에 3개)

---

#### 3.4 Graph Visualization (시나리오 4)
- [ ] `react-force-graph-3d` 통합
- [ ] 노드 색상/크기 규칙 (type별, degree 기반)
- [ ] 노드 클릭 → 우측 상세 패널
- [ ] 필터 (노드 타입별 토글)
- [ ] 검색 (이름으로 노드 점프)
- [ ] 엔티티 편집 모달 (rename, merge, delete)
- [ ] 타입 범례 (legend)

---

#### 3.5 진행 상황 UI (시나리오 1)
- [ ] 상단 상태바: 스캔 진행률, 현재 파일명, 예상 남은 시간
- [ ] 일시정지/재개 버튼
- [ ] 리뷰 큐 배지 (`_review/` 개수)
- [ ] 리뷰 모달: 후보 선택 or 새 카테고리 입력

---

### Week 3 산출물
- ✅ 온보딩 → 첫 스캔 → 질의응답 → 그래프 탐색 UI 엔드투엔드
- ✅ 엔티티 편집 모달 (이름 변경, 병합)
- ✅ 리뷰 큐 UI
- ✅ Tauri 빌드 성공 (DMG/AppImage/MSI)

---

## Phase 4: 다듬기 (Week 4: 5/6 - 5/12)

### 목표
버그 수정, 성능 최적화, 사용자 경험 개선

### Tasks

#### 4.1 버그 수정
- [ ] 엣지 케이스 테스트
  - 빈 파일
  - 손상된 PDF
  - 권한 오류
  - 대용량 파일 (>100MB)
- [ ] 에러 핸들링 강화
- [ ] 로그 추가 (디버깅용)

---

#### 4.2 성능 최적화
- [ ] 캐싱 전략
  ```python
  @lru_cache(maxsize=1000)
  def analyze_file_cached(file_hash: str):
      ...
  ```
- [ ] 배치 처리 (여러 파일 한 번에 분석)
- [ ] 인덱스 추가 (그래프 DB)
  ```cypher
  CREATE INDEX person_name FOR (p:Person) ON (p.name);
  ```
- [ ] 메모리 사용량 최적화

**목표**:
- 파일 1개 처리 시간: <5초 (이전 10초)
- 메모리 사용량: <16GB

---

#### 4.3 UI/UX 개선
- [ ] 다크 모드 지원
- [ ] 키보드 단축키 (Cmd+K: 검색, Cmd+N: 새 파일)
- [ ] 툴팁 및 도움말
- [ ] 온보딩 플로우
  1. 환영 메시지
  2. 폴더 선택 (모니터링할 폴더)
  3. 첫 분석 시작
  4. 튜토리얼 (간단한 질문 예시)

---

#### 4.4 데모 데이터 준비
- [ ] 테스트용 샘플 파일 20개 생성
  - 회의록 5개
  - PDF 논문 5개
  - 이미지 5개
  - 메모 5개
- [ ] 각 파일에 의도적으로 연결 관계 포함
  - "김과장"이라는 이름이 여러 파일에 등장
  - "Gemvis 프로젝트"가 공통 주제
  - 날짜/장소 정보 포함
- [ ] 데모 시나리오 스크립트 작성

---

### Week 4 산출물
- ✅ 안정적인 애플리케이션 (치명적 버그 제거)
- ✅ 성능 목표 달성 (응답 <5초)
- ✅ 직관적인 UI/UX
- ✅ 데모용 샘플 데이터

---

## Phase 5: 제출 준비 (Week 5: 5/13 - 제출일)

### 목표
해커톤 제출 자료 완성

### Tasks

#### 5.1 데모 영상 제작 (3분, [user_scenarios.md#데모-시나리오](./user_scenarios.md) 기준)
- [ ] 스크립트:
  - Act 1: Problem (30초) — 어수선한 Downloads 폴더
  - Act 2: Demo (2분) — 폴더 추가 → 실시간 분석 타임랩스 → 자연어 질의 → 그래프 탐색
  - Act 3: Why it matters (30초) — **네트워크 끊고 질의** (프라이버시 데모)
- [ ] 화면 녹화 (OBS Studio)
- [ ] 편집 (자막, 배경음악, 트랜지션)
- [ ] 유튜브 업로드 (Unlisted)

**품질 목표**:
- 해상도: 1080p
- 오디오: 명확한 나레이션
- 자막: 한글 + 영어

---

#### 5.2 README.md 작성
- [ ] 구조:
  ```markdown
  # Gemvis - Privacy-First On-Device Personal Knowledge Graph
  
  ## Problem
  ## Solution
  ## Why Gemma 4?
  ## Demo
  ## Installation
  ## Architecture
  ## Tech Stack
  ## Social Impact
  ## Roadmap
  ## Team
  ```
- [ ] 시각 자료 추가
  - 아키텍처 다이어그램
  - 스크린샷 5장
  - Before/After 비교
  - 그래프 시각화 GIF

---

#### 5.3 발표 슬라이드
- [ ] 10장 구성
  1. Title Slide
  2. Problem (통계 + 사례)
  3. Existing Solutions (비교 매트릭스)
  4. Gemvis Solution (한 줄 + 다이어그램)
  5. Demo Screenshot 1 (Chat UI)
  6. Demo Screenshot 2 (Graph Viz)
  7. Technical Architecture
  8. Gemma 4 Integration
  9. Social Impact (페르소나)
  10. Roadmap + Call to Action
- [ ] 디자인 템플릿 적용 (Canva 또는 Pitch)

---

#### 5.4 코드 정리
- [ ] 코드 리뷰 및 리팩토링
- [ ] 주석 추가 (핵심 로직 설명)
- [ ] 불필요한 파일 삭제
- [ ] 폴더 구조 정리
  ```
  gemvis/
  ├── backend/
  │   ├── main.py
  │   ├── file_watcher.py
  │   ├── content_extractor.py
  │   ├── gemma_agent.py
  │   └── graph_db.py
  ├── frontend/
  │   ├── src/
  │   └── public/
  ├── docs/
  ├── tests/
  ├── README.md
  └── LICENSE
  ```
- [ ] LICENSE 추가 (MIT 또는 Apache 2.0)

---

#### 5.5 최종 점검
- [ ] 다른 Mac에서 설치 테스트 (Clean Install)
- [ ] 모든 링크 작동 확인
- [ ] 데모 영상 재생 확인
- [ ] 오타 및 문법 검토 (Grammarly)
- [ ] 제출 폼 작성 (Kaggle)

---

### Week 5 산출물
- ✅ 5분 데모 영상 (유튜브 링크)
- ✅ 완성된 README.md
- ✅ 발표 슬라이드 (PDF)
- ✅ 정리된 코드 (GitHub)
- ✅ Kaggle 제출 완료

---

## 개발 환경 및 도구

### 필수 도구
- **Python**: 3.11+
- **Node.js**: 18+
- **llama.cpp**: Gemma 4 실행 (GPU/CPU 자동)
- **Git**: 버전 관리

### IDE 및 에디터
- **Backend**: VS Code + Python extension
- **Frontend**: VS Code + React extension
- **DB**: Neo4j Browser 또는 DBeaver

### 협업 도구
- **GitHub**: 코드 저장소
- **Slack**: 팀 커뮤니케이션
- **Notion**: 작업 관리 (선택적)
- **Loom**: 화면 녹화

---

## 역할 분담 제안

| 역할 | 담당자 | 주요 작업 |
|------|--------|---------|
| **Backend Lead** | 인규 | Gemma 4 통합, 파이프라인 구축 |
| **Graph Expert** | 준혁 | 지식그래프 설계, 쿼리 최적화 |
| **Frontend Lead** | 혜지 | Electron UI, 그래프 시각화 |
| **Content** | 태종 | 문서 작성, 데모 영상 |

**협업 방식**:
- 매일 Slack에 진행 상황 공유
- 주 2회 화상 회의 (화요일, 금요일)
- GitHub Pull Request 리뷰 (코드 품질 유지)

---

## 위험 관리

### 위험 1: Gemma 4 성능이 예상보다 낮음

**완화 전략**:
- Week 1에 조기 검증
- 양자화 버전 테스트 (4-bit, 8-bit)
- 프롬프트 최적화
- 최악의 경우: Gemma 4 9B로 폴백 (속도 우선)

---

### 위험 2: 그래프 DB 성능 이슈

**완화 전략**:
- MVP는 경량 DB (sqlite-vec)
- 노드/엣지 수 제한 (테스트 데이터 <1000개)
- 인덱스 적극 활용
- 필요 시 메모리 DB 사용

---

### 위험 3: UI 개발 지연

**완화 전략**:
- Week 2에 기본 구조 먼저 완성
- 템플릿 활용 (Electron Boilerplate)
- 그래프 시각화는 기존 라이브러리 활용 (직접 구현 X)
- 최악의 경우: 웹 UI로 대체 (Electron 포기)

---

### 위험 4: 시간 부족

**완화 전략**:
- **MoSCoW 우선순위** (시나리오 기반):
  - **Must**: 시나리오 0 (설치+온보딩), 1 (초기 스캔+symlink), 2 (증분+리뷰), 3 (자연어 질의)
  - **Should**: 시나리오 4 (그래프+엔티티 편집), 시나리오 5 기본 설정
  - **Could**: 멀티모달 (OCR, ASR), 벡터 하이브리드, 피드백 학습
  - **Won't**: Mobile, Multi-device Sync, 플러그인, 외부 API 연동
- Must 항목 먼저 완성 후 나머지 추가
- Week 4에 Feature Freeze (새 기능 추가 금지, `.claude/hooks/pre-commit`이 자동 체크)

---

## 성공 기준

### Minimum Viable Demo (최소 성공)
- [x] Gemma 4 로컬 실행
- [x] 텍스트 파일 자동 분석
- [x] 간단한 지식그래프 생성
- [x] 자연어 질의 1개 성공
- [x] 기본 UI (작동 확인)

### Target Demo (목표)
- [x] 최소 성공 +
- [x] 3가지 파일 형식 지원
- [x] 그래프 시각화
- [x] Chat UI
- [x] 5분 데모 영상

### Stretch Goal (이상적)
- [x] 목표 +
- [x] 이미지 OCR
- [x] 음성 전사
- [x] 파일 정리 제안
- [x] 10장 슬라이드 발표

---

## 일일 체크인 템플릿

매일 Slack에 다음 형식으로 공유:

```
[날짜] 진행 상황

✅ 완료:
- Task 1
- Task 2

🚧 진행 중:
- Task 3 (70% 완료)

❌ 블로커:
- 이슈 설명

📅 내일 계획:
- Task 4
- Task 5
```

---

## 최종 체크리스트

제출 전 마지막 확인:

### 기능
- [ ] 파일 자동 감지 및 분석
- [ ] 지식그래프 생성
- [ ] 자연어 질의응답
- [ ] 그래프 시각화
- [ ] Chat UI

### 제출 자료
- [ ] README.md (완성)
- [ ] 데모 영상 (5분)
- [ ] 슬라이드 (10장)
- [ ] 코드 (GitHub)
- [ ] LICENSE

### 품질
- [ ] 치명적 버그 없음
- [ ] 다른 Mac에서 설치 성공
- [ ] 응답 시간 <5초
- [ ] 데모 시나리오 3개 모두 성공

### 스토리
- [ ] 문제 설명 명확
- [ ] Gemma 4 활용 강조
- [ ] 사회적 임팩트 설명
- [ ] 확장 로드맵 제시

---

## 결론

이 로드맵은 **5주간의 집중 개발**을 통해 해커톤 제출 가능한 MVP를 만드는 계획입니다.

핵심은:
1. **Week 1**: 기술 검증 (실패하면 빨리 알 수 있음)
2. **Week 2-3**: 핵심 기능 구현
3. **Week 4**: 다듬기 (버그 수정, 성능 개선)
4. **Week 5**: 제출 준비 (문서, 영상)

**성공의 열쇠**:
- 조기 검증 (Week 1에 모든 위험 확인)
- 명확한 우선순위 (MoSCoW)
- 정기적 소통 (매일 체크인)
- Feature Freeze (Week 4 이후 새 기능 금지)

한 달은 충분히 긴 시간입니다. 계획대로만 하면 가능합니다! 💪
