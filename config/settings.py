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
# dataset/ is the canonical location for source videos and downloads
DATASET_DIR = SCRIPT_DIR / "dataset"
VIDEO_DIR   = DATASET_DIR   # alias — all code can use either name

# ── Labels ────────────────────────────────────────────────────
LABELS = ["Shant", "Hasya", "Bhayanak", "Karuna", "Rudra"]

# ── Server ────────────────────────────────────────────────────
PORT = int(os.environ.get("PORT", 7860))
HOST = os.environ.get("HOST", "0.0.0.0")

# ── Supabase ──────────────────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://ppowvdipoyqgkjmisind.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBwb3d2ZGlwb3lxZ2tqbWlzaW5kIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODQyOTk1NDAsImV4cCI6MjA5OTg3NTU0MH0.NhrD0NDeGmfSrvTjrE52WCbzX8_0k-og8m458f9gKUc")
SUPABASE_TABLE = "annotations"
SUPABASE_CONFIGURED = bool(SUPABASE_URL and SUPABASE_KEY)

# ── Temp dirs ─────────────────────────────────────────────────
TEMP_VIDEO_DIR    = Path(tempfile.gettempdir()) / "video_annotator"
PREVIEW_CACHE_DIR = Path(tempfile.gettempdir()) / "video_annotator_preview"

# ── Creating directories ─────────────────────────────────────
def makeDir():
    """Create all required directories on startup."""
    DATASET_DIR.mkdir(parents=True, exist_ok=True)

    TEMP_VIDEO_DIR.mkdir(exist_ok=True)
    PREVIEW_CACHE_DIR.mkdir(exist_ok=True)

    print(f"SCRIPT_DIR    : {SCRIPT_DIR}")
    print(f"DATASET_DIR   : {DATASET_DIR}")
    print(f"VIDEO_DIR     : {VIDEO_DIR}")
    print(f"PORT          : {PORT}")

