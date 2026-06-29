# Gemvis - 기술 스펙 (v1, 초기 설계)

> ⚠️ **이 문서는 초기 설계 기록(v1)입니다.** 현재 구현은 [ARCHITECTURE_V2.md](ARCHITECTURE_V2.md) · [API_CONTRACT.md](../API_CONTRACT.md) · [FEATURES_SIDEBAR.md](FEATURES_SIDEBAR.md)가 우선이며, 본문의 "Tauri / Kùzu / Cypher" 등은 초기 가정입니다. 실제는 순수 React+Vite + rdflib TTL + SPARQL을 사용합니다.

> 이 문서는 구현 세부사항을 다룬다. **먼저 [user_scenarios.md](./user_scenarios.md)를 읽을 것.** 모든 기술 결정은 시나리오를 만족하기 위한 수단이다.

## 기술 스택 개요 (2026-04-17 기준)

```
Frontend:  Tauri + React + TypeScript
Backend:   Python 3.11+ (FastAPI, async)
LLM:       Gemma 4 E2B Q4_K_M (GGUF, ~2GB) — 기본
             (추후 Q8_0 / BF16 / 더 큰 모델로 업그레이드 가능)
Runtime:   llama.cpp (CPU/CUDA/Metal/Vulkan)
Graph DB:  Kùzu (임베디드, Cypher 호환)
Vector DB: ChromaDB (Phase 2)
File Watcher: watchdog
OCR (Phase 2): tesseract / Gemma vision
ASR (Phase 2): whisper.cpp
```

**핵심 변경점 (원문 대비):**
- **llama.cpp 단일 런타임** (GPU 가능 시 GPU, 아닐 시 CPU — CUDA Blackwell까지 포괄)
- Gemma 4 26B + E4B 이중 → **E2B 단일** (MVP 단순화, 해커톤 일정 현실화)
- Electron → **Tauri** (번들 크기·메모리)
- macOS 중심 → **Linux/WSL2 개발 + 크로스 플랫폼 빌드**

---

## 1. LLM 활용 부분 (Gemma 4)

### 1.1 Gemma 4 모델 선택 (MVP)

| 이름 | 파일 | 크기 | 용도 |
|------|------|-----|------|
| **기본** | `gemma-4-E2B-it-Q4_K_M.gguf` | ~2GB | 모든 추론 (분석 + 질의) — llama-server 상주 |
| 선택 | `gemma-4-E2B-it-Q8_0.gguf` | ~4GB | 정확도 필요 시 |
| 선택 | `gemma-4-E2B-it-BF16.gguf` | ~8GB | 벤치마크 |

**단일 모델 전략의 근거:**
- 해커톤 일정(5주)에 두 모델 관리 리스크 불필요
- E2B Q4_K_M도 RTX 5090에서 충분히 빠름 (생성 >30 t/s)
- 하나의 상주 서버가 인제스트 + 질의를 모두 처리
- Phase 2에 대형 모델로 교체 — 프롬프트/파이프라인 동일

### 1.2 llama.cpp 서버 아키텍처

```
[llama-server]  (상주, VRAM에 모델 로드 유지)
    │
    │ HTTP :8080  /completion, /health, /tokenize
    ▼
[backend/gemma_client.py]  (async httpx)
    │
    ├─ ingest path: 파일 분석 (JSON 강제 출력)
    ├─ nl2cypher: 자연어 → Cypher
    └─ answer: 쿼리 결과 + 원문 → 자연어 응답
```

**프로세스 관리:**
- `scripts/start_server.sh` → llama-server 백그라운드 기동
- FastAPI 시작 시 서버 health check, 없으면 자동 기동
- 종료 시 SIGTERM 전파 (모델 unload)

**성능 목표 (E2B Q4_K_M, RTX 5090):**
- 엔티티 추출 (2KB 텍스트): < 3초
- NL2Cypher: < 1초
- 답변 합성 (짧은 결과): < 2초
- 첫 토큰 지연 (TTFT): < 300ms

