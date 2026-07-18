# 🎭 Natak Annotation Tool

A browser-based tool for annotating Rasa (emotional) segments in
Gujarati theatrical video recordings. Built with Gradio and FastAPI,
backed by Supabase for cloud-native annotation storage.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Technology Stack](#technology-stack)
- [Supabase Setup](#supabase-setup)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [Usage Guide](#usage-guide)
- [Segment ID Format](#segment-id-format)
- [On-Demand Media Extraction](#on-demand-media-extraction)
- [Spectral Analysis](#spectral-analysis)
- [Project Structure](#project-structure)
- [Changelog](#changelog)

---

## Overview

The Natak Annotation Tool enables researchers to:

1. **Annotate** — Watch a source video, identify a segment by
   start/end timestamps, label it with a Rasa category, and save
   the annotation to Supabase with a single click.

2. **Browse** — View all saved annotations in an interactive
   table, filterable by Rasa category. Every annotation shows its
   label, timing, source, and date.

3. **Preview** — Click any annotation to open a detail panel.
   Load audio or video previews on demand — ffmpeg extracts the
   segment from the source video in real time and streams it to
   the browser. No files are stored permanently.

4. **Analyse** — Run a full normalized spectral analysis on any
   segment. The tool extracts audio on demand, computes the
   normalized spectrum with 95% confidence interval, and displays
   a three-panel plot inline.

5. **Download** — Download individual segments (audio or video)
   or batch-download all segments for a Rasa as a zip file.
   Everything is extracted on demand from source videos.

---

## Architecture

### Cloud-Native, Zero Local Storage

All annotation data is stored in **Supabase** (PostgreSQL).
Audio and video files are **never stored permanently** — neither
locally nor in any cloud bucket.

When a user requests a preview or download, the server:

1. Fetches annotation metadata from Supabase (source URL,
   start time, end time)
2. Runs ffmpeg on demand to extract the segment
3. Streams the bytes directly to the browser
4. Deletes the temp file immediately

```
┌─────────────────────────────────────────────────────────┐
│                     Browser (User)                       │
│                                                          │
│  Annotation Tab    Segments Tab    Download Tab          │
└──────────┬──────────────┬──────────────┬────────────────┘
           │              │              │
           ▼              ▼              ▼
┌─────────────────────────────────────────────────────────┐
│              FastAPI + Gradio Server                     │
│                                                          │
│  /segment/audio/{id}     — on-demand audio stream       │
│  /segment/video/{id}     — on-demand video stream       │
│  /segment/download/audio/{id}  — audio attachment       │
│  /segment/download/video/{id}  — video attachment       │
│                                                          │
│  controllers/                                            │
│    extractor.py          — metadata only, no files      │
│    media_extractor.py    — ffmpeg on-demand extraction  │
│    spectrogram_analysis.py — normalized spectrum        │
│    supabase_sync.py      — all Supabase operations      │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                     Supabase                             │
│                                                          │
│  Table: annotations                                      │
│    id TEXT PRIMARY KEY                                   │
│    source_video TEXT                                     │
│    start_time NUMERIC                                    │
│    end_time NUMERIC                                      │
│    duration NUMERIC                                      │
│    label TEXT                                            │
│    notes TEXT                                            │
│    audio_file TEXT  (reserved, empty)                   │
│    video_file TEXT  (reserved, empty)                   │
│    timestamp TEXT                                        │
└─────────────────────────────────────────────────────────┘
```

### Source Video Accessibility

When a segment is previewed or downloaded, the server must be
able to access the **original source video**. This means:

- **HTTP/HTTPS URLs** — accessible from any machine running
  the app, as long as the URL is public
- **Local file paths** — only accessible if the file exists on
  the server machine running the app

---

## Features

### Annotation Tab
- Load source video via public URL or local file path
- Browse local video files from a configured folder
- Video player with keyboard shortcuts for timestamp capture
- One-click timestamp extraction (start / end)
- Rasa label selector with all categories
- **Video Name field** (required) — becomes part of the
  segment ID
- Notes field for free-text annotation
- Save to Supabase with a single click

### Extracted Segments Tab
- Summary stats strip — total count and per-Rasa pill cards
- Filter sidebar — view all or filter by Rasa
- Interactive table — click any row to open detail panel
- Detail panel:
  - Segment identity card (label, timing, source, ID)
  - On-demand video preview
  - On-demand audio preview with waveform display
  - Normalized spectral analysis (three-panel plot)
  - Delete with confirmation popup

### Download Tab
- Download individual segments (audio or video) on demand
- Batch download all segments for a Rasa as a zip file
- Everything extracted from source videos at request time

---

## Technology Stack

| Component | Technology |
|---|---|
| UI Framework | Gradio 4.x |
| Server | FastAPI + Uvicorn |
| Database | Supabase (PostgreSQL) |
| Media Extraction | ffmpeg (subprocess) |
| Audio Analysis | librosa, numpy, scipy |
| Visualization | matplotlib |
| Python | 3.10+ |

---

## Supabase Setup

### Step 1 — Create the Table

Run this SQL in your Supabase SQL editor:

```sql
create table annotations (
    id           text primary key,
    source_video text,
    start_time   numeric,
    end_time     numeric,
    duration     numeric,
    label        text,
    notes        text,
    audio_file   text default '',
    video_file   text default '',
    timestamp    text
);

-- Optional: index for faster filtering by label
create index idx_annotations_label
    on annotations (label);

-- Optional: index for timestamp ordering
create index idx_annotations_timestamp
    on annotations (timestamp desc);
```

### Step 2 — Get Your Credentials

In your Supabase project:
1. Go to **Settings → API**
2. Copy your **Project URL** → `SUPABASE_URL`
3. Copy your **anon public key** → `SUPABASE_KEY`

### Step 3 — Configure Environment

```bash
cp .env.example .env
# Edit .env with your Supabase URL and key
```

> **Important**: The `id` column is `TEXT` (not UUID).
> The Python backend generates IDs in this format:
>
> ```
> {video_name}_{label}_{YYYYMMDD}_{HHMMSS}_{microseconds}
> ```
>
> Example: `lalyo_laptayo_Hasya_20260718_143022_847291`

> **Note**: `audio_file` and `video_file` columns are reserved
> and stored as empty strings. Segments are extracted on demand
> from `source_video` — nothing is stored in these columns.

---

## Installation

### Prerequisites

- Python 3.10+
- ffmpeg installed and in PATH
- Supabase account and project

### Install ffmpeg

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt update && sudo apt install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
# Add to PATH
```

### Install Python Dependencies

```bash
git clone <repository-url>
cd natak-annotation-tool

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

---

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
# Required
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_TABLE=annotations

# Optional
APP_HOST=0.0.0.0
APP_PORT=7860
APP_SHARE=false
APP_TITLE=Natak Annotation Tool
```

---

## Running the Application

```bash
# Activate virtual environment
source venv/bin/activate

# Start the server
python app.py
```

The app will be available at `http://localhost:7860`.

---

## Usage Guide

### Creating an Annotation

1. Open the **Annotation Tab**
2. Enter a source video URL or select a local file
3. Play the video and identify the segment
4. Click timestamps to capture start and end times
5. Enter a **Video Name** (required — e.g. `lalyo_laptayo`)
6. Select the **Rasa** label
7. Add optional notes
8. Click **Extract Segment**

The annotation metadata is saved to Supabase immediately.
No audio or video files are created at this point.

### Browsing and Previewing Segments

1. Open the **Extracted Segments Tab**
2. Click **Refresh** to load annotations from Supabase
3. Use the filter sidebar to view All or filter by Rasa
4. Click any row to open the detail panel
5. Click **Load Video Preview** or **Load Audio Preview**
   to extract and stream the segment on demand
6. Click **Analyse Spectrum** for spectral analysis

### Downloading Segments

Individual segments can be downloaded from the detail panel
via the download links (extracted on demand).

For batch downloads, use the **Download Tab** to download
all segments for a Rasa as a zip file.

---

## Segment ID Format

```
{video_name}_{label}_{YYYYMMDD}_{HHMMSS}_{microseconds}
```

Examples:
```
lalyo_laptayo_Hasya_20260718_143022_847291
v1_Shant_20260719_091534_203847
natak2_Rudra_20260720_154201_394821
```

Rules:
- `video_name` — provided by user, spaces → underscores,
  special characters removed
- `label` — Rasa category name
- Timestamp — local server time at annotation creation
- Microseconds — ensures uniqueness within the same second

---

## On-Demand Media Extraction

When a user requests a preview or download:

```
User clicks "Load Audio Preview"
    → handler calls extract_audio_to_tempfile()
    → ffmpeg reads source_video (URL or local path)
    → ffmpeg writes WAV to NamedTemporaryFile
    → Gradio serves the temp file to the browser player
    → Waveform is displayed in the audio player

User clicks download link
    → FastAPI route /segment/download/audio/{id}
    → fetch_annotation_by_id() from Supabase
    → extract_audio_bytes() via ffmpeg
    → StreamingResponse with WAV bytes
    → Browser triggers file download dialog

User requests zip download
    → For each segment in the Rasa:
        → extract_audio_bytes() + extract_video_bytes()
        → Add to in-memory zip
    → Write zip to temp file
    → Serve as gr.File download
```

ffmpeg must be installed and accessible from PATH on the
server running the application.

---

## Spectral Analysis

The spectral analysis module (`controllers/spectrogram_analysis.py`)
implements a normalized spectrum analysis pipeline:

1. **Extract** — Audio extracted from source video via ffmpeg
2. **Segment** — Up to 40 non-silent 0.1s segments sampled
3. **FFT** — Normalized spectrum computed per segment:
   - Fn = F / Fm (normalized frequency ratio)
   - An = A / Am (normalized amplitude)
4. **Aggregate** — Mean spectrum + 95% CI computed across
   all valid segments
5. **Plot** — Three-panel figure:
   - Panel A: Full audio waveform
   - Panel B: Mean normalized spectrum (Fn 1–8) with 95% CI
   - Panel C: Zoomed octave range (Fn 1–2)

The analysis is based on acoustic research methodology for
Rasa classification in Gujarati theatrical speech.

---

## Project Structure

```
natak-annotation-tool/
│
├── app.py                      # FastAPI + Gradio entry point
│                               # On-demand streaming routes
│
├── config/
│   └── settings.py             # All configuration settings
│
├── controllers/
│   ├── extractor.py            # Annotation metadata creation
│   │                           # Supabase insert — no file writes
│   ├── media_extractor.py      # On-demand ffmpeg extraction
│   │                           # Audio/video bytes for streaming
│   ├── spectrogram_analysis.py # Normalized spectrum analysis
│   │                           # librosa + matplotlib pipeline
│   └── supabase_sync.py        # All Supabase operations
│                               # fetch, insert, delete
│
├── models/
│   └── annotation.py           # Annotation data model
│
├── views/
│   ├── ui.py                   # Gradio UI layout — all tabs
│   └── handlers.py             # All Gradio event handlers
│
├── .env.example                # Environment variable template
├── .gitignore                  # Git ignore rules
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

---

## Changelog

### [2.1] — Spectrogram Analysis Module

**Added**
- `controllers/spectrogram_analysis.py` with full pipeline:
  - `_ext_seg` — non-silent segment extraction
  - `_norm_spect` — FFT normalized spectrum computation
  - `_compute_mean_spectrum` — mean + stack over segments
  - `analyse_segment_spectrogram` — main entry point
- `handle_analyse_spectrum` in `views/handlers.py`
- `analyse_spectrum_btn` in segment detail panel
- `spectrogram_group`, `spectrogram_image` (gr.Image)
- `spectrogram_status_outer` for error display
- Dark-themed three-panel matplotlib figure
- Dependencies: `librosa>=0.10.0`, `matplotlib>=3.7.0`,
  `scipy>=1.10.0`

---

### [2.0] — Cloud Migration Release

**Breaking Changes**
- Removed all local file storage for extracted segments
- Removed `annotations/annotations.csv` — all data now in Supabase
- Removed `OUTPUT_DIR` and `ANNOTATIONS_CSV` settings
- Annotation extraction no longer writes audio or video files to disk

**Added**
- `controllers/media_extractor.py` — on-demand ffmpeg extraction
  for browser streaming, with no permanent file storage
- `controllers/spectrogram_analysis.py` — full normalized spectrum
  analysis pipeline using librosa and matplotlib
- FastAPI streaming routes:
  - `GET /segment/audio/{id}` — inline audio stream
  - `GET /segment/video/{id}` — inline video stream
  - `GET /segment/download/audio/{id}` — audio download
  - `GET /segment/download/video/{id}` — video download
- `fetch_annotation_by_id` in `supabase_sync.py`
- On-demand zip download for all segments in a Rasa
- Delete confirmation popup overlay with full segment details
- Spectral Analysis panel in segment detail view
- Three-panel spectrogram plot (waveform, Fn 1–8, Fn 1–2)
- Video Name field in Annotation Tab (mandatory, part of segment ID)
- Hardened video name validation — rejects `[object Object]`,
  `undefined`, `null`, and empty values
- Waveform audio player in segment detail panel
- `.env.example` for environment configuration

**Changed**
- `controllers/extractor.py` — now records metadata only,
  no ffmpeg at annotation time, no file writes
- `controllers/supabase_sync.py` — confirmed column names:
  `id`, `source_video`, `start_time`, `end_time`, `duration`,
  `label`, `notes`, `audio_file`, `video_file`, `timestamp`
- `annotation_object_to_supabase_dict` — uses confirmed schema,
  `audio_file` and `video_file` stored as empty strings
- `parse_annotations_to_segments` — reads `label` and
  `source_video` with no aliases
- `handle_segment_row_selected` — passes streaming URLs to
  players instead of local file paths
- Segment ID format: `{video_name}_{label}_{YYYYMMDD}_{HHMMSS}_{µs}`

**Removed**
- Local audio/video file extraction at annotation time
- `annotations/annotations.csv` and `annotations/` directory
- `OUTPUT_DIR` and `ANNOTATIONS_CSV` from settings
- `_resolve_segment_path` — replaced by `_get_media_url`
- "Audio Only" and "Video Only" filter modes from segments tab
- Download buttons from segment detail panel (moved to routes)
- Supabase Storage bucket usage — not needed, no files stored

---

### [1.2] — Extracted Segments Tab Overhaul

**Added**
- Full UI overhaul of the Extracted Segments Tab
- Stats strip with total count and per-Rasa pill cards
- Filter sidebar with view mode radio and Rasa dropdown
- How-to-use tips panel in sidebar
- Segment identity card with timing badges in detail panel
- Media preview section with video (left) and audio (right)
- Load Audio / Load Video preview buttons
- Spectral Analysis section with explanatory description
- Enhanced Analyse Spectrum button (primary, large, gradient)
- Global CSS block for all button and table styles
- Decorative section dividers in detail panel
- Action row with Close Panel and Delete Annotation buttons

**Changed**
- `_build_segments_summary_html` — rasa color palette,
  horizontally scrollable pills, large total count block
- `_build_segment_detail_html` — identity card with label badge,
  timing badges, source code block, notes block
- `_build_segments_dataframe` — new columns:
  `#, Rasa, Duration, Timing, Source, Annotated`
- Segments table has larger row height and hover styling
- Audio player uses green waveform colors (`#34d399`)

**Removed**
- Download Audio and Download Video buttons from detail panel
- Audio Only / Video Only filter options

---

### [1.1] — On-Demand Streaming Architecture

**Added**
- `controllers/media_extractor.py`:
  - `extract_audio_to_tempfile` — WAV to temp file
  - `extract_video_to_tempfile` — MP4 to temp file
  - `extract_audio_bytes` — WAV as bytes
  - `extract_video_bytes` — MP4 as bytes
  - `extract_zip_for_rasa` — batch zip creation
- FastAPI streaming routes in `app.py`
- `fetch_annotation_by_id` in `supabase_sync.py`
- `handle_load_audio_preview` — loads audio via ffmpeg,
  passes temp file path to `gr.Audio`
- `handle_load_video_preview` — loads video via ffmpeg
- `load_audio_btn` and `load_video_btn` in detail panel
- `_check_source_available` — checks URL vs local path
- `_find_segment_by_id` — segment lookup helper
- `_build_download_links_html` — HTML anchor download links

**Changed**
- `handle_segment_row_selected` — shows metadata only on
  row click, media loaded on separate button click
- Gradio `gr.Audio` uses `type="filepath"` with waveform display
- `gr.Audio` receives temp file path (not URL) for waveform

---

### [1.0] — Initial Release

**Added**
- Annotation Tab with video player and timestamp capture
- URL and local folder source video modes
- Rasa label selector
- Segment extraction via ffmpeg to local disk
- `annotations/annotations.csv` for local storage
- Extracted Segments Tab with basic table
- Supabase sync for cloud backup
- Download Tab for local file downloads
- `controllers/extractor.py` with full ffmpeg pipeline
- `controllers/supabase_sync.py` for Supabase operations
- `views/ui.py` and `views/handlers.py`
- `config/settings.py` with `OUTPUT_DIR` and `ANNOTATIONS_CSV`
- `models/annotation.py`

---

*Built for the study of Rasa in Gujarati theatrical speech.*
