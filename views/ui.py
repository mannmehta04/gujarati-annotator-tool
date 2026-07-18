# views/ui.py
"""
View layer.
Builds the entire Gradio UI layout — two tabs:
  Tab 1: 📥 Download  — URL input, yt-dlp streaming log  [UNCHANGED]
  Tab 2: 🎬 Annotate  — source mode toggle (Local Folder / URL) + annotation

No business logic. No ffmpeg. No CSV.
Imports handlers for event wiring only.
"""

import gradio as gr
from pathlib import Path

from config.settings import LABELS, VIDEO_DIR
from controllers.extractor import scan_videos
from models.annotation import get_stats
from views.handlers import (
    # Existing annotation handlers
    on_load_video,
    on_time_change,
    on_extract,
    
    # New Extracted Segments Handlers
    handle_segment_row_selected,
    handle_fetch_supabase_segments,
    handle_view_mode_changed,
    handle_rasa_filter_changed,
    handle_delete_segment,
    handle_show_delete_confirm,
    handle_cancel_delete_confirm,
    handle_analyse_spectrum,
    _build_rasa_filter_choices,
    _build_view_mode_choices,
    _build_table_headers,
    _build_table_datatypes,
    
    # Download tab handler
    handle_fetch_video_info_with_progress,
    handle_update_download_link,
    # Source mode handlers
    handle_source_toggle,
    handle_load_folder,
    handle_avail_video_select,
    handle_load_url,
    scan_folder_full,
    handle_clear_video,
)

# Removed module-level cache load to prevent stale state on hot-reload


# ── Static assets ──────────────────────────────────────────────

_HIDE_FOOTER_CSS = """
/* Hide Gradio footer elements */
footer {
    display: none !important;
}

/* Hide 'Built with Gradio' */
.built-with-gradio {
    display: none !important;
}

/* Hide 'Use via API' button */
.api-docs-button {
    display: none !important;
}

/* Hide settings gear icon */
.settings-button {
    display: none !important;
}

/* Hide the entire footer bar */
gradio-app > div > footer,
.footer,
#footer {
    display: none !important;
}

/* Gradio 4.x specific selectors */
.gr-footer,
[class*="footer"],
[id*="footer"] {
    display: none !important;
}
"""

