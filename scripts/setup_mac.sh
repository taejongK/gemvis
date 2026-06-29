#!/usr/bin/env bash
# Gemvis 원클릭 설치 — cross-platform (Linux/macOS/Windows Git Bash)
#
# Usage:
#   ./scripts/setup_mac.sh                  # 전체 설치 (deps + llama.cpp + frontend)
#   ./scripts/setup_mac.sh --no-frontend    # 프론트 빌드 스킵
#   ./scripts/setup_mac.sh --no-llama       # llama.cpp 설치 스킵 (이미 있음)
#   ./scripts/setup_mac.sh --build-llama    # third_party에 직접 빌드 (Linux/Mac)
#   ./scripts/setup_mac.sh --gpu cuda       # CUDA 빌드 (--build-llama 와 함께)
#   ./scripts/setup_mac.sh --gpu metal      # Metal (Apple Silicon)
#   ./scripts/setup_mac.sh --gpu vulkan     # Vulkan

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
cd "$ROOT"

# ----------- OS 감지 -----------
case "$(uname -s)" in
    Linux*)               PLATFORM=linux ;;
    Darwin*)              PLATFORM=macos ;;
    MINGW*|MSYS*|CYGWIN*) PLATFORM=windows ;;
    *) echo "지원하지 않는 OS: $(uname -s)"; exit 1 ;;
esac

# ----------- 옵션 파싱 -----------
INSTALL_FRONTEND=1
INSTALL_LLAMA=1
BUILD_LLAMA=0
GPU_BACKEND="cpu"

while [ $# -gt 0 ]; do
    case "$1" in
        --no-frontend) INSTALL_FRONTEND=0; shift ;;
        --no-llama)    INSTALL_LLAMA=0; shift ;;
        --build-llama) BUILD_LLAMA=1; shift ;;
        --gpu)         GPU_BACKEND="$2"; shift 2 ;;
        -h|--help)     grep '^#' "$0" | head -15; exit 0 ;;
        *) echo "알 수 없는 옵션: $1"; exit 1 ;;
    esac
done

# ----------- 유틸 -----------
step() { echo ""; echo "━━━ $* ━━━"; }
ok()   { echo "   ✅ $*"; }
warn() { echo "   ⚠️  $*"; }
fail() { echo ""; echo "   ❌ $*"; echo ""; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

# ----------- Pre-check: Git -----------
if ! have git; then
    echo ""
    echo "❌ Git not found. Install:"
    case "$PLATFORM" in
        macos)   echo "   brew install git" ;;
        linux)   echo "   sudo apt install git  (Debian/Ubuntu)" ;;
        windows) echo "   winget install --id Git.Git --source winget" ;;
    esac
    fail "Git 설치 후 재실행"
fi
ok "git detected: $(command -v git)"

# Python 버전 선택 (3.11 우선, rdflib/pyparsing 호환성)
if have python3.11; then
    PYTHON=python3.11
    ok "Python 3.11 감지 (권장)"
elif have python3.12; then
    PYTHON=python3.12
    warn "Python 3.12 사용 (3.11 권장)"
elif have python3; then
    PYTHON=python3
    PY_VER=$("$PYTHON" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
    if [[ "$PY_VER" == "3.13" ]] || [[ "$PY_VER" == "3.14" ]]; then
        warn "Python $PY_VER 감지 — rdflib와 호환성 문제 가능성"
        warn "Python 3.11 설치 권장:"
        case "$PLATFORM" in
            macos) warn "   brew install python@3.11" ;;
            linux) warn "   sudo apt install python3.11" ;;
        esac
    fi
else
    PYTHON=python
fi

if ! have "$PYTHON"; then
    echo ""
    echo "❌ Python not found. Install:"
    case "$PLATFORM" in
        macos)   echo "   brew install python@3.11" ;;
        linux)   echo "   sudo apt install python3.11" ;;
        windows) echo "   winget install --id Python.Python.3.11 --source winget" ;;
    esac
    fail "Python 설치 후 재실행"
fi

echo "Gemvis setup 시작 (platform=$PLATFORM, python=$PYTHON)"

# ----------- 1. .env 생성 -----------
step "1/4  .env 생성"
if [ ! -f .env ]; then
    cat > .env <<EOF
# Gemvis 환경 변수 — setup.sh 자동 생성
LLM_BASE_URL=http://127.0.0.1:8080/v1
LLM_API_KEY=none
LLM_MODEL=unsloth/gemma-4-E2B-it-GGUF:Q4_K_M

# 감시 폴더 (기본: ~/gemvis_watch)
GEMVIS_WATCH_DIR=$HOME/gemvis_watch

