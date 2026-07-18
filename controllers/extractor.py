# controllers/extractor.py
"""
Business logic layer.
All ffmpeg calls, file extraction, preview cache.
No Gradio imports. No UI logic.

Supports both local file paths and HTTP(S) stream URLs as video sources.
"""

import re
import subprocess
import shutil
import time
import logging
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(ch)

from config.settings import (
    LABELS,
    TEMP_VIDEO_DIR, PREVIEW_CACHE_DIR
)



# ── Helpers ────────────────────────────────────────────────────

def _sanitize_stem(stem: str) -> str:
    """
    Strip any UUID prefix Gradio may have injected (e.g. '7b5b305f-').
    Remove characters that cause ffmpeg 'Invalid argument' on Linux.
    """
    # Strip UUID prefix like "7b5b305f-" at start
    stem = re.sub(r'^[0-9a-f]{8}-', '', stem)
    # Remove illegal filename characters
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f\s]', '_', stem)
    # Truncate to stay under filesystem limits
    stem = stem[:60]
    # Ensure it doesn't start with a dash (confuses ffmpeg arg parsing)
    stem = stem.lstrip('-') or 'clip'
    return stem


def _is_url(source: str) -> bool:
    """Return True if source looks like an HTTP/HTTPS URL."""
    try:
        parsed = urlparse(source)
        return parsed.scheme in ('http', 'https') and bool(parsed.netloc)
    except Exception:
        return False


def _url_stem(url: str) -> str:
    """
    Derive a clean filename stem from a URL for use in output filenames.
    Uses the URL path's last segment, sanitized.
    """
    try:
        path_part = urlparse(url).path.rstrip('/')
        stem = Path(path_part).stem or 'stream'
    except Exception:
        stem = 'stream'
    return _sanitize_stem(stem) or 'stream'


# ── Video loading ──────────────────────────────────────────────

def load_video(path_str: str):
    """
    Validate path, copy to temp dir for clean Gradio serving.
    Returns: (temp_path, status_md, start, end, duration_str, result)
    """
    path_str = path_str.strip() if path_str else ""

    if not path_str:
        return None, "⚠️ Enter a video path above", 0, 10, "10.0s", ""

    src = Path(path_str)

    if not src.exists():
        return None, f"❌ File not found: `{path_str}`", 0, 10, "10.0s", ""

    if src.suffix.lower() != ".mp4":
        return None, f"❌ Not an mp4 file: `{path_str}`", 0, 10, "10.0s", ""

    tmp = TEMP_VIDEO_DIR / src.name
    try:
        shutil.copy2(src, tmp)
    except Exception as e:
        return None, f"❌ Could not copy: {e}", 0, 10, "10.0s", ""

    return (
        str(tmp),
        f"✅ Loaded: **{src.name}**  \n`{path_str}`",
        0, 10,
        "10.0s (00:00 → 00:10)",
        ""
    )



# ── Segment extraction ─────────────────────────────────────────

def _generate_annotation_id(video_name, label: str) -> str:
    """
    Generates a unique annotation ID.
    Format: {video_name}_{label}_{YYYYMMDD}_{HHMMSS}_{microseconds}

    video_name is sanitized — spaces become underscores,
    special characters are removed.

    Defensive: if video_name is a dict, list, or non-string type,
    falls back to 'segment' rather than producing a broken ID.
    """
    import re
    from datetime import datetime

    # Defensive type check — if not a plain string, use fallback
    if not isinstance(video_name, str):
        # Log warning so developer can trace the source
        import logging
        logging.getLogger('natak.extractor').warning(
            f"_generate_annotation_id non-string video_name: "
            f"type={type(video_name)!r}, repr={repr(video_name)[:100]}"
        )
        video_name = 'segment'
    else:
        video_name = video_name.strip()

    _INVALID = {
        '', '[object object]', 'undefined', 'null', 'none', '{}', '[]'
    }
    if video_name.lower() in _INVALID:
        video_name = 'segment'

    # Replace spaces with underscores, remove non-alphanumeric/underscore chars
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', video_name)
    sanitized = re.sub(r'_+', '_', sanitized)   # Collapse multiple underscores
    sanitized = sanitized.strip('_')

    if not sanitized:
        sanitized = 'segment'

    # Sanitize label
    if not isinstance(label, str):
        label = str(label) if label is not None else 'unknown'
    label_clean = re.sub(r'[^a-zA-Z0-9_]', '', label.strip())
    if not label_clean:
        label_clean = 'unknown'

    # Generate timestamp component
    now = datetime.now()
    timestamp_part = now.strftime('%Y%m%d_%H%M%S')
    micro_part = str(now.microsecond)

    return f"{sanitized}_{label_clean}_{timestamp_part}_{micro_part}"


