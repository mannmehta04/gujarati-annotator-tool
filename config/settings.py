# config/settings.py
"""
Central configuration.
All paths, labels, and environment-driven settings live here.
Import this everywhere instead of hardcoding anything.
"""

import os
import tempfile
from pathlib import Path

# ── Directories ───────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent.parent  # project root
OUTPUT_DIR = SCRIPT_DIR / "annotations"

# dataset/ is the canonical location for source videos and downloads
DATASET_DIR = SCRIPT_DIR / "dataset"
VIDEO_DIR   = DATASET_DIR   # alias — all code can use either name

# ── Labels ────────────────────────────────────────────────────
LABELS = ["Shant", "Hasya", "Bhayanak", "Karuna", "Rudra"]

# ── Server ────────────────────────────────────────────────────
PORT = int(os.environ.get("PORT", 7860))
HOST = os.environ.get("HOST", "0.0.0.0")

# ── Temp dirs ─────────────────────────────────────────────────
TEMP_VIDEO_DIR    = Path(tempfile.gettempdir()) / "video_annotator"
PREVIEW_CACHE_DIR = Path(tempfile.gettempdir()) / "video_annotator_preview"

# ── Creating directories ─────────────────────────────────────
def makeDir():
    """Create all required directories on startup."""
    DATASET_DIR.mkdir(parents=True, exist_ok=True)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(OUTPUT_DIR, 0o777)

    for label in LABELS:
        (OUTPUT_DIR / label / "audio").mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / label / "video").mkdir(parents=True, exist_ok=True)

    TEMP_VIDEO_DIR.mkdir(exist_ok=True)
    PREVIEW_CACHE_DIR.mkdir(exist_ok=True)

    print(f"SCRIPT_DIR    : {SCRIPT_DIR}")
    print(f"DATASET_DIR   : {DATASET_DIR}")
    print(f"VIDEO_DIR     : {VIDEO_DIR}")
    print(f"OUTPUT_DIR    : {OUTPUT_DIR}")
    print(f"PORT          : {PORT}")

