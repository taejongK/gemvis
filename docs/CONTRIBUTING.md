# Contributing to Gemvis

**Gemvis** = **Gem**ma + Jar**vis** + Vi**sion** — Privacy-first on-device personal knowledge graph assistant

Thank you for your interest in contributing! This guide covers everything from environment setup to PR submission.

---

## Table of Contents

- [Development Environment Setup](#development-environment-setup)
- [Available Scripts](#available-scripts)
- [Testing Procedures](#testing-procedures)
- [Code Style](#code-style)
- [PR Submission Checklist](#pr-submission-checklist)
- [Architecture Overview](#architecture-overview)

---

## Development Environment Setup

### Prerequisites

| Tool | Required Version | Notes |
|------|------------------|-------|
| **Python** | 3.11 | **Strongly recommended** — 3.13/3.14 have pyparsing issues |
| **Node.js** | 18+ | For frontend development |
| **npm** | 9+ | Comes with Node.js |
| **Git** | Any recent | Version control |
| **LLM Server** | llama.cpp | Local inference (optional — setup script installs llama.cpp automatically) |

### Quick Start

#### Windows

1. **Double-click setup**:
   ```cmd
   scripts\setup_windows.bat
   ```
   Or PowerShell:
   ```powershell
   .\scripts\setup_windows.ps1
   ```

2. **Run**:
   ```cmd
   scripts\start_windows.bat
   ```
   Or PowerShell:
   ```powershell
   .\scripts\start_windows.ps1
   ```

#### macOS / Linux / WSL

1. **Setup**:
   ```bash
   ./scripts/setup_mac.sh
   ```

2. **Run**:
   ```bash
   ./scripts/start_mac.sh
   ```

Your browser will open at `http://localhost:8000`.

### Manual Setup

#### 1. Clone the repository

```bash
git clone <repository-url>
cd gemvis
```

#### 2. Environment variables

```bash
cp .env.example .env
```

Edit `.env` to configure your local LLM endpoint. See [docs/ENV.md](ENV.md) for details.

#### 3. Backend dependencies

```bash
# Create virtual environment with Python 3.11
python3.11 -m venv venv

# Activate (macOS/Linux/WSL)
source venv/bin/activate

# Activate (Windows)
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

First run downloads the sentence-transformer model (~120 MB) to `~/.cache/huggingface/hub/`.

#### 4. Frontend build

```bash
cd frontend
npm install
npm run build
cd ..
```

#### 5. Run backend

```bash
python run.py
```

Open `http://localhost:8000`.

### Development Mode (Hot Reload)

For frontend development with hot reload:

```bash
# Terminal 1: Backend
python run.py

# Terminal 2: Frontend dev server
cd frontend
npm run dev
```

Open `http://localhost:5173` — API calls are proxied to `:8000` automatically.

---

## Available Scripts

<!-- AUTO-GENERATED: package.json scripts -->

### Frontend (`frontend/package.json`)

| Command | Description |
|---------|-------------|
| `npm run dev` | Start Vite development server with hot reload (port 5173) |
| `npm run build` | Production build with TypeScript compilation (`tsc -b && vite build`) |
| `npm run lint` | Run ESLint on all files |
| `npm run preview` | Preview production build locally |

### Backend / Setup Scripts

| Script | Purpose | Platform |
|--------|---------|----------|
| `./scripts/setup_mac.sh` | One-click install (deps + llama.cpp + frontend build) | macOS / Linux / WSL |
| `./scripts/setup_windows.bat` | One-click install | Windows (double-click) |
| `./scripts/setup_windows.ps1` | One-click install | Windows (PowerShell) |
| `./scripts/start_mac.sh` | Start llama-server + backend + open browser | macOS / Linux / WSL |
| `./scripts/start_windows.bat` | Start llama-server + backend + open browser | Windows (double-click) |
| `./scripts/start_windows.ps1` | Start llama-server + backend + open browser | Windows (PowerShell) |
| `./scripts/stop_mac.sh` | Kill all Gemvis processes | macOS / Linux / WSL |
| `python run.py` | Start FastAPI backend directly | All platforms |

<!-- END AUTO-GENERATED -->

---

## Testing Procedures

### Running Tests

```bash
# Backend tests (when available)
pytest tests/ -v

# Frontend tests
cd frontend
npm test
```

### Writing Tests

- **Test-Driven Development (TDD)** is encouraged
- Write tests **before** implementation:
  1. **RED**: Write a failing test
  2. **GREEN**: Write minimal code to pass
  3. **IMPROVE**: Refactor while keeping tests green

### Coverage Requirements

- Aim for **80%+ test coverage** on new code
- Critical paths (file analysis, search, graph operations) require tests

### Manual Testing

See [docs/QA_MANUAL_CHECKLIST.md](QA_MANUAL_CHECKLIST.md) for the full manual QA checklist before releases/demos.

---

## Code Style

### Python (Backend)

- **Formatter**: `black` (auto-applied on commit)
- **Type checker**: `mypy`
- **Style**: PEP 8 compliant
- **Naming**:
  - Functions/variables: `snake_case`
  - Classes: `PascalCase`
  - Constants: `UPPER_SNAKE_CASE`

```bash
# Format all Python files
black gemvis/

# Type check
mypy gemvis/
```

### TypeScript/JavaScript (Frontend)

- **Formatter**: `prettier` (auto-applied on commit)
- **Linter**: ESLint (config in `frontend/eslint.config.js`)
- **Naming**:
  - Components: `PascalCase` (`GraphView.tsx`)
  - Hooks: `camelCase` with `use` prefix (`useGraphQuery`)
  - Functions/variables: `camelCase`
  - Constants: `UPPER_SNAKE_CASE`

```bash
cd frontend

# Lint
npm run lint

# Format
npx prettier --write src/
```

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>: <description>

[optional body]
```

**Types**: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`

**Examples**:
```
feat: add hybrid SPARQL + embedding search
fix: resolve pyparsing race condition in Python 3.13
refactor: extract GemInsight dataclass from insight.py
docs: update ENV.md with GEMVIS_WATCH_DIR description
```

---

## PR Submission Checklist

Before submitting a pull request:

- [ ] **Tests pass**: `pytest tests/ -v` (backend), `npm test` (frontend)
- [ ] **Type checks pass**: `mypy gemvis/` (backend), `tsc -b` (frontend)
- [ ] **Code formatted**: `black gemvis/` (backend), `prettier --write frontend/src/` (frontend)
- [ ] **Linter clean**: `npm run lint` (frontend)
- [ ] **Privacy check**: No external API calls (see [.claude/rules/privacy.md](.claude/rules/privacy.md))
  - ❌ No `anthropic`, `openai.com`, `googleapis` calls
  - ✅ `openai` SDK allowed **only with local `base_url`** (llama-server)
- [ ] **MVP scope**: Feature is within MVP scope (see [docs/mvp_roadmap.md](mvp_roadmap.md))
- [ ] **Commit message**: Follows conventional commits format
- [ ] **Documentation**: Update docs if API/behavior changes
- [ ] **Branch up-to-date**: Rebased on latest `main`

### PR Description Template

```markdown
## Summary
<!-- What does this PR do? -->

## Changes
<!-- List of files/components changed -->

## Testing
<!-- How was this tested? -->

## Screenshots (if UI change)
<!-- Add before/after screenshots -->

## Related Issues
<!-- Link to issues this PR closes/addresses -->
```

---

## Architecture Overview

Quick reference — see [docs/ARCHITECTURE_V2.md](ARCHITECTURE_V2.md) for full details.

### Backend Core Files

```
gemvis/
├── api.py                # FastAPI endpoints + lifecycle (embedding warmup)
├── config.py             # Config (LLM endpoint, watch dirs, graph/embedding paths)
├── insight.py            # GemInsight dataclass + Gemma 4 tool calling
├── llm_client.py         # OpenAI-compatible LLM client wrapper
├── knowledge_graph.py    # rdflib-based KG + SPARQL query engine (TTL/RDF)
├── embeddings.py         # Local sentence-transformer embeddings store
├── watcher.py            # Filesystem watching (watchdog) + 2-stage hydration
└── search.py             # Hybrid search (LLM intent + KG + embedding re-rank)
```

### Frontend Core Files

```
frontend/src/
├── App.tsx               # Routing + sidebar + global shortcuts
├── Spotlight.tsx         # Ctrl+K overlay search UI
├── api.ts                # API client (v2 FileRecord unified)
├── types.ts              # Shared types (mirrors backend Pydantic)
└── pages/
    ├── Dashboard.tsx     # Stats + paginated file list with 4-state badges
    ├── GraphView.tsx     # Force-directed KG viewer with focus highlight
    ├── Search.tsx        # Conversational chat search UI
    └── Settings.tsx      # Config + watcher control + work schedule
```

### Key Concepts

**GemInsight** (Source of Truth):
- Dataclass defined in `gemvis/insight.py`
- Generated by Gemma 4 for each file
- Fields: `title`, `summary`, `categories`, `tags`, `entities`, `language`, `quality`, `date`, `sentiment`, `is_work`, `is_personal`, `status`
- Stored in RDF/Turtle (`~/.gemvis/graph.ttl`)

**4-State Machine**:
- **queued** → **processing** → **completed** / **failed**
- UI badges reflect current state
- Retry available for failed files

**Hybrid Search**:
1. **SPARQL** (structural/exact) — "files mentioning Alice", "tag:meeting"
2. **Embeddings** (semantic) — "happy photos", typos/synonyms
3. **LLM** (intent parsing + answer generation)

---

## Troubleshooting

### Common Issues

#### Python 3.13 / 3.14: `pyparsing.exceptions.ParseException`

**Symptom**: `Expected SelectQuery, found 'ORDER'`

**Fix**: Use Python 3.11

```bash
brew install python@3.11  # macOS
rm -rf venv
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### Port already in use

```bash
# Check what's holding port 8000
lsof -ti:8000

# Kill all Gemvis processes
./scripts/stop_mac.sh

# Verify ports are free
lsof -ti:8000 || echo "port 8000 free"
lsof -ti:8080 || echo "port 8080 free"
```

#### LLM server not responding

```bash
# Check llama-server logs
tail -f .gemvis/llama-server.log

# Manually start llama-server (if needed)
llama-server -hf unsloth/gemma-4-E2B-it-GGUF:Q4_K_M -ngl 999 --host 0.0.0.0 --port 8080
```

#### Frontend not updating after rebuild

```bash
# Hard refresh in browser
Ctrl+Shift+R (Windows/Linux)
Cmd+Shift+R (macOS)

# Or rebuild
cd frontend
npm run build
```

### Log Monitoring

**Always tail logs when debugging**:

```bash
# Backend (errors, API calls, file processing)
tail -f .gemvis/backend.log

# llama-server (model downloads, inference errors)
tail -f .gemvis/llama-server.log

# Both at once
tail -f .gemvis/backend.log .gemvis/llama-server.log
```

**What to look for**:
- `ERROR:` / `Traceback` — Python exceptions
- `500 Internal Server Error` — API failures
- `pyparsing.exceptions.ParseException` — SPARQL parser multithread race (use Python 3.11)
- `Loaded graph with N nodes, M edges` — graph loaded successfully
- `File watcher auto-started` — watcher online

---

## Additional Resources

- **Architecture**: [docs/ARCHITECTURE_V2.md](ARCHITECTURE_V2.md)
- **API Contract**: [API_CONTRACT.md](../API_CONTRACT.md)
- **Environment Variables**: [docs/ENV.md](ENV.md)
- **QA Checklist**: [docs/QA_MANUAL_CHECKLIST.md](QA_MANUAL_CHECKLIST.md)
- **MVP Roadmap**: [docs/mvp_roadmap.md](mvp_roadmap.md)
- **Hackathon Strategy**: [docs/hackathon_strategy.md](hackathon_strategy.md)

---

## Questions?

- **Project direction**: See [docs/gemvis_team_direction.md](gemvis_team_direction.md)
- **Technical issues**: Check [docs/README.md](README.md) for full docs tree
- **Feature requests**: Open an issue with `[Feature Request]` prefix

---

**Happy hacking! 🚀**

*Last updated: 2026-05-14*