### 1.2 Gemma 4 활용 영역

#### (1) 파일 내용 분석 및 엔티티 추출

**입력**: 파일 내용 (텍스트, 이미지 OCR 결과, 음성 전사)

**출력**: 구조화된 엔티티 및 관계

**프롬프트 예시**:
```
당신은 개인 파일 분석 AI입니다. 다음 문서에서 엔티티와 관계를 추출하세요.

문서 내용:
"""
2026년 3월 15일 김과장님과 강남역 근처 식당에서 Gemvis 프로젝트 논의
- 해커톤 참가 결정
- 지식그래프 기반 아키텍처 합의
- 다음 주 화요일 재논의
"""

다음 형식으로 출력하세요:
{
  "entities": [
    {"type": "Person", "name": "김과장"},
    {"type": "Place", "name": "강남역 근처 식당"},
    {"type": "Project", "name": "Gemvis"},
    {"type": "Event", "name": "회의", "date": "2026-03-15"}
  ],
  "relationships": [
    {"from": "회의", "to": "김과장", "type": "ATTENDED_BY"},
    {"from": "회의", "to": "Gemvis", "type": "ABOUT"},
    {"from": "회의", "to": "강남역 근처 식당", "type": "LOCATED_AT"}
  ]
}
```

**Function Calling 활용**:
```python
tools = [
    {
        "name": "extract_entities",
        "description": "Extract entities and relationships from text",
        "parameters": {
            "type": "object",
            "properties": {
                "entities": {"type": "array"},
                "relationships": {"type": "array"}
            }
        }
    }
]
```

#### (2) 파일 분류 및 정리 제안

**입력**: 파일 메타데이터 + 내용 요약

**출력**: 추천 폴더 경로 + 신뢰도

**프롬프트 예시**:
```
파일 정보:
- 이름: gemma_4_hackathon_idea.md
- 내용: Gemma 4를 활용한 온디바이스 지식그래프 프로젝트 아이디어...

기존 폴더 구조:
- ~/Documents/Projects/
- ~/Documents/Work/
- ~/Documents/Personal/

이 파일을 어디에 정리하는 것이 적절한가요?
- 추천 경로를 제시하세요
- 신뢰도를 0-1 사이로 제공하세요
- 0.8 미만이면 사용자에게 확인을 요청합니다
```

#### (3) 자연어 질의 → 그래프 쿼리 변환

**입력**: 사용자의 자연어 질문

**출력**: Cypher 쿼리 (Neo4j) 또는 SPARQL

**프롬프트 예시**:
```
사용자 질문: "지난달 김과장이랑 같이 간 식당 어디였지?"

지식그래프 스키마:
- Person (name, contact)
- Place (name, address)
- Event (name, date)
- File (path, type)

관계:
- ATTENDED_BY (Event → Person)
- LOCATED_AT (Event → Place)
- MENTIONED_IN (Entity → File)

이 질문을 Cypher 쿼리로 변환하세요:
"""
MATCH (p:Person {name: "김과장"})-[:ATTENDED_BY]-(e:Event)-[:LOCATED_AT]->(place:Place)
WHERE e.date >= date("2026-03-01") AND e.date <= date("2026-03-31")
RETURN place.name, e.date
"""
```

**Function Calling**:
```python
tools = [
    {
        "name": "query_knowledge_graph",
        "description": "Execute Cypher query on knowledge graph",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Cypher query"}
            }
        }
    }
]
```

#### (4) 멀티모달 입력 처리

**이미지 분석**:
```python
# Gemma 4의 vision 기능 활용
prompt = """
이 스크린샷에서 중요한 정보를 추출하세요:
- 사람 이름
- 날짜/시간
- 장소
- 프로젝트명
- 핵심 내용 요약
"""
response = gemma_vision.generate(prompt, image=screenshot_path)
```

