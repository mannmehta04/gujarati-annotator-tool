# views/handlers.py
"""
Gradio event handlers.
Translates UI events into controller calls and formats
results back into Gradio component updates.
No business logic here. No ffmpeg. No CSV.
"""

import os
import logging
import gradio as gr
from pathlib import Path
import urllib.parse
import traceback
import yt_dlp
import concurrent.futures
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(ch)

from controllers.extractor import (
    load_video,
    extract_segment,
    get_preview_copy,
    format_time,
    scan_folder,
)

from models.annotation import get_stats


# ── Existing annotation handlers ───────────────────────────────

def on_load_video(path_str: str):
    return load_video(path_str)


def on_time_change(start, end):
    try:
        dur = float(end) - float(start)
        return (
            f"{dur:.1f}s ({format_time(start)} → {format_time(end)})"
            if dur >= 0 else "⚠️ Invalid range"
        )
    except Exception:
        return "Invalid"


def on_extract(video_source: str, start, end, video_name: str, label: str, notes: str, segments_data_state: dict = None):
    """
    Extract a segment from either a local path or a resolved stream URL.
    """
    # ── Video name validation ──────────────────────────────────────────
    if video_name is None:
        video_name = ''
    elif not isinstance(video_name, str):
        import logging
        logging.getLogger('natak.handlers').warning(
            f"on_extract: video_name non-string: "
            f"type={type(video_name)!r}, repr={repr(video_name)[:120]}"
        )
        video_name = ''
    else:
        video_name = video_name.strip()

    _INVALID_VIDEO_NAME_VALUES = {
        '', '[object object]', 'undefined', 'null', 'none', '{}', '[]'
    }
    if video_name.lower() in _INVALID_VIDEO_NAME_VALUES:
        video_name = ''

    if not video_name:
        # COUNT: 4 (outputs = [result_md, stats_md, cloud_sync_status_md, segments_data_state])
        return (
            "❌ **Video Name is required.**\n\n"
            "Please enter a short name for the source video "
            "in the **🏷️ Video Name** field before clicking Extract.\n\n"
            "**Example:** `lalyo_laptayo`, `v1`, `natak2`\n\n"
            "_Use letters, numbers, and underscores only._",
            get_stats(),
            gr.update(visible=False),
            segments_data_state,
        )
    # ── End video name validation ──────────────────────────────────────
    
    logger.info(f"on_extract called.")
    try:
        annotation_dict, error = extract_segment(
            video_source, start, end, video_name, label, notes
        )
        
        stats = get_stats()
        
        if error:
            return (
                f"❌ Extraction error: {error}",
                stats,
                gr.update(value=f"❌ Sync error: {error}", visible=True),
                segments_data_state,
            )
            
        # --- Build success message ---
        msg = (
            f"✅ **{label}** | {annotation_dict['duration']:.1f}s | "
            f"`{annotation_dict['id'][-40:]}`\n\n"
            f"Storage: Cloud sync"
        )
        sync_status = "☁️ Supabase sync initiated in background."
            
        full_message = f"{msg}\n\n{sync_status}"
        
        return (
            full_message,
            stats,
            gr.update(value=sync_status, visible=bool(sync_status)),
            segments_data_state,
        )
    except Exception as e:
        return (
            f"❌ Extraction error: {str(e)}",
            get_stats(),
            gr.update(value=f"❌ Sync error: {str(e)}", visible=True),
            segments_data_state,
        )


# ── Download tab handler ───────────────────────────────────────

_FETCH_PROGRESS_HTML = """
<div style="
    padding: 14px 18px;
    background: linear-gradient(135deg, #1a1a2e, #16213e);
    border-radius: 10px;
    border: 1px solid #2563eb;
    display: flex;
    align-items: center;
    gap: 14px;
">
    <div style="
        width: 22px;
        height: 22px;
        border: 3px solid #2563eb;
        border-top-color: transparent;
        border-radius: 50%;
        animation: fetchSpin 0.8s linear infinite;
        flex-shrink: 0;
    "></div>
    <div>
        <p style="margin:0; font-size:13px; color:#fff; font-weight:600;">
            Fetching video information...
        </p>
        <p style="margin:3px 0 0 0; font-size:11px; color:#7eb8f7;">
            Analyzing formats and validating download availability. 
            This may take 5–15 seconds.
        </p>
    </div>
</div>
<style>
@keyframes fetchSpin {
    to { transform: rotate(360deg); }
}
</style>
"""

def _get_codec(f: dict, codec_key: str) -> str:
    """Safely extracts codec value from format dict, normalizing None to empty string."""
    val = f.get(codec_key, 'none')
    return val if val else 'none'


def _build_video_info_html(
    title: str,
    thumbnail: str,
    uploader: str,
    duration,
    n_video_formats: int,
    n_audio_formats: int,
) -> str:
    """
    Builds the video information card HTML.
    Robust against missing thumbnail, uploader, duration.
    Always returns valid renderable HTML.
    """
    # Thumbnail section
    if thumbnail and thumbnail.strip():
        thumb_section = f"""
        <div style="flex-shrink:0;">
            <img
                src="{thumbnail}"
                alt="thumbnail"
                style="
                    width:180px; height:101px;
                    object-fit:cover; border-radius:6px;
                    display:block; background:#222;
                "
                onerror="this.parentElement.innerHTML='<div style=\\'width:180px;height:101px;background:#222;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:32px;\\'>🎬</div>'"
            />
        </div>
        """
    else:
        thumb_section = """
        <div style="
            flex-shrink:0; width:180px; height:101px;
            background:#222; border-radius:6px;
            display:flex; align-items:center;
            justify-content:center; font-size:32px;
        ">🎬</div>
        """
    
    # Duration
    if duration and int(duration) > 0:
        total = int(duration)
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        dur_str = f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
    else:
        dur_str = "Unknown duration"
    
    # Uploader
    uploader_str = uploader.strip() if uploader and uploader.strip() else "Unknown uploader"
    
    # Format summary
    total_formats = n_video_formats + n_audio_formats
    if total_formats == 0:
        format_badge = """
        <div style="
            display:inline-block; background:#3d1010;
            border-radius:20px; padding:3px 10px;
            font-size:11px; color:#ff7eb8;
        ">⚠️ No downloadable formats found</div>
        """
    else:
        parts = []
        if n_video_formats > 0:
            parts.append(f"{n_video_formats} video format{'s' if n_video_formats != 1 else ''}")
        if n_audio_formats > 0:
            parts.append(f"{n_audio_formats} audio format{'s' if n_audio_formats != 1 else ''}")
        format_badge = f"""
        <div style="
            display:inline-block; background:#0f3460;
            border-radius:20px; padding:3px 10px;
            font-size:11px; color:#7eb8f7;
        ">✅ {' · '.join(parts)} available</div>
        """
    
    return f"""
    <div style="
        display:flex; gap:16px; padding:14px;
        background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);
        border-radius:10px; border:1px solid #2d2d4e;
        align-items:flex-start; margin:4px 0;
    ">
        {thumb_section}
        <div style="flex:1; min-width:0; overflow:hidden;">
            <p style="
                margin:0 0 6px 0; font-size:15px;
                font-weight:700; color:#ffffff;
                line-height:1.3; word-break:break-word;
            ">{title}</p>
            <p style="margin:0 0 8px 0; font-size:12px; color:#8888aa;">
                📺 {uploader_str} &nbsp;·&nbsp; ⏱️ {dur_str}
            </p>
            {format_badge}
        </div>
    </div>
    """


def _build_format_choices(
    premuxed_formats: list,
    audio_formats: list,
) -> list:
    """
    Builds the format dropdown choices list from validated formats.
    All formats passed here are confirmed downloadable.
    """
    choices = ["⭐ Auto — Best Available Quality"]
    
    for f in premuxed_formats:
        label = _build_format_label(f)
        choices.append(label)
    
    if audio_formats:
        choices.append("─────── 🎵 Audio Only Formats ───────")
        for f in audio_formats:
            label = _build_format_label(f)
            choices.append(label)
    
    return choices


