# GemInsight 도입 영향 분석 (AS-IS → TO-BE)

> ✅ **이 리팩터는 완료되었습니다.** 현재 코드베이스는 `GemInsight`만 사용하며, v2에서 `raw_insight` JSON을 KG file 노드에 저장해 SSoT로 승격되었습니다. 최신 아키텍처는 [ARCHITECTURE_V2.md](ARCHITECTURE_V2.md) 참조. 이 문서는 리팩터 회고용입니다.

> **작성일**: 2026-05-11  
> **목적**: GemInsight 개념 공식화에 따른 시스템 전반 변화 분석

---

## 개요

### 변경 핵심
**AS-IS**: 파일 분석 결과(`AnalysisResult`)가 묵시적으로 각 저장소에 분산 저장  
**TO-BE**: **GemInsight**를 1급 객체(First-Class Concept)로 승격, 단일 진실 공급원(SSoT) 확립

### 영향 범위
- ✅ **백엔드**: 클래스명 변경, API 엔드포인트 추가
- ✅ **프론트엔드**: 타입 정의 추가, 컴포넌트 참조 명확화
- ✅ **데이터 흐름**: 3중 저장 패턴 명시화 (KG + Embedding + EventLog)
- ✅ **문서**: 용어 통일, 아키텍처 다이어그램 갱신

---

## 실제 예시: test_meeting_note.md

### 원본 파일
```markdown
# Gemvis 프로젝트 회의록
**날짜**: 2026년 5월 11일  
**참석자**: Alice, Bob, Carol, Dave  
**장소**: 강남 스타벅스

### 1. 해커톤 일정 확인
- 제출 마감: 5월 15일 오후 11시
- 최종 발표: 5월 20일
- 백엔드 담당자이 백엔드 파이프라인 마무리 담당
...
```

### Gemma 4 분석 결과 (현재 AnalysisResult → 향후 GemInsight)
```json
{
  "file_path": "/Users/username/gemvis_watch/test_meeting_note.md",
  "category": "document",
  "summary": "Gemvis 프로젝트 회의록 — 해커톤 일정과 기술 스택 결정, 다음 주 할 일 논의",
  "tags": ["회의록", "프로젝트", "해커톤", "기술스택", "LLM", "React", "그래프DB"],
  "entities": {
    "people":   ["Alice", "Bob", "Carol", "Dave"],
    "places":   ["강남 스타벅스"],
    "projects": ["Gemvis"],
    "dates":    ["2026-05-11", "2026-05-15", "2026-05-20", "2026-05-13"],
    "events":   ["회의", "해커톤"]
  },
  "relations": [
    {"source": "Alice", "target": "Gemvis", "relation": "works_on"},
    {"source": "회의", "target": "2026-05-11", "relation": "occurred_at"},
    {"source": "회의", "target": "강남 스타벅스", "relation": "located_at"}
  ],
  "risk_level": "auto_safe"
}
```

---

## AS-IS vs TO-BE 비교

### 1. Dashboard (통계 뷰)

#### AS-IS
```python
# 백엔드 (api.py)
@app.get("/api/dashboard")
def get_dashboard():
    stats = knowledge_graph.get_stats()  # 그래프에서 직접 집계
    recent_files = knowledge_graph.get_file_nodes()[:6]
    return {"stats": stats, "recent_files": recent_files}
```

**문제점**:
- "파일 분석 결과"라는 개념이 코드에 드러나지 않음
- `knowledge_graph`가 유일한 데이터 소스인 것처럼 보임
- 프론트엔드에서 "이 카드의 요약은 어디서 온 건가?" 질문 시 답변 어려움

#### TO-BE
```python
# 백엔드 (api.py)
@app.get("/api/dashboard")
def get_dashboard():
    # GemInsight 통계 집계
    insights = insight_service.get_all_insights(limit=6, order_by="created_desc")
    category_counts = insight_service.count_by_category()
    
    return {
        "stats": {
            "total_insights": len(insights),
            "category_breakdown": category_counts,
            "node_count": knowledge_graph.get_stats()["nodes"],
            "edge_count": knowledge_graph.get_stats()["edges"]
        },
        "recent_insights": [
            {
                "file_path": i.file_path,
                "category": i.category,
                "summary": i.summary,
                "tags": i.tags,
                "created_at": i.created_at
            }
            for i in insights
        ]
    }
```

