# controllers/downloader.py
"""
Business logic layer — video downloading.
Uses yt-dlp to download videos from URLs (YouTube, etc.)
directly into dataset/.

No Gradio imports. No UI logic.
"""

import re
import subprocess
import shutil
from pathlib import Path
from typing import Generator

from config.settings import DATASET_DIR


# ── Helpers ────────────────────────────────────────────────────

def _sanitize_filename(name: str) -> str:
    """
    Remove characters unsafe for filenames.
    Keeps spaces as underscores. Truncates to 80 chars.
    """
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', name)
    name = re.sub(r'\s+', '_', name.strip())
    name = name[:80]
    name = name.strip('._') or 'video'
    return name


def check_ytdlp() -> bool:
    """Return True if yt-dlp is available on PATH or importable."""
    return shutil.which("yt-dlp") is not None


# ── Downloader ─────────────────────────────────────────────────

def download_video(url: str) -> Generator[str, None, None]:
    """
    Download a video from `url` using yt-dlp into DATASET_DIR.

    Yields status strings (one per yt-dlp output line) for real-time
    display in the UI log box.

    Final yield is a special sentinel dict (stringified) that the handler
    unpacks to get (final_status, saved_path | None).

    Usage:
        for line in download_video(url):
            if line.startswith("__RESULT__:"):
                status, path = parse_result(line)
            else:
                show_in_log(line)
    """
    url = (url or "").strip()

    if not url:
        yield "__RESULT__:error:No URL provided"
        return

    if not check_ytdlp():
        yield "__RESULT__:error:yt-dlp not found. Run: pip install yt-dlp"
        return

    if not DATASET_DIR.exists():
        DATASET_DIR.mkdir(parents=True, exist_ok=True)

    # Output template — yt-dlp will set the final name
    # We use a temp pattern first, then detect what was saved
    output_template = str(DATASET_DIR / "%(title).80s.%(ext)s")

    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--merge-output-format", "mp4",
        "--newline",                     # one progress line per line
        "--progress",
        "-o", output_template,
        url,
    ]

    yield f"⬇️  Starting download: {url}\n"
    yield f"📁 Saving to: {DATASET_DIR}\n"
    yield "─" * 50 + "\n"

    saved_path = None
    error_lines = []

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        for line in proc.stdout:
            line = line.rstrip()
            if not line:
                continue

            # Detect the final merged/destination file
            if "[Merger]" in line and "Merging formats into" in line:
                # e.g. [Merger] Merging formats into "path/to/file.mp4"
                m = re.search(r'"(.+?\.mp4)"', line)
                if m:
                    saved_path = m.group(1)

            # Also catch the [download] Destination line for direct mp4
            if "[download] Destination:" in line:
                candidate = line.split("Destination:")[-1].strip()
                if candidate.endswith(".mp4"):
                    saved_path = candidate

            # Catch already-downloaded
            if "[download]" in line and "has already been downloaded" in line:
                m = re.search(r'\[download\]\s+(.+?)\s+has already', line)
                if m:
                    saved_path = m.group(1).strip()

            yield line + "\n"

            if "ERROR" in line:
                error_lines.append(line)

        proc.wait()

        if proc.returncode != 0:
            err = "\n".join(error_lines) or "Unknown error"
            yield f"\n❌ yt-dlp exited with code {proc.returncode}\n"
            yield f"__RESULT__:error:{err}"
            return

        # If we didn't catch the path from output, scan for newest mp4
        if not saved_path or not Path(saved_path).exists():
            mp4s = sorted(
                DATASET_DIR.glob("*.mp4"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            if mp4s:
                saved_path = str(mp4s[0])

        if saved_path and Path(saved_path).exists():
            size_mb = Path(saved_path).stat().st_size / (1024 * 1024)
            fname   = Path(saved_path).name
            yield f"\n✅ Download complete!\n"
            yield f"📄 File : {fname}\n"
            yield f"📦 Size : {size_mb:.1f} MB\n"
            yield f"__RESULT__:ok:{saved_path}"
        else:
            yield "\n⚠️  Download finished but output file not found.\n"
            yield "__RESULT__:error:Output file not found after download"

    except FileNotFoundError:
        yield "❌ yt-dlp not found on PATH.\n"
        yield "   Install with: pip install yt-dlp\n"
        yield "__RESULT__:error:yt-dlp not installed"
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        yield f"❌ Unexpected error: {e}\n{tb}\n"
        yield f"__RESULT__:error:{e}"
