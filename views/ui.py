# views/ui.py
"""
View layer.
Builds the entire Gradio UI layout — two tabs:
  Tab 1: 📥 Download  — URL input, yt-dlp streaming log
  Tab 2: 🎬 Annotate  — existing annotation workflow

No business logic. No ffmpeg. No CSV.
Imports handlers for event wiring only.
"""

import gradio as gr
from pathlib import Path

from config.settings import LABELS, VIDEO_DIR
from controllers.extractor import scan_videos
from models.annotation import build_segment_choices, get_stats
from views.handlers import (
    on_load_video,
    on_time_change,
    on_extract,
    on_segment_flush,
    on_segment_load,
    on_refresh,
    on_delete_request,
    on_confirm_delete,
    on_download_video,
)


# ── Static assets ──────────────────────────────────────────────

CUSTOM_CSS = """
/* ── Layout ── */
.gradio-container { max-width:100% !important; padding:10px !important; }
h1  { font-size:22px !important; margin:4px 0 !important; }
h2  { font-size:15px !important; margin:4px 0 !important; }
input, textarea { font-size:13px !important; padding:4px !important; }
button { font-size:13px !important; padding:7px 11px !important; }

/* ── Tab styling ── */
.tabs > .tab-nav { border-bottom: 2px solid #333 !important; }
.tabs > .tab-nav button {
    font-size   : 15px     !important;
    font-weight : 600      !important;
    padding     : 10px 20px !important;
    border-radius: 6px 6px 0 0 !important;
}
.tabs > .tab-nav button.selected {
    background  : #1a1a2e  !important;
    color       : #e2b714  !important;
    border-bottom: 2px solid #e2b714 !important;
}

/* ── Extract button ── */
.extract-btn button {
    font-size    : 17px    !important;
    padding      : 14px    !important;
    font-weight  : bold    !important;
    background   : #2e7d32 !important;
    color        : white   !important;
    border-radius: 8px     !important;
}
.extract-btn button:hover { background: #1b5e20 !important; }

/* ── Load button ── */
.load-btn button {
    background   : #1565c0 !important;
    color        : white   !important;
    font-size    : 14px    !important;
    padding      : 10px    !important;
    border-radius: 6px     !important;
}
.load-btn button:hover { background: #0d47a1 !important; }

/* ── Download button ── */
.download-btn button {
    background   : #6a1b9a !important;
    color        : white   !important;
    font-size    : 15px    !important;
    font-weight  : bold    !important;
    padding      : 12px    !important;
    border-radius: 8px     !important;
    width        : 100%    !important;
}
.download-btn button:hover { background: #4a148c !important; }

/* ── Go to Annotate button ── */
.goto-annotate-btn button {
    background   : #00695c !important;
    color        : white   !important;
    font-size    : 14px    !important;
    font-weight  : bold    !important;
    padding      : 11px    !important;
    border-radius: 8px     !important;
    width        : 100%    !important;
}
.goto-annotate-btn button:hover { background: #004d40 !important; }

/* ── Download log box ── */
.download-log textarea {
    font-family : monospace !important;
    font-size   : 12px      !important;
    background  : #0d1117   !important;
    color       : #c9d1d9   !important;
    border      : 1px solid #30363d !important;
    border-radius: 6px      !important;
}

/* ── Time inputs ── */
.time-input input {
    font-size  : 17px   !important;
    font-weight: bold   !important;
    text-align : center !important;
}

/* ── Path input ── */
.path-input input {
    font-family: monospace !important;
    font-size  : 12px      !important;
}

/* ── URL input ── */
.url-input input {
    font-family : monospace !important;
    font-size   : 13px      !important;
}

/* ── Delete button ── */
.delete-btn button {
    background : #c62828 !important;
    color      : white   !important;
    font-weight: bold    !important;
}
.delete-btn button:hover { background: #b71c1c !important; }

/* ── Confirm delete button ── */
.confirm-btn button {
    background : #b71c1c !important;
    color      : white   !important;
    font-weight: bold    !important;
    font-size  : 13px    !important;
}
.confirm-btn button:hover { background: #7f0000 !important; }

/* ── Cancel button ── */
.cancel-btn button {
    background : #424242 !important;
    color      : white   !important;
    font-size  : 13px    !important;
}
.cancel-btn button:hover { background: #212121 !important; }

/* ── Confirm HTML info box ── */
#confirm-html-box {
    border-radius: 8px;
    overflow     : hidden;
}
#confirm-html-box:not(:empty) {
    border    : 1px solid #c62828;
    padding   : 14px;
    margin    : 6px 0;
    background: #1e1e1e;
}

/* ── Delete status ── */
.delete-status p { font-size: 13px !important; margin-top: 4px !important; }
"""

