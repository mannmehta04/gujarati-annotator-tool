# models/annotation.py
"""
Data layer.
Handles all CSV read/write, segment list building, stats.
No Gradio imports. No ffmpeg calls. Pure data.
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
from config.settings import OUTPUT_DIR, LABELS


COLUMNS = [
    "id", "source_video", "start_time", "end_time",
    "duration", "label", "notes",
    "audio_file", "video_file", "timestamp"
]


def load_csv() -> pd.DataFrame:
    csv_path = OUTPUT_DIR / "annotations.csv"
    if csv_path.exists():
        return pd.read_csv(csv_path)
    return pd.DataFrame(columns=COLUMNS)


def save_row(row: dict) -> pd.DataFrame:
    df      = load_csv()
    new_row = pd.DataFrame([row])
    df      = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(OUTPUT_DIR / "annotations.csv", index=False, encoding="utf-8-sig")
    return df


def get_stats() -> str:
    try:
        df = load_csv()
        if df.empty:
            return "**0** clips"
        parts = [
            f"{l}: {len(df[df['label'] == l])}"
            for l in LABELS if len(df[df['label'] == l]) > 0
        ]
        return (
            f"**{len(df)}** clips "
            f"({df['duration'].sum():.0f}s) | "
            + " | ".join(parts)
        )
    except Exception:
        return "Error reading stats"


def build_segment_choices() -> tuple[list[str], str, dict]:
    try:
        df = load_csv()
        if df.empty:
            return [], "No segments yet", {}

        df      = df.sort_values("timestamp", ascending=False).reset_index(drop=True)
        choices = []
        seg_map = {}

        for pos, (_, row) in enumerate(df.iterrows()):
            display = (
                f"[{row['label']}] "
                f"{row['duration']:.1f}s | "
                f"{row['source_video'][:15]} | "
                f"{row['start_time']:.1f}s-{row['end_time']:.1f}s"
            )
            if display in seg_map:
                display += f" #{pos}"
            choices.append(display)
            seg_map[display] = pos

        parts   = [
            f"{l}: {len(df[df['label'] == l])}"
            for l in LABELS if len(df[df['label'] == l]) > 0
        ]
        summary = f"**{len(df)} segments** | " + " | ".join(parts)
        return choices, summary, seg_map

    except Exception as e:
        return [], f"Error: {e}", {}


def get_segment_row(display_str: str, seg_map: dict) -> pd.Series | None:
    pos = seg_map.get(display_str)
    if pos is None:
        return None
    df = load_csv()
    df = df.sort_values("timestamp", ascending=False).reset_index(drop=True)
    if pos >= len(df):
        return None
    return df.iloc[pos]


def delete_segment(
    display_str: str, seg_map: dict
) -> tuple[str, list, str, dict]:
    """
    FIXED: delegates to delete_segment_by_id using row's unique 'id'
    field as stable deletion key — not positional index.
    """
    if not display_str or not seg_map:
        return "⚠️ No segment selected", [], "No segments", {}

    try:
        pos = seg_map.get(display_str)
        if pos is None:
            return "❌ Segment not found in map", [], "Error", {}

        df = load_csv()
        if df.empty:
            return "❌ No segments in CSV", [], "No segments", {}

        df_sorted = df.sort_values(
            "timestamp", ascending=False
        ).reset_index(drop=True)

        if pos >= len(df_sorted):
            return "❌ Index out of range", [], "Error", {}

        target_id = df_sorted.iloc[pos]["id"]
        return delete_segment_by_id(target_id)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"❌ Delete failed: {e}", [], "Error", {}


def get_segment_info_for_confirmation(
    display_str: str,
    seg_map: dict
) -> tuple[str, str]:
    """
    Returns clean markdown for the confirmation panel.
    No tables — uses bold labels on separate lines.
    Content is populated BEFORE the panel becomes visible,
    ensuring immediate correct render.
    """
    if not display_str or not seg_map:
        return "⚠️ No segment selected.", ""

    try:
        pos = seg_map.get(display_str)
        if pos is None:
            return "❌ Segment not found in map.", ""

        df = load_csv()
        if df.empty:
            return "❌ CSV is empty.", ""

        df_sorted = df.sort_values(
            "timestamp", ascending=False
        ).reset_index(drop=True)

        if pos >= len(df_sorted):
            return "❌ Index out of range.", ""

        row       = df_sorted.iloc[pos]
        target_id = row["id"]

        audio_path = OUTPUT_DIR / row["audio_file"]
        video_path = OUTPUT_DIR / row["video_file"]

        audio_status = "✅" if audio_path.exists() else "❌"
        video_status = "✅" if video_path.exists() else "❌"

        html = f"""<div style="font-family:sans-serif;font-size:13px;line-height:1.8;color:#e0e0e0;">
