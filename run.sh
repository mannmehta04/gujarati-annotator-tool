#!/bin/bash
# ================================================================
# VIDEO ANNOTATOR — LAUNCHER
# Usage:
#   bash run.sh                          # default port 7860
#   bash run.sh /path/to/videos          # custom video folder
#   PORT=8080 bash run.sh                # custom port
#   NO_TMUX=1 bash run.sh                # run in foreground
#   VIDEO_DIR=/data/videos bash run.sh   # custom video dir
# ================================================================

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

ok()   { echo -e "${GREEN}✅  $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️   $1${NC}"; }
fail() { echo -e "${RED}❌  $1${NC}"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT="${PORT:-7860}"
HOST="${HOST:-0.0.0.0}"

echo "Starting Video Annotator..."

# Optional: custom video folder as first argument
if [[ -n "${1:-}" ]]; then
    export VIDEO_DIR="$1"
    ok "VIDEO_DIR = $VIDEO_DIR"
fi

# Sanity checks
command -v python3 &>/dev/null || fail "Python3 not found. Run: bash install.sh"
command -v ffmpeg  &>/dev/null || fail "ffmpeg not found.  Run: bash install.sh"
python3 -c "import gradio, pandas" 2>/dev/null \
    || fail "Packages missing. Run: bash install.sh"

# Kill anything already on the port
fuser -k "${PORT}/tcp" 2>/dev/null || true
sleep 1

# Launch
if command -v tmux &>/dev/null && [[ "${NO_TMUX:-0}" != "1" ]]; then
    tmux kill-session -t annotator 2>/dev/null || true
    sleep 1
    tmux new-session -d -s annotator \
        "cd '$SCRIPT_DIR' && PORT=$PORT HOST=$HOST python3 app.py 2>&1 | tee ~/annotator.log"

    echo "Waiting for server to start..."
    for i in $(seq 1 15); do
        sleep 2
        if curl -s "http://localhost:$PORT" > /dev/null 2>&1; then
            echo ""
            ok "SERVER IS UP"
            echo ""
            echo "   🌐  http://localhost:$PORT"
            echo "   📋  Logs   : tmux attach -t annotator"
            echo "   🔇  Detach : Ctrl+B then D"
            echo "   🛑  Stop   : tmux kill-session -t annotator"
            echo ""
            exit 0
        fi
        echo "   waiting... ($((i*2))s)"
    done

    echo ""
    fail "Server did not start in 30s. Check: tail -40 ~/annotator.log"
else
    warn "Running in foreground (Ctrl+C to stop)"
    echo ""
    PORT=$PORT HOST=$HOST python3 app.py
fi