**개선점**:
- ✅ `GemInsight`가 명시적으로 등장 → "파일 카드 = GemInsight 하나"라는 멘탈 모델 확립
- ✅ 통계가 "그래프의 노드 수"가 아니라 "GemInsight 개수" 기준으로 설명 가능
- ✅ 프론트엔드 `Dashboard.tsx`에서 `Insight` 타입 import하여 타입 안정성 확보

**test_meeting_note.md 예시**:
- AS-IS: 대시보드에 "document (1개)" 통계 표시, 출처 불명확
- TO-BE: "총 1개의 GemInsight / document 카테고리" + 카드에 `summary` 표시 → Gemma 4 분석 결과임을 명확히 인지

---

### 2. Calendar (시간 축 뷰)

#### AS-IS
```python
# 백엔드 (summary.py)
def generate_daily_summary(date: str, period: str):
    # EventLog에서 파일 경로 조회
    events = event_log.get_events_for_date(date, period)
    
    # 각 파일의 현재 summary를 그래프에서 조회
    file_summaries = []
    for event in events:
        node = knowledge_graph.get_node(f"file:{event['file_path']}")
        file_summaries.append({
            "path": event["file_path"],
            "summary": node.get("summary", ""),  # ← 어디서 온 데이터인가?
            "category": node.get("category", "other")
        })
    
    # LLM에게 종합 요약 요청
    llm_summary = llm_client.complete_text(
        f"다음 파일들을 하루 요약으로 만들어줘:\n{file_summaries}"
    )
    return llm_summary
```

**문제점**:
- `node.get("summary")`가 어떻게 생성된 건지 추적 어려움
- 그래프 노드가 "분석 결과"를 담고 있다는 사실이 암묵적

#### TO-BE
```python
# 백엔드 (summary.py)
def generate_daily_summary(date: str, period: str):
    # EventLog에서 파일 경로 조회
    events = event_log.get_events_for_date(date, period)
    
    # 각 파일의 GemInsight 조회
    insights = [
        insight_service.get_insight(event["file_path"])
        for event in events
    ]
    
    # GemInsight의 summary + tags를 LLM에 전달
    context = [
        {
            "path": i.file_path,
            "summary": i.summary,           # ← GemInsight의 summary
            "category": i.category,
            "tags": i.tags,
            "entities": i.entities["people"]  # 참석자 정보
        }
        for i in insights if i is not None
    ]
    
    llm_summary = llm_client.complete_text(
        f"다음 GemInsight들을 일일 요약으로 만들어줘:\n{context}"
    )
    return llm_summary
```

**개선점**:
- ✅ "일일 요약 = 그날의 GemInsight들을 종합한 것"이라는 의미 명확
- ✅ `insight_service.get_insight()`로 데이터 출처 일관성 확보
- ✅ 프론트엔드 캘린더 팝업에서 "이 요약은 N개의 GemInsight를 기반으로 생성됨" 표시 가능

**test_meeting_note.md 예시**:
- AS-IS: 2026-05-11 요약 생성 시 "회의록 파일의 summary를 어디선가 가져옴"
- TO-BE: 2026-05-11 요약 = `test_meeting_note.md`의 **GemInsight**를 참조
  - summary: "Gemvis 프로젝트 회의록 — 해커톤 일정과 기술 스택 결정..."
  - entities.people: ["Alice", "Bob", "Carol", "Dave"] → LLM이 "4명 참석" 컨텍스트로 활용

---

### 3. Graph View (관계 뷰)

#### AS-IS
```python
# 백엔드 (api.py)
@app.get("/api/graph/data")
def get_graph_data():
    return knowledge_graph.get_graph_data()
```

**문제점**:
- 그래프 노드가 "무엇을 표현하는가?"가 불분명
- 파일 노드 = 분석 결과 컨테이너라는 사실이 숨겨짐

#### TO-BE
```python
# 백엔드 (api.py)
@app.get("/api/graph/data")
def get_graph_data():
    # GemInsight 기반 그래프 데이터 생성
    graph_data = knowledge_graph.get_graph_data()
    
    # 각 파일 노드에 GemInsight 메타데이터 부착
    for node in graph_data["nodes"]:
        if node["type"] == "file":
            insight = insight_service.get_insight(node["id"].split(":", 1)[1])
            if insight:
                node["insight"] = {
                    "summary": insight.summary,
                    "tags": insight.tags,
                    "category": insight.category
                }
    
    return graph_data
```