<div style="font-size:14px;font-weight:bold;margin-bottom:10px;color:#ff6b6b;">⚠️ Confirm Deletion</div>
<table style="width:100%;border-collapse:collapse;font-size:13px;">
<tr><td style="padding:3px 12px 3px 0;color:#aaa;white-space:nowrap;vertical-align:top;">Label</td>
    <td style="padding:3px 0;"><b>{row['label']}</b></td></tr>
<tr><td style="padding:3px 12px 3px 0;color:#aaa;white-space:nowrap;vertical-align:top;">Source</td>
    <td style="padding:3px 0;">{row['source_video']}</td></tr>
<tr><td style="padding:3px 12px 3px 0;color:#aaa;white-space:nowrap;vertical-align:top;">Time</td>
    <td style="padding:3px 0;">{row['start_time']:.2f}s → {row['end_time']:.2f}s &nbsp;<span style="color:#aaa;">({row['duration']:.2f}s)</span></td></tr>
<tr><td style="padding:3px 12px 3px 0;color:#aaa;white-space:nowrap;vertical-align:top;">Audio</td>
    <td style="padding:3px 0;">{audio_status} <code style="font-size:11px;color:#ccc;word-break:break-all;">{row['audio_file']}</code></td></tr>
<tr><td style="padding:3px 12px 3px 0;color:#aaa;white-space:nowrap;vertical-align:top;">Video</td>
    <td style="padding:3px 0;">{video_status} <code style="font-size:11px;color:#ccc;word-break:break-all;">{row['video_file']}</code></td></tr>
<tr><td style="padding:3px 12px 3px 0;color:#aaa;white-space:nowrap;vertical-align:top;">ID</td>
    <td style="padding:3px 0;"><code style="font-size:11px;color:#ccc;">{target_id[-40:]}</code></td></tr>
</table>
<div style="margin-top:12px;font-size:12px;color:#ff8a80;font-style:italic;">This action is permanent and cannot be undone.</div>
</div>"""

        return html, target_id

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"❌ Error reading segment: {e}", ""



def delete_segment_by_id(
    target_id: str
) -> tuple[str, list, str, dict]:
    """
    Delete a segment by its unique 'id' field.
    Called after confirmation — positional index never used, so
    there is zero chance of deleting the wrong segment.
    """
    if not target_id:
        return "❌ No target ID", [], "Error", {}

    try:
        csv_path = OUTPUT_DIR / "annotations.csv"
        df       = load_csv()

        if df.empty:
            return "❌ CSV is empty", [], "No segments", {}

        mask = df["id"] == target_id
        if not mask.any():
            return f"❌ ID not found: {target_id}", [], "Error", {}

        row = df[mask].iloc[0]
        print(f"[delete_by_id] {target_id}")

        # Delete audio
        audio_path = OUTPUT_DIR / row["audio_file"]
        if audio_path.exists():
            audio_path.unlink()
            print(f"[delete_by_id] audio removed")
        else:
            print(f"[delete_by_id] audio not on disk")

        # Delete video
        video_path = OUTPUT_DIR / row["video_file"]
        if video_path.exists():
            video_path.unlink()
            print(f"[delete_by_id] video removed")
        else:
            print(f"[delete_by_id] video not on disk")

        # Drop by ID — stable regardless of order
        df_updated = df[~mask].reset_index(drop=True)
        df_updated.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"[delete_by_id] {len(df_updated)} rows remain")

        status = (
            f"🗑️ Deleted **{row['label']}** | "
            f"{row['duration']:.1f}s | "
            f"`{target_id[-35:]}`  \n"
            f"Audio + video removed from disk."
        )

        new_choices, new_summary, new_seg_map = build_segment_choices()
        return status, new_choices, new_summary, new_seg_map

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"❌ Delete failed: {e}", [], "Error", {}
