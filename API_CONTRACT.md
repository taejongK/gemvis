# Gemvis API Contract

**프론트↔백엔드 약속 문서 (Source of Truth)**

변경 시 이 파일을 먼저 업데이트하고, 프론트/백엔드가 각각 구현합니다.

> **v2 (geminsight-develop)**: `FileRecord` 단일 타입 + `/api/files` 통합 엔드포인트 도입. v1 엔드포인트는 Deprecated 상태로 당분간 유지.
> 자세한 아키텍처: [docs/ARCHITECTURE_V2.md](docs/ARCHITECTURE_V2.md)

---

## 🆕 v2 Unified Endpoints (권장)

모든 UI 기능은 이 엔드포인트들만 사용해야 함. 응답은 `FileRecord` 또는 `FileListResponse`.

### FileRecord 타입 (프론트↔백 공유)

```typescript
interface FileRecord {
  // Identity
  file_id: string;        // absolute path
  file_name: string;
  extension: string;

  // Physical
  size_bytes: number | null;
  file_mtime: string;     // ISO datetime
  file_ctime: string;
  added_at: string;

  // Analytical (null when analysis_status !== 'completed')
  category: string | null;
  summary: string | null;
  tags: string[];
  risk_level: string | null;
  entities: { people?: string[]; places?: string[]; projects?: string[]; dates?: string[]; events?: string[] };
  relations: Array<{ source: string; source_type: string; target: string; target_type: string; relation: string }>;

  // State
  analysis_status: 'pending' | 'processing' | 'completed' | 'failed';
  last_analyzed_at: string | null;
  error: string | null;
}

interface FileListResponse {
  files: FileRecord[];
  pagination: { page; limit; total; total_pages; sort_by; order };
  stats: GraphStats | null;
  status_counts: Record<AnalysisStatus, number>;
}
```

### GET `/api/files`

Query params: `page`, `limit`, `sort_by` (`added_at|file_mtime|file_ctime`), `order` (`desc|asc`), `status` (`pending|processing|completed|failed`), `category`, `include_stats` (bool).

Response: `FileListResponse`

### GET `/api/file/{file_id}`

`file_id`는 URL-encoded 절대 경로. Response: `FileRecord` (404 if not found).

### POST `/api/file/{file_id}/regenerate`

파일을 재분석. KG에서 기존 노드 제거 후 새 GemInsight 생성. Response: `FileRecord`.

### POST `/api/files/retry-failed`

`analysis_status="failed"` 파일 전원을 `"pending"`으로 되돌려 재시도 큐에 등록.

Response: `{ status: "requeued", count: number }`

---

## ⚠️ v1 Deprecated (호환 유지)

v1 엔드포인트는 삭제하지 않고 FastAPI `deprecated=True`로 마킹. 프론트가 완전히 전환된 뒤 제거 예정.

| v1 | v2 대체 |
|----|---------|
| `GET /api/dashboard` | `GET /api/files?include_stats=true` |
| `GET /api/insights` | `GET /api/files?status=completed` |
| `GET /api/insight/{file_id}` | `GET /api/file/{file_id}` |
| `POST /api/insight/{file_id}/regenerate` | `POST /api/file/{file_id}/regenerate` |
| `GET /api/watcher/files` | `GET /api/files` |

---

## 📋 규칙

1. **TypeScript 타입 정의가 기준** (`frontend/src/types.ts`)
2. 백엔드는 이 타입을 Pydantic 모델로 변환
3. FastAPI 자동 문서(`/docs`)가 있으므로 Swagger 별도 작성 불필요
4. 변경 시 이 파일 + `frontend/src/types.ts` + `gemvis/api.py::FileRecord`를 같이 업데이트

---

## ✅ 완성된 API (feature/multi-agent + tj/poc)

### 1. Dashboard

**GET** `/api/dashboard`

Response: `DashboardData`
```typescript
{
  stats: {
    total_nodes: number;
    total_edges: number;
    node_types: { [type: string]: number };
  };
  files: Array<{
    name: string;
    path: string;
    category: string;
    summary: string;
    risk_level: string;
    added_at: string;
  }>;
}
```

### 2. Graph Data

**GET** `/api/graph/data`

Response: `GraphData`
```typescript
{
  nodes: Array<{
    id: string;
    name: string;
    type: string;
    [key: string]: unknown;
  }>;
  edges: Array<{
    source: string;
    target: string;
    type: string;
  }>;
}
```

### 3. Search (하이브리드)

**POST** `/api/search`

Request:
```typescript
{
  question: string;
}
```

Response: `SearchResponse`
```typescript
{
  answer: string;
  intent: {
    search_terms: string[];
    node_types: string[];
    intent: string;
  } | null;
  graph_results: Array<Record<string, unknown>>;
}
```