# 그래프/임베딩 저장 (기본: ~/.gemvis/)
# GEMVIS_GRAPH_PATH=$HOME/.gemvis/graph.ttl
# GEMVIS_EMBEDDINGS_PATH=$HOME/.gemvis/embeddings.npz
EOF
    ok ".env 생성"
else
    ok ".env 이미 존재 (스킵)"
fi
mkdir -p "$HOME/gemvis_watch"
ok "감시 폴더 준비: $HOME/gemvis_watch"

# ----------- 2. Python venv + deps -----------
step "2/4  Python venv + 의존성"
if [ ! -d venv ]; then
    "$PYTHON" -m venv venv
    ok "venv 생성"
else
    ok "venv 존재"
fi

case "$PLATFORM" in
    windows) source venv/Scripts/activate ;;
    *)       source venv/bin/activate ;;
esac

python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt
ok "백엔드 의존성 설치 완료"

# ----------- 3. llama.cpp -----------
step "3/4  llama.cpp 설치"
if [ "$INSTALL_LLAMA" -eq 0 ]; then
    ok "--no-llama 옵션 (스킵)"
elif have llama-server; then
    ok "llama-server 이미 설치됨: $(command -v llama-server)"
elif [ "$BUILD_LLAMA" -eq 1 ]; then
    have git || fail "git 없음"
    have cmake || fail "cmake 없음"
    LLAMA_DIR="third_party/llama.cpp"
    if [ ! -d "$LLAMA_DIR/.git" ]; then
        git clone --depth 1 https://github.com/ggerganov/llama.cpp.git "$LLAMA_DIR"
    fi
    CMAKE_FLAGS=()
    case "$GPU_BACKEND" in
        cuda)   CMAKE_FLAGS=(-DGGML_CUDA=ON) ;;
        metal)  CMAKE_FLAGS=(-DGGML_METAL=ON) ;;
        vulkan) CMAKE_FLAGS=(-DGGML_VULKAN=ON) ;;
    esac
    cmake -S "$LLAMA_DIR" -B "$LLAMA_DIR/build" -DCMAKE_BUILD_TYPE=Release "${CMAKE_FLAGS[@]:-}"
    cmake --build "$LLAMA_DIR/build" --config Release -j --target llama-cli llama-server
    ok "llama.cpp 빌드 완료: $LLAMA_DIR/build/bin/"
    warn "PATH 등록 필요: export PATH=\"$ROOT/$LLAMA_DIR/build/bin:\$PATH\""
else
    case "$PLATFORM" in
        windows)
            echo "   winget install llama.cpp 시도..."
            cmd //c "winget install llama.cpp --accept-source-agreements --accept-package-agreements" 2>&1 || true
            if have llama-server; then
                ok "llama.cpp 설치 완료"
            else
                warn "자동 설치 안 됨. 새 PowerShell 열어 PATH 적용 후 재실행"
                warn "또는 ./scripts/setup_mac.sh --build-llama 로 직접 빌드"
            fi
            ;;
        macos)
            have brew || fail "brew 없음. https://brew.sh"
            brew install llama.cpp
            ok "llama.cpp 설치 (brew)"
            ;;
        linux)
            warn "Linux는 패키지 미지원. --build-llama 옵션으로 빌드하세요"
            ;;
    esac
fi

# ----------- 4. Frontend -----------
if [ "$INSTALL_FRONTEND" -eq 1 ]; then
    step "4/4  Frontend 빌드"
    if ! have npm; then
        warn "npm 없음. Node.js LTS 설치 중..."
        case "$PLATFORM" in
            macos)
                if have brew; then
                    brew install node 2>&1 | grep -v "Pouring"
                    ok "Node.js 설치 완료 (brew)"
                else
                    warn "Homebrew 없음. Node.js 수동 설치 필요: https://nodejs.org/"
                fi
                ;;
            linux)
                if have apt-get; then
                    warn "Node.js 설치 명령: sudo apt install nodejs npm"
                else
                    warn "Node.js 수동 설치 필요: https://nodejs.org/ 또는 nvm"
                fi
                ;;
            windows)
                warn "winget install --id OpenJS.NodeJS.LTS --source winget"
                ;;
        esac
    fi

    if have npm; then
        ( cd frontend && npm install --silent && npm run build )
        ok "frontend/dist/ 빌드 완료"
    else
        warn "프론트 빌드 스킵 (백엔드만 동작 가능)"
    fi
else
    step "4/4  Frontend (스킵)"
fi

cat <<EOF

═══════════════════════════════════════════════════
🎉  Gemvis 셋업 완료
═══════════════════════════════════════════════════

다음 단계:
  ./scripts/start_mac.sh

첫 실행 시 Gemma 4 모델 (~2GB)이 자동 다운로드됩니다.
EOF
