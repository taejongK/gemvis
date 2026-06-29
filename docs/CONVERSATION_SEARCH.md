# 대화 검색 (Conversation Search) 동작 로직

> 마지막 업데이트: 2026-05-13
> 관련 파일: `gemvis/chat.py`, `gemvis/api.py`, `gemvis/search.py`

---

## 개요

대화 검색은 사용자의 자연어 메시지를 받아 **항상 파일 검색을 먼저 수행**하고, 검색된 파일의 실제 내용을 컨텍스트로 구성해 LLM이 답변하는 RAG(Retrieval-Augmented Generation) 방식으로 동작한다.

LLM이 검색 여부를 판단하는 도구 호출(tool calling) 방식은 사용하지 않는다.

---

## 전체 흐름

```
사용자 입력
    ↓
1. 검색 (search_engine.retrieve)
    ↓
2. 파일 내용 읽기 (_read_file_content)
    ↓
3. RAG 컨텍스트 구성
    ↓
4. LLM 스트리밍 답변 (stream_chat)
    ↓
사용자 응답
```

---

## 단계별 상세

### 1. 검색 (`search_engine.retrieve`)

- 사용자의 마지막 메시지를 쿼리로 사용
- 내부적으로 LLM이 쿼리를 파싱해 다음 항목 추출:
  - `search_terms`: 고유명사, 날짜 등 구조적 키워드
  - `semantic_query`: 의미 기반 주제어
  - `categories`: 파일 타입 필터 (photo, document, memo 등)
- KG 구조 검색 + 임베딩 유사도 검색 **하이브리드** 방식
- 최대 5개 파일 결과 반환
- 검색 실패 시 빈 결과로 계속 진행 (오류 미반환)

### 2. 파일 내용 읽기 (`_read_file_content`)

검색된 각 파일의 실제 내용을 디스크에서 직접 읽는다.

| 파일 타입 | 처리 방식 |
|-----------|-----------|
| 텍스트 계열 (`.txt`, `.md`, `.py`, `.json`, `.csv` 등) | `read_text()` 직접 읽기 |
| PDF | `extract_pdf_text()` 로 텍스트 추출 |
| 이미지 / 바이너리 | 읽지 않음 → KG에 저장된 summary로 폴백 |

- 파일당 최대 **8,000자** (초과 시 truncate)

### 3. RAG 컨텍스트 구성

파일당 다음 형식의 블록으로 구성한다.

```
[파일명]
카테고리: ...
태그: ...
관련 엔티티: people: ... | places: ... | projects: ...

--- 파일 내용 ---
(원문 텍스트, 최대 8,000자)
```

- 파일을 읽을 수 없는 경우 `--- 요약 ---` 으로 대체
- 검색 결과가 없으면 `"검색된 파일 없음"` 문자열 전달

### 4. LLM 스트리밍 답변

- **시스템 프롬프트**: `FILE_ANSWER_SYSTEM`
  - 파일명을 `[파일명]` 형식으로 출처 표시
  - 답변 마지막에 `**참고 파일:**` 목록 정리
  - 마크다운 형식 답변
- **메시지 구조**:
  ```
  [이전 대화 히스토리 (최근 6턴)]
  + [user] "파일 정보:\n\n{context_block}\n\n질문: {last_q}"
  ```
- temperature `0.5`, 스트리밍 출력

---

## SSE 이벤트 순서 (프론트엔드 수신)

엔드포인트: `POST /api/chat/stream`

| 순서 | 이벤트 타입 | 내용 |
|------|------------|------|
| 1 | `meta` | `intent_type: "file_search"`, `files: [{file_id, file_name, category, summary}]` |
| 2~N | `chunk` | 답변 텍스트 조각 |
| N+1 | `done` | 스트림 종료 |
| (오류 시) | `error` | 오류 메시지 문자열 |

---

## 주요 제약

| 항목 | 제한값 |
|------|--------|
| 대화 히스토리 | 최근 6턴 (12개 메시지) |
| 어시스턴트 발화 truncate | 500자 |
| 검색 결과 파일 수 | 최대 5개 |
| 파일 내용 | 파일당 최대 8,000자 |
| 컨텍스트 총량 (추정) | ~40,000자 + 메타데이터 |

---

## 관련 파일

| 파일 | 역할 |
|------|------|
| `gemvis/chat.py` | `ChatEngine.stream()` — 전체 흐름 제어 |
| `gemvis/search.py` | `SearchEngine.retrieve()` — KG + 임베딩 하이브리드 검색 |
| `gemvis/llm_client.py` | `stream_chat()`, `extract_pdf_text()` |
| `gemvis/api.py` | `/api/chat/stream` 엔드포인트, `ChatRequest` 모델 |
| `frontend/src/SearchContext.tsx` | SSE 이벤트 수신 및 세션 상태 관리 |
