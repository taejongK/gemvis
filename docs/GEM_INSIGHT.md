# GemInsight — Gemvis의 핵심 참조 데이터

> **핵심 정의**: 사용자가 지정한 경로의 **모든 파일에 대해 Gemma 4가 추출한 구조화된 메타데이터**. Gemvis의 모든 UI/쿼리/검색이 이 데이터를 중심으로 동작한다.
>
> **슬로건**: *Every file becomes a Gem.*

---

## 1. 왜 GemInsight인가

### 문제
파일 시스템은 이름·확장자·수정일 같은 **얕은 메타데이터**만 갖는다. 사용자가 "지난주 김과장이랑 간 식당" 같이 질문하려면:
- 파일 **내용**을 이해해야 하고 (summary)
- 그 안의 **개념**을 뽑아내야 하고 (entities)
- 개념끼리의 **연결**을 알아야 한다 (relations)

### 해결
**Gemma 4가 로컬에서 파일을 읽고, 각 파일당 하나의 GemInsight를 생성**한다. GemInsight는 **3개 저장소(KnowledgeGraph, Embeddings, EventLog)로 변환되어 저장**되며, 모든 UI는 이 저장소들을 조회한다.

```
원본 파일 (변경 금지)
    ↓ Gemma 4 분석
┌──────────────────────────────┐
│       GemInsight             │  ← 파일 분석 결과 (중간 구조)
│  (파일 1개당 1개, Python 객체) │
└──────────────────────────────┘
    ↓ 3가지 저장소로 변환 저장
┌─────────────┬─────────────┬─────────────┐
│ KnowledgeGraph │ Embeddings │  EventLog  │
│  (구조)        │  (의미)     │  (시간)     │
│  RDF 노드/엣지  │ numpy 벡터  │ RDF 이벤트  │
└─────────────┴─────────────┴─────────────┘
    ↑ 4개 UI가 저장소 직접 조회
┌──────────┬──────────┬──────────┬──────────┐
│Dashboard │ Calendar │  Graph   │  Chat    │
│ (통계)    │ (시간)    │ (구조)    │ (RAG)    │
│ KG 직접   │ Event+KG │ KG 직접   │ KG+Embed │
└──────────┴──────────┴──────────┴──────────┘

선택적: GET /api/insight/{file_path} 로 GemInsight 원본 조회 가능
```

---

## 2. GemInsight의 구조

### 스키마 (Python `AnalysisResult` → rename to `GemInsight`)

```python
@dataclass
class GemInsight:
    # 식별자
    file_path: str              # 절대 경로 (Primary Key)

    # 분류 & 요약
    category: Literal[
        "memo", "photo", "screenshot", "document",
        "voice_memo", "code", "data", "other"
    ]
    summary: str                # 한 줄 요약 (한국어, ~50자)
    tags: list[str]             # 3-7개 태그

    # 엔티티 (그래프 노드 재료)
    entities: dict[str, list[str]] = {
        "people":   [...],      # 사람 이름
        "places":   [...],      # 장소
        "projects": [...],      # 프로젝트
        "dates":    [...],      # 날짜 (YYYY-MM-DD 정규화)
        "events":   [...],      # 이벤트
    }

    # 관계 (그래프 엣지 재료)
    relations: list[Relation]   # {source, target, relation, ...}

    # 메타
    risk_level: Literal["auto_safe", "review_first"]
    error: str | None           # 분석 실패 시 원인
```

### 실제 예시 (회의록 파일)