**음성 분석**:
```python
# Whisper로 전사 → Gemma 4로 분석
transcript = whisper.transcribe(audio_path)
prompt = f"다음 음성 메모를 분석하고 엔티티를 추출하세요:\n{transcript}"
response = gemma.generate(prompt)
```

---

## 2. 지식그래프 활용 부분

### 2.1 그래프 DB 선택

**Option 1: Neo4j Lite** (성숙도 우선)
- 성숙한 그래프 DB
- Cypher 쿼리 언어 (직관적)
- 시각화 도구 내장
- 단점: 무거움 (Java 기반)

**Option 2: sqlite-vec** (경량 우선)
- 경량 (single file DB)
- Python 통합 쉬움
- 벡터 검색 지원
- 단점: 그래프 쿼리 기능 제한적

**Option 3: Kùzu** (추천 - 균형)
- 임베디드 그래프 DB (C++ 기반)
- Cypher 호환 쿼리
- 매우 빠른 성능 (컬럼 기반 저장)
- 단일 파일 DB
- Python 바인딩 우수

**Option 4: DuckDB + Graph Extension** (실험적)
- 분석용 DB에 그래프 기능 추가
- SQL + Cypher 혼합 가능
- 매우 빠른 분석 쿼리
- 단점: 그래프 확장이 아직 초기 단계

**MVP 선택**: **Kùzu** (빠른 개발 + 좋은 성능 + 확장성)

**선택 이유**:
- 경량하면서도 Cypher 완전 지원
- 임베디드 방식으로 별도 서버 불필요
- Neo4j 대비 10-100배 빠른 쿼리 성능 (벤치마크 기준)
- Python 통합 간단

### 2.2 그래프 스키마

```cypher
// 노드 타입
(:Person {name, contact, tags})
(:Place {name, address, coordinates})
(:Project {name, description, status})
(:Event {name, date, time})
(:Concept {name, category})
(:File {path, type, size, created_at, modified_at})

// 관계 타입
-[:ATTENDED_BY]-> (Person)
-[:LOCATED_AT]-> (Place)
-[:PART_OF]-> (Project)
-[:RELATED_TO]-> (Any)
-[:MENTIONED_IN]-> (File)
-[:HAPPENED_AT]-> (Time)
-[:TAGGED_AS]-> (Concept)
-[:SIMILAR_TO {score}]-> (File)
```

### 2.3 핵심 쿼리 패턴

#### (1) 관계 추론 쿼리

```cypher
// "김과장과 관련된 모든 프로젝트"
MATCH (p:Person {name: "김과장"})-[:ATTENDED_BY|MENTIONED_IN*1..3]-(proj:Project)
RETURN proj.name, count(*) as relevance
ORDER BY relevance DESC
```

#### (2) 시간축 추적

```cypher
// "지난 한 달간 Gemvis 프로젝트 활동"
MATCH (proj:Project {name: "Gemvis"})-[:PART_OF]-(e:Event)
WHERE e.date >= date() - duration({days: 30})
RETURN e.name, e.date
ORDER BY e.date DESC
```

#### (3) 멀티홉 연결 탐색

```cypher
// "이 파일과 연결된 모든 사람"
MATCH (f:File {path: "/path/to/file.md"})-[:MENTIONED_IN*..3]-(p:Person)
RETURN DISTINCT p.name, length(path) as degree
ORDER BY degree
```

### 2.4 벡터 임베딩 통합

**목적**: 의미 기반 유사 파일 검색

**구현**:
```python
from chromadb import Client

# 1. 파일 내용을 벡터로 임베딩
client = Client()
collection = client.create_collection("files")

# 2. 임베딩 저장 (Gemma 4 embedding 사용)
embedding = gemma.embed(file_content)
collection.add(
    ids=[file_id],
    embeddings=[embedding],
    metadatas=[{"path": file_path, "type": file_type}]
)

# 3. 유사 파일 검색
results = collection.query(
    query_embeddings=[query_embedding],
    n_results=5
)
```