def extract_segment(
    video_path_input: str,
    start,
    end,
    video_name_input: str,
    label: str,
    notes: str,
):
    """
    Records annotation metadata in Supabase.
    
    NO file extraction happens here.
    NO local files are written.
    NO CSV is written.
    
    ffmpeg extraction happens on demand when user requests
    preview or download in the browser.
    
    Returns:
        (annotation_dict: dict | None, error: str | None)
    """
    from controllers.supabase_sync import (
        insert_annotation,
        annotation_object_to_supabase_dict,
    )
    from datetime import datetime
    import logging
    
    _logger = logging.getLogger('natak.extractor')
    
    # Validate video_name — mandatory, hardened
    if video_name_input is None:
        video_name = ''
    elif not isinstance(video_name_input, str):
        _logger.warning(
            f"extract_segment: video_name non-string: "
            f"type={type(video_name_input)}, val={repr(video_name_input)[:80]}"
        )
        video_name = ''
    else:
        video_name = video_name_input.strip()
    
    _INVALID_NAMES = {
        '', '[object object]', 'undefined', 'null', 'none', '{}', '[]'
    }
    if video_name.lower() in _INVALID_NAMES:
        video_name = ''

    if not video_name:
        return None, (
            "Video Name is required. "
            "Enter a short name for the source video before extracting."
        )
    
    # Validate source_video (video_path_input)
    source_video = video_path_input
    if not source_video or not str(source_video).strip():
        return None, "Source video is required."
    
    # If Gradio passed a temp copy (UUID-prefixed), resolve back to source
    path_str = str(source_video).strip()
    source_is_url = _is_url(path_str)

    if not source_is_url:
        tmp_str = str(TEMP_VIDEO_DIR)
        if path_str.startswith(tmp_str):
            tmp_name   = Path(path_str).name
            clean_name = re.sub(r'^[0-9a-f]{8}-', '', tmp_name)
            from config.settings import VIDEO_DIR
            candidates = (
                list(VIDEO_DIR.glob(f"*{clean_name}")) +
                list(VIDEO_DIR.parent.glob(f"*{clean_name}"))
            )
            if candidates:
                path_str = str(candidates[0])
            source_video = path_str
    
    # Validate timing
    try:
        start_f = float(start)
        end_f   = float(end)
    except (ValueError, TypeError):
        return None, "Start time and end time must be valid numbers."
    
    if end_f <= start_f:
        return None, "End time must be greater than start time."
    
    duration = round(end_f - start_f, 3)
    
    # Validate label
    if not label or not str(label).strip():
        return None, "Emotion label is required."
    
    # Generate annotation ID
    annotation_id = _generate_annotation_id(video_name, str(label))
    
    # Build metadata dict
    annotation_dict = {
        'id':           annotation_id,
        'source_video': str(source_video).strip(),
        'start_time':   start_f,
        'end_time':     end_f,
        'duration':     duration,
        'label':        str(label).strip(),
        'notes':        str(notes).strip() if notes else '',
        'audio_file':   '',   # extracted on demand — not stored
        'video_file':   '',   # extracted on demand — not stored
        'timestamp':    datetime.now().isoformat(),
    }
    
    # Insert into Supabase
    supabase_dict = annotation_object_to_supabase_dict(annotation_dict)
    success, error = insert_annotation(supabase_dict)
    
    if not success:
        return None, f"Supabase insert failed: {error}"
    
    _logger.info(f"Annotation recorded: {annotation_id}")
    return annotation_dict, None


# ── Preview cache ──────────────────────────────────────────────

def get_preview_copy(source_video_path: str) -> str | None:
    """
    Re-mux video with faststart for glitch-free browser streaming.
    Caches result so re-mux only happens once per file.
    """
    if not source_video_path:
        return None
    src = Path(source_video_path)
    if not src.exists():
        return None

    mtime      = int(src.stat().st_mtime)
    cache_name = f"preview_{abs(hash(str(src)))}_{mtime}.mp4"
    cached     = PREVIEW_CACHE_DIR / cache_name

    if cached.exists() and cached.stat().st_size > 0:
        return str(cached)

    result = subprocess.run(
        ["ffmpeg", "-nostdin", "-y", "-i", str(src),
         "-c", "copy", "-movflags", "+faststart",
         str(cached)],
        capture_output=True, text=True, timeout=30
    )

    return str(cached) if (
        result.returncode == 0
        and cached.exists()
        and cached.stat().st_size > 0
    ) else str(src)


# ── Utilities ──────────────────────────────────────────────────

def scan_videos() -> list[str]:
    from config.settings import VIDEO_DIR
    if not VIDEO_DIR.exists():
        return []
    return sorted(str(p) for p in VIDEO_DIR.glob("*.mp4"))


def scan_folder(folder_path: str) -> list[str]:
    """
    Scan a local directory (non-recursively) for video files.
    Returns a sorted list of filenames (not full paths).
    """
    VIDEO_EXTS = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv'}
    folder = Path(folder_path)
    if not folder.exists() or not folder.is_dir():
        return []
    files = sorted(
        f.name for f in folder.iterdir()
        if f.is_file() and f.suffix.lower() in VIDEO_EXTS
    )
    return files


def format_time(seconds) -> str:
    if seconds is None or seconds < 0:
        return "00:00"
    return f"{int(seconds//60):02d}:{int(seconds%60):02d}"