**개선점**:
- ✅ 그래프 노드 클릭 시 "이 파일의 GemInsight 보기" 액션 가능
- ✅ 프론트엔드 `GraphView.tsx`에서 툴팁에 `insight.summary` 표시
- ✅ "파일 노드 = GemInsight의 시각화"라는 멘탈 모델

**test_meeting_note.md 예시**:
- AS-IS: 
  ```
  [file:test_meeting_note.md] 노드
    → mentions → [person:Alice]
    → mentions → [place:강남 스타벅스]
  ```
  → 이 관계들이 어디서 왔는지 불명확

- TO-BE:
  ```
  [file:test_meeting_note.md] 노드 (GemInsight)
    ↓ insight.summary: "Gemvis 프로젝트 회의록..."
    ↓ insight.entities: {"people": ["Alice",...], "places": ["강남 스타벅스"]}
    → mentions → [person:Alice]  ← GemInsight.entities.people에서 파생
    → mentions → [place:강남 스타벅스]  ← GemInsight.entities.places에서 파생
  ```
  → 그래프 엣지가 **GemInsight의 entities/relations**에서 생성됨을 명확히 인지

---

### 4. Chat Search (RAG 뷰) — **가장 큰 변화**

#### AS-IS
```python
# 백엔드 (search.py)
class SearchEngine:
    def search(self, question: str) -> dict:
        intent = self._parse_intent(question)
        
        # 1. 그래프 검색 (구조적)
        graph_results = []
        for term in intent["search_terms"]:
            nodes = self.graph.search_nodes(term)
            graph_results.extend(nodes)
        
        # 2. 임베딩 재랭킹 (의미적)
        if intent["semantic_query"]:
            file_ids = [r["id"] for r in graph_results if r["type"] == "file"]
            scores = self.graph.embeddings.score(intent["semantic_query"], file_ids)
            graph_results.sort(key=lambda r: scores.get(r["id"], 0), reverse=True)
        
        # 3. LLM 답변 생성
        answer = self._generate_answer(question, graph_results)
        return {"answer": answer, "graph_results": graph_results}
```

**문제점**:
- RAG의 "R"(Retrieval)이 "그래프 노드 수집"으로만 설명됨
- 실제로는 **파일 분석 결과**를 검색하는 건데 용어가 없음
- `graph_results`가 과연 "검색 결과"인가, "컨텍스트"인가 모호

#### TO-BE
```python
# 백엔드 (search.py)
class SearchEngine:
    def search(self, question: str) -> dict:
        intent = self._parse_intent(question)
        
        # 1. GemInsight 후보 수집 (Hybrid Retrieval)
        candidate_insights = self._retrieve_insights(intent)
        
        # 2. RAG Context 구성
        rag_context = [
            {
                "file_path": insight.file_path,
                "summary": insight.summary,
                "tags": insight.tags,
                "entities": insight.entities,
                "category": insight.category
            }
            for insight in candidate_insights
        ]
        
        # 3. LLM 답변 생성 (Generation)
        answer = self._generate_answer_from_insights(question, rag_context)
        
        return {
            "answer": answer,
            "insights": [self._insight_to_dict(i) for i in candidate_insights],
            "intent": intent
        }
    
    def _retrieve_insights(self, intent: dict) -> list[GemInsight]:
        """Hybrid Retrieval: KG (structural) + Embedding (semantic)"""
        # Step 1: 구조적 검색 (SPARQL + 1-hop)
        matched_file_ids = set()
        for term in intent["search_terms"]:
            nodes = self.graph.search_nodes(term)
            for node in nodes:
                if node["type"] == "file":
                    matched_file_ids.add(node["id"])
                else:
                    # 엔티티 노드의 1-hop 이웃 파일 수집
                    neighbors = self.graph.get_neighbors(node["id"])
                    matched_file_ids.update(
                        n["id"] for n in neighbors if n["type"] == "file"
                    )
        
        # Step 2: 의미적 재랭킹 (Embedding)
        if intent["semantic_query"]:
            scores = self.graph.embeddings.score(
                intent["semantic_query"],
                list(matched_file_ids)
            )
            sorted_ids = sorted(matched_file_ids, key=lambda x: scores.get(x, 0), reverse=True)
        else:
            sorted_ids = list(matched_file_ids)
        
        # Step 3: GemInsight 객체로 변환
        insights = []
        for file_id in sorted_ids[:20]:  # top 20
            file_path = file_id.split(":", 1)[1]
            insight = insight_service.get_insight(file_path)
            if insight:
                insights.append(insight)
        
        return insights
```