**통합 전략**:
- Graph DB: 명시적 관계 (구조적 쿼리)
- Vector DB: 암묵적 유사성 (의미 기반 검색)
- 하이브리드 검색: 두 가지 결과를 re-ranking

---

## 2.5 Gemvis 관리 폴더 구조 (시나리오 1 구현)

사용자가 선택한 "관리 폴더" (기본 `~/Gemvis/`) 안에 다음 뷰를 **symlink로** 자동 생성한다. 원본은 절대 이동하지 않는다.

```
~/Gemvis/
├── by-category/
│   ├── 업무/
│   │   ├── 회의록/  → symlink 수십 개
│   │   ├── 기획서/
│   │   └── 이메일/
│   ├── 금융/
│   │   ├── 영수증/
│   │   └── 청구서/
│   ├── 개인/
│   └── 사진-행사/
├── by-person/
│   ├── 김과장/
│   ├── Bob/
│   └── ...
├── by-project/
│   ├── Gemvis-해커톤/
│   └── A사-프로모션/
├── by-time/
│   ├── 2026-04/
│   ├── 2026-03/
│   └── ...
├── recent/                    (최근 30일 스캔, 자동 정리)
└── _review/                   (신뢰도 < 0.8, 사용자 확인 대기)
```

**구현 규칙:**
- 파일 1개가 여러 뷰에 동시에 존재 (한 파일이 `by-person/김과장/` + `by-category/업무/회의록/` + `by-time/2026-04/` 에 전부 symlink로)
- symlink 이름 충돌 시 suffix 추가 (`_1`, `_2`)
- 관리 폴더 자체 파일 변경은 무시 (watchdog 제외)
- 사용자가 symlink를 삭제해도 원본·그래프 영향 없음

## 2.6 신뢰도 기반 자동/리뷰 분기 (시나리오 2 구현)

```python
CONFIDENCE_THRESHOLD = 0.8  # 환경변수로 조정 가능

def classify_and_link(file_path: str, analysis: AnalysisResult):
    if analysis.confidence >= CONFIDENCE_THRESHOLD:
        # 자동: 해당 카테고리/엔티티 symlink 뷰에 바로 연결
        create_symlinks(file_path, analysis.views)
        emit_notification("auto_classified", file_path, analysis)
    else:
        # 리뷰: _review/ 에 임시 심볼릭 + 배지 +1
        create_symlink(file_path, REVIEW_DIR)
        enqueue_review(file_path, analysis)
```

**Gemma 프롬프트에서 신뢰도 획득:**
- JSON 출력에 `confidence: 0-1` 필수 필드
- 애매한 카테고리는 top-3 후보 + 각각의 점수 반환
- 사용자 되묻기 모달이 이 후보를 그대로 표시

## 3. 파일 모니터링 및 처리

### 3.1 File Watcher

**Python - watchdog 라이브러리**:
```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class GemvisFileHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            # 새 파일 감지 → 분석 큐에 추가
            file_queue.put(event.src_path)
    
    def on_modified(self, event):
        # 수정된 파일도 재분석
        if should_reanalyze(event.src_path):
            file_queue.put(event.src_path)

# 모니터링 시작
observer = Observer()
observer.schedule(GemvisFileHandler(), path="/Users/username/Documents", recursive=True)
observer.start()
```

### 3.2 Content Extraction

**지원 파일 형식**:

| 형식 | 라이브러리 | 추출 내용 |
|------|-----------|-----------|
| `.txt`, `.md` | built-in | 전체 텍스트 |
| `.pdf` | PyPDF2 | 텍스트 + 메타데이터 |
| `.docx` | python-docx | 텍스트 + 스타일 |
| `.jpg`, `.png` | Pillow + pytesseract | OCR 텍스트 |
| `.mp3`, `.m4a` | whisper-cpp | 음성 전사 |