def _is_format_valid(f: dict) -> bool:
    """
    Determines whether a yt-dlp format entry represents a genuinely
    downloadable stream with real content.
    
    Exclusion criteria — exclude if ANY of these are true:
    1. Both filesize and filesize_approx are None or 0
       AND tbr (total bitrate) is None or 0
       — means the format has no size information at all,
         indicating it likely does not exist or is a manifest reference
    
    2. The format is a storyboard format
       — storyboards are thumbnail sprite sheets, not video
    
    3. The format extension is 'mhtml'
       — mhtml is used for storyboards, not downloadable video
    
    4. vcodec and acodec are both 'none'
       — format has neither video nor audio, unusable
    
    5. format_note contains 'storyboard'
       — explicitly marked as storyboard
    
    A format passes if it has at least one of:
    - filesize > 0
    - filesize_approx > 0  
    - tbr > 0 (total bitrate indicates real content)
    - abr > 0 (audio bitrate, for audio-only streams)
    - vbr > 0 (video bitrate, for video streams)
    """
    # Get all size/bitrate indicators
    filesize = f.get('filesize') or 0
    filesize_approx = f.get('filesize_approx') or 0
    tbr = f.get('tbr') or 0
    abr = f.get('abr') or 0
    vbr = f.get('vbr') or 0
    vcodec = f.get('vcodec', 'none') or 'none'
    acodec = f.get('acodec', 'none') or 'none'
    f_ext = f.get('ext', '') or ''
    format_note = f.get('format_note', '') or ''
    
    # Exclude storyboards and mhtml
    if f_ext == 'mhtml':
        return False
    if 'storyboard' in format_note.lower():
        return False
    if 'storyboard' in (f.get('format_id', '') or '').lower():
        return False
    
    # Exclude formats with no codec at all
    if vcodec == 'none' and acodec == 'none':
        return False
    
    # Must have at least one size or bitrate indicator > 0
    has_size = filesize > 0 or filesize_approx > 0
    has_bitrate = tbr > 0 or abr > 0 or vbr > 0
    
    if not has_size and not has_bitrate:
        return False
    
    return True


