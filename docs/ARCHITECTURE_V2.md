# Gemvis 아키텍처 v2 — GemInsight as Single Source of Truth

> **버전**: v2 (2026-05-12, `geminsight-develop` 브랜치)
> **상태**: Refactoring In Progress
> **설계 원칙**: "파일 하나당 하나의 완결된 마스터 레코드"
> **관련 문서**: [architecture.md](architecture.md) (v1, 4-레이어 관점), [GEMINSIGHT_IMPACT.md](GEMINSIGHT_IMPACT.md) (AnalysisResult→GemInsight rename 영향 분석)

---

## 0. 한 줄 요약

**모든 파일은 Gemma 4에 의해 하나의 GemInsight로 변환되고, GemInsight는 KnowledgeGraph의 file 노드에 원본 JSON(`raw_insight`)으로 박혀 영구 보존된다.** 모든 기능은 이 마스터 레코드 하나만 읽고 동작한다.

## v1 대비 핵심 변화

| 항목 | v1 (AS-IS) | v2 (TO-BE) |
|------|-----------|-----------|
| GemInsight 지속성 | 생성 직후 3곳으로 쪼개지고 원본 폐기 | file 노드의 `raw_insight` 속성에 JSON 원본 영구 보존 |
| Relations 복원 | 불가능 (`insight_service.py` TODO) | `raw_insight` JSON 역직렬화로 완전 복원 |
| 분석 상태 | `analyzed: bool` (2상태, has_node 기반) | `analysis_status`: `pending`/`processing`/`completed`/`failed` (4상태) |
| 재분석 트리거 | `on_modified`에서 중복 방지 스킵 | 상태를 `pending`으로 롤백 후 재실행 |
| API 응답 타입 | `FileInfo`/`GemInsight`/`WatchedFile` 3종 분산 | `FileRecord` 단일 타입 |
| 프론트 타입 | 세 개로 분리 | `FileRecord` 단일 interface |

---

## 1. GemInsight 스키마 (마스터 레코드)

파일 1개 = GemInsight 1개 = 아래 모든 필드를 가진 **하나의 객체**.

### 1.1. 필드 정의

| 분류 | 필드 | 타입 | 출처 | 필수 | 용도 |
|------|------|------|------|------|------|
| **Identity** | `file_path` | str (절대경로) | OS | 항상 | Primary Key |
| **Physical** | `file_mtime` | float (epoch) | `os.stat` | 항상 | 파일 수정 시간 |
| | `file_ctime` | float (epoch) | `os.stat` | 항상 | 파일 생성 시간 |
| | `size_bytes` | int | `os.stat` | 항상 | 파일 크기 |
| **Analytical** | `category` | enum(8) | Gemma 4 | completed 시 | 파일 분류 |
| | `summary` | str (KO, 1줄) | Gemma 4 | completed 시 | 요약 |
| | `tags` | list[str] (3~7) | Gemma 4 | completed 시 | 태그 |
| | `risk_level` | enum(2) | Gemma 4 | completed 시 | 민감도 |
| **Relational** | `entities` | dict[str, list[str]] | Gemma 4 | completed 시 | 엔티티 (people/places/projects/dates/events) |
| | `relations` | list[dict] | Gemma 4 | completed 시 | 엔티티 간 관계 |
| **State** | `analysis_status` | enum(4) | System | 항상 | pending / processing / completed / failed |
| | `last_analyzed_at` | ISO datetime \| null | System | completed 시 | 마지막 분석 시점 |
| | `added_at` | ISO datetime | System | 항상 | Gemvis가 발견한 시점 |
| | `error` | str \| null | System | failed 시 | 실패 원인 |

### 1.2. enum 값

```
category:         memo | photo | screenshot | document | voice_memo | code | data | other
risk_level:       auto_safe | review_first
analysis_status:  pending | processing | completed | failed
```

### 1.3. 실제 예시 (analysis_status=completed)