```json
{
  "file_path": "/Users/andy/gemvis_watch/test_meeting_note.md",
  "category": "document",
  "summary": "Gemvis 프로젝트 회의록 — 해커톤 일정과 기술 스택 결정, 다음 주 할 일 논의",
  "tags": ["회의록", "프로젝트", "해커톤", "기술스택", "LLM", "React", "그래프DB"],
  "entities": {
    "people":   ["인규", "준혁", "혜지", "태종"],
    "places":   ["강남 스타벅스"],
    "projects": ["Gemvis"],
    "dates":    ["2026-05-11", "2026-05-15", "2026-05-20", "2026-05-13"],
    "events":   ["회의", "해커톤"]
  },
  "relations": [
    {"source": "인규", "source_type": "person",
     "target": "Gemvis", "target_type": "project", "relation": "works_on"},
    {"source": "회의", "source_type": "event",
     "target": "2026-05-11", "target_type": "date", "relation": "occurred_at"},
    {"source": "회의", "source_type": "event",
     "target": "강남 스타벅스", "target_type": "place", "relation": "located_at"}
  ],
  "risk_level": "auto_safe"
}
```

---

## 3. 불변식 (Invariants)

1. **1:1 대응** — 파일 경로 하나당 GemInsight 하나
2. **불변** — 파일이 수정되면 새 GemInsight로 교체 (patch 아님)
3. **원본 보호** — GemInsight 생성/삭제가 원본 파일에 영향 없음
4. **로컬 전용** — 외부 전송 금지 (프라이버시 핵심)
5. **복원 가능** — 파일이 있으면 GemInsight는 언제든 재생성 가능

---

## 4. 저장 구조 (GemInsight → 3개 파생 저장소)

GemInsight 1개가 생성되면 **3곳에 동시 기록**된다.

### (A) KnowledgeGraph — 구조적 관계

```turtle
# ~/.gemvis/graph.ttl
<file/test_meeting_note.md> rdf:type gvt:file ;
    gva:summary "Gemvis 프로젝트 회의록..." ;
    gva:category "document" ;
    gvr:mentions <person/인규> ;
    gvr:mentions <place/강남 스타벅스> ;
    gvr:tagged_with <tag/회의록> .

<event/회의> gvr:occurred_at <date/2026-05-11> ;
             gvr:located_at <place/강남 스타벅스> .
```

**용도**: "김과장이 참석한 회의의 장소는?" 같은 **관계 추적 쿼리** (SPARQL)

### (B) Embeddings — 의미적 유사도

```python
# ~/.gemvis/embeddings.npz
"file:test_meeting_note.md" → [0.12, -0.44, 0.87, ...]  # 384-dim
```

**인덱싱 대상**: `f"{name} | {summary} | {' '.join(tags)}"`

**용도**: "회의록 분위기 파일" 같은 **의미 기반 퍼지 매칭**

### (C) EventLog — 시간 축

```turtle
# ~/.gemvis/events.ttl
<event/xxx> evt:action "created" ;
            evt:file_path "/Users/andy/.../test_meeting_note.md" ;
            evt:timestamp "2026-05-11T14:30:00" ;
            evt:period "work" .
```

**용도**: "지난주 내가 만든 파일들" 같은 **시간 기반 쿼리 + 일일 요약**

---

## 5. 4개 UI의 GemInsight 활용법

### 5.1. Dashboard — 통계 뷰

**쿼리 방식**: KnowledgeGraph의 `category` 속성 집계

```
모든 GemInsight
    ↓ GROUP BY category
┌────────────────────────────────┐
│ document: 42                   │
│ photo:    17                   │
│ memo:     8                    │
│ code:     23                   │
└────────────────────────────────┘
    ↓ 렌더
Bento Grid (파이 차트 + 최근 파일 카드)
```

**표시 항목**:
- 총 파일 수 / 노드 수 / 엣지 수
- 카테고리별 분포 (파이 차트)
- 태그 빈도 탑 10 (향후)
- 최근 추가된 GemInsight 6개 (카드)

---

### 5.2. Calendar — 시간 축 뷰

**쿼리 방식**: EventLog 타임스탬프 + KnowledgeGraph file 노드 조인

```
날짜 선택 (2026-05-11)
    ↓
EventLog에서 해당 날짜 이벤트 조회
    ↓
각 이벤트의 file_path로 KnowledgeGraph file 노드 조회
    ↓ (노드 속성 = 원래 GemInsight에서 파생)
LLM에게 "이 날의 파일들(summary, category, tags)을 요약해줘" 요청
    ↓
DailySummary 생성 → daily_summary 노드로 저장
```