### 4. File Watcher

**POST** `/api/watcher/start`  
**POST** `/api/watcher/stop`  
**GET** `/api/watcher/status`  
**POST** `/api/watcher/scan`

Response: `WatcherStatus` | `ApiMessage`
```typescript
{
  running: boolean;
  watch_dir: string;
  processed_count: number;
}
// or
{
  status: string;
  message: string;
}
```

### 5. Config

**POST** `/api/config`

Request:
```typescript
{
  api_key?: string;
  watch_dir?: string;
}
```

Response: `ApiMessage`

### 6. Preferences (LLM 설정)

**GET** `/api/preferences`

Response:
```typescript
{
  analyze_lang: string;        // "ko" | "en" | "ja" | "zh"
  analyze_images: boolean;
  web_search_enabled: boolean;
  llm_temperature: number;     // 0.0 ~ 2.0
  llm_max_tokens: number;      // 512 ~ 8192
  llm_top_p: number;           // 0.0 ~ 1.0
  llm_top_k: number;           // 1 ~ 100
}
```

**POST** `/api/preferences`

Request (모든 필드 optional):
```typescript
{
  analyze_lang?: string;
  analyze_images?: boolean;
  web_search_enabled?: boolean;
  llm_temperature?: number;
  llm_max_tokens?: number;
  llm_top_p?: number;
  llm_top_k?: number;
}
```

Response: 업데이트된 전체 preferences 객체 (GET과 동일 형태)

### 7. Graph Management

**DELETE** `/api/graph`

Response: `ApiMessage`

### 7. File Operations

**POST** `/api/file/open-folder`

Request:
```typescript
{
  path: string;
}
```

Response:
```typescript
{
  status: string;
  opened: string;
}
```

---

## ⚠️ 미구현 API (백엔드 작업 필요)

프론트엔드(`feature/frontend`)에서 사용 중이지만 백엔드에 없는 API

### 8. Work Schedule (우선순위: 낮음)

**GET** `/api/schedule`

Response: `ScheduleResponse`
```typescript
{
  schedule: {
    monday: { start: string; end: string } | null;
    tuesday: { start: string; end: string } | null;
    // ... 7일치
  };
}
```

**POST** `/api/schedule`

Request: `{ schedule: WorkScheduleMap }`  
Response: `ScheduleResponse`

### 9. Calendar Summary (우선순위: ★★★ 높음)

**GET** `/api/summary?date_from={from}&date_to={to}`

Response: `SummaryListResponse`
```typescript
{
  summaries: Array<{
    date: string;
    work_summary: string | null;
    personal_summary: string | null;
  }>;
}
```

**GET** `/api/summary/{date}`

Response: `DaySummaryResponse`
```typescript
{
  date: string;
  work: {
    summary: string;
    file_count: number;
    generated_at: string;
  } | null;
  personal: {
    summary: string;
    file_count: number;
    generated_at: string;
  } | null;
}
```

**POST** `/api/summary/{date}/{period}`

Path Params:
- `date`: "2026-04-29"
- `period`: "work" | "personal"

Response: `DailySummary`
```typescript
{
  date: string;
  period: "work" | "personal";
  summary: string;
  file_count: number;
  generated_at: string;
}
```

**DELETE** `/api/summary/{date}/{period}`

Response:
```typescript
{
  status: string;
}
```

---

## 🚀 구현 우선순위

### Phase 1 (5/1 완료)
- ✅ Calendar Summary API 4개 구현 (GET, GET /{date}, POST, DELETE)

### Phase 2 (필요시)
- Work Schedule API 2개 (우선순위 낮음, 프론트에서 로컬 스토리지로 대체 가능)

---

## 📝 변경 프로세스

1. **API 변경 필요 시**:
   - 이 문서 업데이트
   - `frontend/src/types.ts` 업데이트
   - `gemvis/api.py::FileRecord` Pydantic 모델과 TypeScript `FileRecord` interface가 1:1로 일치하는지 확인

2. **백엔드 구현**:
   - `gemvis/api.py`에 엔드포인트 추가
   - Pydantic 모델 정의
   - FastAPI 자동 문서 확인 (`http://localhost:8000/docs`)

3. **프론트 연동**:
   - `frontend/src/api.ts`에 함수 추가
   - 타입 체크 통과 확인

---

## 🔍 확인 방법

### 백엔드 자동 문서
```bash
cd ~/gemvis
source .venv/bin/activate
python run.py

# 브라우저에서 http://localhost:8000/docs 열기
# FastAPI가 자동 생성한 Swagger UI 확인
```

### 타입 체크
```bash
cd frontend
npm run type-check  # 또는 tsc --noEmit
```

---

**Last Updated**: 2026-05-17  
**Status**: v2 Unified FileRecord API 완성, v1 deprecated 유지