CUSTOM_CSS = _HIDE_FOOTER_CSS + """
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

/* ── Download button (Download tab) ── */
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

/* ── URL input ── */
.url-input input {
    font-family : monospace !important;
    font-size   : 13px      !important;
}

/* ── Load URL button (Annotate tab) ── */
.load-url-btn button {
    background   : #6a1b9a !important;
    color        : white   !important;
    font-size    : 13px    !important;
    padding      : 9px     !important;
    border-radius: 6px     !important;
}
.load-url-btn button:hover { background: #4a148c !important; }

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
    # Scan dataset/ for the Available Videos accordion initial state.
    # These full paths are shown in the accordion but no auto-load happens.
    all_videos = scan_videos()

    with gr.Blocks(title="Video Annotator") as app:

        gr.Markdown("# 🎬 Video Annotator")
        
        segments_data_state = gr.State(None)

        # ── Two-tab layout ────────────────────────────────────────
        with gr.Tabs() as tabs:

            # ════════════════════════════════════════════════════
            #  TAB 1 — DOWNLOAD
            # ════════════════════════════════════════════════════
            with gr.Tab("📥 Download Video", id="tab-download"):

                gr.Markdown(
                    "### Download a video directly to your device\n"
                    f"Videos stream through the server and are saved directly to your browser's download folder. Zero server storage."
                )

                # Row 1: URL Input
                url_input = gr.Textbox(
                    label="🔗 Video URL",
                    placeholder="Paste YouTube or video URL here...",
                    lines=1,
                    elem_classes=["url-input"]
                )

                # Row 2: Fetch Info Button + Status
                fetch_info_btn = gr.Button("🔍 Fetch Video Info", variant="secondary")
                
                fetch_progress = gr.HTML(
                    value="",       # Empty on init — not shown until search starts
                    visible=False,  # Hidden initially — shown only during fetch
                )
                
                fetch_status = gr.Markdown(value="", visible=False)

                # Row 3: Video Info Display (shown after fetch)
                video_info_display = gr.HTML(value="", visible=False)

                # Row 4: Download Options (shown after fetch)
                with gr.Group(visible=False) as download_options_group:
                    
                    # Format selector — populated after fetch, shows specific format IDs
                    format_selector = gr.Dropdown(
                        choices=[],
                        value=None,
                        label="🎬 Specific Format (optional — overrides Quality if selected)",
                        interactive=True,
                        allow_custom_value=False,
                    )

                # Download link — this is what triggers the actual browser download
                # Using gr.HTML to render an <a> tag with the download URL
                download_link_html = gr.HTML(value="", visible=False)

            # ════════════════════════════════════════════════════
            #  TAB 2 — ANNOTATE
            # ════════════════════════════════════════════════════
            with gr.Tab("🎬 Annotate", id="tab-annotate"):

                # ── Session state ─────────────────────────────────────
                # source_state: resolved local path or stream URL fed to extractor.
                # Starts empty — no auto-load on page open (Fix 4).
                source_state = gr.State("")

                # folder_state: current folder path (Local Folder mode only)
                folder_state = gr.State("")
                
                # available_videos_state: stores the available videos list across tab switches
                available_videos_state = gr.State([])

                # ── Source mode toggle ────────────────────────────────
                gr.Markdown("### 📂 Video Source")
                source_mode_radio = gr.Radio(
                    choices=["Local Folder", "URL"],
                    value="Local Folder",
                    label="Source Mode",
                    show_label=False,
                    interactive=True,
                )

                # ── LOCAL FOLDER section (visible by default) ─────────
                with gr.Column(visible=True) as folder_section:
                    # gr.File with file_count="directory" opens the OS folder picker.
                    # Gradio 4.x returns a list of file objects; we derive the
                    # folder path from os.path.dirname(files[0].name) in the handler.
                    folder_picker = gr.File(
                        label="📁 Select Folder",
                        file_count="directory",
                        file_types=None,   # accept everything; we filter in handler
                    )

                # ── URL STREAMING section (hidden by default) ─────────
                with gr.Column(visible=False) as url_section:
                    with gr.Row():
                        annotate_url_input = gr.Textbox(
                            label="🔗 Video URL",
                            placeholder="https://example.com/video.mp4  or  https://youtube.com/watch?v=...",
                            scale=5,
                            elem_classes=["url-input"],
                        )
                        load_url_btn = gr.Button(
                            "▶️ Load URL",
                            scale=1,
                            elem_classes=["load-url-btn"],
                        )

                # ── Available Videos accordion ─────────────────────────
                # Populated when the user selects a folder via the folder picker.
                # Items are full absolute paths — clicking one loads the video.
                # Starts empty (no auto-scan on page open — Fix 4).
                with gr.Accordion("📋 Available Videos", open=False, visible=False) as avail_accordion:
                    avail_radio = gr.Radio(
                        choices=all_videos,   # full paths from dataset/ — read-only initial list
                        label="Click a video to load it",
                        value=None,
                        interactive=True,
                    )

                # ── Main row — video player + annotation controls ─────
                with gr.Row():
                    with gr.Column(scale=3):
                        # Local file mode player (gr.Video).
                        # Visible by default (Local Folder mode is default).
                        # IMPORTANT: Never pass a stream URL to this component —
                        # Gradio proxies gr.Video URLs through /tmp/gradio/, downloading
                        # the entire stream to server disk. Only local file paths go here.
                        video_player = gr.Video(
                            label="", height=400, show_label=False,
                            value=None, visible=True
                        )

                        clear_video_btn = gr.Button(
                            value="🗑️ Clear Video", variant="secondary", size="sm", visible=True
                        )

                        # URL mode player (gr.HTML with native HTML5 <video> tag).
                        # Hidden by default; shown when source mode = "URL".
                        # The browser fetches the stream URL directly — zero server
                        # disk usage. Gradio's caching pipeline is bypassed entirely.
                        url_player = gr.HTML(
                            value="",
                            visible=True,
                        )

                        video_status = gr.Markdown(
                            "*Choose a source above and load a video*"
                        )

                    with gr.Column(scale=2):
                        shortcuts_display = gr.HTML(
                            value="""
                            <details style="
                                background: #1a1a2e;
                                border: 1px solid #2d2d4e;
                                border-radius: 10px;
                                padding: 0;
                                margin: 8px 0;
                                overflow: hidden;
                            ">
                                <summary style="
                                    padding: 10px 16px;
                                    cursor: pointer;
                                    font-size: 13px;
                                    font-weight: 600;
                                    color: #a0a0c0;
                                    user-select: none;
                                    display: flex;
                                    align-items: center;
                                    gap: 8px;
                                    list-style: none;
                                ">
                                    ⌨️ Keyboard Shortcuts
                                    <span style="font-size:10px; color:#666; font-weight:400; margin-left:auto;">
                                        click to expand
                                    </span>
                                </summary>
                                <div style="
                                    padding: 12px 16px;
                                    display: grid;
                                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                                    gap: 8px;
                                ">
                                    <div style="
                                        background: #0f0f1a;
                                        border-radius: 8px;
                                        padding: 10px 12px;
                                        display: flex;
                                        align-items: center;
                                        gap: 10px;
                                    ">
                                        <kbd style="
                                            background: #2d2d4e;
                                            color: #e0e0ff;
                                            border: 1px solid #4d4d7e;
                                            border-bottom: 3px solid #4d4d7e;
                                            border-radius: 5px;
                                            padding: 3px 8px;
                                            font-size: 12px;
                                            font-family: monospace;
                                            white-space: nowrap;
                                        ">A</kbd>
                                        <span style="font-size:12px; color:#c0c0e0;">
                                            Start Time
                                        </span>
                                    </div>
                                    <div style="
                                        background: #0f0f1a;
                                        border-radius: 8px;
                                        padding: 10px 12px;
                                        display: flex;
                                        align-items: center;
                                        gap: 10px;
                                    ">
                                        <kbd style="
                                            background: #2d2d4e;
                                            color: #e0e0ff;
                                            border: 1px solid #4d4d7e;
                                            border-bottom: 3px solid #4d4d7e;
                                            border-radius: 5px;
                                            padding: 3px 8px;
                                            font-size: 12px;
                                            font-family: monospace;
                                            white-space: nowrap;
                                        ">D</kbd>
                                        <span style="font-size:12px; color:#c0c0e0;">
                                            End Time
                                        </span>
                                    </div>
                                    <div style="
                                        background: #0f0f1a;
                                        border-radius: 8px;
                                        padding: 10px 12px;
                                        display: flex;
                                        align-items: center;
                                        gap: 10px;
                                    ">
                                        <kbd style="
                                            background: #2d2d4e;
                                            color: #e0e0ff;
                                            border: 1px solid #4d4d7e;
                                            border-bottom: 3px solid #4d4d7e;
                                            border-radius: 5px;
                                            padding: 3px 8px;
                                            font-size: 12px;
                                            font-family: monospace;
                                            white-space: nowrap;
                                        ">E</kbd>
                                        <span style="font-size:12px; color:#c0c0e0;">
                                            Extract
                                        </span>
                                    </div>
                                    <div style="
                                        background: #0f0f1a;
                                        border-radius: 8px;
                                        padding: 10px 12px;
                                        display: flex;
                                        align-items: center;
                                        gap: 10px;
                                    ">
                                        <kbd style="
                                            background: #2d2d4e;
                                            color: #e0e0ff;
                                            border: 1px solid #4d4d7e;
                                            border-bottom: 3px solid #4d4d7e;
                                            border-radius: 5px;
                                            padding: 3px 8px;
                                            font-size: 12px;
                                            font-family: monospace;
                                            white-space: nowrap;
                                        ">Space</kbd>
                                        <span style="font-size:12px; color:#c0c0e0;">
                                            Play/Pause
                                        </span>
                                    </div>
                                    <div style="
                                        background: #0f0f1a;
                                        border-radius: 8px;
                                        padding: 10px 12px;
                                        display: flex;
                                        align-items: center;
                                        gap: 10px;
                                    ">
                                        <kbd style="
                                            background: #2d2d4e;
                                            color: #e0e0ff;
                                            border: 1px solid #4d4d7e;
                                            border-bottom: 3px solid #4d4d7e;
                                            border-radius: 5px;
                                            padding: 3px 8px;
                                            font-size: 12px;
                                            font-family: monospace;
                                            white-space: nowrap;
                                        ">←/→</kbd>
                                        <span style="font-size:12px; color:#c0c0e0;">
                                            Seek ±5s
                                        </span>
                                    </div>
                                    <div style="
                                        background: #0f0f1a;
                                        border-radius: 8px;
                                        padding: 10px 12px;
                                        display: flex;
                                        align-items: center;
                                        gap: 10px;
                                    ">
                                        <kbd style="
                                            background: #2d2d4e;
                                            color: #e0e0ff;
                                            border: 1px solid #4d4d7e;
                                            border-bottom: 3px solid #4d4d7e;
                                            border-radius: 5px;
                                            padding: 3px 8px;
                                            font-size: 12px;
                                            font-family: monospace;
                                            white-space: nowrap;
                                        ">Shift+←/→</kbd>
                                        <span style="font-size:12px; color:#c0c0e0;">
                                            Seek ±1s
                                        </span>
                                    </div>
                                </div>
                            </details>
                            """,
                            visible=True,
                        )
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
                        
                        video_name_input = gr.Textbox(
                            label="Video Name (for ID)",
                            value="",
                            placeholder="Enter a video name (Required)",
                            info="Required for extraction",
                            lines=1
                        )

                        notes_text = gr.Textbox(label="Notes", lines=2)

                        extract_btn = gr.Button(
                            "✂️ EXTRACT (E)", variant="primary", size="lg",
                            elem_classes=["extract-btn"],
                            elem_id="extract-btn"
                        )
                        result_md = gr.Markdown("")
                        cloud_sync_status_md = gr.Markdown("", visible=False)

                stats_md = gr.Markdown(get_stats())

            # ════════════════════════════════════════════════════
            #  TAB 3 — EXTRACTED SEGMENTS
            # ════════════════════════════════════════════════════
            # ══════════════════════════════════════════════════════════
            #  EXTRACTED SEGMENTS TAB (Supabase)
            # ══════════════════════════════════════════════════════════
            with gr.Tab("📊 Extracted Segments", id="extracted_tab"):
                gr.Markdown("# 📊 Extracted Segments (Supabase)")
                selected_segment_id = gr.State("")

                gr.Markdown("View, filter, and download your extracted video and audio segments synced from Supabase.")
                
                with gr.Row(variant="panel"):
                    refresh_supabase_btn = gr.Button("🔄 Refresh from Supabase", variant="primary", scale=1)
                    
                supabase_status_display = gr.HTML("")
                
                with gr.Group(visible=False) as segments_summary_group:
                    segments_summary_html = gr.HTML("")
                    
                with gr.Group(visible=False) as segments_filter_group:
                    with gr.Row():
                        view_mode_radio = gr.Radio(
                            choices=_build_view_mode_choices(),
                            value="All Segments",
                            label="View Mode",
                            interactive=True,
                        )
                        with gr.Column():
                            rasa_filter_dropdown = gr.Dropdown(
                                choices=_build_rasa_filter_choices(),
                                value="All",
                                label="Filter by Rasa",
                                visible=False
                            )
                        segments_count_html = gr.HTML("")
                        
                with gr.Group(visible=False) as segments_table_group:
                    segments_dataframe = gr.Dataframe(
                        headers=_build_table_headers(),
                        datatype=_build_table_datatypes(),
                        interactive=False,
                        wrap=True
                    )
                    
                with gr.Group(visible=False) as segment_detail_group:
                    segment_detail_html = gr.HTML("")
                    with gr.Row():
                        video_preview = gr.HTML(label="Video Preview", visible=False)
                        audio_preview = gr.Audio(
                            value=None,
                            label="Audio Preview",
                            type="filepath",
                            interactive=False,
                            visible=False,
                            waveform_options=gr.WaveformOptions(
                                waveform_color="#7eb8f7",
                                waveform_progress_color="#3b82f6",
                                trim_region_color="#f59e0b22",
                                # show_controls=True,
                            ),
                            # show_download_button=False,
                        )
                    # ── Spectrogram Analysis Section ──────────────────────────────────
                    # Added inside detail_group, below download_links_html,
                    # above the close/delete button row

                    # ── Spectral Analysis Section ──────────────────────────────────────
                    gr.HTML("""
                    <div style="
                        margin: 18px 0 10px 0;
                        padding: 14px 18px 10px 18px;
                        background: linear-gradient(135deg, #0f1f3d 0%, #1a1a2e 100%);
                        border-radius: 12px;
                        border: 1px solid #2d4a7a;
                        border-left: 4px solid #7eb8f7;
                    ">
                        <div style="
                            display: flex;
                            align-items: center;
                            gap: 10px;
                            margin-bottom: 4px;
                        ">
                            <span style="font-size: 20px;">📊</span>
                            <div>
                                <div style="
                                    font-size: 14px;
                                    font-weight: 700;
                                    color: #e0e8ff;
                                    letter-spacing: 0.3px;
                                ">Spectral Analysis</div>
                                <div style="
                                    font-size: 11px;
                                    color: #6b82a8;
                                    margin-top: 2px;
                                ">
                                    Computes normalized spectrum with 95% CI across
                                    sampled segments — extracts audio on demand
                                </div>
                            </div>
                        </div>
                    </div>
                    """)

                    analyse_spectrum_btn = gr.Button(
                        "📊  Analyse Spectrum",
                        variant="primary",
                        size="lg",
                        elem_id="analyse_spectrum_btn",
                        elem_classes=["natak-analyse-btn"],
                    )

                    gr.HTML("""
                    <style>
                    /* Analyse Spectrum button — enhanced styling */
                    #analyse_spectrum_btn button,
                    .natak-analyse-btn button {
                        background: linear-gradient(135deg, #1d4ed8 0%, #1e40af 50%, #1d3a8a 100%) !important;
                        border: 1.5px solid #3b82f6 !important;
                        border-radius: 10px !important;
                        color: #ffffff !important;
                        font-size: 15px !important;
                        font-weight: 700 !important;
                        letter-spacing: 0.5px !important;
                        padding: 14px 28px !important;
                        box-shadow:
                            0 4px 15px rgba(59, 130, 246, 0.35),
                            0 2px 6px rgba(0, 0, 0, 0.4),
                            inset 0 1px 0 rgba(255,255,255,0.1) !important;
                        transition: all 0.2s ease !important;
                        width: 100% !important;
                    }

                    #analyse_spectrum_btn button:hover,
                    .natak-analyse-btn button:hover {
                        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 50%, #1e40af 100%) !important;
                        border-color: #60a5fa !important;
                        box-shadow:
                            0 6px 20px rgba(59, 130, 246, 0.5),
                            0 3px 8px rgba(0, 0, 0, 0.4),
                            inset 0 1px 0 rgba(255,255,255,0.15) !important;
                        transform: translateY(-1px) !important;
                    }

                    #analyse_spectrum_btn button:active,
                    .natak-analyse-btn button:active {
                        transform: translateY(0px) !important;
                        box-shadow:
                            0 2px 8px rgba(59, 130, 246, 0.3),
                            0 1px 3px rgba(0, 0, 0, 0.4) !important;
                    }
                    </style>
                    """)

                    # Spectrogram result group — hidden until analysis completes
                    with gr.Group(visible=False) as spectrogram_group:

                        spectrogram_status = gr.Markdown(
                            value="",
                            visible=False,
                        )

                        spectrogram_image = gr.Image(
                            value=None,
                            label="Spectral Analysis",
                            type="filepath",
                            interactive=False,
                            visible=False,
                            # show_download_button=True,
                            show_label=True,
                            elem_id="spectrogram_image_display",
                        )

                    # Status shown outside the group so errors are always visible
                    spectrogram_status_outer = gr.Markdown(
                        value="",
                        visible=False,
                    )
                    # ── End Spectrogram Analysis Section ─────────────────────────────

                    with gr.Row():
                        delete_segment_btn = gr.Button("🗑️ Delete this Segment", variant="stop", visible=False)
                        close_detail_btn = gr.Button("❌ Close Details", variant="secondary")

        # ── Delete Confirmation Popup Overlay ─────────────────────────────
        delete_popup_html = gr.HTML(
            value="",   # empty = hidden layer
            visible=True,
            elem_id="delete_popup_overlay",
        )

        # Hidden proxy elements that our inline JavaScript looks for to bridge workflows
        with gr.Row(
            visible=True,
            elem_id="delete_popup_btn_row",
            elem_classes=["natak-hidden-btn-row"],
        ):
            confirm_delete_btn = gr.Button(
                "confirm_delete_hidden",
                variant="stop",
                elem_id="confirm_delete_hidden_btn",  # <-- Must match your JS query exactly
                elem_classes=["natak-hidden-btn"],
            )
            cancel_delete_btn = gr.Button(
                "cancel_delete_hidden",
                variant="secondary",
                elem_id="cancel_delete_hidden_btn",   # <-- Must match your JS query exactly
                elem_classes=["natak-hidden-btn"],
            )
            
        gr.HTML("""
<style>
.natak-hidden-btn-row {
    position: absolute !important;
    width: 1px !important;
    height: 1px !important;
    padding: 0 !important;
    margin: -1px !important;
    overflow: hidden !important;
    clip: rect(0,0,0,0) !important;
    white-space: nowrap !important;
    border: 0 !important;
    opacity: 0 !important;
    pointer-events: none !important;
}
.natak-hidden-btn {
    position: absolute !important;
    opacity: 0 !important;
    pointer-events: none !important;
    width: 1px !important;
    height: 1px !important;
}
</style>
""")
        # ══════════════════════════════════════════════════════════
        #  EVENT WIRING — DOWNLOAD TAB
        # ══════════════════════════════════════════════════════════

        # Fetch Info button click
        fetch_info_btn.click(
            fn=handle_fetch_video_info_with_progress,
            inputs=[url_input],
            outputs=[
                fetch_progress,          
                fetch_status,            
                video_info_display,      
                download_options_group,  
                format_selector,         
                download_link_html,      
            ],
        )

        _download_link_inputs = [url_input, format_selector]
        _download_link_outputs = [download_link_html]
        
        format_selector.change(
            fn=handle_update_download_link,
            inputs=_download_link_inputs,
            outputs=_download_link_outputs,
        )


        # ══════════════════════════════════════════════════════════
        #  EVENT WIRING — ANNOTATE TAB
        # ══════════════════════════════════════════════════════════

        # Shared load outputs tuple used by multiple handlers
        _load_outputs = [
            video_player, video_status,
            start_num, end_num, duration_md, result_md
        ]

        # ── Source mode toggle ────────────────────────────────────
        source_mode_radio.change(
            fn      = handle_source_toggle,
            inputs  = [source_mode_radio, available_videos_state],
            outputs = [folder_section, url_section, video_player, url_player, avail_accordion, clear_video_btn, avail_radio],
        )

        # ── Local Folder: folder picker fires on selection ────────
        folder_picker.change(
            fn      = handle_load_folder,
            inputs  = [folder_picker],
            outputs = [avail_radio, folder_state, avail_accordion, available_videos_state],
        )

        # ── Available Videos radio: clicking a video loads it ─────
        avail_radio.change(
            fn      = handle_avail_video_select,
            inputs  = [avail_radio],
            outputs = _load_outputs + [source_state],
        )

        # ── Clear Video ───────────────────────────────────────────
        clear_video_btn.click(
            fn      = handle_clear_video,
            inputs  = [],
            outputs = [video_player, source_state, avail_radio],
        )

        # ── URL mode: Load URL button ─────────────────────────────
        _url_load_outputs = [
            url_player,   
            video_status,
            start_num, end_num, duration_md, result_md
        ]
        load_url_btn.click(
            fn      = handle_load_url,
            inputs  = [annotate_url_input],
            outputs = _url_load_outputs + [source_state],
        )

        # ── Time inputs ───────────────────────────────────────────
        start_num.change(on_time_change, [start_num, end_num], [duration_md])
        end_num.change(on_time_change,   [start_num, end_num], [duration_md])

        # ── Extract ───────────────────────────────────────────────
        extract_btn.click(
            fn      = on_extract,
            inputs  = [source_state, start_num, end_num, video_name_input, label_radio, notes_text, segments_data_state],
            outputs = [result_md, stats_md, cloud_sync_status_md, segments_data_state],
        )


        # ══════════════════════════════════════════════════════════
        #  EVENT WIRING — EXTRACTED SEGMENTS TAB (Supabase)
        # ══════════════════════════════════════════════════════════

        _load_supabase_outputs = [
            supabase_status_display,
            segments_data_state,
            segments_dataframe,
            segments_summary_html,
        ]
        
        refresh_supabase_btn.click(
            fn=handle_fetch_supabase_segments,
            inputs=[segments_data_state],
            outputs=_load_supabase_outputs
        ).then(
            fn=lambda: gr.update(visible=True),
            outputs=[segments_summary_group]
        ).then(
            fn=lambda: gr.update(visible=True),
            outputs=[segments_filter_group]
        ).then(
            fn=lambda: gr.update(visible=True),
            outputs=[segments_table_group]
        ).then(
            fn=handle_view_mode_changed,
            inputs=[view_mode_radio, rasa_filter_dropdown, segments_data_state],
            outputs=[segments_dataframe, segments_count_html, rasa_filter_dropdown]
        )
        
        view_mode_radio.change(
            fn=handle_view_mode_changed,
            inputs=[view_mode_radio, rasa_filter_dropdown, segments_data_state],
            outputs=[segments_dataframe, segments_count_html, rasa_filter_dropdown]
        )
        
        rasa_filter_dropdown.change(
            fn=handle_rasa_filter_changed,
            inputs=[view_mode_radio, rasa_filter_dropdown, segments_data_state],
            outputs=[segments_dataframe, segments_count_html, rasa_filter_dropdown]
        )
        
        segments_dataframe.select(
            fn=handle_segment_row_selected,
            inputs=[segments_data_state, view_mode_radio, rasa_filter_dropdown],
            outputs=[
                segment_detail_group, 
                segment_detail_html, 
                video_preview, 
                audio_preview, 
                selected_segment_id
            ]
        ).then(
            fn=lambda: gr.update(visible=True),
            outputs=[delete_segment_btn]
        )
        
        close_detail_btn.click(
            fn=lambda: (
                gr.update(visible=False), 
                gr.update(value=""),
                gr.update(value=None, visible=False),  # spectrogram_image
                gr.update(value="", visible=False),    # spectrogram_status_outer
                gr.update(visible=False),              # spectrogram_group
            ),
            outputs=[
                segment_detail_group, 
                delete_popup_html,
                spectrogram_image,
                spectrogram_status_outer,
                spectrogram_group,
            ]
        )
        # COUNT inputs: 0, COUNT outputs: 5
        
        analyse_spectrum_btn.click(
            fn=handle_analyse_spectrum,
            inputs=[
                selected_segment_id,   # segment id
                segments_data_state,   # full segments dict
            ],
            outputs=[
                spectrogram_image,           # 1 — PNG image
                spectrogram_status_outer,    # 2 — status message (outside group)
                spectrogram_group,           # 3 — group visible on success
            ],
            show_progress="minimal",
        )
        # COUNT inputs: 2, COUNT outputs: 3
        
        delete_segment_btn.click(
            fn=handle_show_delete_confirm,
            inputs=[selected_segment_id, segments_data_state],
            outputs=[
                delete_popup_html,
                supabase_status_display,
            ]
        )
        # COUNT inputs: 2, COUNT outputs: 2
        
        cancel_delete_btn.click(
            fn=handle_cancel_delete_confirm,
            inputs=[],
            outputs=[
                delete_popup_html,
                supabase_status_display,
            ]
        )
        # COUNT inputs: 0, COUNT outputs: 2
        
        confirm_delete_btn.click(
            fn=handle_delete_segment,
            inputs=[selected_segment_id, segments_data_state, view_mode_radio, rasa_filter_dropdown],
            outputs=[
                delete_popup_html,           # 1
                supabase_status_display,     # 2
                segments_data_state,         # 3
                segments_dataframe,          # 4
                segments_count_html,         # 5
                segment_detail_group,        # 6
                segment_detail_html,         # 7
                video_preview,               # 8
                audio_preview,               # 9
                delete_segment_btn,          # 10
                spectrogram_image,           # 11
                spectrogram_status_outer,    # 12
                spectrogram_group,           # 13
            ]
        ).then(
            fn=handle_fetch_supabase_segments,
            inputs=[segments_data_state],
            outputs=_load_supabase_outputs
        )

    return app