CUSTOM_JS = """
let _mainVideo = null;

// ── Find the main player video (not preview) ──────────────────
function getMainVideo() {
    const all = document.querySelectorAll('video');
    return all.length > 0 ? all[0] : null;
}

// ── Find Extract button by ID first, text fallback ────────────
function findExtractBtn() {
    const byId = document.querySelector('#extract-btn button');
    if (byId) return byId;
    for (const btn of document.querySelectorAll('button')) {
        const txt = (btn.innerText || btn.textContent || '')
                        .trim().toUpperCase();
        if (txt.includes('EXTRACT')) return btn;
    }
    return null;
}

// ── Use React-compatible value setter ─────────────────────────
function setInputValue(input, value) {
    const descriptor = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype, 'value'
    );
    descriptor.set.call(input, value);
    input.dispatchEvent(new Event('input',  { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
}

// ── Flash feedback ────────────────────────────────────────────
function flash(el, color) {
    if (!el) return;
    const prev = el.style.backgroundColor;
    el.style.backgroundColor = color;
    setTimeout(() => el.style.backgroundColor = prev, 350);
}

// ── Shortcut handler ──────────────────────────────────────────
function setupShortcuts() {
    document.addEventListener('keydown', function(e) {

        // Never fire shortcuts when user is typing
        const tag = e.target.tagName.toUpperCase();
        if (tag === 'INPUT' || tag === 'TEXTAREA') return;
        if (e.target.isContentEditable) return;

        _mainVideo = getMainVideo();
        const k = e.key;

        // A — set start time
        if (k === 'a' || k === 'A') {
            e.preventDefault();
            if (!_mainVideo) return;
            const nums = document.querySelectorAll('input[type="number"]');
            if (nums[0]) {
                setInputValue(nums[0], _mainVideo.currentTime.toFixed(2));
                flash(nums[0], '#90EE90');
                console.log('[Shortcut] Start =', _mainVideo.currentTime.toFixed(2));
            }
        }

        // D — set end time
        if (k === 'd' || k === 'D') {
            e.preventDefault();
            if (!_mainVideo) return;
            const nums = document.querySelectorAll('input[type="number"]');
            if (nums[1]) {
                setInputValue(nums[1], _mainVideo.currentTime.toFixed(2));
                flash(nums[1], '#FFB6C1');
                console.log('[Shortcut] End =', _mainVideo.currentTime.toFixed(2));
            }
        }

        // E — trigger extraction
        if (k === 'e' || k === 'E') {
            e.preventDefault();
            const btn = findExtractBtn();
            if (btn) {
                flash(btn, '#90EE90');
                console.log('[Shortcut] E pressed — clicking Extract');
                btn.click();
            } else {
                console.warn('[Shortcut] Extract button not found in DOM');
            }
        }

        // Space — play/pause
        if (k === ' ') {
            e.preventDefault();
            if (!_mainVideo) return;
            _mainVideo.paused
                ? _mainVideo.play()
                : _mainVideo.pause();
        }

        // Arrow keys — seek
        if (k === 'ArrowLeft') {
            e.preventDefault();
            if (!_mainVideo) return;
            _mainVideo.currentTime = Math.max(
                0,
                _mainVideo.currentTime - (e.shiftKey ? 1 : 5)
            );
        }
        if (k === 'ArrowRight') {
            e.preventDefault();
            if (!_mainVideo) return;
            _mainVideo.currentTime = Math.min(
                _mainVideo.duration || 1e9,
                _mainVideo.currentTime + (e.shiftKey ? 1 : 5)
            );
        }
    });

    console.log('[VideoAnnotator] Keyboard shortcuts active');
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupShortcuts);
} else {
    setupShortcuts();
}
"""