**표시 항목**:
- 요약 있는 날 마커 표시
- 날짜 클릭 → 해당 일 업무/개인 요약
- 요약은 **GemInsight의 summary/category/tags를 종합**한 내러티브

---

### 5.3. Graph View — 관계 뷰

**쿼리 방식**: KnowledgeGraph 전체 로드 → ForceGraph 렌더

```
GET /api/graph/data
    ↓
KnowledgeGraph.get_graph_data() — 모든 노드/엣지 반환
    ↓ (file 노드 = 원래 GemInsight에서 추가됨)
file → person → project (연결 관계 시각화)
    ↓
하이라이트 모드: 특정 file 노드 + 1-hop 이웃 강조
```

**인터랙션**:
- 파일 노드 = GemInsight에서 파생된 그래프 노드
- 엣지 = GemInsight의 entities/relations에서 생성
- 클릭 → 파일 상세 (category, summary, tags 표시)
- GET `/api/insight/{file_path}` 로 원본 GemInsight 조회 가능

---

### 5.4. Chat Search — RAG 뷰 (가장 중요)

**쿼리 방식**: Hybrid Retrieval + LLM 답변 생성

```
사용자: "인규가 담당한 업무 뭐였지?"
    ↓
[1] Intent 파싱 (Gemma 4)
    search_terms: ["인규"], semantic_query: "담당 업무"
    ↓
[2] 파일 후보 검색 (2단계 병렬)
    ┌─ KG: person:인규의 1-hop 이웃 → 연결된 file 노드 수집
    └─ Embedding: "담당 업무" 유사도 → file top-K
    ↓
[3] 교집합 재랭킹 → 후보 file 노드 10~20개
    ↓ (각 file 노드 = 원래 GemInsight에서 파생)
[4] RAG Context 구성
    각 file 노드의 {summary, tags, category} → 프롬프트에 삽입
    ↓
[5] Gemma 4 답변 생성
    "인규님은 백엔드 파이프라인 마무리를 담당했어요.
     관련 파일: test_meeting_note.md (2026-05-11 회의록)"
```

**핵심 포인트**:
- **RAG의 "R"(Retrieval)** = KnowledgeGraph file 노드 검색 (SPARQL + Embedding)
- **RAG의 "G"(Generation)** = file 노드 속성(summary/tags)을 context로 Gemma 4 답변
- **답변의 근거(citation)** = file 노드 path (사용자에게 표시)
- **GemInsight 역할**: 파일 분석 시 KnowledgeGraph에 file 노드 생성 → 검색 대상이 됨

---

## 6. 핵심 API (현재 구현)

### GemInsight 직접 조회 API (신규 추가, 2026-05-11)

```http
# GemInsight 원본 데이터 조회
GET    /api/insights                    # 전체 목록 (페이징 + 필터)
GET    /api/insights?category=photo     # 카테고리 필터링
GET    /api/insight/{file_path}         # 단건 상세 (entities, relations 포함)
POST   /api/insight/{file_path}/regenerate # 재분석 (파일 다시 읽기)
```

### 기존 UI 엔드포인트 (KnowledgeGraph 직접 조회)

```http
GET    /api/dashboard        # KG.get_file_nodes() → 통계
GET    /api/graph/data       # KG.get_graph_data() → 시각화용
POST   /api/search           # KG SPARQL + Embedding → RAG
GET    /api/summary/{date}   # EventLog + KG 조인 → 일일 집계
```

**관계**: UI 엔드포인트들은 KnowledgeGraph를 직접 쿼리하며, GemInsight는 파일 분석 시점에 KG로 변환됨. `/api/insight/*` 는 원본 GemInsight 데이터 조회용.

---

## 7. 라이프사이클

