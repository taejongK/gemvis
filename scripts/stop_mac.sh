#!/usr/bin/env bash
# Gemvis 전체 종료 스크립트

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
cd "$ROOT"

echo "🛑 Gemvis 종료 중..."

# PID 파일로 종료
killed=0
for pidfile in .gemvis/backend.pid .gemvis/llama-server.pid; do
    if [ -f "$pidfile" ]; then
        pid=$(cat "$pidfile")
        if kill "$pid" 2>/dev/null; then
            echo "   ✓ 프로세스 종료: PID $pid"
            killed=$((killed + 1))
        fi
        rm -f "$pidfile"
    fi
done

# 포트로 찾아서 종료 (PID 파일이 없는 경우 대비)
for port in 8000 8080; do
    pid=$(lsof -ti:$port 2>/dev/null || true)
    if [ -n "$pid" ]; then
        kill "$pid" 2>/dev/null || true
        echo "   ✓ 포트 $port 프로세스 종료"
        killed=$((killed + 1))
    fi
done

# Python 멀티프로세싱 워커도 정리
pkill -f "multiprocessing.spawn" 2>/dev/null || true

if [ $killed -eq 0 ]; then
    echo "   (이미 종료되어 있습니다)"
else
    echo "✅ Gemvis 종료 완료"
fi