**개선점**:
- ✅ RAG의 "R" = **GemInsight 후보 검색**으로 명확히 정의
- ✅ RAG의 "G" = GemInsight의 summary/tags/entities를 context로 LLM 답변 생성
- ✅ "검색 결과 = GemInsight 목록"으로 일관된 용어 사용
- ✅ 프론트엔드 `Spotlight.tsx`에서 `insights` 배열 렌더링 → 각 카드가 GemInsight임을 명확히 인지

**test_meeting_note.md 예시**:

**사용자 질문**: "Alice가 담당한 업무 뭐였지?"

**AS-IS 흐름**:
```
1. Intent 파싱: search_terms=["Alice"], semantic_query="담당 업무"
2. 그래프 검색:
   - "Alice" 노드 찾기
   - 1-hop 이웃 파일: [file:test_meeting_note.md]
3. 임베딩 재랭킹: "담당 업무" 유사도로 정렬
4. LLM 답변:
   - 입력: graph_results (file 노드 + person 노드 혼재)
   - 출력: "백엔드 담당자은 백엔드 파이프라인 마무리를 담당했어요."
```
→ 그래프 노드를 LLM에 어떻게 전달했는지, 파일 내용은 어디서 가져왔는지 불투명

**TO-BE 흐름**:
```
1. Intent 파싱: 동일
2. GemInsight 후보 수집:
   - KG: "Alice" → [person:Alice] → 1-hop → [file:test_meeting_note.md]
   - Embedding: "담당 업무" 유사도 계산 → test_meeting_note.md 상위 랭크
   - 결과: [GemInsight(test_meeting_note.md)]
3. RAG Context 구성:
   {
     "file_path": "/Users/username/gemvis_watch/test_meeting_note.md",
     "summary": "Gemvis 프로젝트 회의록 — 해커톤 일정과 기술 스택 결정...",
     "tags": ["회의록", "프로젝트", "해커톤"],
     "entities": {
       "people": ["Alice", "Bob", "Carol", "Dave"]
     },
     "category": "document"
   }
4. LLM 답변 생성:
   - 프롬프트: "다음 GemInsight를 참고해서 답변해줘: [위 context]"
   - 출력: "백엔드 담당자은 백엔드 파이프라인 마무리를 담당했어요.
            (관련 GemInsight: test_meeting_note.md - Gemvis 프로젝트 회의록)"
```

**답변 품질 향상**:
- AS-IS: LLM이 그래프 노드 구조를 파싱해야 함 (복잡, 오류 가능성)
- TO-BE: LLM이 **GemInsight의 summary/tags/entities**라는 정리된 컨텍스트 수신 → 더 정확한 답변

**프론트엔드 표시**:
- AS-IS: "1개의 파일 찾음: test_meeting_note.md"
- TO-BE: "1개의 GemInsight 찾음: test_meeting_note.md (회의록 / 2026-05-11)"
  - 카드 클릭 → GemInsight 상세 모달: summary, tags, entities, 폴더 열기 버튼

---

## 코드 레벨 변경사항

### 1. 백엔드 리팩토링

#### A. 파일/클래스 rename
```bash
# Before
gemvis/analyzer.py          # AnalysisResult 정의
gemvis/knowledge_graph.py   # add_file_analysis(result: AnalysisResult)

# After
gemvis/insight.py           # GemInsight 정의 (analyzer.py rename)
gemvis/knowledge_graph.py   # add_insight(insight: GemInsight)
```

