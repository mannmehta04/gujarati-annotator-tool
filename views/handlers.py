# views/handlers.py
"""
Gradio event handlers.
Translates UI events into controller calls and formats
results back into Gradio component updates.
No business logic here. No ffmpeg. No CSV.
"""

import gradio as gr
from controllers.extractor import (
    load_video,
    extract_segment,
    get_preview_copy,
    format_time,
)
from controllers.downloader import download_video
from models.annotation import (
    build_segment_choices,
    get_segment_row,
    get_stats,
    delete_segment,
    get_segment_info_for_confirmation,
    delete_segment_by_id,
)
from config.settings import OUTPUT_DIR
from pathlib import Path


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


def on_extract(video_path_input, start, end, label, notes):
    msg, _a, _v              = extract_segment(video_path_input, start, end, label, notes)
    stats                     = get_stats()
    choices, summary, new_map = build_segment_choices()
    return (
        msg,
        stats,
        gr.update(choices=choices, value=None),
        summary,
        new_map
    )


def on_segment_flush(_display_str, _seg_map):
    """Phase 1: clear preview before loading new one."""
    return None, None, "*Loading...*"


def on_segment_load(display_str: str, seg_map: dict):
    """Phase 2: load real segment preview."""
    if not display_str or not seg_map:
        return None, None, "*Select a segment to preview*"

    try:
        row = get_segment_row(display_str, seg_map)
        if row is None:
            return None, None, "❌ Segment not found"

        audio_path = OUTPUT_DIR / row["audio_file"]
        video_path = OUTPUT_DIR / row["video_file"]

        if not audio_path.exists():
            return None, None, "❌ Audio file missing"
        if not video_path.exists():
            return None, None, "❌ Video file missing"

        preview_video = get_preview_copy(str(video_path))

        info = (
            f"### {row['label']}\n\n"
            f"**Source:** {row['source_video']}  \n"
            f"**Time:** {row['start_time']:.1f}s → {row['end_time']:.1f}s  \n"
            f"**Duration:** {row['duration']:.1f}s  \n"
            f"**ID:** `{row['id'][-30:]}`"
        )
        return str(audio_path), preview_video, info

    except Exception as e:
        import traceback
        traceback.print_exc()
        return None, None, f"❌ Error: {e}"


def on_refresh(_seg_map):
    choices, summary, new_map = build_segment_choices()
    return gr.update(choices=choices, value=None), summary, new_map


def on_delete_request(display_str: str, seg_map: dict):
    """
    Step 1: populate confirm_info_md and lock the ID.
    Does NOT touch confirm_group visibility — that is handled
    separately via .then() in ui.py to avoid the spinner bug.
    Returns: (confirm_info_md, confirm_id_state)
    """
    if not display_str:
        return "\u26a0\ufe0f Select a segment from the list first.", ""

    info_md, target_id = get_segment_info_for_confirmation(
        display_str, seg_map
    )
    return info_md, target_id


def on_confirm_delete(target_id: str):
    """
    Step 2: execute deletion using the locked-in ID.
    Returns 10 values — confirm_group visibility handled via
    .then() in ui.py so the container never appears in outputs.

    Outputs order (must match ui.py wiring):
      delete_status_md, segment_radio, seg_summary_md,
      seg_map_state, stats_md,
      preview_audio, preview_video, preview_info,
      confirm_info_md, confirm_id_state
    """
    if not target_id:
        return (
            "\u26a0\ufe0f No segment ID — select a segment first",
            gr.update(), gr.update(), {},
            get_stats(),
            None, None,
            "*Select a segment to preview*",
            "", ""
        )

    status, new_choices, new_summary, new_seg_map = \
        delete_segment_by_id(target_id)

    return (
        status,
        gr.update(choices=new_choices, value=None),
        new_summary,
        new_seg_map,
        get_stats(),
        None,
        None,
        "*Segment deleted — select another to preview*",
        "",   # clear confirm_info_md
        ""    # clear confirm_id_state
    )


# Legacy alias
def on_delete_segment(display_str: str, seg_map: dict):
    return on_delete_request(display_str, seg_map)


def on_download_video(url: str):
    """
    Streaming handler for the Download tab.

    Yields (log_text, path_or_empty, gr.update) tuples as yt-dlp runs.
    The log_text accumulates all output lines.
    On completion yields the saved path (or "") for auto-population.

    Outputs (in order):
        download_log    — scrolling text log
        download_path   — final saved path (empty until done)
        download_status — status markdown (empty until done)
    """
    log = ""
    saved_path = ""
    status_md  = ""

    for chunk in download_video(url):
        if chunk.startswith("__RESULT__:"):
            # Parse sentinel: __RESULT__:ok:<path> or __RESULT__:error:<msg>
            _, kind, payload = chunk.split(":", 2)
            if kind == "ok":
                saved_path = payload
                status_md  = f"✅ **Downloaded:** `{saved_path}`"
            else:
                status_md  = f"❌ **Error:** {payload}"
            yield log, saved_path, status_md
        else:
            log += chunk
            yield log, "", ""

