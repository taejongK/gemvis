# 검색 대화 히스토리 (Previous Intent Carry-forward)

## 개요

Search 페이지에서 후속 질문을 지원하기 위해 **이전 턴의 파싱된 intent + 결과 요약**을 다음 요청에 전달하는 방식을 도입했다.

### 문제
- Search 페이지가 채팅 UI이지만 백엔드가 stateless → "그 중에서 PDF만" 같은 후속 질문 불가
- 소형 모델(Gemma 4 E2B/E4B) 제약으로 full chat history 전달은 비효율적

### 해결: Previous Intent Carry-forward
- 매 응답에 `context` 객체를 포함 (이전 intent + 파일 수 + 파일명)
- 다음 요청 시 `prev_context`로 전달 → intent 프롬프트에 ~150 토큰 컨텍스트 블록 주입
- LLM이 후속 질문의 참조("그 중에서", "첫 번째" 등)를 해석하여 intent를 병합

## 변경 파일

### Backend

#### `gemvis/search.py`
- `CONTEXT_BLOCK` 템플릿 추가 — 이전 턴 정보를 LLM에 전달하는 프롬프트 블록
- `SearchEngine.search(question, prev_context=None)` — 시그니처 확장, 응답에 `context` 필드 추가
- `SearchEngine._build_context_block(prev_context)` — 새 메서드, context dict → 프롬프트 문자열 변환
- `SearchEngine._parse_intent(question, prev_context=None)` — prev_context 있으면 simple query도 LLM 경로 사용
- `SearchEngine._generate_answer(question, results, prev_context=None)` — 후속 질문 시 힌트 추가

#### `gemvis/api.py`
- `SearchRequest.prev_context: dict | None = None` — 요청 모델 확장
- `search()` 엔드포인트에서 `prev_context` 전달

### Frontend

#### `frontend/src/types.ts`
- `SearchResponse.context?: Record<string, unknown>` 추가

#### `frontend/src/api.ts`
- `api.search(question, prevContext?)` — `prev_context` 파라미터 추가

#### `frontend/src/SearchContext.tsx`
- `lastContext` state 추가 — 마지막 응답의 context 저장
- `send()` — `api.search(q, lastContext)` 호출, 응답 context 저장
- `reset()` — `lastContext` 초기화

### 변경하지 않은 파일
- `Spotlight.tsx` — 단일 검색 유지 (prev_context 없이 호출)
- `llm_client.py` — complete_text 인터페이스 그대로

## 데이터 흐름

```
[1차 질문] "김과장 관련 파일"
  Frontend: api.search("김과장 관련 파일", null)
  Backend:  _parse_intent(question, null) → intent
            _search_graph(intent) → results (5 files)
            → 응답: { answer, intent, graph_results, context }

[2차 질문] "그 중에서 PDF만"
  Frontend: api.search("그 중에서 PDF만", context)  ← 이전 context 전달
  Backend:  _parse_intent(question, prev_context)
            → INTENT_PROMPT + CONTEXT_BLOCK 주입
            → LLM이 search_terms=["김과장"] 유지 + categories=["document"] 추가
            _search_graph(merged_intent) → filtered results
            → 응답: { answer, intent, graph_results, context }
```

## context 객체 구조

```json
{
  "intent": {
    "search_terms": ["김과장"],
    "node_types": [],
    "categories": [],
    "semantic_query": "김과장 관련 파일",
    "intent": "김과장 관련 파일 검색"
  },
  "file_count": 5,
  "file_names": ["meeting_notes.pdf", "report.docx", ...],
  "categories_found": ["document", "memo"]
}
```

## 토큰 오버헤드

| 구성 요소 | 토큰 (without context) | 토큰 (with context) |
|-----------|----------------------|---------------------|
| INTENT_PROMPT | ~500 | ~500 |
| User question | ~20-50 | ~20-50 |
| CONTEXT_BLOCK | 0 | ~120-150 |
| **합계** | **~550** | **~700** |

턴당 ~150 토큰 추가. Gemma 4 E2B (8K context) 내 충분.

## 설계 결정 근거

| 대안 | 기각 이유 |
|------|-----------|
| Full chat history | 소형 모델 컨텍스트 소모 과다 (2-3턴이면 8K 초과) |
| Frontend query rewriting | 한국어 후속 참조 해석이 regex로 불가능 |
| Condensed summary (LLM 요약) | 요약용 추가 LLM 호출 필요 → 레이턴시 2배 |
| **Prev intent carry-forward** | **구조화된 데이터 ~150토큰, 추가 LLM 호출 없음** |
