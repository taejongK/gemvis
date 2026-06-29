#!/usr/bin/env bash
# Gemvis 원클릭 실행 — llama-server + 백엔드 + 브라우저 오픈
#
# Usage:
#   ./scripts/start_mac.sh
#   ./scripts/start_mac.sh --no-browser   # 브라우저 자동 오픈 안 함

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
cd "$ROOT"

# ----------- OS 감지 -----------
case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*) PLATFORM=windows; OPENER="cmd //c start" ;;
    Darwin*)              PLATFORM=macos;   OPENER="open" ;;
    Linux*)               PLATFORM=linux;   OPENER="xdg-open" ;;
esac

OPEN_BROWSER=1
[ "${1:-}" = "--no-browser" ] && OPEN_BROWSER=0

# ----------- .env 로드 -----------
if [ -f .env ]; then
    set -a; source .env; set +a
fi

LLAMA_PORT="${LLAMA_PORT:-8080}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
LLM_MODEL="${LLM_MODEL:-unsloth/gemma-4-E2B-it-GGUF:Q4_K_M}"

mkdir -p .gemvis

# ----------- 종료 시 자식 프로세스 정리 -----------
LLAMA_PID=""
BACKEND_PID=""
cleanup() {
    echo ""
    echo "🛑 종료 처리"
    [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null || true
    [ -n "$LLAMA_PID" ]   && kill "$LLAMA_PID"   2>/dev/null || true
}
trap cleanup EXIT INT TERM

# ----------- 1. llama-server -----------
if curl -sf "http://127.0.0.1:${LLAMA_PORT}/v1/models" >/dev/null 2>&1; then
    echo "[1/3] llama-server 이미 실행 중 (port $LLAMA_PORT)"
else
    if ! command -v llama-server >/dev/null 2>&1; then
        echo "❌ llama-server 명령 없음. ./scripts/setup_mac.sh 먼저 실행"
        echo "   (Windows라면 새 PowerShell 열어서 PATH 적용 확인)"
        exit 1
    fi
    echo "[1/3] llama-server 기동 (모델 첫 다운로드 시 ~2GB)"
    # Vision 지원: HF 캐시에서 mmproj 파일 찾아 명시적으로 로드
    # (-hf만으로는 자동 로드가 동작하지 않는 케이스가 있어 명시 지정)
    MMPROJ_FILE=$(find ~/.cache/huggingface/hub -name "mmproj*.gguf" 2>/dev/null | head -1)
    MMPROJ_ARG=""
    if [ -n "$MMPROJ_FILE" ] && [ -f "$MMPROJ_FILE" ]; then
        echo "      Vision mmproj 사용: $MMPROJ_FILE"
        MMPROJ_ARG="--mmproj $MMPROJ_FILE"
    else
        echo "      ⚠ mmproj 파일을 찾지 못함 — 첫 실행 시 -hf가 자동 다운로드"
    fi
    llama-server -hf "$LLM_MODEL" -ngl 999 \
        $MMPROJ_ARG \
        --host 127.0.0.1 --port "$LLAMA_PORT" \
        --ctx-size 128000 \
        > .gemvis/llama-server.log 2>&1 &
    LLAMA_PID=$!
    echo $LLAMA_PID > .gemvis/llama-server.pid

    echo "      준비 대기 (최대 120초, 모델 다운로드 포함)..."
    for i in $(seq 1 120); do
        if curl -sf "http://127.0.0.1:${LLAMA_PORT}/v1/models" >/dev/null 2>&1; then
            echo "      OK (${i}s)"
            break
        fi
        if ! kill -0 $LLAMA_PID 2>/dev/null; then
            echo "❌ llama-server 비정상 종료. 로그: tail .gemvis/llama-server.log"
            exit 1
        fi
        sleep 1
    done
fi

# ----------- 2. 백엔드 -----------
case "$PLATFORM" in
    windows) source venv/Scripts/activate ;;
    *)       source venv/bin/activate ;;
esac

echo "[2/3] 백엔드 기동 (port $BACKEND_PORT)"
python run.py > .gemvis/backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > .gemvis/backend.pid

echo "      준비 대기..."
for i in $(seq 1 30); do
    if curl -sf "http://127.0.0.1:${BACKEND_PORT}/" >/dev/null 2>&1; then
        echo "      OK (${i}s)"
        break
    fi
    if ! kill -0 $BACKEND_PID 2>/dev/null; then
        echo "❌ 백엔드 비정상 종료. 로그: tail .gemvis/backend.log"
        exit 1
    fi
    sleep 1
done

# ----------- 3. 브라우저 -----------
URL="http://localhost:${BACKEND_PORT}"
if [ "$OPEN_BROWSER" -eq 1 ]; then
    echo "[3/3] 브라우저 열기: $URL"
    $OPENER "$URL" >/dev/null 2>&1 || true
else
    echo "[3/3] 브라우저 자동 오픈 스킵 ($URL)"
fi

cat <<EOF

═══════════════════════════════════════════════════
🚀  Gemvis 실행 중
═══════════════════════════════════════════════════
   접속:        $URL
   종료:        Ctrl+C 또는 ./scripts/stop_mac.sh
   백엔드 로그: tail -f .gemvis/backend.log
   LLM 로그:    tail -f .gemvis/llama-server.log

EOF

# 백엔드가 종료될 때까지 대기 (Ctrl+C 시 trap이 정리)
# wait는 시그널을 받으면 즉시 종료되도록 함
while kill -0 $BACKEND_PID 2>/dev/null; do
    sleep 1
done
