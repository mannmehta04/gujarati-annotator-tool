# controllers/extractor.py
"""
Business logic layer.
All ffmpeg calls, file extraction, preview cache.
No Gradio imports. No UI logic.
"""

import re
import subprocess
import shutil
import time
from pathlib import Path
from datetime import datetime

from config.settings import (
    OUTPUT_DIR, LABELS,
    TEMP_VIDEO_DIR, PREVIEW_CACHE_DIR
)
from models.annotation import save_row


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

def extract_segment(
    video_path_input: str,
    start,
    end,
    label: str,
    notes: str
):
    """
    Cut audio + video segment from source file using ffmpeg.
    Returns: (status_msg, audio_path, video_path)
    """
    try:
        # ── 1. Resolve input path ─────────────────────────────
        path_str = (video_path_input or "").strip()
        print(f"[extract] raw path   : {path_str!r}")

        # If Gradio passed a temp copy (UUID-prefixed), resolve back to source
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
                print(f"[extract] resolved   : {path_str!r}")
            else:
                # temp path still exists — use it, just sanitize stem later
                print(f"[extract] using temp as-is: {path_str!r}")

        if not path_str:
            return "❌ No video path entered", None, None

        video_file = Path(path_str)
        if not video_file.exists():
            return f"❌ File not found: {path_str}", None, None

        print(f"[extract] video      : {video_file.name}")

        # ── 2. Validate timestamps ────────────────────────────
        try:
            start_f = float(start) if start is not None else 0.0
            end_f   = float(end)   if end   is not None else 0.0
        except (TypeError, ValueError) as e:
            return f"❌ Invalid timestamps: {e}", None, None

        print(f"[extract] range      : {start_f}s → {end_f}s")

        if start_f < 0:
            return "❌ Start time cannot be negative", None, None
        if start_f >= end_f:
            return f"❌ Start ({start_f}s) must be before end ({end_f}s)", None, None
        if (end_f - start_f) < 0.5:
            return "❌ Segment too short — minimum 0.5 seconds", None, None
        if not label or label not in LABELS:
            return f"❌ Invalid label: '{label}'", None, None

        # ── 3. Build clean output paths ───────────────────────
        duration   = end_f - start_f
        ts         = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        clean_stem = _sanitize_stem(video_file.stem)
        output_id  = f"{clean_stem}_{label}_{ts}"

        print(f"[extract] clean_stem : {clean_stem!r}")
        print(f"[extract] output_id  : {output_id!r}")

        audio_out = OUTPUT_DIR / label / "audio" / f"{output_id}.wav"
        video_out = OUTPUT_DIR / label / "video" / f"{output_id}.mp4"

        print(f"[extract] audio_out  : {audio_out}")
        print(f"[extract] video_out  : {video_out}")

        # ── 4. Ensure output dirs exist and are writable ──────
        audio_out.parent.mkdir(parents=True, exist_ok=True)
        video_out.parent.mkdir(parents=True, exist_ok=True)

        for d in [audio_out.parent, video_out.parent]:
            probe = d / ".write_test"
            try:
                probe.write_text("ok")
                probe.unlink()
            except Exception as e:
                return f"❌ Output dir not writable: {d}\n{e}", None, None

        time.sleep(0.01)

        # ── 5. Extract audio ──────────────────────────────────
        r_audio = subprocess.run(
            ["ffmpeg", "-nostdin", "-y",
             "-ss", str(start_f), "-t", str(duration),
             "-i", str(video_file),
             "-vn", "-acodec", "pcm_s16le",
             "-ar", "16000", "-ac", "1",
             str(audio_out)],
            capture_output=True, text=True, timeout=60
        )

        if r_audio.returncode != 0:
            err = r_audio.stderr[-400:].strip()
            print(f"[extract] audio FAIL:\n{err}")
            return f"❌ Audio extraction failed:\n{err}", None, None

        if not audio_out.exists() or audio_out.stat().st_size == 0:
            return "❌ Audio file empty after extraction", None, None

        audio_size = audio_out.stat().st_size
        print(f"[extract] audio OK   : {audio_size/1024:.1f} KB")

        # ── 6. Extract video ──────────────────────────────────
        r_video = subprocess.run(
            ["ffmpeg", "-nostdin", "-y",
             "-ss", str(start_f), "-t", str(duration),
             "-i", str(video_file),
             "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
             "-c:a", "aac", "-movflags", "+faststart",
             str(video_out)],
            capture_output=True, text=True, timeout=120
        )

        if r_video.returncode != 0:
            err = r_video.stderr[-400:].strip()
            print(f"[extract] video FAIL:\n{err}")
            return f"⚠️ Video failed (audio saved):\n{err}", str(audio_out), None

        if not video_out.exists() or video_out.stat().st_size == 0:
            return "⚠️ Video file empty (audio saved)", str(audio_out), None

        video_size = video_out.stat().st_size
        print(f"[extract] video OK   : {video_size/(1024*1024):.1f} MB")

        # ── 7. Save to CSV ────────────────────────────────────
        df = save_row({
            "id"          : output_id,
            "source_video": video_file.name,
            "start_time"  : start_f,
            "end_time"    : end_f,
            "duration"    : duration,
            "label"       : label,
            "notes"       : notes or "",
            "audio_file"  : str(audio_out.relative_to(OUTPUT_DIR)),
            "video_file"  : str(video_out.relative_to(OUTPUT_DIR)),
            "timestamp"   : datetime.now().isoformat()
        })
        print(f"[extract] CSV total  : {len(df)}")

        msg = (
            f"✅ **{label}** | {duration:.1f}s | "
            f"`{output_id[-40:]}`\n\n"
            f"🎵 {audio_size/1024:.1f} KB  |  "
            f"🎬 {video_size/(1024*1024):.1f} MB  |  "
            f"Total: {len(df)} clips"
        )
        return msg, str(audio_out), str(video_out)

    except subprocess.TimeoutExpired:
        return "❌ ffmpeg timed out — video may be too large", None, None
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"❌ {type(e).__name__}: {e}", None, None


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


def format_time(seconds) -> str:
    if seconds is None or seconds < 0:
        return "00:00"
    return f"{int(seconds//60):02d}:{int(seconds%60):02d}"
