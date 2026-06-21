# config/settings.py
"""
Central configuration.
All paths, labels, and environment-driven settings live here.
Import this everywhere instead of hardcoding anything.
"""

import os
from pathlib import Path

# ── Directories ───────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent.parent  # rasa_pipeline/
OUTPUT_DIR = SCRIPT_DIR / "annotations"

def resolve_video_dir() -> Path:
    if "VIDEO_DIR" in os.environ:
        p = Path(os.environ["VIDEO_DIR"])
        if p.exists():
            return p

    candidates = [
        SCRIPT_DIR / "videos",
        SCRIPT_DIR.parent / "videos",
        SCRIPT_DIR.parent / "dataset" / "video",
        SCRIPT_DIR.parent / "video",
        Path.home() / "videos",
        Path.home() / "Videos",
    ]
    for c in candidates:
        if c.exists() and list(c.glob("*.mp4")):
            return c

    found = list(Path.home().rglob("*.mp4"))
    if found:
        return found[0].parent

    fallback = SCRIPT_DIR / "videos"
    fallback.mkdir(exist_ok=True)
    return fallback

VIDEO_DIR = resolve_video_dir()

# ── Labels ────────────────────────────────────────────────────
LABELS = ["Shant", "Hasya", "Bhayanak", "Karuna", "Rudra"]

# ── Server ────────────────────────────────────────────────────
PORT = int(os.environ.get("PORT", 7860))
HOST = os.environ.get("HOST", "0.0.0.0")

# ── Temp dirs ─────────────────────────────────────────────────
import tempfile
TEMP_VIDEO_DIR    = Path(tempfile.gettempdir()) / "video_annotator"
PREVIEW_CACHE_DIR = Path(tempfile.gettempdir()) / "video_annotator_preview"

# ── Creating directories ─────────────────────────────────────
def makeDir():
    """Create all required directories on startup."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(OUTPUT_DIR, 0o777)

    for label in LABELS:
        (OUTPUT_DIR / label / "audio").mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / label / "video").mkdir(parents=True, exist_ok=True)

    TEMP_VIDEO_DIR.mkdir(exist_ok=True)
    PREVIEW_CACHE_DIR.mkdir(exist_ok=True)

    print(f"SCRIPT_DIR    : {SCRIPT_DIR}")
    print(f"VIDEO_DIR     : {VIDEO_DIR}")
    print(f"OUTPUT_DIR    : {OUTPUT_DIR}")
    print(f"PORT          : {PORT}")