```json
{
  "file_path": "/Users/username/gemvis_watch/meeting.md",
  "file_mtime": 1715435400.0,
  "file_ctime": 1715400000.0,
  "size_bytes": 2847,

  "category": "document",
  "summary": "Gemvis 해커톤 진행 상황 회의",
  "tags": ["회의록", "해커톤", "Gemvis"],
  "risk_level": "auto_safe",
  "entities": {
    "people": ["Alice", "Bob"],
    "places": [],
    "projects": ["Gemvis"],
    "dates": ["2026-05-11"],
    "events": ["회의"]
  },
  "relations": [
    {"source": "Alice", "source_type": "person",
     "target": "Gemvis", "target_type": "project", "relation": "works_on"}
  ],

  "analysis_status": "completed",
  "last_analyzed_at": "2026-05-12T10:30:00",
  "added_at": "2026-05-12T10:29:55",
  "error": null
}
```

---

## 2. Hydration 파이프라인 (상태 머신)

```
   [파일 발견]                [분석 시작]                [분석 성공]
       │                         │                          │
       ▼                         ▼                          ▼
   ┌────────┐  Stage 1      ┌────────────┐  Stage 2    ┌───────────┐
   │ pending│─ skeleton ───▶│ processing │── Gemma 4 ─▶│ completed │
   └────────┘ 즉시/Fast     └────────────┘  Slow/LLM    └───────────┘
       ▲                         │                          │
       │                         │ 실패 시                   │
       │                         ▼                          │
       │ [파일 수정]         ┌────────┐                      │
       └──────── Stage 3 ────│ failed │                      │
                              └────────┘                     │
                                                             │
                              [파일 수정 감지]               │
                              ──── pending으로 롤백 ─────────┘
```

### Stage 1: Skeleton 생성 (Fast, 비동기 즉시)

**트리거**: watcher의 `on_created` 또는 기존 파일 스캔.

**동작**:
1. `os.stat`으로 physical 메타데이터 수집 (`file_mtime`, `file_ctime`, `size_bytes`)
2. KG에 file 노드 생성 (physical 속성만, 엔티티 없음)
3. `analysis_status = "pending"`
4. 분석 큐에 enqueue

**효과**: 파일 목록 UI에 즉시 "⏳ 분석 대기" 상태로 노출됨.

### Stage 2: LLM 분석 (Slow)

**트리거**: 큐 dequeue.

**동작**:
1. `analysis_status = "processing"`으로 전환
2. `generate_insight(path)` 호출 (Gemma 4 Tool Calling)
3. 성공 시:
   - GemInsight 객체 완성 (`analysis_status = "completed"`, `last_analyzed_at = now`)
   - `kg.add_insight()` 호출 → file 노드 속성 업데이트 + 엔티티/관계 생성 + `raw_insight` JSON 저장
   - 임베딩 계산 + 저장
   - EventLog 기록
4. 실패 시: `analysis_status = "failed"`, `error = "..."` 저장, 원본 skeleton 유지

### Stage 3: 재분석 트리거

**트리거**: watcher의 `on_modified`.

**동작**:
1. KG 노드의 `analysis_status`를 `"pending"`으로 되돌림
2. 큐 재등록 → Stage 2 재실행

### 복구 규칙

- **앱 재시작 시**: `analysis_status == "processing"`인 노드를 모두 `"pending"`으로 롤백 (Gemma 4 크래시 대비).
- **파일 삭제 감지**: KG 노드 cascade 제거 (기존 로직 유지).

---

## 3. 저장 구조

### 3.1. Primary Store: KnowledgeGraph

**파일**: `~/.gemvis/graph.ttl` (RDF/Turtle)

**file 노드 속성** (GemInsight 1개분):

```turtle
<node/file/{path}> rdf:type gvt:file ;
    gva:name              "/Users/username/meeting.md" ;
    gva:category          "document" ;
    gva:summary           "Gemvis 해커톤 진행 상황 회의" ;
    gva:risk_level        "auto_safe" ;
    gva:file_mtime        "2026-05-11T14:30:00" ;
    gva:file_ctime        "2026-05-11T04:40:00" ;
    gva:added_at          "2026-05-12T10:29:55" ;
    gva:size_bytes        "2847" ;
    gva:analysis_status   "completed" ;
    gva:last_analyzed_at  "2026-05-12T10:30:00" ;
    gva:error             "" ;
    gva:raw_insight       "{ ... GemInsight full JSON ... }" .
```

**엔티티/관계 노드** — 검색·그래프뷰용 **파생 인덱스**로 역할 재정의.
`raw_insight`가 진짜 원본이며, KG 엣지는 SPARQL 쿼리 성능을 위해 풀어놓은 인덱스.

