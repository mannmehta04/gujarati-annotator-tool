import re

with open('/home/mann/gujarati-natak/views/ui.py', 'r') as f:
    content = f.read()

# 1. Remove `build_segment_choices` from models.annotation import
content = re.sub(r'build_segment_choices,\s*', '', content)

# 2. Add new handlers to import from views.handlers
content = content.replace(
    'from views.handlers import (',
    'from views.handlers import (\n    handle_load_sheet,\n    handle_filter_segments,\n    handle_segment_selected,\n    handle_refresh_sheet,'
)

# 3. Add states at the beginning of gr.Blocks
blocks_start = '    with gr.Blocks(title="Video Annotator") as app:\n\n        gr.Markdown("# 🎬 Video Annotator")\n'
new_states = """
        # --- Shared Cloud Sync States ---
        cloud_config_state = gr.State({'enabled': False})
        sheet_csv_url_state = gr.State("")
        segments_data_state = gr.State(None)
"""
content = content.replace(blocks_start, blocks_start + new_states)

# 4. Remove init_choices and seg_map_state
content = re.sub(r'\s*init_choices, init_summary, init_seg_map = build_segment_choices\(\)\n', '', content)
content = re.sub(r'\s*seg_map_state = gr\.State\(init_seg_map\)\n', '', content)

# 5. Replace "All Segments" UI and add `cloud_sync_status_md`
# The "All Segments" row starts at `# ── Segments + Preview row ───`
# It ends right before `# ══════════════════════════════════════════════════════════\n        #  EVENT WIRING — DOWNLOAD TAB`

segments_ui_regex = re.compile(
    r'([ \t]+)# ── Segments \+ Preview row ─+.*?(?=[ \t]+# ══════════════════════════════════════════════════════════\n[ \t]+#  EVENT WIRING — DOWNLOAD TAB)',
    re.DOTALL
)

cloud_sync_md_and_new_tab = """
                cloud_sync_status_md = gr.Markdown(value="", visible=False)

            # ════════════════════════════════════════════════════
            #  TAB 3 — EXTRACTED SEGMENTS
            # ════════════════════════════════════════════════════
            with gr.Tab("📊 Extracted Segments", id="tab-segments"):
                gr.Markdown("## 📊 Cloud Sync & Segments")
                
                with gr.Row():
                    sheet_read_url = gr.Textbox(
                        label="Cloud Sheet URL (Read-Only CSV/Published Link)",
                        placeholder="https://docs.google.com/spreadsheets/d/.../edit or .csv link",
                        scale=3
                    )
                    sheet_write_url = gr.Textbox(
                        label="Apps Script Web App URL (For Writing - Optional)",
                        placeholder="https://script.google.com/macros/s/.../exec",
                        scale=2
                    )
                    load_sheet_btn = gr.Button("🔄 Load / Refresh Sheet", variant="primary", scale=1)
                
                sheet_status_display = gr.Markdown("*No sheet loaded. Enter a URL above and click Load.*")
                
                with gr.Group(visible=False) as segments_summary_group:
                    segments_summary_html = gr.HTML("")
                    
                with gr.Group(visible=False) as segments_filter_group:
                    with gr.Row():
                        view_mode_radio = gr.Radio(
                            choices=["All Segments", "By Rasa", "Audio Only", "Video Only"],
                            value="All Segments",
                            label="View Mode"
                        )
                        rasa_filter_dropdown = gr.Dropdown(
                            choices=["All"] + LABELS,
                            value="All",
                            label="Filter by Rasa",
                            visible=False
                        )
                    segments_count_html = gr.HTML("")
                    
                with gr.Group(visible=False) as segments_table_group:
                    segments_dataframe = gr.Dataframe(
                        headers=["#", "Rasa", "Start", "End", "Duration", "Source", "Audio", "Video", "Date"],
                        interactive=False,
                        wrap=True
                    )
                    
                with gr.Group(visible=False) as segment_detail_group:
                    segment_detail_html = gr.HTML("")
                    with gr.Row():
                        audio_download_file = gr.File(label="Download Audio Segment", visible=False)
                        video_download_file = gr.File(label="Download Video Segment", visible=False)

"""

content = segments_ui_regex.sub(cloud_sync_md_and_new_tab, content)

# 6. Update on_extract binding
# From: outputs = [result_md, stats_md, segment_radio, seg_summary_md, seg_map_state]
# To:   inputs  = [source_state, start_num, end_num, label_radio, notes_text, cloud_config_state], outputs = [result_md, stats_md, cloud_sync_status_md]

extract_binding_old = """        extract_btn.click(
            fn      = on_extract,
            inputs  = [source_state, start_num, end_num, label_radio, notes_text],
            outputs = [result_md, stats_md, segment_radio, seg_summary_md, seg_map_state],
        )"""

extract_binding_new = """        extract_btn.click(
            fn      = on_extract,
            inputs  = [source_state, start_num, end_num, label_radio, notes_text, cloud_config_state],
            outputs = [result_md, stats_md, cloud_sync_status_md],
        )"""
content = content.replace(extract_binding_old, extract_binding_new)

# 7. Remove dead event bindings: on_segment_flush, on_segment_load, on_refresh, on_delete_request, etc.
# These are between "# ── Segment preview ─" and "# NOTE: No app.load() here"
dead_bindings_regex = re.compile(
    r'[ \t]+# ── Segment preview ─+.*?(?=[ \t]+# NOTE: No app.load\(\) here)',
    re.DOTALL
)

new_tab_bindings = """        # ══════════════════════════════════════════════════════════
        #  EVENT WIRING — EXTRACTED SEGMENTS TAB
        # ══════════════════════════════════════════════════════════

        # Load / Refresh Sheet
        _load_sheet_outputs = [
            sheet_status_display,
            segments_summary_group, segments_filter_group,
            segments_table_group, segment_detail_group,
            cloud_sync_status_md, segments_data_state,
            sheet_csv_url_state, cloud_config_state
        ]
        
        load_sheet_btn.click(
            fn=handle_load_sheet,
            inputs=[sheet_read_url, sheet_write_url],
            outputs=_load_sheet_outputs
        ).then(
            fn=handle_filter_segments,
            inputs=[view_mode_radio, rasa_filter_dropdown, segments_data_state],
            outputs=[segments_dataframe, segments_count_html, rasa_filter_dropdown]
        )
        
        # Filters
        _filter_inputs = [view_mode_radio, rasa_filter_dropdown, segments_data_state]
        _filter_outputs = [segments_dataframe, segments_count_html, rasa_filter_dropdown]
        
        view_mode_radio.change(
            fn=handle_filter_segments,
            inputs=_filter_inputs,
            outputs=_filter_outputs
        )
        
        rasa_filter_dropdown.change(
            fn=handle_filter_segments,
            inputs=_filter_inputs,
            outputs=_filter_outputs
        )
        
        # Row Selection
        segments_dataframe.select(
            fn=handle_segment_selected,
            inputs=[segments_data_state, view_mode_radio, rasa_filter_dropdown],
            outputs=[segment_detail_group, segment_detail_html, audio_download_file, video_download_file]
        )

"""
content = dead_bindings_regex.sub(new_tab_bindings, content)

with open('/home/mann/gujarati-natak/views/ui.py', 'w') as f:
    f.write(content)
