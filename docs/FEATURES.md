# Gemvis 기능 스펙 정리

> **최종 업데이트**: 2026-05-11  
> **버전**: MVP 1.0 (해커톤 제출 버전)
>
> **관점별 문서 안내**:
>
> - 👉 **사이드바 메뉴별 기능 + GemInsight 필드 매핑**: [FEATURES_SIDEBAR.md](FEATURES_SIDEBAR.md)
> - 👉 **v2 아키텍처 (raw_insight SSoT)**: [ARCHITECTURE_V2.md](ARCHITECTURE_V2.md)
> - 이 문서는 **컴포넌트/계층** 관점의 레퍼런스입니다.

이 문서는 Gemvis 프로젝트의 **실제 구현된 기능**을 백엔드/프론트엔드/데이터 계층별로 정리한 레퍼런스입니다.

---

## 목차

1. [시스템 아키텍처](#시스템-아키텍처)
2. [백엔드 기능](#백엔드-기능)
3. [프론트엔드 기능](#프론트엔드-기능)
4. [데이터 저장소](#데이터-저장소)
5. [API 엔드포인트](#api-엔드포인트)
6. [지원 파일 형식](#지원-파일-형식)
7. [보안 및 프라이버시](#보안-및-프라이버시)
8. [성능 특성](#성능-특성)

---

## 시스템 아키텍처

```
┌────────────────────────────────────────────────────────────┐
│                    프론트엔드 (React)                        │
│  Dashboard │ GraphView │ Search │ Calendar │ Settings      │
│  (Vite + TypeScript + React Router + FullCalendar)         │
└─────────────────────┬──────────────────────────────────────┘
                      │ REST API (HTTP)
┌─────────────────────┴──────────────────────────────────────┐
│                  백엔드 (FastAPI)                            │
│  api.py: HTTP 엔드포인트 + 라이프사이클 관리                 │
├──────────────────────────────────────────────────────────────┤
│  핵심 컴포넌트:                                               │
│  • analyzer.py      - 파일 분석 (LLM 호출)                   │
│  • search.py        - 하이브리드 검색 엔진                    │
│  • knowledge_graph.py - RDF 그래프 + SPARQL 쿼리             │
│  • embeddings.py    - 벡터 임베딩 (sentence-transformer)     │
│  • watcher.py       - 파일 시스템 감시 (watchdog)            │
│  • summary.py       - 일일 요약 생성                         │
│  • scheduler.py     - 백그라운드 요약 스케줄러                │
│  • event_log.py     - 파일 이벤트 로그 (TTL)                 │
│  • schedule.py      - 주간 업무 스케줄                       │
│  • llm_client.py    - LLM 통신 (OpenAI 호환)                │
└─────────────────────┬──────────────────────────────────────┘
                      │
┌─────────────────────┴──────────────────────────────────────┐
│                로컬 LLM 서버 (llama-server)                  │
│  • Gemma 4 E2B Q4_K_M (~2GB GGUF)                           │
│  • Metal 가속 (Apple Silicon) / CUDA / CPU                  │
│  • OpenAI 호환 API (/v1/chat/completions)                   │
│  • 멀티모달 지원 (텍스트 + 이미지)                           │
└──────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│               데이터 저장소 (로컬 파일)                       │
│  • ~/.gemvis/graph.ttl        - 지식그래프 (RDF/Turtle)      │
│  • ~/.gemvis/embeddings.npz   - 벡터 임베딩 (numpy)          │
│  • ~/.gemvis/events.ttl       - 파일 이벤트 로그             │
│  • ~/.gemvis/schedule.json    - 주간 업무 스케줄             │
└──────────────────────────────────────────────────────────────┘
```

---

## 백엔드 기능

### 1. 파일 분석 (analyzer.py)

#### 기능
- 지원 파일 형식을 자동으로 분석하여 구조화된 메타데이터 추출
- Gemma 4 로컬 LLM을 통한 의미론적 분석

#### 분석 항목
- **category**: 파일 유형 (memo/photo/screenshot/document/voice_memo/code/data/other)
- **summary**: 한 줄 요약 (한국어)
- **tags**: 관련 태그 리스트 (3-7개, 한국어)
- **entities**: 추출된 엔티티
  - `people`: 사람 이름
  - `places`: 장소
  - `projects`: 프로젝트명
  - `dates`: 날짜
  - `events`: 이벤트
- **relations**: 엔티티 간 관계
  - `source` / `target`: 엔티티명
  - `source_type` / `target_type`: 엔티티 타입
  - `relation`: 관계 유형 (belongs_to/located_at/participated_in/works_on/occurred_at/related_to)
- **risk_level**: 민감도 (auto_safe / review_first)

#### 처리 방식
- **텍스트 파일**: 최대 10,000자까지 직접 전송
- **이미지 파일**: base64 data URL로 인코딩 후 비전 모델 전송
  - 멀티모달 미지원 시 파일명 기반 폴백
- **PDF 파일**: pypdf로 텍스트 추출 후 LLM 전달

#### 에러 처리
- JSON 파싱 실패 시 error 필드에 기록
- LLM 응답 실패 시 기본값 반환
- 마크다운 코드 펜스 자동 제거

---

### 2. 지식그래프 (knowledge_graph.py)

#### 저장 형식
- **RDF/Turtle (.ttl)** — 표준 시맨틱 웹 형식
- rdflib 라이브러리 사용

#### 노드 타입 (7종)
```python
NODE_TYPES = {
  "file",      # 파일
  "person",    # 사람
  "place",     # 장소
  "project",   # 프로젝트
  "event",     # 이벤트
  "date",      # 날짜
  "tag"        # 태그
}
```

#### 시스템 노드 (숨김)
```python
SYSTEM_NODE_TYPES = {
  "daily_summary"  # 일일 요약 (검색/통계에서 제외)
}
```

#### 엣지 타입 (10종)
```python
EDGE_TYPES = {
  "mentions",        # 파일 → 엔티티 (일반 언급)
  "taken_at",        # 파일 → 장소 (사진 촬영 위치)
  "related_to",      # 범용 관계
  "part_of",         # 부분-전체
  "created_on",      # 생성 날짜
  "tagged_with",     # 파일 → 태그
  "added_on",        # 그래프 추가 날짜
  "belongs_to",      # 사람 → 프로젝트
  "located_at",      # 엔티티 → 장소
  "participated_in", # 사람 → 이벤트
  "works_on",        # 사람 → 프로젝트
  "occurred_at"      # 이벤트 → 날짜
}
```

#### 주요 메서드
- `add_file_analysis(result: AnalysisResult)`: 분석 결과를 그래프에 추가
- `search_nodes(query, node_type=None)`: CONTAINS 필터로 노드 검색
- `get_neighbors(node_id)`: 1-hop 이웃 노드 조회
- `get_file_nodes()`: 모든 파일 노드 반환
- `get_graph_data()`: 프론트엔드용 JSON 형식 변환
- `get_stats()`: 통계 (노드/엣지 수, 타입별 분포)
- `clear()`: 그래프 전체 초기화

#### URI 스키마
```
노드: http://gemvis.local/node/{type}/{url_encoded_name}
타입: http://gemvis.local/type/{type}
관계: http://gemvis.local/rel/{relation}
속성: http://gemvis.local/attr/{attribute}
```

---

### 3. 벡터 임베딩 (embeddings.py)

#### 모델
- **sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2**
- 384차원 벡터
- 다국어 지원 (한국어/영어)

#### 저장 형식
- `.npz` (numpy 압축 배열)
- 메모리 맵 가능

#### 주요 메서드
- `encode(text)`: 텍스트 → 벡터
- `add_or_update(node_id, text)`: 노드 임베딩 저장
- `remove(node_id)`: 임베딩 삭제
- `top_k(query, k=10)`: 유사도 상위 K개 반환
- `score(query, node_ids)`: 특정 노드들의 유사도 점수

#### 인덱싱 대상
- 파일: `{name} | {summary} | {tags}`
- 엔티티: `{name}`

#### 성능
- 첫 로드: ~10초 (워밍업)
- 검색: <100ms (1000 노드 기준)

---

### 4. 하이브리드 검색 (search.py)

#### 검색 파이프라인
```
사용자 질문
    ↓
1. 의도 파싱 (Intent Parsing)
   - 간단한 질문 (3단어 이하, 구두점 없음) → 룰 기반
   - 복잡한 질문 → LLM 파싱
   ↓
   출력: {
     search_terms: [],    // 구조적 키워드 (이름, 날짜, 태그)
     node_types: [],      // 노드 타입 필터
     categories: [],      // 파일 카테고리 필터
     semantic_query: ""   // 의미적 검색어
   }
    ↓
2. 그래프 검색 (Structural)
   - search_terms 각각에 대해 CONTAINS 매칭
   - 매칭된 엔티티의 1-hop 이웃 파일 수집
   - 복수 term은 AND 결합 (교집합)
   ↓
3. 임베딩 재랭킹 (Semantic)
   - semantic_query로 2단계 결과 파일들 재정렬
   - cosine similarity 내림차순
   ↓
4. 답변 생성 (LLM)
   - 파일 리스트 + 관련 엔티티 → LLM 프롬프트
   - 파일 개수 일치 강제 (UI와 동기화)
   ↓
출력: {
  answer: "",             // 자연어 답변
  intent: {...},          // 파싱된 의도
  graph_results: [...]    // 파일 + 엔티티 노드 (최대 50개)
}
```

#### 폴백 메커니즘
1. **카테고리 전용 쿼리** (예: "이미지 파일")
   - search_terms 없음 + categories 있음 → 해당 카테고리 모든 파일 반환
2. **"최근" 키워드** → 최근 5개 파일 반환
3. **구조적 검색 실패 시**
   - semantic_query 또는 search_terms로 임베딩 검색 (top 20)
4. **LLM 파싱 실패 시** → 룰 기반 폴백

#### 카테고리 자동 감지
```python
_CATEGORY_KEYWORDS = {
  "이미지": ["photo", "screenshot"],
  "사진": ["photo", "screenshot"],
  "문서": ["document"],
  "메모": ["memo"],
  "음성": ["voice_memo"],
  "코드": ["code"],
  "데이터": ["data"],
  ...
}
```

---

### 5. 파일 시스템 감시 (watcher.py)

#### 라이브러리
- **watchdog** — 크로스 플랫폼 파일 시스템 이벤트

#### 감시 이벤트
- **created**: 새 파일 추가 → 자동 분석 + 그래프 추가
- **modified**: 파일 수정 → 재분석 + 그래프 업데이트
- **deleted**: 파일 삭제 → 그래프에서 제거

#### 중복 방지
- `_processed` 캐시로 파일당 1회만 처리
- 삭제 시 캐시에서 제거 (재생성 시 재분석)

#### 이벤트 로깅
- 모든 액션을 EventLog에 기록 (타임스탬프 + 업무/개인 기간 구분)
- 일일 요약 생성 시 사용

#### 백그라운드 실행
- 서버 시작 시 자동 시작
- 별도 스레드에서 감시 (논블로킹)

---

### 6. 일일 요약 (summary.py)

#### 요약 생성 방식
1. **이벤트 수집** (events.ttl)
   - 지정 날짜의 파일 생성/수정/삭제 이벤트 필터
   - 업무 스케줄에 따라 work / personal 기간 분리
2. **파일 메타데이터 조인** (graph.ttl)
   - 이벤트 파일의 현재 요약/카테고리/태그 병합
   - 삭제된 파일은 이벤트만 참조
3. **LLM 요약 생성**
   - 그룹화된 액티비티 → Gemma 4
   - 한국어 2-4 문단 또는 불릿 리스트
4. **그래프 저장**
   - `daily_summary:YYYY-MM-DD_work` / `daily_summary:YYYY-MM-DD_personal`
   - 메타: summary, file_count, created/modified/deleted_count, work_hours

#### 자동 스케줄러 (scheduler.py)
- **주기**: 매일 자정 + 업무 종료 시간
- **조건**: 해당 기간 이벤트 5개 이상 → 자동 생성
- **백그라운드 스레드**로 실행 (논블로킹)

#### 재생성
- POST `/api/summary/{date}/{period}` — 기존 요약 덮어쓰기
- 이벤트는 보존 (삭제 안 됨)

---

### 7. 업무 스케줄 (schedule.py)

#### 설정 형식
```json
{
  "monday": {"start": "08:00", "end": "17:00"},
  "tuesday": {"start": "08:00", "end": "17:00"},
  ...
  "saturday": null,  // 휴일
  "sunday": null
}
```

#### 저장 위치
- `~/.gemvis/schedule.json`

#### 기본값
- 월~금 08:00-17:00
- 주말 off (personal)

#### 사용처
1. **이벤트 로그**: 파일 액션 시 period(work/personal) 기록
2. **일일 요약**: work/personal 기간 분리
3. **프론트엔드**: 캘린더 UI 표시

---

### 8. 이벤트 로그 (event_log.py)

#### 저장 형식
- **RDF/Turtle (.ttl)** — `~/.gemvis/events.ttl`
- 파일 액션 전용 (그래프와 분리)

#### 이벤트 속성
```python
{
  "id": "uuid",
  "action": "created" | "modified" | "deleted",
  "file_path": "/absolute/path",
  "timestamp": "2026-05-11T14:30:00",
  "period": "work" | "personal" | null
}
```

#### 특징
- **Append-only** — 삭제 안 됨 (영구 보존)
- **일일 요약 재생성** 시 과거 이벤트 참조 가능
- 그래프 초기화해도 이벤트는 유지

---

### 9. LLM 클라이언트 (llm_client.py)

#### 엔드포인트
- OpenAI 호환 API (`/v1/chat/completions`)
- 환경 변수:
  - `LLM_BASE_URL`: http://127.0.0.1:8080/v1
  - `LLM_API_KEY`: none (로컬이므로 불필요)
  - `LLM_MODEL`: unsloth/gemma-4-E2B-it-GGUF:Q4_K_M

#### 함수
- `complete_text(prompt)`: 텍스트 전용 프롬프트
- `complete_image(image_path, prompt)`: 이미지 + 텍스트 (멀티모달)
- `extract_pdf_text(pdf_path)`: pypdf로 PDF 추출

#### 타임아웃
- 기본 180초 (Gemma 4 E2B는 빠름, 26B는 느림)

---

### 10. 설정 관리 (config.py)

#### 환경 변수
```python
LLM_BASE_URL      # LLM 서버 URL
LLM_API_KEY       # API 키 (로컬은 "none")
LLM_MODEL         # 모델 이름
GEMVIS_WATCH_DIR  # 단일 감시 폴더 (레거시)
GEMVIS_WATCH_DIRS # 다중 감시 폴더 (콜론 구분, 우선)
GEMVIS_GRAPH_PATH      # 그래프 TTL 경로
GEMVIS_EMBEDDINGS_PATH # 임베딩 npz 경로
GEMVIS_EVENTS_PATH     # 이벤트 TTL 경로
```

#### 기본값
- 감시 폴더: `~/Downloads`, `~/Pictures`, `~/Documents`
- 그래프: `~/.gemvis/graph.ttl`
- 임베딩: `~/.gemvis/embeddings.npz`
- 이벤트: `~/.gemvis/events.ttl`

#### 경로 정규화
- `~` → 사용자 홈
- Windows/Unix 자동 변환 (pathlib)
- 시작 시 자동 생성 (mkdir)

---

## 프론트엔드 기능

### 1. 대시보드 (Dashboard.tsx)

#### 표시 정보
- **Privacy Bento**: 온디바이스 강조
- **지식그래프 통계**: 노드/엣지 수, 타입별 분포
- **파일 통계**: 카테고리별 분포 (파이 차트)
- **최근 파일**: 최근 6개 (카테고리 아이콘 + 요약)

#### Bento Grid 레이아웃
```
┌────────────────┬────────────────┐
│ Privacy        │ 지식그래프 노드  │
│ 🔒 On-device   │ 1,234 nodes    │
├────────────────┼────────────────┤
│ 파일 카테고리   │ 노드 타입 분포  │
│ (파이 차트)     │ (바 차트)       │
├────────────────┴────────────────┤
│ 최근 파일 (6개, 카드 형식)        │
└──────────────────────────────────┘
```

---

### 2. 그래프 뷰 (GraphView.tsx)

#### 시각화 라이브러리
- **react-force-graph-2d** (WebGL)

#### 노드 색상
```typescript
const NODE_COLORS = {
  file: '#4FACFE',      // 파란색
  person: '#F093FB',    // 분홍색
  place: '#43E97B',     // 녹색
  project: '#FFAD73',   // 주황색
  event: '#9D50BB',     // 보라색
  date: '#FFE53B',      // 노란색
  tag: '#C471ED'        // 연보라
};
```

#### 인터랙션
- **노드 클릭**: 이름 표시
- **줌/팬**: 마우스 휠 + 드래그
- **하이라이트 모드**: 특정 노드 + 1-hop 이웃 강조 (다른 노드 흐리게)
  - Spotlight에서 `Ctrl+Alt+V` 로 진입
  - 자동 줌인 + 중심 배치

#### 성능 최적화
- 1000 노드 이하 → 전체 렌더
- 초과 시 성능 경고 (추후 LOD 구현 예정)

---

### 3. Spotlight 검색 (Spotlight.tsx)

#### 단축키
- **Ctrl+K** (Mac: Cmd+K): 오버레이 토글
- **↑/↓**: 결과 이동
- **Enter**: 선택한 파일의 폴더 열기
- **Ctrl+Alt+V**: 그래프 뷰에서 하이라이트
- **Esc**: 닫기

#### 검색 흐름
1. 사용자 입력 + Enter → 검색 실행
2. 로딩 스피너 표시
3. 결과 수신:
   - **LLM 답변** (마크다운 렌더)
   - **파일 리스트** (카테고리 아이콘 + 경로 + 요약)
   - **관련 엔티티** (파일 아님, 회색 표시)

#### 상태 유지
- 닫았다 열어도 이전 검색 결과 유지
- 쿼리 텍스트 선택 상태로 포커스 (바로 교체 가능)

---

### 4. 캘린더 (Calendar.tsx)

#### 라이브러리
- **FullCalendar** (dayGridPlugin)

#### 표시 항목
- **요약 있는 날**: 마커 표시 (work: 🟦 / personal: 🟩)
- **날짜 클릭**: 해당 일자 요약 팝업
  - work / personal 탭 전환
  - 파일 목록 + 생성/수정/삭제 카운트
  - Markdown 렌더링

#### 액션
- **요약 생성**: 없는 날짜에 대해 수동 생성
- **재생성**: 기존 요약 덮어쓰기
- **삭제**: 요약 제거 (이벤트는 유지)
- **월/년 네비게이션**: 드롭다운 + 화살표

---

### 5. 설정 (Settings.tsx)

#### 파일 감시
- **감시 폴더 설정**: 체크박스로 다중 선택
  - 기본 폴더: Downloads, Pictures, Documents
  - 커스텀 폴더 추가 가능
- **감시 시작/중지**: 토글 버튼
- **기존 파일 스캔**: 수동 일괄 분석

#### 업무 스케줄
- **요일별 시작/종료 시간** 설정
  - HH:MM 형식 입력
  - 휴일 설정 (null)
- **저장**: 즉시 적용 (schedule.json 업데이트)

#### 그래프 관리
- **초기화**: 전체 그래프 + 임베딩 삭제 (확인 다이얼로그)

---

### 6. 상태 바 (StatusBar.tsx)

#### 표시 정보
- **🔒 On-device**: 프라이버시 인디케이터 (항상 표시)
- **파일 감시 상태**: 실행 중 / 중지
- **처리 완료 파일 수**: 누적 카운트
- **API 상태**: 연결 OK / 오류

---

### 7. 검색 컨텍스트 (SearchContext.tsx)

#### 글로벌 상태
- 검색 결과 공유 (Spotlight ↔ GraphView)
- 하이라이트할 노드 ID 전달

---

## 데이터 저장소

### 1. 지식그래프 (graph.ttl)

#### 형식
- RDF/Turtle (시맨틱 웹 표준)
- rdflib로 SPARQL 쿼리 가능

#### 크기 예상
- 1000 노드 + 2000 엣지 → ~500KB
- 10000 노드 → ~5MB

#### 백업
- 텍스트 파일이므로 Git 버전 관리 가능
- 압축 시 1/5 크기

---

### 2. 벡터 임베딩 (embeddings.npz)

#### 형식
- numpy 압축 배열 (`.npz`)

#### 크기 예상
- 384차원 × 1000 노드 × 4바이트 → ~1.5MB
- 메모리 맵 가능 (대용량 지원)

---

### 3. 이벤트 로그 (events.ttl)

#### 형식
- RDF/Turtle (graph.ttl과 동일)

#### 크기 예상
- 1년 × 100 이벤트/일 → ~1MB
- 압축 시 ~200KB

---

### 4. 업무 스케줄 (schedule.json)

#### 형식
- JSON (가독성)

#### 크기
- 고정 ~500 bytes

---

## API 엔드포인트

### 대시보드
- `GET /api/dashboard` — 통계 + 최근 파일

### 그래프
- `GET /api/graph/data` — 노드/엣지 JSON
- `DELETE /api/graph` — 그래프 초기화

### 검색
- `POST /api/search` — 자연어 검색
  ```json
  {
    "question": "지난달 회의록"
  }
  ```

### 파일 감시
- `POST /api/watcher/start` — 감시 시작
- `POST /api/watcher/stop` — 감시 중지
- `GET /api/watcher/status` — 상태 조회
- `POST /api/watcher/scan` — 기존 파일 일괄 스캔

### 설정
- `POST /api/config` — 감시 폴더/API 키 저장
  ```json
  {
    "watch_dirs": ["~/Downloads", "~/Documents"],
    "api_key": "none"
  }
  ```

### 파일 작업
- `POST /api/file/open-folder` — OS 탐색기에서 폴더 열기
  ```json
  {
    "path": "/absolute/path/to/file"
  }
  ```
  - macOS: `open -R` (Finder)
  - Windows: `explorer /select,`
  - Linux: `xdg-open`
  - WSL: `\\wsl.localhost\{distro}\...` UNC 경로

### 업무 스케줄
- `GET /api/schedule` — 현재 스케줄 조회
- `POST /api/schedule` — 스케줄 업데이트
  ```json
  {
    "schedule": {
      "monday": {"start": "09:00", "end": "18:00"},
      ...
    }
  }
  ```

### 일일 요약
- `GET /api/summary` — 요약 목록 (date_from/date_to 필터 가능)
- `GET /api/summary/{date}` — 특정 날짜의 work + personal 요약
- `GET /api/summary/{date}/{period}` — 특정 기간 요약
- `POST /api/summary/{date}/{period}` — 요약 생성/재생성
- `DELETE /api/summary/{date}/{period}` — 요약 삭제

---

## 지원 파일 형식

### 텍스트
- `.txt`, `.md`, `.csv`, `.json`, `.log`
- 최대 10,000자 (초과 시 truncate)

### 이미지
- `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.bmp`
- base64 인코딩 → 멀티모달 LLM

### 문서
- `.pdf`
- pypdf로 텍스트 추출

### 향후 지원 예정 (Phase 2)
- **오디오**: `.mp3`, `.wav`, `.m4a` (Whisper)
- **비디오**: `.mp4`, `.mov` (프레임 추출 + OCR)
- **오피스**: `.docx`, `.xlsx`, `.pptx` (python-docx, openpyxl)

---

## 보안 및 프라이버시

### 온디바이스 보장
1. **모든 데이터 로컬 저장**
   - 그래프: `~/.gemvis/`
   - 파일: 원본 위치 그대로
2. **외부 전송 금지**
   - LLM: 로컬 llama-server만
   - 텔레메트리 없음
   - 클라우드 동기화 없음
3. **Symbolic Link만 사용**
   - 원본 파일 이동/삭제 금지
   - 정리는 가상 폴더로만

### 자동 검증
- Git hooks로 외부 API 호출 감지
  ```bash
  grep -E "openai|anthropic|googleapis" *.py
  ```

---

## 성능 특성

### 응답 시간 (M4 Mac 기준)
- **파일 분석** (Gemma 4 E2B): 1-3초
- **검색** (하이브리드): <1초
  - SPARQL: <50ms
  - 임베딩: <100ms
  - LLM 답변 생성: 500-1000ms
- **그래프 렌더링**: <500ms (1000 노드)

### 메모리 사용
- **백엔드**: ~200MB (idle)
- **LLM 서버**: ~2GB (Gemma 4 E2B 로드 시)
- **프론트엔드**: ~100MB

### 디스크 사용
- **지식그래프**: 1000 노드 → ~500KB
- **임베딩**: 1000 노드 → ~1.5MB
- **이벤트 로그**: 1년 → ~1MB
- **LLM 모델**: 2GB (GGUF Q4_K_M)

### 확장성
- **1만 노드** → 검색 여전히 빠름 (인덱싱 필요 없음)
- **10만 노드** → SPARQL 느려짐 (10초+), 임베딩 메모리 부족 가능
  - 해결책: 그래프 DB 마이그레이션 (Neo4j, Kùzu), FAISS 벡터 인덱스

---

## 향후 계획 (Phase 2+)

### 멀티모달 확장
- [ ] 오디오 분석 (Whisper)
- [ ] 비디오 요약 (프레임 샘플링 + OCR)
- [ ] 오피스 문서 (DOCX/XLSX)

### 모바일 + 동기화
- [ ] iOS/Android 앱 (React Native)
- [ ] E2EE 동기화 (CRDTs)

### 고급 검색
- [ ] 시간 범위 필터 ("2주 전부터 지금까지")
- [ ] 논리 연산자 (AND/OR/NOT)
- [ ] 저장된 검색 (즐겨찾기)

### 자동화
- [ ] 태스크 추출 (TODO 리스트 생성)
- [ ] 자동 분류 (폴더 제안)
- [ ] 중복 파일 탐지

---

## 버전 히스토리

- **v1.0** (2026-05-11) — MVP 해커톤 제출 버전
  - 7가지 노드 타입
  - 하이브리드 검색 (SPARQL + 임베딩)
  - 일일 요약 (업무/개인 분리)
  - 다중 감시 폴더
  - 캘린더 UI

---

**문서 끝**