**구현 예시**:
```python
def extract_content(file_path: str) -> dict:
    ext = Path(file_path).suffix.lower()
    
    if ext in [".txt", ".md"]:
        return {"text": Path(file_path).read_text()}
    
    elif ext == ".pdf":
        import PyPDF2
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            text = "\n".join(page.extract_text() for page in reader.pages)
        return {"text": text, "pages": len(reader.pages)}
    
    elif ext in [".jpg", ".png"]:
        # Gemma 4 vision 직접 사용
        return gemma_vision.analyze(file_path)
    
    elif ext in [".mp3", ".m4a"]:
        transcript = whisper.transcribe(file_path)
        return {"text": transcript["text"]}
```

---

## 4. 백엔드 API 설계

### 4.1 FastAPI 서버 구조

```python
from fastapi import FastAPI, UploadFile
from pydantic import BaseModel

app = FastAPI()

# 1. 파일 분석 엔드포인트
@app.post("/api/analyze")
async def analyze_file(file_path: str):
    """파일 분석 및 엔티티 추출"""
    content = extract_content(file_path)
    entities = gemma_agent.extract_entities(content)
    graph_db.add_entities(entities)
    return {"status": "success", "entities": entities}

# 2. 자연어 질의
@app.post("/api/query")
async def natural_language_query(query: str):
    """자연어 질문 → 그래프 쿼리 → 응답"""
    cypher_query = gemma_agent.convert_to_cypher(query)
    results = graph_db.execute(cypher_query)
    answer = gemma_agent.generate_answer(query, results)
    return {"answer": answer, "sources": results}

# 3. 파일 정리 제안
@app.post("/api/organize")
async def suggest_organization(file_path: str):
    """파일 정리 제안"""
    suggestion = gemma_agent.suggest_folder(file_path)
    return {
        "suggested_path": suggestion["path"],
        "confidence": suggestion["confidence"],
        "reason": suggestion["reason"]
    }

# 4. 그래프 시각화 데이터
@app.get("/api/graph")
async def get_graph_data(focus_entity: str = None):
    """그래프 시각화용 데이터"""
    if focus_entity:
        subgraph = graph_db.get_subgraph(focus_entity, depth=2)
    else:
        subgraph = graph_db.get_overview()
    return {"nodes": subgraph.nodes, "edges": subgraph.edges}
```

---

## 5. 프론트엔드 UI

### 5.1 Electron + React 구조

```
src/
├── main/           # Electron main process
│   ├── index.ts
│   └── fileWatcher.ts
├── renderer/       # React UI
│   ├── components/
│   │   ├── ChatInterface.tsx
│   │   ├── GraphVisualization.tsx
│   │   └── FileBrowser.tsx
│   └── App.tsx
└── shared/         # 공통 타입
    └── types.ts
```

### 5.2 주요 컴포넌트

#### (1) ChatInterface.tsx
```tsx
const ChatInterface = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");

  const handleSend = async () => {
    const response = await fetch("/api/query", {
      method: "POST",
      body: JSON.stringify({ query: input })
    });
    const data = await response.json();
    setMessages([...messages, 
      { role: "user", content: input },
      { role: "assistant", content: data.answer }
    ]);
  };

  return (
    <div className="chat-container">
      <MessageList messages={messages} />
      <Input value={input} onChange={setInput} onSend={handleSend} />
    </div>
  );
};
```

#### (2) GraphVisualization.tsx
```tsx
import { ForceGraph2D } from 'react-force-graph';

const GraphVisualization = ({ data }) => {
  return (
    <ForceGraph2D
      graphData={data}
      nodeLabel="name"
      nodeColor={node => getColorByType(node.type)}
      onNodeClick={node => showNodeDetails(node)}
    />
  );
};
```

---

## 6. 배포 및 패키징

### 6.1 프론트엔드 프레임워크 선택

**Option 1: Electron** (범용성)
- 크로스 플랫폼 (macOS, Windows, Linux)
- 풍부한 생태계
- 단점: 앱 크기 큼 (~100MB+)

**Option 2: Tauri** (추천 - 경량)
- Rust 기반, 네이티브 WebView 사용
- 앱 크기 작음 (~10MB)
- macOS에서 특히 빠름
- 보안성 우수
- 단점: 생태계가 Electron보다 작음