def _validate_formats_by_real_fetch(formats: list) -> list:
    """
    Validates formats by actually fetching the first bytes of each stream URL.
    
    A HEAD request returning 200 does NOT guarantee downloadability on YouTube.
    YouTube CDN commonly returns 200 on HEAD but 403 on GET.
    
    This function fetches the first 32KB of each stream URL using a GET request
    with Range: bytes=0-32767. If real video/audio bytes are returned
    (content-type is video/* or audio/*, and body size > 0), the format
    is confirmed downloadable. Otherwise it is excluded.
    
    Runs all checks in parallel with per-format timeout of 8 seconds
    and overall timeout of 20 seconds.
    
    Formats without a URL are excluded immediately.
    Network errors (not HTTP errors) include formats with benefit of the doubt.
    HTTP 403, 404, 410 are definitive failures — format excluded.
    """
    if not formats:
        return []
    
    def _fetch_first_bytes(f: dict) -> tuple:
        """
        Attempts to fetch first 32KB of the stream URL.
        Returns (format_dict, is_downloadable: bool, reason: str).
        """
        stream_url = f.get('url', '')
        
        # No URL — cannot validate, exclude
        if not stream_url or not stream_url.startswith('http'):
            return (f, False, 'no_url')
        
        try:
            req = urllib.request.Request(
                stream_url,
                method='GET',
                headers={
                    'User-Agent': (
                        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                        '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                    ),
                    # Request only first 32KB — enough to confirm stream works
                    # without downloading significant data
                    'Range': 'bytes=0-32767',
                    'Accept': '*/*',
                    'Accept-Encoding': 'identity',
                    'Referer': 'https://www.youtube.com/',
                    'Origin': 'https://www.youtube.com',
                }
            )
            
            with urllib.request.urlopen(req, timeout=8) as response:
                status = response.status
                content_type = response.headers.get('Content-Type', '')
                
                # Read first chunk — confirms bytes actually flow
                chunk = response.read(1024)
                
                # Must return actual bytes
                if len(chunk) == 0:
                    return (f, False, 'empty_response')
                
                # Status must be success
                if status not in (200, 206):
                    return (f, False, f'bad_status_{status}')
                
                # Content type should be video or audio
                # Also accept application/octet-stream (generic binary)
                ct_lower = content_type.lower()
                is_media = (
                    'video/' in ct_lower
                    or 'audio/' in ct_lower
                    or 'application/octet-stream' in ct_lower
                    or 'application/mp4' in ct_lower
                    or 'application/x-' in ct_lower
                )
                
                if not is_media:
                    # If content type is HTML or text, it's an error page
                    if 'text/html' in ct_lower or 'text/plain' in ct_lower:
                        return (f, False, 'error_page_response')
                
                # Bytes received, status OK — format is downloadable
                return (f, True, 'ok')
                
        except urllib.error.HTTPError as e:
            # Definitive HTTP failures — format not accessible
            if e.code in (403, 404, 410, 400):
                return (f, False, f'http_{e.code}')
            # Other HTTP errors — benefit of the doubt
            return (f, True, f'http_{e.code}_allowed')
            
        except urllib.error.URLError as e:
            # Network/connection error — benefit of the doubt
            # Could be temporary network issue, not a format problem
            return (f, True, 'network_error_allowed')
            
        except Exception as e:
            # Unknown error — benefit of the doubt
            return (f, True, 'unknown_error_allowed')
    
    # Run all validations in parallel
    max_workers = min(20, len(formats))
    validated = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_format = {
            executor.submit(_fetch_first_bytes, f): f
            for f in formats
        }
        
        try:
            for future in concurrent.futures.as_completed(
                future_to_format,
                timeout=20,
            ):
                try:
                    format_dict, is_downloadable, reason = future.result(timeout=9)
                    if is_downloadable:
                        validated.append(format_dict)
                except concurrent.futures.TimeoutError:
                    # Individual check timed out — include with benefit of the doubt
                    validated.append(future_to_format[future])
                except Exception:
                    validated.append(future_to_format[future])
        except concurrent.futures.TimeoutError:
            # Overall timeout — include remaining unchecked formats
            checked_formats = set(
                id(future_to_format[f]) 
                for f in future_to_format 
                if f.done()
            )
            for future, fmt in future_to_format.items():
                if not future.done():
                    validated.append(fmt)
    
    # Preserve original yt-dlp ordering
    original_order = {f.get('format_id', ''): i for i, f in enumerate(formats)}
    validated.sort(key=lambda f: original_order.get(f.get('format_id', ''), 999))
    
    return validated


def _build_format_label(f: dict) -> str:
    """
    Builds a visually structured, symbol-coded label for a format entry
    in the dropdown list.
    
    Uses Unicode symbols and consistent layout to help users identify:
    - Stream type (video+audio, video only, audio only)
    - Resolution/quality
    - File format/extension
    - Approximate file size
    - Codec information
    
    Works with standard Gradio dropdown (no HTML rendering required).
    """
    f_id = f.get('format_id', '?')
    f_ext = (f.get('ext', '') or '').upper()
    height = f.get('height')
    width = f.get('width')
    vcodec = (f.get('vcodec', 'none') or 'none')
    acodec = (f.get('acodec', 'none') or 'none')
    format_note = f.get('format_note', '') or ''
    tbr = f.get('tbr') or 0
    vbr = f.get('vbr') or 0
    abr = f.get('abr') or 0
    filesize = f.get('filesize') or f.get('filesize_approx') or 0
    fps = f.get('fps')
    
    has_video = vcodec != 'none' and bool(vcodec)
    has_audio = acodec != 'none' and bool(acodec)
    
    # --- Stream Type Icon ---
    # 🎬 = video + audio (pre-muxed, best for download)
    # 📹 = video only (requires merge, not offered)
    # 🎵 = audio only
    if has_video and has_audio:
        type_icon = "✅ 🎬"
        type_label = "Video+Audio"
    elif has_audio and not has_video:
        type_icon = "✅ 🎵"
        type_label = "Audio Only"
    else:
        type_icon = "✅ 📹"
        type_label = "Video Only"
    
    # --- Resolution ---
    if height:
        if height >= 2160:
            res_str = f"4K ({height}p)"
        elif height >= 1440:
            res_str = f"2K ({height}p)"
        elif height >= 1080:
            res_str = f"HD ({height}p)"
        elif height >= 720:
            res_str = f"HD ({height}p)"
        elif height >= 480:
            res_str = f"SD ({height}p)"
        elif height >= 360:
            res_str = f"SD ({height}p)"
        else:
            res_str = f"{height}p"
        if fps and fps > 30:
            res_str += f" {int(fps)}fps"
    elif format_note:
        res_str = format_note
    else:
        res_str = "Unknown res"
    
    # --- File Size ---
    if filesize > 0:
        if filesize >= 1024 * 1024 * 1024:
            size_str = f"{filesize / (1024**3):.1f} GB"
        elif filesize >= 1024 * 1024:
            size_str = f"{filesize / (1024**2):.0f} MB"
        elif filesize >= 1024:
            size_str = f"{filesize / 1024:.0f} KB"
        else:
            size_str = f"{filesize} B"
    elif tbr > 0:
        size_str = f"~{int(tbr)}kbps"
    elif abr > 0:
        size_str = f"~{int(abr)}kbps"
    else:
        size_str = "Size N/A"
    
    # --- Codec Summary ---
    # Abbreviate codec names for readability
    def abbrev_codec(codec: str) -> str:
        if not codec or codec == 'none':
            return ''
        codec_lower = codec.lower()
        if 'avc' in codec_lower or 'h264' in codec_lower or 'h.264' in codec_lower:
            return 'H.264'
        if 'hevc' in codec_lower or 'h265' in codec_lower or 'h.265' in codec_lower:
            return 'H.265'
        if 'vp9' in codec_lower:
            return 'VP9'
        if 'vp8' in codec_lower:
            return 'VP8'
        if 'av01' in codec_lower or 'av1' in codec_lower:
            return 'AV1'
        if 'mp4a' in codec_lower or 'aac' in codec_lower:
            return 'AAC'
        if 'opus' in codec_lower:
            return 'Opus'
        if 'mp3' in codec_lower:
            return 'MP3'
        if 'vorbis' in codec_lower:
            return 'Vorbis'
        # Return first part before dot for unknown codecs
        return codec.split('.')[0].upper()[:6]
    
    v_abbrev = abbrev_codec(vcodec) if has_video else ''
    a_abbrev = abbrev_codec(acodec) if has_audio else ''
    
    if v_abbrev and a_abbrev:
        codec_str = f"{v_abbrev}+{a_abbrev}"
    elif v_abbrev:
        codec_str = v_abbrev
    elif a_abbrev:
        codec_str = a_abbrev
    else:
        codec_str = ''
    
    # --- Assemble Label ---
    # Format: "🎬 HD (720p) · MP4 · 245 MB · H.264+AAC  [137]"
    # The format_id at the end in brackets allows parsing for download
    parts = [
        f"{type_icon} {type_label}",
        res_str,
        f_ext if f_ext else '?',
        size_str,
    ]
    if codec_str:
        parts.append(codec_str)
    
    label = "  ·  ".join(parts)
    label += f"  [{f_id}]"
    
    return label


def _parse_format_id_from_label(label: str) -> str:
    """
    Extracts the format_id from a formatted dropdown label.
    
    Labels follow the pattern: "... [format_id]" at the end.
    This function extracts the format_id from the trailing bracket.
    
    Returns 'auto' if label is the auto/separator entry.
    """
    if not label:
        return 'auto'
    
    # Auto option
    if label.startswith('⚙️') or 'Auto' in label or 'recommended' in label.lower():
        return 'auto'
    
    # Separator lines — not selectable as download
    if label.startswith('──') or label.startswith('—'):
        return 'auto'
    
    # Extract format_id from trailing [format_id]
    import re
    match = re.search(r'\[([^\[\]]+)\]$', label.strip())
    if match:
        return match.group(1)
    
    return 'auto'


def handle_fetch_video_info_with_progress(url: str):
    """
    Combined handler that shows progress then fetches video info.
    Uses Python generator (yield) to stream multiple UI updates
    from a single Gradio event — no .then() chain needed.
    """
    # --- First yield: Show progress, clear previous state ---
    yield (
        gr.update(value=_FETCH_PROGRESS_HTML, visible=True),  # fetch_progress
        gr.update(value="", visible=False),                    # fetch_status
        gr.update(value="", visible=False),                    # video_info_display
        gr.update(visible=False),                              # download_options_group
        gr.update(
            choices=["⭐ Auto — Best Available Quality"],
            value="⭐ Auto — Best Available Quality"
        ),
        gr.update(value="", visible=False),                    # download_link_html
    )
    
    # --- Validate URL ---
    if not url or not url.strip():
        yield (
            gr.update(visible=False),
            gr.update(value="⚠️ Please enter a URL first.", visible=True),
            gr.update(value="", visible=False),
            gr.update(visible=False),
            gr.update(
                choices=["⭐ Auto — Best Available Quality"],
                value="⭐ Auto — Best Available Quality"
            ),
            gr.update(value="", visible=False),
        )
        return
    
    # --- Fetch and process ---
    try:
        import yt_dlp
        
        ydl_opts = {
            'skip_download': True,
            'quiet': True,
            'no_warnings': True,
            'cachedir': False,
            'nopart': True,
            'writethumbnail': False,
            'writeinfojson': False,
            'writedescription': False,
            'writesubtitles': False,
            'writeautomaticsub': False,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url.strip(), download=False)
            
            if 'entries' in info:
                info = next(iter(info['entries']), None)
                if info is None:
                    raise ValueError("Playlist is empty or unavailable.")
            
            title = info.get('title', 'Unknown Title')
            duration = info.get('duration')
            thumbnail = info.get('thumbnail', '')
            uploader = info.get('uploader', '')
            formats = info.get('formats', [])
        
        # --- Layer 1: Structural validation ---
        structurally_valid = [f for f in formats if _is_format_valid(f)]
        
        # Separate by type
        candidate_premuxed = [
            f for f in structurally_valid
            if (_get_codec(f, 'vcodec') not in ('none', None, '')
                and _get_codec(f, 'acodec') not in ('none', None, ''))
        ]
        candidate_audio = [
            f for f in structurally_valid
            if (_get_codec(f, 'vcodec') in ('none', None, '')
                and _get_codec(f, 'acodec') not in ('none', None, ''))
        ]
        
        # --- Layer 2: Real byte fetch validation ---
        valid_premuxed_formats = _validate_formats_by_real_fetch(candidate_premuxed)
        valid_audio_formats = _validate_formats_by_real_fetch(candidate_audio)
        
        # --- Build info HTML ---
        info_html = _build_video_info_html(title, thumbnail, uploader, duration,
                                            len(valid_premuxed_formats),
                                            len(valid_audio_formats))
        
        # --- Build format dropdown ---
        format_choices = _build_format_choices(valid_premuxed_formats, valid_audio_formats)
        
        # --- Default format selection ---
        default_format = format_choices[0] if format_choices else "⭐ Auto — Best Available Quality"
        
        # --- Build initial download link ---
        initial_link = handle_update_download_link(url.strip(), default_format)
        
        # --- Determine status message ---
        if not valid_premuxed_formats and not valid_audio_formats:
            status_msg = "⚠️ No downloadable formats found for this video."
        else:
            total = len(valid_premuxed_formats) + len(valid_audio_formats)
            status_msg = f"✅ Found {total} downloadable format{'s' if total != 1 else ''}."
        
        # --- Second yield: Show results ---
        yield (
            gr.update(visible=False),                              # fetch_progress — hide
            gr.update(value=status_msg, visible=True),            # fetch_status
            gr.update(value=info_html, visible=True),             # video_info_display
            gr.update(visible=True),                               # download_options_group
            gr.update(choices=format_choices, value=default_format),  # format_selector
            initial_link,                                          # download_link_html
        )
        
    except Exception as e:
        yield (
            gr.update(visible=False),
            gr.update(value=f"❌ Error: {str(e)}", visible=True),
            gr.update(value="", visible=False),
            gr.update(visible=False),
            gr.update(
                choices=["⭐ Auto — Best Available Quality"],
                value="⭐ Auto — Best Available Quality"
            ),
            gr.update(value="", visible=False),
        )


def handle_update_download_link(url: str, format_selection: str):
    """
    Generates download link based solely on format dropdown selection.
    Quality and extension are determined by the selected format entry.
    No separate quality or extension parameters — format dropdown is the
    single source of truth for what will be downloaded.
    """
    if not url or not url.strip():
        return gr.update(value="", visible=False)
    
    # Parse format_id from the selected dropdown label
    format_id = _parse_format_id_from_label(format_selection)
    
    # Build endpoint URL — pass format_id only
    # The server resolves quality and ext from the format_id directly
    import urllib.parse
    encoded_url = urllib.parse.quote(url.strip(), safe='')
    
    download_endpoint = (
        f"/download/video"
        f"?url={encoded_url}"
        f"&format_id={urllib.parse.quote(format_id, safe='')}"
    )
    
    # Build display label from format_selection
    if format_id == 'auto' or not format_selection:
        quality_label = "Best Available Quality"
    else:
        quality_label = format_selection
    
    link_html = f"""
    <div style="margin-top:12px; text-align:center;">
        <a 
            href="{download_endpoint}" 
            download
            style="
                display:inline-block;
                padding:12px 32px;
                background:#2563eb;
                color:white;
                border-radius:8px;
                text-decoration:none;
                font-size:15px;
                font-weight:600;
            "
        >
            ⬇️ Click to Download to Your Device
        </a>
        <p style="margin:8px 0 0 0; font-size:11px; color:#666;">
            Quality: {quality_label} &nbsp;·&nbsp; 
            Nothing is stored on the server.
        </p>
    </div>
    """
    
    return gr.update(value=link_html, visible=True)


# ── Annotation tab — source mode handlers ──────────────────────

_URL_VIDEO_PLACEHOLDER_HTML = (
    "<div style='"
    "padding: 40px;"
    "text-align: center;"
    "color: #666;"
    "background: #111;"
    "border-radius: 8px;"
    "min-height: 200px;"
    "display: flex;"
    "align-items: center;"
    "justify-content: center;"
    "border: 1px dashed #333;"
    "'>"
    "<div>"
    "<p style='font-size: 24px; margin: 0;'>📺</p>"
    "<p style='margin: 8px 0 0 0; font-size: 14px;'>"
    "Enter a URL above and click <strong>Load URL</strong>"
    "</p>"
    "</div>"
    "</div>"
)

def handle_source_toggle(mode: str, available_videos: list = None):
    is_local = (mode == "Local Folder")
    
    if available_videos is None:
        available_videos = []
        
    has_videos = bool(available_videos)
    
    return (
        gr.update(visible=is_local),     # folder_section
        gr.update(visible=not is_local), # url_section
        gr.update(visible=is_local),     # video_player
        gr.update(value=_URL_VIDEO_PLACEHOLDER_HTML if not is_local else ""), # url_player
        gr.update(visible=is_local and has_videos), # avail_accordion
        gr.update(visible=is_local),     # clear_video_btn
        gr.update(choices=available_videos) # avail_radio
    )


def handle_load_folder(files):
    """
    Called when the gr.File(file_count="directory") picker fires .change().
    """
    if not files:
        return gr.update(choices=[], value=None), "", gr.update(visible=False), []

    # Derive folder from the first file's path
    first_path = files[0].name if hasattr(files[0], "name") else str(files[0])
    folder_path = os.path.dirname(first_path)

    full_paths = scan_folder_full(folder_path)

    if not full_paths:
        return gr.update(choices=[], value=None), folder_path, gr.update(visible=False), []

    return gr.update(choices=full_paths, value=None), folder_path, gr.update(visible=True, open=True), full_paths


def scan_folder_full(folder_path: str) -> list[str]:
    """
    Return sorted list of FULL absolute paths to video files in folder_path.
    Used to populate the avail_radio choices with paths the player can use directly.
    """
    VIDEO_EXTS = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv'}
    folder = Path(folder_path)
    if not folder.exists() or not folder.is_dir():
        return []
    return sorted(
        str(f) for f in folder.iterdir()
        if f.is_file() and f.suffix.lower() in VIDEO_EXTS
    )


def handle_avail_video_select(full_path: str):
    """
    Called when user selects a video from the Available Videos radio list.
    full_path is the complete absolute path to the video file.

    Returns: (video_player, video_status, start, end, duration_md, result_md, source_state)
    """
    if not full_path:
        return None, "*Select a video from the list*", 0, 10, "10.0s (00:00 → 00:10)", "", ""

    result = load_video(full_path)
    # load_video returns 6-tuple; append full_path as source_state (7th element)
    return result + (full_path,)


def handle_clear_video():
    """
    Clears the video player and resets all related state.
    """
    return (
        gr.update(value=None),   # video_player — clear to empty
        None,                    # source_state — reset to None
        gr.update(value=None),   # avail_radio — deselect
    )


def _resolve_stream_url_no_download(url: str):
    ydl_opts = {
        'format': 'best[ext=mp4][protocol=https]/best[ext=mp4][protocol=http]/best[protocol=https]/best[protocol=http]/best',
        'skip_download': True,
        'nodownload': True,
        'cachedir': False,
        'nopart': True,
        'outtmpl': '/dev/null',
        'writethumbnail': False,
        'writeinfojson': False,
        'writedescription': False,
        'writesubtitles': False,
        'writeautomaticsub': False,
        'quiet': True,
        'no_warnings': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        if 'entries' in info:
            info = next(iter(info['entries']), None)
            if info is None:
                raise ValueError("Playlist is empty.")
        
        stream_url = info.get('url') or info.get('manifest_url')
        thumbnail_url = info.get('thumbnail', '')
        title = info.get('title', '')
        
        if not stream_url:
            raise ValueError(
                "yt-dlp could not extract a direct stream URL. "
                "The video may be private, region-locked, or require authentication."
            )
        return stream_url, thumbnail_url, title

def _build_url_video_html(proxy_url: str, poster_url: str, title: str) -> str:
    """
    Builds the HTML5 video player for URL mode.
    Uses poster image for correct sizing before playback.
    Uses preload=none to avoid unnecessary proxy requests on render.
    """
    poster_attr = f'poster="{poster_url}"' if poster_url else ''
    title_display = title if title else 'URL Video'
    
    return f"""
    <div style="
        width: 100%;
        background: #000;
        border-radius: 8px;
        overflow: hidden;
        position: relative;
    ">
        <video
            controls
            width="100%"
            height="480"
            style="
                display: block;
                width: 100%;
                height: 480px;
                object-fit: contain;
                background: #000;
            "
            {poster_attr}
            preload="none"
            crossorigin="anonymous"
            title="{title_display}"
            onloadedmetadata="this.style.height='auto'"
        >
            <source src="{proxy_url}" type="video/mp4">
            <source src="{proxy_url}" type="video/webm">
            <p style="color:white; padding:20px; margin:0;">
                HTML5 video not supported in this browser.
            </p>
        </video>
        <div style="
            padding: 6px 10px;
            background: #111;
            font-size: 12px;
            color: #888;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        ">
            📺 {title_display}
        </div>
    </div>
    """

def handle_load_url(url: str):
    """
    Load a video from a URL for streaming playback.
    Uses a custom proxy route to bypass CORS.
    """
    if not url or not url.strip():
        return _URL_VIDEO_PLACEHOLDER_HTML, "⚠️ Enter a URL", 0, 10, "10.0s", "", ""
    
    url = url.strip()
    try:
        stream_url, thumbnail_url, title = _resolve_stream_url_no_download(url)
        encoded = urllib.parse.quote(stream_url, safe='')
        proxy_url = f"/proxy/video?url={encoded}"
        
        video_html = _build_url_video_html(proxy_url, thumbnail_url, title)
        
        status_md = f"✅ Stream loaded: `{url}`"
        return video_html, status_md, 0, 10, "10.0s (00:00 → 00:10)", "", stream_url
        
    except Exception as e:
        error_html = f"""
        <div style="padding:20px; color:#ff6b6b; background:#1a0000; 
                    border-radius:8px; border:1px solid #ff3333;">
            <strong>❌ Failed to load URL:</strong><br>
            <code>{str(e)}</code>
        </div>
        """
        return error_html, f"❌ Error: {e}", 0, 10, "10.0s", "", ""


# ============================================================
# EXTRACTED SEGMENTS TAB HANDLERS
# ============================================================

# ══════════════════════════════════════════════════════════
#  EXTRACTED SEGMENTS TAB (Supabase)
# ══════════════════════════════════════════════════════════

def _build_view_mode_choices():
    return ["All Segments", "By Rasa"]

def _build_rasa_filter_choices():
    from config.settings import LABELS
    return ["All"] + list(LABELS)

def _build_table_headers():
    return ["#", "Rasa", "Start", "End", "Duration", "Source", "Audio", "Video", "Date", "ID"]

def _build_table_datatypes():
    return ["number", "str", "str", "str", "str", "str", "str", "str", "str", "str"]

def _build_supabase_init_html(msg: str, is_error: bool = False) -> str:
    color = "#ef4444" if is_error else "#10b981"
    bg = "#4a1010" if is_error else "#06402b"
    return f"""
    <div style="padding:12px 16px; background:{bg}; border-left:4px solid {color}; border-radius:4px; color:#fff; font-size:13px; margin:8px 0;">
        {msg}
    </div>
    """

def _filter_segments(segments_data: dict, view_mode: str, rasa_filter: str) -> list:
    if not segments_data:
        return []
    if view_mode == "All Segments":
        return segments_data.get('all', [])
    elif view_mode == "By Rasa":
        if rasa_filter and rasa_filter != "All":
            return segments_data.get('by_rasa', {}).get(rasa_filter, [])
        return segments_data.get('all', [])
    return segments_data.get('all', [])

def _build_segments_dataframe(segments: list):
    """
    Converts segment list to dataframe rows for display.
    
    Reads segment dicts using CONFIRMED field names:
    label, source_video, start_time, end_time, duration,
    audio_file, video_file, timestamp, id
    
    These names come from parse_annotations_to_segments which
    reads from Supabase using confirmed column names.
    """
    if not segments:
        return None
    
    rows = []
    
    for i, seg in enumerate(segments, 1):
        audio_icon = "☁️"
        video_icon = "☁️"
        
        # Format timestamp
        ts = str(seg.get('timestamp', ''))
        date_display = ts[:10] if ts else ''
        
        # Source video — read 'source_video' (confirmed column name)
        source = str(seg.get('source_video', ''))
        if not source:
            source = 'N/A'
        if len(source) > 40:
            source = source[:37] + "..."
        
        # Label/Rasa — read 'label' (confirmed column name)
        label = str(seg.get('label', ''))
        if not label:
            label = 'N/A'
        
        # Format timing
        try:
            start_disp = f"{float(seg.get('start_time', 0)):.1f}"
            end_disp   = f"{float(seg.get('end_time', 0)):.1f}"
            dur_disp   = f"{float(seg.get('duration', 0)):.1f}"
        except (ValueError, TypeError):
            start_disp = str(seg.get('start_time', ''))
            end_disp   = str(seg.get('end_time', ''))
            dur_disp   = str(seg.get('duration', ''))
        
        rows.append([
            i,            # #
            label,        # Rasa/Label — from 'label' field
            start_disp,   # Start (s)
            end_disp,     # End (s)
            dur_disp,     # Duration (s)
            source,       # Source — from 'source_video' field
            audio_icon,   # Audio
            video_icon,   # Video
            date_display, # Date
            str(seg.get('id', ''))
        ])
    
    return rows if rows else None

def _build_segments_summary_html(segments_data: dict) -> str:
    total = segments_data.get('total_count', 0)
    rasa_counts = segments_data.get('rasa_counts', {})
    
    rasa_pills = "".join([
        f'<div style="display:inline-block; margin:2px; background:#0f3460; border-radius:20px; padding:4px 12px; font-size:12px; color:#7eb8f7;">🎭 {r}: <strong>{c}</strong></div>'
        for r, c in rasa_counts.items() if c > 0
    ])
    
    return f"""
    <div style="padding:16px; background:linear-gradient(135deg,#1a1a2e,#16213e); border-radius:10px; border:1px solid #2d2d4e; margin:8px 0;">
        <div style="display:flex; gap:24px; flex-wrap:wrap; margin-bottom:12px;">
            <div style="text-align:center;">
                <div style="font-size:28px; font-weight:700; color:#fff;">{total}</div>
                <div style="font-size:11px; color:#888;">Total Segments</div>
            </div>
        </div>
        <div style="flex-wrap:wrap; display:flex; gap:4px;">{rasa_pills}</div>
    </div>
    """

def _build_count_display_html(count: int, view_mode: str, rasa_filter: str) -> str:
    label = view_mode
    if view_mode == "By Rasa" and rasa_filter and rasa_filter != "All":
        label = f"{rasa_filter} (By Rasa)"
    return f"""
    <p style="margin:4px 0; font-size:13px; color:#888;">
        Showing <strong style="color:#fff;">{count}</strong> segment{'s' if count != 1 else ''}
        &nbsp;·&nbsp; Filter: <strong style="color:#7eb8f7;">{label}</strong>
    </p>
    """

def _build_segment_detail_html(segment: dict) -> str:
    """
    Builds the information card HTML for a selected segment.
    
    Reads segment dict using CONFIRMED field names:
    label, source_video, start_time, end_time, duration,
    notes, timestamp, id
    """
    # Read 'label' — confirmed column name for rasa/emotion
    label = str(segment.get('label', ''))
    if not label:
        label = 'N/A'
    
    # Read settings to get actual rasa category colors
    try:
        from config import settings
        rasa_list = getattr(settings, 'RASA_CATEGORIES', 
                   getattr(settings, 'EMOTIONS', []))
    except Exception:
        rasa_list = []
    
    rasa_colors = {
        'Hasya':    '#f59e0b',
        'Karuna':   '#60a5fa',
        'Rudra':    '#f87171',
        'Shant':    '#34d399',
        'Bhayanak': '#c084fc',
        'Veer':     '#fb923c',
        'Adbhuta':  '#e879f9',
        'Shringara':'#f472b6',
    }
    label_color = rasa_colors.get(label, '#7eb8f7')
    
    # Format timing — read 'start_time', 'end_time', 'duration'
    start    = segment.get('start_time', 0)
    end      = segment.get('end_time', 0)
    duration = segment.get('duration', 0)
    
    try:
        start_fmt = f"{float(start):.2f}"
        end_fmt   = f"{float(end):.2f}"
        dur_fmt   = f"{float(duration):.2f}"
    except (ValueError, TypeError):
        start_fmt = str(start)
        end_fmt   = str(end)
        dur_fmt   = str(duration)
    
    # Format timestamp
    ts = str(segment.get('timestamp', ''))
    if 'T' in ts:
        ts_display = ts.replace('T', ' ')[:19]
    elif ts:
        ts_display = ts[:19]
    else:
        ts_display = 'N/A'
    
    # Source video — read 'source_video' (confirmed column name)
    source = str(segment.get('source_video', ''))
    if not source:
        source = 'N/A'
    source_display = source if len(source) <= 80 else source[:77] + "..."
    
    # Segment ID
    seg_id = str(segment.get('id', 'N/A'))
    
    # Notes
    notes = str(segment.get('notes', '')).strip()
    notes_section = (
        f"""<div style="margin-top:8px;padding:8px;
                        background:#0f0f1a;border-radius:6px;">
                <div style="color:#666;font-size:10px;
                            text-transform:uppercase;margin-bottom:4px;">Notes</div>
                <div style="color:#c0c0e0;font-size:12px;">{notes}</div>
            </div>"""
        if notes else ""
    )
    
    return f"""
    <div style="
        padding:16px;
        background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);
        border-radius:12px;
        border:1px solid #2d2d4e;
        margin:8px 0;
    ">
        <div style="
            display:flex; align-items:center;
            gap:12px; margin-bottom:14px; flex-wrap:wrap;
        ">
            <div style="
                background:{label_color}22;
                border:2px solid {label_color};
                border-radius:10px; padding:6px 16px;
                font-size:15px; font-weight:700;
                color:{label_color}; letter-spacing:0.5px;
            ">🎭 {label}</div>
            
            <div style="
                font-size:10px; color:#555; font-family:monospace;
                background:#0a0a1a; padding:4px 8px; border-radius:4px;
                word-break:break-all;
            ">{seg_id}</div>
        </div>
        
        <div style="
            display:grid;
            grid-template-columns:repeat(3, 1fr);
            gap:8px; margin-bottom:10px;
        ">
            <div style="
                background:#0f0f1a; border-radius:8px;
                padding:10px; text-align:center;
            ">
                <div style="color:#666;font-size:10px;
                            text-transform:uppercase;margin-bottom:4px;">Start</div>
                <div style="color:#7eb8f7;font-size:18px;font-weight:700;">
                    {start_fmt}s
                </div>
            </div>
            <div style="
                background:#0f0f1a; border-radius:8px;
                padding:10px; text-align:center;
            ">
                <div style="color:#666;font-size:10px;
                            text-transform:uppercase;margin-bottom:4px;">End</div>
                <div style="color:#7eb8f7;font-size:18px;font-weight:700;">
                    {end_fmt}s
                </div>
            </div>
            <div style="
                background:#0f0f1a; border-radius:8px;
                padding:10px; text-align:center;
                border:1px solid {label_color}44;
            ">
                <div style="color:#666;font-size:10px;
                            text-transform:uppercase;margin-bottom:4px;">Duration</div>
                <div style="color:{label_color};font-size:18px;font-weight:700;">
                    {dur_fmt}s
                </div>
            </div>
        </div>
        
        <div style="
            padding:8px 10px; background:#0f0f1a;
            border-radius:6px; margin-bottom:6px;
        ">
            <div style="color:#666;font-size:10px;
                        text-transform:uppercase;margin-bottom:3px;">Source Video</div>
            <code style="font-size:11px;color:#a0c0ff;word-break:break-all;">
                {source_display}
            </code>
        </div>
        
        <div style="
            padding:6px 10px; background:#0f0f1a;
            border-radius:6px; margin-bottom:6px;
        ">
            <div style="color:#666;font-size:10px;
                        text-transform:uppercase;margin-bottom:2px;">Annotated</div>
            <div style="color:#888;font-size:12px;">{ts_display}</div>
        </div>
        
        {notes_section}
    </div>
    """

def handle_fetch_supabase_segments(segments_data_state: dict):
    from controllers.supabase_sync import fetch_all_annotations, parse_annotations_to_segments
    from config import settings

    if not settings.SUPABASE_CONFIGURED:
        return (
            gr.update(value=_build_supabase_init_html("Supabase is not configured. Set SUPABASE_URL and SUPABASE_KEY.", True), visible=True),
            None, gr.update(value=None), gr.update(value="")
        )

    rows, error = fetch_all_annotations()
    if error:
        return (
            gr.update(value=_build_supabase_init_html(f"Error fetching from Supabase: {error}", True), visible=True),
            segments_data_state, gr.update(value=None), gr.update(value="")
        )

    segments_data = parse_annotations_to_segments(rows)
    df_data = _build_segments_dataframe(segments_data.get('all', []))
    summary_html = _build_segments_summary_html(segments_data)

    return (
        gr.update(value=_build_supabase_init_html(f"✅ Synced from Supabase. {segments_data['total_count']} segments found."), visible=True),
        segments_data,
        gr.update(value=df_data),
        gr.update(value=summary_html)
    )

def handle_view_mode_changed(view_mode: str, rasa_filter: str, segments_data: dict):
    filtered = _filter_segments(segments_data, view_mode, rasa_filter)
    df_data = _build_segments_dataframe(filtered)
    count_html = _build_count_display_html(len(filtered), view_mode, rasa_filter)
    show_rasa = (view_mode == "By Rasa")
    return (
        gr.update(value=df_data),
        gr.update(value=count_html),
        gr.update(visible=show_rasa)
    )

def handle_rasa_filter_changed(view_mode: str, rasa_filter: str, segments_data: dict):
    return handle_view_mode_changed(view_mode, rasa_filter, segments_data)

def handle_segment_row_selected(evt: gr.SelectData, segments_data: dict, view_mode: str, rasa_filter: str):
    if not segments_data or evt is None:
        return (gr.update(visible=False), gr.update(value=""), gr.update(value=None, visible=False), gr.update(value=None, visible=False), gr.update(visible=False)) # COUNT return items: 5

    try:
        row_index = evt.index[0] if hasattr(evt, 'index') else evt.index
        filtered = _filter_segments(segments_data, view_mode, rasa_filter)
        
        if row_index >= len(filtered):
            return (
                gr.update(visible=False), gr.update(value=""), 
                gr.update(value=None, visible=False), gr.update(value=None, visible=False), 
                gr.update(visible=False)
            ) # COUNT return items: 5
            
        segment = filtered[row_index]
        detail_html = _build_segment_detail_html(segment)
        
        seg_id = segment.get('id', '')
        audio_url = f"/segment/audio/{seg_id}"
        video_url = f"/segment/video/{seg_id}"
        
        video_html = f'<div style="margin-top:10px;"><video controls src="{video_url}" style="width:100%; max-height:400px; background:#000; border-radius:8px;"></video></div>'

        from controllers.media_extractor import extract_audio_to_tempfile
        source_video = str(segment.get('source_video', ''))
        start_time   = float(segment.get('start_time', 0))
        end_time     = float(segment.get('end_time', 0))
        
        tmp_path, err = extract_audio_to_tempfile(
            source_video, start_time, end_time, seg_id
        )
        if not tmp_path:
            audio_update = gr.update(value=None, visible=False)
        else:
            audio_update = gr.update(
                value=tmp_path,
                visible=True,
                label=f"🎵 {segment.get('label', '')} — Audio",
            )

        return (
            gr.update(visible=True),
            gr.update(value=detail_html),
            gr.update(value=video_html, visible=True),
            audio_update,
            gr.update(visible=True, value=seg_id) # We store the ID in the delete button's value for the next callback
        ) # COUNT return items: 5
    except Exception as e:
        return (
            gr.update(visible=False), gr.update(value=f"Error: {e}"), 
            gr.update(value=None, visible=False), gr.update(value=None, visible=False), 
            gr.update(visible=False)
        ) # COUNT return items: 5

def _remove_segment_from_state(segments: dict, segment_id: str) -> dict:
    """
    Returns a new segments dict with the specified segment_id removed.
    Updates all lists and counts.
    """
    if not segments or not segment_id:
        return segments or {}
    
    import copy
    updated = copy.deepcopy(segments)
    
    # Remove from 'all'
    updated['all'] = [
        s for s in updated.get('all', [])
        if str(s.get('id', '')) != str(segment_id)
    ]
    updated['total_count'] = len(updated['all'])
    
    # Remove from 'by_rasa'
    for rasa_key in list(updated.get('by_rasa', {}).keys()):
        updated['by_rasa'][rasa_key] = [
            s for s in updated['by_rasa'][rasa_key]
            if str(s.get('id', '')) != str(segment_id)
        ]
        updated['rasa_counts'][rasa_key] = len(updated['by_rasa'][rasa_key])
    
    return updated

def _build_delete_popup_html(segment: dict) -> str:
    """
    Builds a full-screen fixed overlay HTML for delete confirmation.
    Visual appearance is unchanged from previous version.
    Only the onclick JavaScript is fixed to reliably find and click
    the hidden Gradio buttons which are now visible in DOM via CSS hiding.
    """
    label    = str(segment.get('label', 'N/A'))
    seg_id   = str(segment.get('id', 'N/A'))
    source   = str(segment.get('source_video', 'N/A'))
    start    = segment.get('start_time', 0)
    end      = segment.get('end_time', 0)
    duration = segment.get('duration', 0)
    ts       = str(segment.get('timestamp', ''))
    notes    = str(segment.get('notes', '')).strip()

    try:
        start_fmt = f"{float(start):.2f}s"
        end_fmt   = f"{float(end):.2f}s"
        dur_fmt   = f"{float(duration):.2f}s"
    except (ValueError, TypeError):
        start_fmt = str(start)
        end_fmt   = str(end)
        dur_fmt   = str(duration)

    if 'T' in ts:
        ts_display = ts.replace('T', ' ')[:19]
    else:
        ts_display = ts[:19] if ts else 'N/A'

    source_display = (source[:70] + "...") if len(source) > 70 else source
    notes_display  = notes if notes else "—"

    def detail_row(label_text: str, value_html: str, value_color: str = "#e0e0e0") -> str:
        return f"""
        <tr style="border-bottom:1px solid #3d1111;">
            <td style="
                padding:8px 12px;
                color:#888;
                text-transform:uppercase;
                font-size:10px;
                font-weight:600;
                white-space:nowrap;
                width:90px;
                vertical-align:top;
            ">{label_text}</td>
            <td style="
                padding:8px 12px;
                color:{value_color};
                font-size:12px;
                word-break:break-all;
            ">{value_html}</td>
        </tr>"""

    # JavaScript — updated to perfectly query Gradio wrapper component boxes
    cancel_js = """
(function() {
    function tryClick() {
        var wrapper = document.getElementById('cancel_delete_hidden_btn') || 
                      document.querySelector('[id*="cancel_delete_hidden_btn"]');
        if (wrapper) {
            var btn = wrapper.querySelector('button');
            if (btn) { btn.click(); return true; }
        }
        var all = document.querySelectorAll('button');
        for (var i = 0; i < all.length; i++) {
            var t = (all[i].textContent || all[i].innerText || '').trim();
            if (t === 'cancel_delete_hidden' || all[i].id === 'cancel_delete_hidden_btn') { 
                all[i].click(); 
                return true; 
            }
        }
        return false;
    }
    if (!tryClick()) { setTimeout(tryClick, 100); }
})();
""".strip().replace('\n', ' ')

    confirm_js = """
(function() {
    function tryClick() {
        var wrapper = document.getElementById('confirm_delete_hidden_btn') || 
                      document.querySelector('[id*="confirm_delete_hidden_btn"]');
        if (wrapper) {
            var btn = wrapper.querySelector('button');
            if (btn) { btn.click(); return true; }
        }
        var all = document.querySelectorAll('button');
        for (var i = 0; i < all.length; i++) {
            var t = (all[i].textContent || all[i].innerText || '').trim();
            if (t === 'confirm_delete_hidden' || all[i].id === 'confirm_delete_hidden_btn') { 
                all[i].click(); 
                return true; 
            }
        }
        return false;
    }
    if (!tryClick()) { setTimeout(tryClick, 100); }
})();
""".strip().replace('\n', ' ')

    return f"""
<div id="natak_delete_overlay" style="
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    background: rgba(0, 0, 0, 0.75);
    z-index: 99999;
    display: flex;
    align-items: center;
    justify-content: center;
    backdrop-filter: blur(4px);
    -webkit-backdrop-filter: blur(4px);
">
    <div style="
        background: linear-gradient(135deg, #1a0505 0%, #2d0a0a 100%);
        border: 2px solid #dc2626;
        border-radius: 16px;
        padding: 28px 32px;
        max-width: 520px;
        width: 90vw;
        max-height: 85vh;
        overflow-y: auto;
        box-shadow: 0 25px 60px rgba(0,0,0,0.7), 0 0 0 1px rgba(220,38,38,0.3);
        animation: natak_popup_in 0.18s ease-out;
    ">
        <div style="
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 20px;
        ">
            <span style="font-size: 28px;">⚠️</span>
            <div>
                <div style="
                    font-size: 18px;
                    font-weight: 700;
                    color: #ef4444;
                    line-height: 1.2;
                ">Delete Annotation?</div>
                <div style="
                    font-size: 12px;
                    color: #888;
                    margin-top: 2px;
                ">This action cannot be undone.</div>
            </div>
        </div>

        <table style="
            width: 100%;
            border-collapse: collapse;
            background: #0f0505;
            border-radius: 10px;
            overflow: hidden;
            margin-bottom: 18px;
        ">
            {detail_row("ID", f'<code style="font-size:10px;color:#fca5a5;">{{seg_id}}</code>')}
            {detail_row("Label", f'<strong style="font-size:13px;">{{label}}</strong>', "#fbbf24")}
            {detail_row("Timing", f'{{start_fmt}} → {{end_fmt}} &nbsp;|&nbsp; <strong>{{dur_fmt}}</strong>')}
            {detail_row("Source", f'<code style="font-size:10px;">{{source_display}}</code>', "#93c5fd")}
            {detail_row("Annotated", ts_display, "#c0c0e0")}
            {detail_row("Notes", f'<em>{{notes_display}}</em>', "#c0c0e0")}
        </table>

        <div style="
            padding: 10px 14px;
            background: #450a0a;
            border-radius: 8px;
            border: 1px solid #7f1d1d;
            font-size: 12px;
            color: #fca5a5;
            margin-bottom: 22px;
        ">
            🗑️ Only the annotation record will be deleted.
            The original source video is not affected.
        </div>

        <div style="
            display: flex;
            gap: 12px;
            justify-content: flex-end;
        ">
            <button
                onclick="{cancel_js}"
                style="
                    padding: 10px 22px;
                    background: #1f2937;
                    border: 1px solid #374151;
                    border-radius: 8px;
                    color: #d1d5db;
                    font-size: 14px;
                    font-weight: 600;
                    cursor: pointer;
                "
                onmouseover="this.style.background='#374151'"
                onmouseout="this.style.background='#1f2937'"
            >✖ Cancel</button>

            <button
                onclick="{confirm_js}"
                style="
                    padding: 10px 22px;
                    background: linear-gradient(135deg, #dc2626, #991b1b);
                    border: 1px solid #ef4444;
                    border-radius: 8px;
                    color: #ffffff;
                    font-size: 14px;
                    font-weight: 700;
                    cursor: pointer;
                "
                onmouseover="this.style.opacity='0.85'"
                onmouseout="this.style.opacity='1'"
            >🗑️ Yes, Delete</button>
        </div>
    </div>
</div>

<style>
@keyframes natak_popup_in {{
    from {{ opacity: 0; transform: scale(0.95) translateY(-8px); }}
    to   {{ opacity: 1; transform: scale(1) translateY(0); }}
}}
</style>
"""

def handle_show_delete_confirm(segment_id_btn, segments_data: dict) -> tuple:
    segment_id = getattr(segment_id_btn, "value", segment_id_btn) if hasattr(segment_id_btn, "value") else str(segment_id_btn)
    if not segment_id or not segments_data:
        return (
            gr.update(value=""),
            gr.update(value="⚠️ No segment selected."),
        )

    segment = None
    for s in segments_data.get('all', []):
        if str(s.get('id', '')) == str(segment_id):
            segment = s
            break
            
    if not segment:
        return (
            gr.update(value=""),
            gr.update(value="⚠️ Segment not found."),
        )

    popup_html = _build_delete_popup_html(segment)
    return (
        gr.update(value=popup_html),
        gr.update(value=""),
    )

def handle_cancel_delete_confirm() -> tuple:
    import logging
    logging.getLogger('natak.handlers').info(
        "handle_cancel_delete_confirm called"
    )
    return (
        gr.update(value=""),
        gr.update(value=""),
    )

def handle_delete_segment(
    segment_id: str,
    segments: dict,
    view_mode: str,
    rasa_filter: str,
):
    """
    Deletes annotation from Supabase and updates local state.
    """
    import logging
    logging.getLogger('natak.handlers').info(
        f"handle_confirmed_delete called: segment_id={segment_id!r}"
    )
    from controllers.supabase_sync import delete_annotation
    
    _default_keep_open = (
        gr.update(value=""),                                            # 1. delete_popup_html
        gr.update(value="⚠️ No segment selected to delete."),          # 2. supabase_status_display
        segments,                                                # 3. segments_data_state
        gr.update(),                                            # 4. segments_dataframe
        gr.update(),                                            # 5. segments_count_html
        gr.update(visible=True),                               # 6. segment_detail_group
        gr.update(),                                            # 7. segment_detail_html
        gr.update(),                                            # 8. video_preview
        gr.update(),                                            # 9. audio_preview
        gr.update(),                                            # 10. delete_segment_btn
        gr.update(value=None, visible=False),                  # 11. spectrogram_image — reset
        gr.update(value="",   visible=False),                  # 12. spectrogram_status_outer — reset
        gr.update(visible=False),                              # 13. spectrogram_group — reset
    )
    
    if not segment_id:
        return _default_keep_open # COUNT return items: 13
    
    # Attempt deletion from Supabase
    success, error = delete_annotation(str(segment_id))
    
    if not success:
        error_return = list(_default_keep_open)
        error_return[1] = gr.update(value=f"❌ Delete failed: {error}")
        return tuple(error_return) # COUNT return items: 13
    
    # Remove segment from local segments dict
    updated_segments = _remove_segment_from_state(segments, segment_id)
    
    # Rebuild table with updated segments
    filtered = _filter_segments(updated_segments, view_mode, rasa_filter)
    table_data = _build_segments_dataframe(filtered)
    
    return (
        gr.update(value=""),                                                   # 1
        gr.update(value=f"✅ Segment `{segment_id}` deleted successfully."),  # 2
        updated_segments,                                                       # 3
        gr.update(value=table_data),                                           # 4
        gr.update(value=f"<b>{len(filtered)}</b> segments found"),             # 5
        gr.update(visible=False),                                              # 6. CLOSE detail group
        gr.update(value=""),                                                   # 7
        gr.update(value=None, visible=False),                                  # 8
        gr.update(value=None, visible=False),                                  # 9
        gr.update(value=""),                                                   # 10
        gr.update(value=None, visible=False),                                  # 11. spectrogram_image — reset
        gr.update(value="",   visible=False),                                  # 12. spectrogram_status_outer — reset
        gr.update(visible=False),                                              # 13. spectrogram_group — reset
    ) # COUNT return items: 13

def handle_analyse_spectrum(
    segment_id: str,
    segments: dict,
) -> tuple:
    """
    Triggered when user clicks 'Analyse Spectrum'.

    Flow:
    1. Find segment in state by id
    2. Check source_video is accessible
    3. Extract audio to temp file using media_extractor
    4. Run spectrogram analysis using spectrogram_analysis module
    5. Return PNG image path to gr.Image component
    6. Temp audio file deleted after analysis
    7. PNG temp file returned to Gradio (Gradio serves it;
       it will be cleaned up by OS temp file management)

    Returns: 3-value tuple
    - spectrogram_image update  (gr.Image value=png_path)
    - spectrogram_status update (gr.Markdown value=status string)
    - spectrogram_group update  (gr.Group visible=True on success)
    COUNT: 3
    """
    import logging
    import os
    _log = logging.getLogger('natak.handlers')

    _default_error = lambda msg: (
        gr.update(value=None, visible=False),   # spectrogram_image
        gr.update(value=msg,  visible=True),    # spectrogram_status
        gr.update(visible=False),               # spectrogram_group
    )  # COUNT: 3

    if not segment_id:
        return _default_error("⚠️ No segment selected.")

    segment = _find_segment_by_id(segments, segment_id)
    if not segment:
        return _default_error(
            "⚠️ Segment not found in state. "
            "Refresh the segments list and try again."
        )

    source_video = str(segment.get('source_video', ''))
    start_time   = float(segment.get('start_time', 0))
    end_time     = float(segment.get('end_time', 0))
    label        = str(segment.get('label', ''))

    if not source_video:
        return _default_error("❌ No source video recorded for this annotation.")

    if not _check_source_available(source_video):
        return _default_error(
            f"⚠️ Source video not accessible from this server:\n\n"
            f"`{source_video[:80]}`\n\n"
            "Spectrum analysis requires the source video to be "
            "accessible on the server."
        )

    # ── Step 1: Extract audio to temp file ──────────────────────────
    from controllers.media_extractor import extract_audio_to_tempfile

    audio_tmp, audio_err = extract_audio_to_tempfile(
        source_video, start_time, end_time, segment_id
    )

    if not audio_tmp:
        return _default_error(
            f"❌ Audio extraction failed:\n\n{audio_err}\n\n"
            f"Source: `{source_video[:60]}`"
        )

    # ── Step 2: Run spectrogram analysis ────────────────────────────
    try:
        from controllers.spectrogram_analysis import analyse_segment_spectrogram

        png_path, spect_err = analyse_segment_spectrogram(
            audio_file_path=audio_tmp,
            segment_label=label,
            segment_id=segment_id,
        )
    finally:
        # Always delete the audio temp file — analysis is done with it
        if audio_tmp and os.path.exists(audio_tmp):
            try:
                os.unlink(audio_tmp)
            except Exception as e:
                _log.warning(f"Could not delete audio temp file {audio_tmp}: {e}")

    if not png_path:
        return _default_error(
            f"❌ Spectrogram analysis failed:\n\n{spect_err}"
        )

    # ── Step 3: Return PNG to Gradio ────────────────────────────────
    # Gradio gr.Image accepts a file path string.
    # Gradio serves the file internally.
    return (
        gr.update(value=png_path, visible=True),   # spectrogram_image
        gr.update(
            value="✅ Spectrogram computed successfully.",
            visible=True,
        ),                                           # spectrogram_status
        gr.update(visible=True),                    # spectrogram_group
    )  # COUNT: 3

def _find_segment_by_id(segments: dict, segment_id: str) -> dict | None:
    """
    Helper to scan the active state dictionary cache 
    and extract a segment matching the requested identifier.
    """
    if not segments or not segment_id:
        return None
        
    # Scan through the primary list collection
    for segment in segments.get('all', []):
        if str(segment.get('id', '')).strip() == str(segment_id).strip():
            return segment
            
    return None

def _check_source_available(video_path: str) -> bool:
    """
    Verifies if a recorded video file or absolute system path 
    is fully accessible and exists locally on the host machine.
    """
    if not video_path:
        return False
        
    # Ignore network streams/URLs for local execution validations
    if video_path.startswith('http://') or video_path.startswith('https://'):
        return True
        
    import os
    return os.path.exists(video_path)