def build_ui() -> gr.Blocks:
    """
    Construct and return the fully wired Gradio Blocks app.
    Called once from app.py.
    """
    all_videos = scan_videos()
    default_path = all_videos[0] if all_videos else ""
    video_list_md = (
        "**Available videos in dataset/:**\n\n" +
        "\n\n".join(f"`{p}`" for p in all_videos)
    ) if all_videos else "⚠️ No videos found in dataset/"

    init_choices, init_summary, init_seg_map = build_segment_choices()

    with gr.Blocks(title="Video Annotator") as app:

        gr.Markdown("# 🎬 Video Annotator")
        gr.HTML("""
        <div style="background:#667eea;color:white;padding:8px;
                    border-radius:5px;text-align:center;
                    font-size:12px;margin-bottom:6px;">
            <b>A</b>=Start &nbsp;|&nbsp; <b>D</b>=End &nbsp;|&nbsp;
            <b>E</b>=Extract &nbsp;|&nbsp;
            <b>Space</b>=Play/Pause &nbsp;|&nbsp;
            <b>←/→</b>=±5s &nbsp;|&nbsp;
            <b>Shift+←/→</b>=±1s
        </div>
        """)

        seg_map_state = gr.State(init_seg_map)

        # ── Two-tab layout ────────────────────────────────────────
        with gr.Tabs() as tabs:

            # ════════════════════════════════════════════════════
            #  TAB 1 — DOWNLOAD
            # ════════════════════════════════════════════════════
            with gr.Tab("📥 Download Video", id="tab-download"):

                gr.Markdown(
                    "### Download a video from YouTube or any URL\n"
                    f"Videos are saved directly to `dataset/` and immediately available for annotation."
                )

                with gr.Row():
                    url_input = gr.Textbox(
                        label="🔗 Video URL",
                        placeholder="https://www.youtube.com/watch?v=... or any direct video URL",
                        scale=5,
                        elem_classes=["url-input"]
                    )
                    download_btn = gr.Button(
                        "⬇️ Download",
                        scale=1,
                        elem_classes=["download-btn"]
                    )

                download_log = gr.Textbox(
                    label="📋 Download Log",
                    lines=14,
                    max_lines=14,
                    interactive=False,
                    placeholder="Download progress will appear here…",
                    elem_classes=["download-log"],
                    autoscroll=True,
                )

                download_status = gr.Markdown("")

                # Hidden state holding the downloaded path
                downloaded_path_state = gr.State("")

                with gr.Row(visible=False) as after_download_row:
                    goto_annotate_btn = gr.Button(
                        "🎬 Go to Annotate Tab →",
                        elem_classes=["goto-annotate-btn"]
                    )

                gr.Markdown(
                    "---\n"
                    "💡 **Tips:** Paste any YouTube, Vimeo, or direct `.mp4` URL.  \n"
                    "yt-dlp automatically picks the best quality and merges into MP4.  \n"
                    "After download, the video is auto-loaded in the **Annotate** tab."
                )

            # ════════════════════════════════════════════════════
            #  TAB 2 — ANNOTATE
            # ════════════════════════════════════════════════════
            with gr.Tab("🎬 Annotate", id="tab-annotate"):

                # ── Path input ───────────────────────────────────────────
                with gr.Row():
                    video_path_input = gr.Textbox(
                        label="📁 Video Path — paste full path, press Enter or Load",
                        value=default_path,
                        placeholder="/path/to/your/video.mp4",
                        scale=5,
                        elem_classes=["path-input"]
                    )
                    load_btn = gr.Button(
                        "📂 Load Video", scale=1,
                        elem_classes=["load-btn"]
                    )

                with gr.Accordion("📋 Available Videos (dataset/)", open=False) as avail_accordion:
                    avail_videos_md = gr.Markdown(video_list_md)

                # ── Main row ─────────────────────────────────────────────
                with gr.Row():
                    with gr.Column(scale=3):
                        video_player = gr.Video(
                            label="", height=400, show_label=False
                        )
                        video_status = gr.Markdown(
                            "*Enter a path above and click Load*"
                        )

                    with gr.Column(scale=2):
                        with gr.Row():
                            with gr.Column():
                                gr.Markdown("**Start (A)**")
                                start_num = gr.Number(
                                    label="", value=0, precision=2,
                                    show_label=False,
                                    elem_classes=["time-input"]
                                )
                            with gr.Column():
                                gr.Markdown("**End (D)**")
                                end_num = gr.Number(
                                    label="", value=10, precision=2,
                                    show_label=False,
                                    elem_classes=["time-input"]
                                )

                        duration_md = gr.Textbox(
                            label="Duration",
                            value="10.0s (00:00 → 00:10)",
                            interactive=False, max_lines=1
                        )

                        gr.Markdown("**🏷️ Rasa Label**")
                        label_radio = gr.Radio(
                            choices=LABELS, value=LABELS[0],
                            show_label=False
                        )

                        notes_text  = gr.Textbox(label="Notes", lines=2)

                        extract_btn = gr.Button(
                            "✂️ EXTRACT (E)", variant="primary", size="lg",
                            elem_classes=["extract-btn"],
                            elem_id="extract-btn"
                        )
                        result_md = gr.Markdown("")

                stats_md = gr.Markdown(get_stats())

                # ── Segments + Preview row ────────────────────────────────
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("## 📋 All Segments")

                        seg_summary_md = gr.Markdown(init_summary)

                        segment_radio = gr.Radio(
                            choices     = init_choices,
                            label       = "Select a segment",
                            value       = None,
                            interactive = True
                        )

                        with gr.Row():
                            refresh_btn = gr.Button("🔄 Refresh", scale=1)
                            delete_btn  = gr.Button(
                                "🗑️ Delete Selected",
                                scale        = 1,
                                elem_classes = ["delete-btn"]
                            )

                        delete_status_md = gr.Markdown(
                            "", elem_classes=["delete-status"]
                        )

                        # Single HTML block — renders segment info with
                        # zero Gradio framing.  Empty = no border shown.
                        confirm_html = gr.HTML(
                            "", elem_id="confirm-html-box"
                        )

                        # Confirm / Cancel buttons — hidden until delete clicked
                        with gr.Row(visible=False) as confirm_btn_row:
                            confirm_btn = gr.Button(
                                "✅ Yes, Delete Permanently",
                                scale        = 1,
                                elem_classes = ["confirm-btn"]
                            )
                            cancel_btn = gr.Button(
                                "❌ Cancel",
                                scale        = 1,
                                elem_classes = ["cancel-btn"]
                            )

                        confirm_id_state = gr.State("")

                    with gr.Column(scale=1):
                        gr.Markdown("## 👁️ Preview")
                        preview_info  = gr.Markdown(
                            "*Select a segment from the list*"
                        )
                        preview_audio = gr.Audio(
                            label="Audio", type="filepath"
                        )
                        preview_video = gr.Video(label="Video", height=200)

        # ── Event wiring — Annotate tab ───────────────────────────
        _load_outputs = [
            video_player, video_status,
            start_num, end_num, duration_md, result_md
        ]

        load_btn.click(on_load_video, [video_path_input], _load_outputs)
        video_path_input.submit(on_load_video, [video_path_input], _load_outputs)

        start_num.change(on_time_change, [start_num, end_num], [duration_md])
        end_num.change(on_time_change,   [start_num, end_num], [duration_md])

        extract_btn.click(
            on_extract,
            [video_path_input, start_num, end_num, label_radio, notes_text],
            [result_md, stats_md, segment_radio, seg_summary_md, seg_map_state]
        )

        (
            segment_radio.change(
                on_segment_flush,
                [segment_radio, seg_map_state],
                [preview_audio, preview_video, preview_info]
            )
            .then(
                on_segment_load,
                [segment_radio, seg_map_state],
                [preview_audio, preview_video, preview_info]
            )
        )

        refresh_btn.click(
            on_refresh,
            [seg_map_state],
            [segment_radio, seg_summary_md, seg_map_state]
        )

        # ── Delete flow ────────────────────────────────────────
        def _populate_confirm(display_str, seg_map):
            if not display_str:
                return "", "", gr.update(visible=False)
            from models.annotation import get_segment_info_for_confirmation
            html, target_id = get_segment_info_for_confirmation(
                display_str, seg_map
            )
            return html, target_id, gr.update(visible=bool(target_id))

        delete_btn.click(
            fn      = _populate_confirm,
            inputs  = [segment_radio, seg_map_state],
            outputs = [confirm_html, confirm_id_state, confirm_btn_row]
        )

        confirm_btn.click(
            fn      = on_confirm_delete,
            inputs  = [confirm_id_state],
            outputs = [
                delete_status_md,
                segment_radio,
                seg_summary_md,
                seg_map_state,
                stats_md,
                preview_audio,
                preview_video,
                preview_info,
                confirm_html,
                confirm_id_state,
            ]
        ).then(
            fn      = lambda: gr.update(visible=False),
            inputs  = [],
            outputs = [confirm_btn_row]
        )

        cancel_btn.click(
            fn      = lambda: ("", ""),
            inputs  = [],
            outputs = [confirm_html, confirm_id_state]
        ).then(
            fn      = lambda: gr.update(visible=False),
            inputs  = [],
            outputs = [confirm_btn_row]
        )

        app.load(
            on_load_video,
            [video_path_input],
            _load_outputs
        )

        # ── Event wiring — Download tab ───────────────────────────

        def _refresh_video_list():
            """Re-scan dataset/ and return updated markdown."""
            videos = scan_videos()
            if videos:
                return (
                    "**Available videos in dataset/:**\n\n" +
                    "\n\n".join(f"`{p}`" for p in videos)
                )
            return "⚠️ No videos found in dataset/"

        # Download button → streaming log
        download_btn.click(
            fn      = on_download_video,
            inputs  = [url_input],
            outputs = [download_log, downloaded_path_state, download_status],
        ).then(
            # Show "Go to Annotate" button if we got a path
            fn      = lambda path: gr.update(visible=bool(path)),
            inputs  = [downloaded_path_state],
            outputs = [after_download_row],
        ).then(
            # Auto-populate path input in Annotate tab
            fn      = lambda path: path,
            inputs  = [downloaded_path_state],
            outputs = [video_path_input],
        ).then(
            # Auto-load video into player
            fn      = on_load_video,
            inputs  = [video_path_input],
            outputs = _load_outputs,
        ).then(
            # Refresh "Available Videos" list
            fn      = _refresh_video_list,
            inputs  = [],
            outputs = [avail_videos_md],
        )

        # "Go to Annotate" button — switch tab programmatically
        # (Gradio doesn't have a direct tab-switch API, so we
        #  use a JS trick via gr.update on the Tabs component)
        goto_annotate_btn.click(
            fn      = lambda: gr.update(selected="tab-annotate"),
            inputs  = [],
            outputs = [tabs],
        )

    return app