#### B. 새 서비스 레이어 추가
```python
# gemvis/insight_service.py (NEW)
from gemvis.insight import GemInsight
from gemvis.knowledge_graph import KnowledgeGraph
from gemvis.embeddings import Embeddings
from gemvis.event_log import EventLog

class InsightService:
    def __init__(self, kg: KnowledgeGraph, embed: Embeddings, events: EventLog):
        self.kg = kg
        self.embed = embed
        self.events = events
    
    def save_insight(self, insight: GemInsight, period: str):
        """GemInsight를 3곳에 동시 저장 (트랜잭션 패턴)"""
        # 1. KnowledgeGraph
        self.kg.add_insight(insight)
        
        # 2. Embeddings
        embed_text = f"{insight.name} | {insight.summary} | {' '.join(insight.tags)}"
        self.embed.add_or_update(f"file:{insight.file_path}", embed_text)
        
        # 3. EventLog
        self.events.record("created", insight.file_path, period)
    
    def get_insight(self, file_path: str) -> GemInsight | None:
        """파일 경로로 GemInsight 조회 (KG에서)"""
        node = self.kg.get_node(f"file:{file_path}")
        if not node:
            return None
        return self._node_to_insight(node)
    
    def get_all_insights(self, limit: int = 100, order_by: str = "created_desc") -> list[GemInsight]:
        """전체 GemInsight 목록"""
        file_nodes = self.kg.get_file_nodes()
        insights = [self._node_to_insight(n) for n in file_nodes]
        # TODO: order_by 구현 (EventLog timestamp 조인)
        return insights[:limit]
    
    def count_by_category(self) -> dict[str, int]:
        """카테고리별 GemInsight 개수"""
        insights = self.get_all_insights()
        counts = {}
        for i in insights:
            counts[i.category] = counts.get(i.category, 0) + 1
        return counts
```

#### C. API 엔드포인트 추가
```python
# gemvis/api.py (추가)
@app.get("/api/insights")
def list_insights(
    limit: int = 100,
    category: str | None = None,
    tag: str | None = None
):
    """GemInsight 목록 조회 (페이징 + 필터)"""
    insights = insight_service.get_all_insights(limit=limit)
    
    if category:
        insights = [i for i in insights if i.category == category]
    if tag:
        insights = [i for i in insights if tag in i.tags]
    
    return {
        "total": len(insights),
        "insights": [
            {
                "file_path": i.file_path,
                "category": i.category,
                "summary": i.summary,
                "tags": i.tags,
                "created_at": i.created_at  # EventLog에서 조회
            }
            for i in insights
        ]
    }

@app.get("/api/insight/{file_id:path}")
def get_insight(file_id: str):
    """단일 GemInsight 상세 조회"""
    insight = insight_service.get_insight(file_id)
    if not insight:
        raise HTTPException(404, "GemInsight not found")
    
    return {
        "file_path": insight.file_path,
        "category": insight.category,
        "summary": insight.summary,
        "tags": insight.tags,
        "entities": insight.entities,
        "relations": insight.relations,
        "risk_level": insight.risk_level
    }

@app.post("/api/insight/{file_id:path}/regenerate")
def regenerate_insight(file_id: str):
    """GemInsight 재생성 (파일 재분석)"""
    from gemvis.analyzer import analyze_file
    
    new_insight = analyze_file(file_id)
    insight_service.save_insight(new_insight, period="work")  # TODO: period 자동 감지
    
    return {"status": "regenerated", "insight": new_insight}
```

---

### 2. 프론트엔드 변경

#### A. 타입 정의 추가
```typescript
// frontend/src/types.ts (추가)
export interface GemInsight {
  file_path: string;
  category: 'memo' | 'photo' | 'screenshot' | 'document' | 'voice_memo' | 'code' | 'data' | 'other';
  summary: string;
  tags: string[];
  entities: {
    people: string[];
    places: string[];
    projects: string[];
    dates: string[];
    events: string[];
  };
  relations: Array<{
    source: string;
    target: string;
    relation: string;
  }>;
  risk_level: 'auto_safe' | 'review_first';
  created_at?: string;  // 추후 EventLog timestamp 조인
}

export interface DashboardData {
  stats: {
    total_insights: number;
    category_breakdown: Record<string, number>;
    node_count: number;
    edge_count: number;
  };
  recent_insights: GemInsight[];
}

export interface SearchResult {
  answer: string;
  insights: GemInsight[];  // ← graph_results 대신
  intent: {
    search_terms: string[];
    semantic_query: string;
  };
}
```

