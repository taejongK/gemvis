# Environment Variables

Gemvis configuration via `.env` file. Copy `.env.example` to `.env` and customize.

```bash
cp .env.example .env
```

---

## Table of Contents

- [Required Variables](#required-variables)
- [Optional Variables](#optional-variables)
- [Advanced Configuration](#advanced-configuration)
- [Examples by Platform](#examples-by-platform)

---

## Required Variables

### `LLM_BASE_URL`

**Type**: URL  
**Required**: Yes  
**Default**: `http://127.0.0.1:8080/v1`

OpenAI-compatible LLM endpoint (local only — see [Privacy Rules](.claude/rules/privacy.md)).

**Valid values**:
- `http://127.0.0.1:8080/v1` — llama.cpp / llama-server (default)
- `http://192.168.1.100:8080/v1` — LAN server
- `http://[::1]:8080/v1` — IPv6 localhost

**Invalid values** (violates privacy-first principle):
- ❌ `https://api.openai.com/v1`
- ❌ `https://api.anthropic.com/v1`
- ❌ `https://generativelanguage.googleapis.com/v1beta`

### `LLM_API_KEY`

**Type**: String  
**Required**: Yes (but can be dummy)  
**Default**: `none`

API key for the LLM endpoint. Most local servers (llama.cpp) don't require authentication, so `none` works.

**Examples**:
- `none` — No authentication (local servers)
- `sk-xxx` — If using a local server with authentication

### `LLM_MODEL`

**Type**: String  
**Required**: Yes  
**Default**: `unsloth/gemma-4-E2B-it-GGUF:Q4_K_M`

Model identifier. For llama.cpp with `-hf` flag, this is the Hugging Face repo + optional filename.

**Examples**:
- `unsloth/gemma-4-E2B-it-GGUF:Q4_K_M` — Default (2 GB, 4-bit quantized)
- `google/gemma-4-E2B-it` — Full precision (requires more VRAM)
- `bartowski/gemma-4-27B-GGUF:Q4_K_M` — Larger model (27B parameters)

---

## Optional Variables

### `GEMVIS_WATCH_DIR`

**Type**: Absolute path  
**Required**: No  
**Default**: `~/gemvis_watch`

Folder(s) to watch for file changes. Can be a single path or comma-separated list.

**Examples**:
```env
# Single folder
GEMVIS_WATCH_DIR=/Users/andy/Documents

# Multiple folders (comma-separated, no spaces)
GEMVIS_WATCH_DIR=/Users/andy/Documents,/Users/andy/Downloads,/Users/andy/Desktop

# Windows
GEMVIS_WATCH_DIR=C:\Users\Andy\Documents

# WSL2 (Windows path via UNC)
GEMVIS_WATCH_DIR=/mnt/c/Users/Andy/Documents
```

**Note**: The settings UI overrides this — user-selected folders are stored in `~/.gemvis/preferences.json`.

### `GEMVIS_GRAPH_PATH`

**Type**: Absolute path  
**Required**: No  
**Default**: `~/.gemvis/graph.ttl`

Path to the knowledge graph file (RDF/Turtle format).

**Example**:
```env
GEMVIS_GRAPH_PATH=/custom/path/to/graph.ttl
```

### `GEMVIS_EMBEDDINGS_PATH`

**Type**: Absolute path  
**Required**: No  
**Default**: `~/.gemvis/embeddings.npz`

Path to the embeddings vector store (NumPy archive).

**Example**:
```env
GEMVIS_EMBEDDINGS_PATH=/custom/path/to/embeddings.npz
```

### `GOOGLE_API_KEY`

**Type**: String  
**Required**: No  
**Default**: (unset)

⚠️ **Privacy warning**: Using Google Gemini API violates the privacy-first principle. This variable exists for legacy compatibility only.

**Recommended**: Leave this unset and use local models only.

---

## Advanced Configuration

### `LLAMA_PORT`

**Type**: Integer  
**Required**: No  
**Default**: `8080`

Port for llama-server. Only used by `scripts/start_mac.sh` / `scripts/start_windows.ps1`.

**Example**:
```env
LLAMA_PORT=8081
```

### `BACKEND_PORT`

**Type**: Integer  
**Required**: No  
**Default**: `8000`

Port for the FastAPI backend. Only used by startup scripts.

**Example**:
```env
BACKEND_PORT=8001
```

---

## Examples by Platform

### Windows (llama.cpp)

```env
LLM_BASE_URL=http://127.0.0.1:8080/v1
LLM_API_KEY=none
LLM_MODEL=unsloth/gemma-4-E2B-it-GGUF:Q4_K_M

GEMVIS_WATCH_DIR=C:\Users\Andy\Documents
```

### macOS / Linux (llama.cpp)

```env
LLM_BASE_URL=http://127.0.0.1:8080/v1
LLM_API_KEY=none
LLM_MODEL=unsloth/gemma-4-E2B-it-GGUF:Q4_K_M

GEMVIS_WATCH_DIR=/Users/andy/Documents
```

### WSL2 (llama.cpp)

```env
LLM_BASE_URL=http://127.0.0.1:8080/v1
LLM_API_KEY=none
LLM_MODEL=unsloth/gemma-4-E2B-it-GGUF:Q4_K_M

# Windows path via /mnt/c/
GEMVIS_WATCH_DIR=/mnt/c/Users/Andy/Documents
```

### LAN Server (Remote llama.cpp)

```env
LLM_BASE_URL=http://192.168.1.100:8080/v1
LLM_API_KEY=none
LLM_MODEL=unsloth/gemma-4-E2B-it-GGUF:Q4_K_M

GEMVIS_WATCH_DIR=/Users/andy/Documents
```

---

## Environment Variable Reference Table

<!-- AUTO-GENERATED: .env.example -->

| Variable | Required | Default | Description | Example |
|----------|----------|---------|-------------|---------|
| `LLM_BASE_URL` | Yes | `http://127.0.0.1:8080/v1` | OpenAI-compatible LLM endpoint (local only) | `http://127.0.0.1:8080/v1` |
| `LLM_API_KEY` | Yes | `none` | API key (or `none` for local servers) | `none`, `sk-xxx` |
| `LLM_MODEL` | Yes | `unsloth/gemma-4-E2B-it-GGUF:Q4_K_M` | Model identifier | `unsloth/gemma-4-E2B-it-GGUF:Q4_K_M` |
| `GEMVIS_WATCH_DIR` | No | `~/gemvis_watch` | Folder(s) to watch (comma-separated) | `/Users/andy/Documents` |
| `GEMVIS_GRAPH_PATH` | No | `~/.gemvis/graph.ttl` | Knowledge graph file path | `~/.gemvis/graph.ttl` |
| `GEMVIS_EMBEDDINGS_PATH` | No | `~/.gemvis/embeddings.npz` | Embeddings vector store path | `~/.gemvis/embeddings.npz` |
| `GOOGLE_API_KEY` | No | (unset) | ⚠️ Google Gemini API key (privacy violation — not recommended) | (leave unset) |

<!-- END AUTO-GENERATED -->

---

## Validation

The backend validates environment variables on startup:

```python
# gemvis/config.py
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://127.0.0.1:8080/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "none")
LLM_MODEL = os.getenv("LLM_MODEL", "unsloth/gemma-4-E2B-it-GGUF:Q4_K_M")
```

**Startup checks**:
- ✅ `LLM_BASE_URL` points to `127.0.0.1`, `localhost`, or LAN IP
- ❌ External API URLs trigger privacy rule violation warning
- ✅ Watch directory exists and is readable
- ❌ Non-existent watch directory → auto-create

---

## Troubleshooting

### "Connection refused" error

**Symptom**: `ConnectionRefusedError: [Errno 61] Connection refused`

**Fix**: Ensure llama-server is running:

```bash
# Check if llama-server is running
curl -sf http://127.0.0.1:8080/v1/models

# If not, start it
llama-server -hf unsloth/gemma-4-E2B-it-GGUF:Q4_K_M -ngl 999 --host 0.0.0.0 --port 8080
```

### "Model not found" error

**Symptom**: `404 Model not found: unsloth/gemma-4-E2B-it-GGUF:Q4_K_M`

**Fix**: Ensure llama-server loaded the model:

```bash
# Check llama-server logs
tail -f .gemvis/llama-server.log

# Look for:
#   Downloading model...
#   Model loaded successfully
```

### Watch directory not detected

**Symptom**: Files added to watch directory aren't processed

**Fix**:
1. Check settings UI — user-selected folders override `.env`
2. Verify watcher is running: **Settings** → **Start Watching**
3. Check backend logs:
   ```bash
   tail -f .gemvis/backend.log | grep "File watcher"
   ```

---

## Privacy Considerations

**NEVER use external API endpoints** — all data processing must happen on-device.

**Allowed**:
- ✅ `127.0.0.1`, `localhost`, `::1` (loopback)
- ✅ `192.168.x.x`, `10.x.x.x`, `172.16.x.x` (LAN)

**Blocked**:
- ❌ `api.openai.com`
- ❌ `api.anthropic.com`
- ❌ `generativelanguage.googleapis.com`

See [.claude/rules/privacy.md](.claude/rules/privacy.md) for full details.

---

## Related Documentation

- [CONTRIBUTING.md](CONTRIBUTING.md) — Development setup
- [API_CONTRACT.md](../API_CONTRACT.md) — Backend API reference
- [ARCHITECTURE_V2.md](ARCHITECTURE_V2.md) — System architecture

---

**Last updated**: 2026-05-14