### 3.2. Secondary: Embeddings

**파일**: `~/.gemvis/embeddings.npz` (numpy)
file 노드당 1개 벡터 (384-dim). 검색 의미 매칭용.

### 3.3. Secondary: EventLog

**파일**: `~/.gemvis/events.ttl` (RDF/Turtle)
`(action, file_path, timestamp, period)` 이벤트 시계열. Calendar 뷰 전용.

### 3.4. 데이터 흐름

```
       ┌─────────────────────┐
       │   GemInsight (JSON) │  ← SSoT 원본
       └─────────────────────┘
                │
                ▼  kg.add_insight()
  ┌─────────────────────────────────┐
  │  KG file 노드 속성 (raw_insight) │  ← 영구 저장
  └─────────────────────────────────┘
                │
                ├─▶ 엔티티/관계 노드 & 엣지   (파생: SPARQL 검색 인덱스)
                ├─▶ 임베딩 벡터              (파생: 의미 검색)
                └─▶ EventLog                 (파생: 시간 타임라인)
```

---

## 4. 기능별 GemInsight 활용

| 기능 | 엔드포인트 | 사용 필드 | 비고 |
|------|-----------|-----------|------|
| **Dashboard** | `GET /api/files` | `file_name`, `category`, `summary`, `file_mtime/ctime`, `added_at`, `analysis_status` | 4상태 배지 표시 |
| **Calendar** | `GET /api/summary/{date}` | `file_mtime`, `summary`, `category` + EventLog | 기존 유지 |
| **GraphView** | `GET /api/graph/data` | file 노드 + 엔티티/관계 엣지 | 파생 인덱스 그대로 |
| **Chat Search** | `POST /api/search` | `summary`, `tags`, `category`, `entities` + 임베딩 | 파생 인덱스 그대로 |
| **InsightDetail** | `GET /api/file/{file_id}` | 전체 (entities, relations 포함) | `raw_insight` 진가 발휘 |

---

## 5. 불변식 (Invariants)

1. **1:1 대응** — `file_path`당 GemInsight 정확히 하나
2. **원본 보존** — `raw_insight` 속성에 전체 JSON 저장, 절대 손실 없음
3. **상태 일관성** — `analysis_status == "completed"` ⟺ 모든 Analytical/Relational 필드 채워짐
4. **로컬 전용** — 외부 전송 절대 금지 (프라이버시 핵심)
5. **복원 가능** — 파일만 있으면 언제든 regenerate
6. **파생 인덱스 우선순위** — KG 엔티티 노드 / 임베딩 / EventLog는 `raw_insight`에서 재생성 가능한 파생물

---

## 6. API v2

### 6.1. 통합 엔드포인트

| 메서드 | 경로 | 설명 | 응답 |
|--------|------|------|------|
| GET | `/api/files` | 전체 파일 목록 (페이징·정렬·필터·stats) | `FileListResponse` |
| GET | `/api/file/{file_id}` | 단일 파일 상세 | `FileRecord` |
| POST | `/api/file/{file_id}/regenerate` | 재분석 | `FileRecord` |
| POST | `/api/files/retry-failed` | 실패 파일 일괄 재시도 | `{count: number}` |

### 6.2. Deprecated (v1 → v2)

| v1 (유지하되 deprecated 주석) | v2 (권장) |
|-----------|-----------|
| `GET /api/dashboard` | `GET /api/files?include_stats=true` |
| `GET /api/insights` | `GET /api/files?status=completed` |
| `GET /api/insight/{file_id}` | `GET /api/file/{file_id}` |
| `POST /api/insight/{file_id}/regenerate` | `POST /api/file/{file_id}/regenerate` |
| `GET /api/watcher/files` | `GET /api/files?status=pending` |

### 6.3. `FileRecord` 타입 (프론트↔백 공유)

백엔드: `gemvis/api.py`의 Pydantic `FileRecord`
프론트: `frontend/src/types.ts`의 `FileRecord` interface
→ **두 정의가 1:1로 일치해야 하며, 어느 한쪽이라도 변경 시 다른 쪽도 반드시 업데이트.**

---

## 7. 마이그레이션 (기존 데이터 취급)