#### B. 컴포넌트 수정 예시
```typescript
// frontend/src/components/Dashboard.tsx
import { GemInsight, DashboardData } from '../types';

export function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  
  useEffect(() => {
    fetch('/api/dashboard')
      .then(res => res.json())
      .then(setData);
  }, []);
  
  return (
    <div>
      <h2>총 {data?.stats.total_insights}개의 GemInsight</h2>
      
      <div className="recent-insights">
        {data?.recent_insights.map(insight => (
          <InsightCard key={insight.file_path} insight={insight} />
        ))}
      </div>
    </div>
  );
}

// 새 컴포넌트: InsightCard
function InsightCard({ insight }: { insight: GemInsight }) {
  return (
    <div className="card">
      <div className="category-badge">{insight.category}</div>
      <h3>{Path.basename(insight.file_path)}</h3>
      <p className="summary">{insight.summary}</p>
      <div className="tags">
        {insight.tags.map(tag => (
          <span key={tag} className="tag">{tag}</span>
        ))}
      </div>
      <button onClick={() => openInsightDetail(insight)}>
        상세 보기
      </button>
    </div>
  );
}
```

---

## 마이그레이션 계획

### Phase 1: 내부 리팩토링 (코드 변경, 기능 동일)
- [ ] `AnalysisResult` → `GemInsight` 클래스 rename
- [ ] `gemvis/analyzer.py` → `gemvis/insight.py` 파일명 변경
- [ ] `InsightService` 클래스 추가
- [ ] 기존 코드 참조 업데이트 (watcher, api 등)
- [ ] 테스트 코드 수정
- [ ] 문서 용어 통일 (README, docs/)

**검증**: 기존 API 엔드포인트 동작 확인, E2E 테스트 통과

### Phase 2: API 확장 (신규 엔드포인트 추가)
- [ ] `GET /api/insights` 구현
- [ ] `GET /api/insight/{file_id}` 구현
- [ ] `POST /api/insight/{file_id}/regenerate` 구현
- [ ] 프론트엔드 `GemInsight` 타입 추가
- [ ] `InsightCard` 컴포넌트 개발
- [ ] Spotlight 결과를 "insights" 필드로 변경

**검증**: 새 API 엔드포인트 Postman 테스트, 프론트엔드 타입 체크

### Phase 3: UI 개선 (사용자 가시성 향상)
- [ ] Dashboard에 "총 N개의 GemInsight" 표시
- [ ] Graph View 노드 툴팁에 insight.summary 표시
- [ ] Spotlight 결과 카드에 "GemInsight" 배지 추가
- [ ] Calendar 일일 요약 하단에 "N개의 GemInsight 기반" 문구

**검증**: UX 리뷰, A/B 테스트

---

## 정량적 변화

| 항목 | AS-IS | TO-BE |
|------|-------|-------|
| **용어 통일** | `AnalysisResult`, `파일 분석 결과`, `노드` 혼용 | `GemInsight` 단일 용어 |
| **코드 가독성** | `graph.get_file_nodes()` (파일 노드 = 뭐?) | `insight_service.get_all_insights()` (명확) |
| **API 명확성** | `POST /api/search` 응답 `graph_results` (모호) | 응답 `insights` (GemInsight 배열) |
| **프론트엔드 타입** | `any[]` 또는 `GraphNode[]` | `GemInsight[]` (엄격한 타입) |
| **멘탈 모델** | "그래프 시스템 + 파일 분석 레이어" | "GemInsight 중심 아키텍처" |
| **데이터 출처 추적** | 3단계 (KG → node → 속성) | 1단계 (GemInsight 직접 조회) |
| **RAG 설명** | "그래프 검색 + 임베딩" (기술 중심) | "GemInsight Retrieval + Generation" (개념 중심) |

---

## 결론

### 핵심 가치
1. **개념적 명확성**: "파일 분석 결과"라는 추상적 개념이 **GemInsight**라는 구체적 객체로 정립
2. **코드 품질**: 1급 객체(First-Class Concept)로 승격 → 타입 안정성, 가독성 향상
3. **사용자 인지**: UI에 "GemInsight" 용어 노출 → "Gemma 4가 추출한 정보"임을 직관적으로 이해
4. **확장성**: 향후 기능(버전 관리, 수동 편집, 크로스 파일 병합)의 기반 마련

### test_meeting_note.md 사례 요약
- **AS-IS**: Gemma 4 분석 → AnalysisResult → 그래프/임베딩에 분산 저장 → 각 UI가 개별 조회
- **TO-BE**: Gemma 4 분석 → **GemInsight** → InsightService로 3중 저장 → 모든 UI가 **GemInsight 참조**

> "Every file becomes a Gem. Every query is a search through Gems."  
> **GemInsight = Gemvis의 단일 진실 공급원(Single Source of Truth)**

---

**문서 끝**
