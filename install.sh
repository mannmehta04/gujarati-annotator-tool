#!/bin/bash
# ================================================================
# VIDEO ANNOTATOR — ONE-SHOT INSTALLER
# Works on: Ubuntu / Debian / Mac (with brew)
# Run once on any new machine:
#   bash install.sh
# ================================================================

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

ok()   { echo -e "${GREEN}✅  $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️   $1${NC}"; }
fail() { echo -e "${RED}❌  $1${NC}"; exit 1; }
info() { echo -e "${BLUE}→   $1${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "================================================================"
echo "   🎬  VIDEO ANNOTATOR — INSTALLER"
echo "================================================================"
echo ""

# ── Detect OS ─────────────────────────────────────────────────
OS="unknown"
if   [[ "$OSTYPE" == "linux-gnu"* ]]; then OS="linux"
elif [[ "$OSTYPE" == "darwin"*    ]]; then OS="mac"
else warn "Unrecognised OS: $OSTYPE — proceeding anyway"; fi
info "OS detected: $OS"

# ── Step 1: Python 3.10+ ──────────────────────────────────────
echo ""
echo "[1/6] Checking Python..."
if ! command -v python3 &>/dev/null; then
    warn "Python3 not found — installing..."
    if   [[ "$OS" == "linux" ]]; then sudo apt-get update -q && sudo apt-get install -y python3 python3-pip
    elif [[ "$OS" == "mac"   ]]; then brew install python3
    else fail "Install Python 3.10+ manually from https://python.org"; fi
fi

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)

if [[ "$PY_MAJOR" -lt 3 || ("$PY_MAJOR" -eq 3 && "$PY_MINOR" -lt 10) ]]; then
    fail "Python 3.10+ required, found $PY_VER"
fi
ok "Python $PY_VER"

# ── Step 2: pip ───────────────────────────────────────────────
echo ""
echo "[2/6] Checking pip..."
if ! python3 -m pip --version &>/dev/null; then
    warn "pip missing — installing..."
    curl -sS https://bootstrap.pypa.io/get-pip.py | python3
fi
ok "pip ready"

# ── Step 3: ffmpeg ────────────────────────────────────────────
echo ""
echo "[3/6] Checking ffmpeg..."
if ! command -v ffmpeg &>/dev/null; then
    warn "ffmpeg not found — installing..."
    if   [[ "$OS" == "linux" ]]; then sudo apt-get install -y ffmpeg
    elif [[ "$OS" == "mac"   ]]; then brew install ffmpeg
    else
        fail "Install ffmpeg manually:
  Ubuntu/Debian : sudo apt install ffmpeg
  Mac           : brew install ffmpeg
  Windows       : https://ffmpeg.org/download.html"
    fi
fi
FFMPEG_VER=$(ffmpeg -version 2>&1 | head -1 | awk '{print $3}')
ok "ffmpeg $FFMPEG_VER"

# ── Step 4: tmux ──────────────────────────────────────────────
echo ""
echo "[4/6] Checking tmux..."
if ! command -v tmux &>/dev/null; then
    warn "tmux not found — installing..."
    if   [[ "$OS" == "linux" ]]; then sudo apt-get install -y tmux
    elif [[ "$OS" == "mac"   ]]; then brew install tmux
    else warn "tmux unavailable — server will run in foreground only"; fi
fi
command -v tmux &>/dev/null && ok "tmux ready" || warn "tmux not available (optional)"

# ── Step 5: Python packages ───────────────────────────────────
echo ""
echo "[5/6] Installing Python packages..."
python3 -m pip install --upgrade pip -q

# Try normal install first; fall back to --break-system-packages for PEP-668 envs
if ! python3 -m pip install -r requirements.txt -q 2>/dev/null; then
    warn "Retrying with --break-system-packages (PEP-668 environment)..."
    python3 -m pip install --break-system-packages -r requirements.txt -q
fi

python3 -c "import gradio; print(f'  gradio  {gradio.__version__}')"
python3 -c "import pandas; print(f'  pandas  {pandas.__version__}')"
ok "Python packages installed"

# ── Step 6: Create output directories ─────────────────────────
echo ""
echo "[6/6] Creating output directories..."
python3 -c "
import sys; sys.path.insert(0, '.')
from config.settings import bootstrap
bootstrap()
print('  directories ready')
"
ok "Output directories created"

# ── Locate videos ─────────────────────────────────────────────
echo ""
echo "── Locating videos ──"
python3 -c "
import sys; sys.path.insert(0, '.')
from config.settings import VIDEO_DIR
videos = list(VIDEO_DIR.glob('*.mp4'))
if videos:
    print(f'  Found {len(videos)} video(s) in {VIDEO_DIR}')
    for v in videos[:5]: print(f'    {v.name}')
else:
    print(f'  ⚠️  No .mp4 files found in {VIDEO_DIR}')
    print(f'  Place your videos there, or set: VIDEO_DIR=/path/to/videos bash run.sh')
"

# ── Done ──────────────────────────────────────────────────────
echo ""
echo "================================================================"
ok "INSTALLATION COMPLETE"
echo "================================================================"
echo ""
echo "  To start the server:"
echo "    bash run.sh"
echo ""
echo "  With custom video folder:"
echo "    VIDEO_DIR=/path/to/videos bash run.sh"
echo ""
echo "  Then open: http://localhost:7860"
echo ""