**MVP 선택**: **Tauri** (macOS 우선 타겟에 최적)

### 6.2 Tauri 빌드 설정

```json
// package.json
{
  "name": "gemvis",
  "version": "0.1.0",
  "scripts": {
    "dev": "tauri dev",
    "build": "tauri build"
  },
  "dependencies": {
    "@tauri-apps/api": "^1.5.0"
  }
}
```

```toml
# src-tauri/tauri.conf.json
{
  "build": {
    "beforeBuildCommand": "npm run build",
    "beforeDevCommand": "npm run dev"
  },
  "package": {
    "productName": "Gemvis",
    "version": "0.1.0"
  },
  "tauri": {
    "bundle": {
      "identifier": "com.gemvis.app",
      "icon": [
        "icons/icon.icns",
        "icons/icon.ico"
      ],
      "macOS": {
        "minimumSystemVersion": "10.15"
      }
    }
  }
}
```

### 6.3 Gemma 4 모델 번들링 (llama.cpp 단일 경로)

**설치/빌드:** `./scripts/setup.sh` (자동)
- llama.cpp 클론 + cmake Release 빌드 (CPU/CUDA/Metal/Vulkan 자동 감지)
- `scripts/models.yaml` 레지스트리 기반 다운로드
- 기본: `unsloth/gemma-4-E2B-it-GGUF` 의 `gemma-4-E2B-it-Q4_K_M.gguf`

**모델 경로 규칙 (플랫폼 독립):**
```
<프로젝트 루트>/models/gemma-4-e2b/*.gguf       (개발)
<앱 데이터 디렉토리>/models/gemma-4-e2b/*.gguf  (배포)
  - macOS:   ~/Library/Application Support/Gemvis/models/
  - Linux:   ~/.local/share/Gemvis/models/
  - Windows: %APPDATA%\Gemvis\models\
```

**서버 기동:**
```bash
./third_party/llama.cpp/build/bin/llama-server \
    -m ./models/gemma-4-e2b/gemma-4-E2B-it-Q4_K_M.gguf \
    -ngl 99 --host 127.0.0.1 --port 8080 \
    --ctx-size 8192 --parallel 2
```

**선택 모델 추가:**
- `scripts/models.yaml` 에 항목 추가 후 `python3 scripts/download_models.py <name>`
- 교체 시 env `GEMVIS_DEFAULT_MODEL` 수정 (`.claude/settings.json` 또는 앱 설정)

---

## 7. 성능 최적화

### 7.1 모델 추론 최적화

```python
# 1. 배치 처리
files = ["file1.txt", "file2.txt", "file3.txt"]
contents = [extract_content(f) for f in files]
results = gemma_agent.batch_analyze(contents)  # 한 번에 처리

# 2. 캐싱
from functools import lru_cache

@lru_cache(maxsize=1000)
def analyze_file_cached(file_hash: str):
    return gemma_agent.analyze(get_file_by_hash(file_hash))

# 3. 비동기 처리
import asyncio

async def process_files_async(files):
    tasks = [analyze_file_async(f) for f in files]
    return await asyncio.gather(*tasks)
```

### 7.2 그래프 쿼리 최적화

```cypher
// 인덱스 생성
CREATE INDEX person_name FOR (p:Person) ON (p.name);
CREATE INDEX file_path FOR (f:File) ON (f.path);

// 쿼리 최적화: LIMIT 사용
MATCH (p:Person)-[:RELATED_TO*..3]-(f:File)
WHERE p.name = "김과장"
RETURN f
LIMIT 10  // 너무 많은 결과 방지
```

---

## 8. 테스트 전략

### 8.1 단위 테스트

```python
# test_entity_extraction.py
def test_extract_person_entity():
    text = "김과장님과 회의"
    entities = gemma_agent.extract_entities(text)
    assert any(e["type"] == "Person" and "김과장" in e["name"] for e in entities)

# test_graph_query.py
def test_find_related_files():
    query = "MATCH (p:Person {name: '김과장'})-[:MENTIONED_IN]-(f:File) RETURN f"
    results = graph_db.execute(query)
    assert len(results) > 0
```