```
[1] 파일 감지 (watcher.py)
    │   on_created / on_modified
    ↓
[2] GemInsight 생성 (analyzer.py)
    │   analyze_file() → AnalysisResult ≡ GemInsight
    ↓
[3] 3곳에 동시 저장
    ├─ KG: graph.add_file_analysis(insight)
    ├─ Embed: embeddings.add_or_update(insight.file_path, text)
    └─ Event: event_log.record("created", insight.file_path, period)
    ↓
[4] UI에서 참조 (읽기 전용)
    └─ Dashboard / Calendar / GraphView / Spotlight
    ↓
[5] 파일 삭제 시
    ├─ KG: 노드 제거 (관계 자동 정리)
    ├─ Embed: 벡터 제거
    └─ Event: "deleted" 기록 (이벤트는 보존)
```

---

## 8. 품질 관리

### 신뢰도 (Confidence)
향후 GemInsight에 추가할 필드:
```python
confidence: float = 0.0  # 0.0 ~ 1.0
# 낮은 신뢰도 → UI에서 "⚠️ 검토 필요" 표시
```

### 재생성 트리거
- 사용자가 수동으로 재분석 요청
- 모델 버전 업그레이드 시 배치 재실행
- 파일 수정 감지 시 자동

### 에러 처리
- Gemma 4 JSON 파싱 실패 → `error` 필드 기록, 나머지는 기본값
- 파일 접근 불가 → GemInsight 생성 스킵, 로그 경고

---

## 9. 확장 로드맵

### Phase 1 (현재)
- [x] 텍스트/이미지/PDF → GemInsight
- [x] KG/Embedding/Event 3중 저장
- [x] 4개 UI가 GemInsight 참조

### Phase 2
- [ ] 오디오 → GemInsight (Whisper 경유)
- [ ] 비디오 → GemInsight (프레임 샘플링)
- [ ] GemInsight 수동 편집 UI (사용자 수정 가능)
- [ ] GemInsight 버전 관리 (변경 이력)

### Phase 3
- [ ] 크로스 파일 GemInsight 병합 ("이 10개 파일은 한 프로젝트")
- [ ] GemInsight 기반 자동 액션 제안 ("이 회의록에서 할 일 3개 추출")

---

## 10. 코드 리팩토링 TODO

현재 코드베이스에서 `AnalysisResult`를 `GemInsight`로 rename하면 명료해진다:

```python
# Before
from gemvis.analyzer import AnalysisResult
result = analyze_file(path)

# After
from gemvis.insight import GemInsight, generate_insight
insight = generate_insight(path)
```

**변경 범위**:
- `gemvis/analyzer.py` → `gemvis/insight.py` (파일명 변경 + 클래스 rename)
- `gemvis/watcher.py` — 참조 이름 업데이트
- `gemvis/knowledge_graph.py` — `add_file_analysis()` → `add_insight()`
- `frontend/src/types.ts` — `GemInsight` 타입 추가

---

## 요약

**GemInsight** = Gemma 4가 파일에서 뽑아낸 **구조화된 분석 결과**.

- **생성**: 파일 감지 → Gemma 4 Tool Calling → GemInsight 객체 생성
- **저장**: GemInsight → 3개 저장소 변환 (KG 노드/엣지 + Embedding 벡터 + EventLog 이벤트)
- **활용**: 4개 UI가 3개 저장소를 직접 조회 (KG/Embedding/EventLog)
- **조회**: `/api/insight/{file_path}` 로 원본 GemInsight 직접 조회 가능

**현재 아키텍처 (2026-05-11)**:
- GemInsight = 파일 분석 결과를 담는 **Python 데이터 클래스** (중간 구조)
- KnowledgeGraph = GemInsight에서 파생된 **영구 저장소** (RDF/Turtle)
- 4개 UI = KnowledgeGraph를 **주요 데이터 소스**로 사용

> Every file becomes a Gem. Every Gem becomes nodes in the Knowledge Graph.
