# Gemvis 사이드바 기능 스펙

> **버전**: v2 (geminsight-develop, 2026-05-12)
> **관점**: 사용자가 보는 **사이드바 메뉴 5개** 기준의 기능 카탈로그.
> 각 기능이 작동할 때 **GemInsight의 어떤 필드를 읽는지** 명시.
>
> 보완 문서:
> - [ARCHITECTURE_V2.md](ARCHITECTURE_V2.md) — GemInsight SSoT 설계
> - [FEATURES.md](FEATURES.md) — 컴포넌트/계층 관점 기능
> - [API_CONTRACT.md](../API_CONTRACT.md) — HTTP 엔드포인트 스펙

---

## 0. 사이드바 구성

[frontend/src/App.tsx:13-19](../frontend/src/App.tsx#L13-L19) `NAV_ITEMS` 기준, 상단 고정 + 전역 오버레이 1개.

| # | 아이콘 | 경로 | 메뉴명 | 주 역할 |
|---|--------|------|--------|--------|
| 1 | ◈ | `/` | **대시보드** | 전체 파일 현황 + 통계 + 상태 모니터링 |
| 2 | ◷ | `/calendar` | **캘린더** | 날짜별 업무/개인 활동 요약 |
| 3 | ◉ | `/graph` | **지식그래프** | 파일·엔티티·관계 시각화 |
| 4 | ✦ | `/search` | **대화 검색** | 자연어 질의 대화형 RAG |
| 5 | ⚙ | `/settings` | **설정** | 감시 폴더·업무 스케줄·데이터 관리 |
| + | 🔍 | `⌘K` | **스포트라이트 (오버레이)** | 빠른 검색 팝업 (사이드바 아님, 전역) |

---

## 1. 📊 대시보드 (`/`)

**구현**: [frontend/src/pages/Dashboard.tsx](../frontend/src/pages/Dashboard.tsx)
**주 API**: `GET /api/files?include_stats=true`

### 기능 목록

| # | 기능 | 상세 |
|---|------|------|
| 1.1 | **프라이버시 안내 카드** | "On-device AI" 고정 카피. 정적 UI, 데이터 없음 |
| 1.2 | **지식그래프 요약 카드** | `stats.total_nodes`, `stats.total_edges` 카운트 |
| 1.3 | **분석 완료 파일 수** | `stats.node_types.file` 카운트 |
| 1.4 | **노드 타입 분포 차트** | `stats.node_types` 전체를 bar chart로 |
| 1.5 | **카테고리 분포 차트** | 현재 페이지 파일들의 `category` 집계 |
| 1.6 | **4상태 배지 + 필터 버튼** | `analysis_status`별 카운트 + 클릭 시 해당 상태만 필터링 |
| 1.7 | **전체 파일 테이블** | 상태/파일명/분류/요약/생성일/수정일/추가일 컬럼 |
| 1.8 | **정렬 토글** | `file_ctime`, `file_mtime`, `added_at` 컬럼 헤더 클릭 |
| 1.9 | **페이지네이션** | `page/limit/total_pages` 기반 ← 이전/다음 → |
| 1.10 | **새로고침 버튼** | 현재 쿼리 재호출 |

### 사용하는 GemInsight 필드

| 기능 | 필드 | 용도 |
|------|------|------|
| 1.2, 1.4 | — (KG `get_stats()` 집계) | 노드/엣지 총계 |
| 1.5, 1.7 | `category` | 분류 배지 + 차트 집계 |
| 1.6, 1.7 | `analysis_status` | 4상태 배지 표시, 필터링 |
| 1.7 | `summary` | 요약 셀 텍스트 (pending/processing일 때는 "분석 대기 중…" 대체) |
| 1.7 | `error` | 실패 시 요약 셀에 `⚠ {error}` 표시 |
| 1.7 | `file_name`, `file_id` | 파일명/경로 노출 |
| 1.8 | `file_mtime`, `file_ctime`, `added_at` | 정렬 키 |
| 1.5 | `tags` (간접) | 향후 확장 (현재 미사용) |

### 상태별 표시 규칙

| analysis_status | 요약 셀 | 분류 셀 |
|-----------------|---------|---------|
| `pending` | "분석 대기 중" | — |
| `processing` | "분석 중…" | — |
| `completed` | `summary` 문자열 | `category` 배지 |
| `failed` | `⚠ {error}` | — |

---

## 2. 📅 캘린더 (`/calendar`)

**구현**: [frontend/src/pages/Calendar.tsx](../frontend/src/pages/Calendar.tsx)
**주 API**: `GET /api/summary`, `GET /api/summary/{date}`, `POST /api/summary/{date}/{period}`, `DELETE /api/summary/{date}/{period}`

### 기능 목록

| # | 기능 | 상세 |
|---|------|------|
| 2.1 | **월간 캘린더 뷰** | FullCalendar dayGridMonth. 요약 있는 날 이벤트 뱃지 |
| 2.2 | **연/월 선택 드롭다운 + 이전/오늘/다음 버튼** | ±5년 범위 |
| 2.3 | **날짜 셀 클릭 → 상세 패널** | 우측 사이드 패널에 `work` / `personal` 2블록 |
| 2.4 | **요약 생성 버튼** | 없으면 "생성", 있으면 "재생성" (LLM 호출, 확인 모달) |
| 2.5 | **요약 삭제 버튼** | 확인 모달 후 `DELETE` |
| 2.6 | **파일 활동 통계** | 파일 수 / created/modified/deleted 카운트 |
| 2.7 | **요약 마크다운 렌더링** | Gemma 4 생성 한국어 내러티브 |
| 2.8 | **관련 파일 목록 펼침** | `<details>` 엘리먼트, 파일명만 (경로 제외) |
| 2.9 | **업무 시간 라벨** | 요약에 `work_hours` 필드 표시 |
| 2.10 | **토스트/모달** | 성공·실패 피드백 |

### 사용하는 GemInsight 필드

요약 생성 시 백엔드 [gemvis/summary.py::_format_activity](../gemvis/summary.py#L108)가 각 파일의 다음 필드를 LLM 프롬프트에 주입:

| 필드 | 용도 |
|------|------|
| `summary` | "그 날 한 일" 내러티브의 재료 |
| `category` | 분류 컨텍스트 |
| `file_mtime` | 날짜 버킷팅 (어느 날의 활동인지) |
| `analysis_status` | `completed`만 요약 재료로 활용 (pending/failed는 "(메타 없음)" 처리) |

**EventLog 파생 데이터** (GemInsight 외부):
- `action` (`created/modified/deleted`) — 통계 카운트
- `timestamp`, `period` (`work/personal`) — 시간 버킷

---

## 3. 🕸️ 지식그래프 (`/graph`)

**구현**: [frontend/src/pages/GraphView.tsx](../frontend/src/pages/GraphView.tsx)
**주 API**: `GET /api/graph/data`

### 기능 목록

| # | 기능 | 상세 |
|---|------|------|
| 3.1 | **Force-Directed 2D 그래프** | `react-force-graph-2d`. WebGL-free 캔버스 |
| 3.2 | **노드 타입별 색상** | file, person, place, project, event, date, tag — 7색 범례 |
| 3.3 | **노드 라벨** | 각 노드의 `name` 표시 (file 노드는 basename만) |
| 3.4 | **줌/드래그** | 휠 줌, 노드 드래그 |
| 3.5 | **포커스 모드** | URL 쿼리 `?focus={node_id}` → 해당 노드 + 1-hop 이웃 강조, 나머지 흐리게 |
| 3.6 | **"검색으로 돌아가기"** | 포커스 배너에서 스포트라이트 재오픈 |
| 3.7 | **포커스 해제 버튼** | `focus` 쿼리 파라미터 제거 |
| 3.8 | **자동 센터링** | 포커스 적용 시 해당 노드로 `centerAt` + `zoom(3)` 애니메이션 |
| 3.9 | **새로고침** | 그래프 재로드 (force simulation 재시작) |
| 3.10 | **범례** | 7개 노드 타입 색상표 |

### 사용하는 GemInsight 필드

| 필드 | 그래프 요소 | 생성 경로 |
|------|------------|----------|
| `file_path` | `file` 노드 id (`file:{path}`) | KG `add_node("file", ...)` |
| `category` | file 노드 속성 (UI에서 미사용, KG 저장) | KG 속성 |
| `entities.people` | `person` 노드 + `mentions` 엣지 | KG entity_type_map |
| `entities.places` | `place` 노드 + `taken_at` 엣지 | 동일 |
| `entities.projects` | `project` 노드 + `part_of` 엣지 | 동일 |
| `entities.events` | `event` 노드 + `related_to` 엣지 | 동일 |
| `entities.dates` | `date` 노드 + `created_on` 엣지 | 동일 |
| `tags` | `tag` 노드 + `tagged_with` 엣지 | KG 태그 처리 |
| `relations` | 엔티티 ↔ 엔티티 엣지 (예: `works_on`) | KG `add_edge` |

> **요약/상태 필드는 GraphView UI에서 사용 안 함** — 하지만 파생 KG 인덱스는 `raw_insight`로부터 재생성 가능.

---

## 4. 💬 대화 검색 (`/search`)

**구현**: [frontend/src/pages/Search.tsx](../frontend/src/pages/Search.tsx) + [frontend/src/SearchContext.tsx](../frontend/src/SearchContext.tsx)
**주 API**: `POST /api/search`

### 기능 목록

| # | 기능 | 상세 |
|---|------|------|
| 4.1 | **대화형 채팅 UI** | user ↔ assistant 버블, 히스토리 유지 |
| 4.2 | **자연어 질의 전송** | Enter / 전송 버튼 |
| 4.3 | **제안 프롬프트** | 초기 상태에 클릭 가능 예시 3개 |
| 4.4 | **답변 마크다운 렌더링** | Gemma 4 생성 한국어 답변 |
| 4.5 | **타이핑 인디케이터** | "답변 생성 중..." |
| 4.6 | **대화 비우기** | `reset()` — 히스토리 초기화 |
| 4.7 | **쿼리 디버그 패널** | 우측 토글. intent 파싱 + graph_results 원본 |
| 4.8 | **디버그: 의도 분석** | `intent`, `search_terms`, `node_types` 표시 |
| 4.9 | **디버그: 그래프 쿼리 결과** | 매치된 노드들 (type/name/edge_type) |

### 사용하는 GemInsight 필드

[gemvis/search.py::_search_graph](../gemvis/search.py#L343)가 하이브리드 리트리벌:

| 단계 | 필드 | 용도 |
|------|------|------|
| Intent 파싱 | — (LLM 입력) | 자연어 → search_terms/node_types/semantic_query |
| Structural 매칭 | `entities.*`, `tags` (KG 노드) | SPARQL 부분문자열 필터 |
| Structural 매칭 | `category` | 카테고리 필터 (`categories=["photo"]` 등) |
| Semantic 매칭 | 임베딩 (`summary + tags + category + entities` 합성) | cosine top-k |
| 결과 조립 | `summary`, `category` | 답변 생성 프롬프트 context |
| 답변 생성 | `file_name` | "매칭된 파일" 리스트 |

### 스포트라이트 오버레이 (⌘K, 별도 메뉴 아님)

**구현**: [frontend/src/Spotlight.tsx](../frontend/src/Spotlight.tsx)
**주 API**: `POST /api/search` + `POST /api/file/open-folder`

| # | 기능 | 상세 |
|---|------|------|
| S.1 | **⌘K/Ctrl+K 토글** | 전역 단축키 |
| S.2 | **검색 결과 키보드 내비** | ↑↓ 이동, Enter 폴더 열기 |
| S.3 | **Ctrl+Alt+V 그래프 보기** | 선택 파일을 `/graph?focus={id}`로 이동 |
| S.4 | **파일명/카테고리/요약 표시** | `file_name`, `category`, `summary` 사용 |
| S.5 | **AI 답변 미리보기** | `SearchResponse.answer` 마크다운 |

---

## 5. ⚙️ 설정 (`/settings`)

**구현**: [frontend/src/pages/Settings.tsx](../frontend/src/pages/Settings.tsx)
**주 API**: `POST /api/config`, `/api/watcher/*`, `/api/schedule`, `GET/POST /api/preferences`, `GET /api/files`, `DELETE /api/graph`


### 기능 목록

| # | 섹션 | 기능 | 상세 |
|---|------|------|------|
| 5.1 | API 및 감시 폴더 | Google API Key 입력 | 선택 사항, 환경변수 주입 |
| 5.2 | API 및 감시 폴더 | 폴더 체크박스 | 기본 3개 (Downloads/Pictures/Documents) + 사용자 추가 |
| 5.3 | API 및 감시 폴더 | 폴더 추가/삭제 | 절대경로 입력 |
| 5.4 | API 및 감시 폴더 | 설정 저장 (감시 재시작) | `POST /api/config` |
| 5.5 | 파일 감시 제어 | 감시 시작/중지/스캔 | `/api/watcher/start|stop|scan` |
| 5.6 | 파일 감시 제어 | 상태 표시 | running 여부 / 폴더 수 / 처리된 파일 수 |
| 5.7 | 데이터 관리 | 모든 데이터 초기화 | `DELETE /api/graph` (graph.ttl + events.ttl) |
| 5.8 | 데이터 관리 | 감시 파일 목록 펼침 | 최대 10000개 (`GET /api/files?limit=10000`) |
| 5.9 | 데이터 관리 | 파일별 상태 아이콘 | ⏳ pending · ⚙️ processing · ✅ completed · ❌ failed |
| 5.10 | 업무 시간 스케줄 | 요일별 start/end time | 저장 후 캘린더 요약에 반영 |
| 5.11 | 업무 시간 스케줄 | 저장 버튼 | `POST /api/schedule` |
| 5.12 | LLM 샘플링 설정 | Temperature 슬라이더+입력 | 0.0~2.0, 실시간 반영 (`POST /api/preferences`) |
| 5.13 | LLM 샘플링 설정 | Max Tokens 슬라이더+입력 | 512~8192, 응답 최대 길이 |
| 5.14 | LLM 샘플링 설정 | Top P 슬라이더+입력 | 0.0~1.0, 누적 확률 샘플링 |
| 5.15 | LLM 샘플링 설정 | Top K 슬라이더+입력 | 1~100, 상위 K개 토큰 선택 |

### 사용하는 GemInsight 필드 (섹션 5.8~5.9 한정)

| 필드 | 용도 |
|------|------|
| `file_name` | 목록 1차 라벨 |
| `file_id` | 툴팁/부제 (전체 경로) |
| `category` | 보조 라벨 `(memo)` 같은 꼬리표 |
| `analysis_status` | 상태 아이콘 (STATUS_ICON 매핑) |
| `size_bytes` | `(xxx KB)` 표시 |
| `error` | 툴팁에 실패 원인 노출 |

### 집계

- `filesTotal = pagination.total`
- `filesAnalyzed = files.filter(f => f.analysis_status === 'completed').length`

---

## 6. 기능 × GemInsight 필드 교차표

행 = 기능, 열 = GemInsight 필드. ✅ = 해당 UI 기능이 **직접** 읽어 렌더에 쓰는 필드.

| 기능 ↓ / 필드 → | file_id | file_name | category | summary | tags | entities | relations | risk_level | file_mtime | file_ctime | size_bytes | added_at | analysis_status | last_analyzed_at | error |
|-----------------|---------|-----------|----------|---------|------|----------|-----------|------------|-----------|-----------|-----------|----------|-----------------|------------------|-------|
| 대시보드 통계 | | | | | | | | | | | | | | | |
| 대시보드 파일 테이블 | ✅ | ✅ | ✅ | ✅ | | | | | ✅ | ✅ | | ✅ | ✅ | | ✅ |
| 대시보드 상태 필터 | | | | | | | | | | | | | ✅ | | |
| 캘린더 요약 생성 | | | ✅ | ✅ | | | | | ✅ | | | | ✅ | | |
| 캘린더 관련 파일 목록 | | ✅ | | | | | | | | | | | | | |
| 지식그래프 노드 | ✅ | ✅ | (KG) | (KG) | ✅ | ✅ | ✅ | | | | | | | | |
| 대화 검색 intent | | | ✅ | | | ✅ | | | | | | | | | |
| 대화 검색 matching | | | ✅ | ✅ | ✅ | ✅ | | | | | | | | | |
| 대화 검색 답변 조립 | | ✅ | ✅ | ✅ | | | | | | | | | | | |
| 스포트라이트 ⌘K | ✅ | ✅ | ✅ | ✅ | | | | | | | | | | | |
| 설정 감시 파일 목록 | ✅ | ✅ | ✅ | | | | | | | | ✅ | | ✅ | | ✅ |

> **risk_level은 아직 어떤 UI도 사용하지 않음** — Phase 2에서 "⚠️ 검토 필요" 배지로 노출 예정 ([GEM_INSIGHT.md §9](GEM_INSIGHT.md) 로드맵).
> **last_analyzed_at도 미사용** — 재분석 이력 디버깅용으로 `/api/file/{id}` 상세에만 포함.

---

## 7. 상태별 UI 매트릭스

`analysis_status`에 따라 각 화면이 어떻게 보이는지:

| 기능 | pending | processing | completed | failed |
|------|---------|-----------|-----------|--------|
| 대시보드 테이블 | ⏳ 분석 대기 / "분석 대기 중" | ⚙️ 분석 중 / "분석 중…" | ✅ 완료 / 요약 표시 | ❌ 실패 / `⚠ {error}` |
| 캘린더 요약 재료 | 제외 (메타 없음) | 제외 | 포함 (summary/category 사용) | 제외 |
| 지식그래프 | 파일 노드만 존재 (entities 없음) | 동일 | 완전한 이웃과 함께 | skeleton만 |
| 대화 검색 retrieval | 임베딩/엔티티 없음 → 결과 제외 | 동일 | 하이브리드 매칭 대상 | 제외 |
| 설정 파일 목록 | ⏳ 아이콘 | ⚙️ 아이콘 | ✅ 아이콘 + 카테고리 | ❌ 아이콘 + 툴팁에 error |

---

## 8. 향후 기능 (Phase 2+ 로드맵)

`FileRecord` 스키마에는 이미 있지만 UI 미사용:

- `risk_level` → "⚠️ 검토 필요" 뱃지 (민감 파일 경고)
- `last_analyzed_at` → 상세 뷰에 "마지막 분석 시간" 표시
- `entities` 전체 → 파일 상세 패널에서 사람/장소/이벤트 그룹핑
- `relations` → 파일 상세에 "이 파일이 만든 관계" 목록

**아직 없는 기능** (제안):
- `/api/file/{id}` 상세 뷰 모달 (Dashboard 행 클릭 시)
- 일괄 선택 + 재분석 버튼
- 실패 파일 필터 → `retry-failed` 원클릭 버튼

---

**Last Updated**: 2026-05-12
**Branch**: `geminsight-develop`