### 8.2 통합 테스트

```python
def test_end_to_end_query():
    # 1. 파일 추가
    file_path = "/tmp/test_meeting.md"
    create_test_file(file_path, "김과장과 Gemvis 논의")
    
    # 2. 자동 분석
    analyze_file(file_path)
    
    # 3. 자연어 질의
    response = query_api("김과장과 관련된 파일 찾아줘")
    
    # 4. 검증
    assert "test_meeting.md" in response["answer"]
```

---

## 9. 모니터링 및 로깅

```python
import logging
from prometheus_client import Counter, Histogram

# 메트릭 정의
files_processed = Counter('gemvis_files_processed', 'Total files processed')
query_duration = Histogram('gemvis_query_duration_seconds', 'Query duration')

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"{HOME}/.gemvis/logs/gemvis.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("gemvis")
logger.info("File processed", extra={"file_path": path, "duration": elapsed})
```

---

## 10. 개발 환경 설정

### 10.1 필수 도구

```bash
# 공통 (Ubuntu/WSL2/Debian 예시)
sudo apt install -y python3 python3-venv python3-pip git cmake build-essential

# CUDA (NVIDIA GPU 사용 시) — Blackwell은 CUDA 12.8+
# CUDA Toolkit: https://developer.nvidia.com/cuda-downloads

# macOS
brew install python git cmake rust
```

### 10.2 원클릭 설치 후 개발 서버

```bash
# 설치 (1회)
./scripts/setup.sh --gpu cuda          # 또는 --gpu metal / --gpu cpu

# venv 활성화
source .venv/bin/activate

# llama.cpp 서버 (백그라운드)
./scripts/start_server.sh              # Day 4 작성 예정

# FastAPI 백엔드
uvicorn backend.main:app --reload --port 8000

# 프론트엔드 (Week 3부터)
cd frontend && npm run tauri dev
```

### 10.3 GPU/빌드 진단

```bash
# llama.cpp 빌드 정보
./third_party/llama.cpp/build/bin/llama-cli --version

# CUDA 링크 확인
ldd ./third_party/llama.cpp/build/bin/llama-cli | grep -i cuda

# GPU 상태 / VRAM
nvidia-smi

# 추론 벤치마크
./third_party/llama.cpp/build/bin/llama-bench \
    -m ./models/gemma-4-e2b/gemma-4-E2B-it-Q4_K_M.gguf -ngl 99
```

---

## 요약

| 항목 | 기술 | 이유 |
|------|------|------|
| LLM | Gemma 4 E2B Q4_K_M (GGUF) | 온디바이스, 빠른 설치, 단일 모델 단순성 |
| AI Runtime | llama.cpp (CUDA/Metal/Vulkan/CPU) | 크로스 플랫폼, 서버 모드, GGUF 에코시스템 |
| 그래프 DB | Kùzu | 임베디드, Cypher 호환, 매우 빠른 쿼리 |
| 백엔드 | FastAPI (async) | 비동기, Python 에코시스템 |
| 프론트엔드 | Tauri + React + TS | 경량 번들, 네이티브 파일 접근 |
| 파일 감시 | watchdog | 크로스 플랫폼 |
| 벡터 DB (Phase 2) | ChromaDB | 경량, Python 통합 |

### 핵심 차별화 요소
1. **온디바이스 단일 모델** — 외부 API 0, 네트워크 없이도 완전 동작
2. **Symbolic Link 가상 정리** — 원본 불변, 모든 작업 되돌릴 수 있음
3. **경량 그래프 DB (Kùzu)** — 별도 서버 없이 임베디드, Cypher로 추론 쿼리
4. **신뢰도 기반 자동/리뷰 분기** — 확실한 건 자동, 애매한 건 사용자에게