기존 `graph.ttl`에는 `raw_insight` 속성이 없다. 처리 방침:

1. **기존 노드 로드 시**: `raw_insight`가 없으면 `_node_to_insight()` fallback으로 KG 이웃 순회해 역조립 (기존 로직 유지, relations는 빈 리스트)
2. **자동 마이그레이션 (선택)**: 앱 시작 시 `raw_insight` 없는 file 노드를 찾아 `_node_to_insight()` 결과를 JSON 직렬화해 속성에 주입 (1회성)
3. **`analysis_status` 기본값**: 기존 노드는 모두 `"completed"`로 취급 (KG에 있다 = 이미 분석됐다)
4. **해커톤 옵션**: 데이터 많지 않으면 Settings의 "모든 데이터 초기화 & 재스캔"으로 새로 시작해도 됨

---

## 8. 구현 범위 (geminsight-develop 브랜치 작업 목록)

| Day | 파일 | 변경 | 커밋 메시지 |
|-----|------|------|-----------|
| 1 | `gemvis/insight.py` | `GemInsight` dataclass에 `analysis_status`/`last_analyzed_at`/`size_bytes` 추가 + `from_dict()` 클래스메서드 | `feat(insight): extend GemInsight with state fields + from_dict` |
| 1 | `gemvis/knowledge_graph.py` | `add_insight()`에 `raw_insight` 속성 저장 | `feat(kg): persist raw GemInsight JSON as SSoT` |
| 1 | `gemvis/insight_service.py` | `get_insight()`에서 `raw_insight` 우선 로드, fallback 유지 | `refactor(insight-service): restore from raw_insight JSON` |
| 2 | `gemvis/knowledge_graph.py` | `upsert_skeleton()` / `update_status()` 메서드 추가 | `feat(kg): analysis_status state machine methods` |
| 2 | `gemvis/watcher.py` | 2단계 hydration 로직 + `on_modified` 재분석 트리거 | `feat(watcher): 2-stage hydration pipeline` |
| 2 | `gemvis/api.py` | lifespan에서 `processing → pending` 롤백 | `fix(api): recover orphaned processing on startup` |
| 3 | `gemvis/api.py` | `FileRecord` Pydantic + `/api/files` 통합 엔드포인트 | `feat(api): unified FileRecord API v2` |
| 3 | `frontend/src/types.ts` | `FileRecord` interface 추가 | `feat(fe): FileRecord unified type` |
| 3 | `frontend/src/api.ts` | `files()`/`file()`/`regenerate()` 메서드 추가 | `feat(fe): api.files unified methods` |
| 4 | `frontend/src/pages/Dashboard.tsx` | 4상태 배지 + 테이블 컬럼 확장 | `feat(fe): analysis status indicator` |
| 4 | `frontend/src/pages/Settings.tsx` | `watchedFiles` 제거, `/api/files?status=pending` 사용 | `refactor(fe): use unified file API` |
| 5 | `API_CONTRACT.md` | v2 반영 + deprecation 주석 | `docs: API contract v2 + migration notes` |

---

## 9. 참고 문서

- [architecture.md](architecture.md) — 기존 아키텍처 문서 (v1, 4레이어 관점)
- [GEM_INSIGHT.md](GEM_INSIGHT.md) — GemInsight 개념 문서 (v1, 분산 저장 설명)
- [GEMINSIGHT_IMPACT.md](GEMINSIGHT_IMPACT.md) — AnalysisResult→GemInsight rename 영향 분석
- [API_CONTRACT.md](../API_CONTRACT.md) — API 계약
- [FEATURES.md](FEATURES.md) — 기능 목록 (컴포넌트/계층 관점)
- [FEATURES_SIDEBAR.md](FEATURES_SIDEBAR.md) — 사이드바 메뉴별 기능 스펙 + GemInsight 필드 매핑
- [QA_REPORT_V2.md](QA_REPORT_V2.md) — v2 자동화 QA 결과 (33/33 통과)
- [QA_MANUAL_CHECKLIST.md](QA_MANUAL_CHECKLIST.md) — 릴리즈 전 라이브 수동 검증 체크리스트
- [technical_spec.md](technical_spec.md) — 기술 스펙

---

**Last Updated**: 2026-05-12
**Branch**: `geminsight-develop`
