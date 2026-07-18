<div align="center">

# 🎭 Natak Annotation Tool

**A cloud-native browser tool for annotating Rasa in Gujarati theatrical speech**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Gradio](https://img.shields.io/badge/Gradio-4.x-ff7c00?style=flat-square&logo=gradio&logoColor=white)](https://gradio.app)
[![FastAPI](https://img.shields.io/badge/FastAPI-latest-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Supabase](https://img.shields.io/badge/Supabase-cloud-3ecf8e?style=flat-square&logo=supabase&logoColor=white)](https://supabase.com)
[![ffmpeg](https://img.shields.io/badge/ffmpeg-required-007808?style=flat-square&logo=ffmpeg&logoColor=white)](https://ffmpeg.org)
[![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)

<br/>

*Natak (નાટક) — Gujarati word for theatrical play*

<br/>

[✨ Features](#-features) •
[🏗 Architecture](#-architecture) •
[⚡ Quick Start](#-quick-start) •
[📖 Usage Guide](#-usage-guide) •
[🔧 Configuration](#-configuration) •
[📊 Spectral Analysis](#-spectral-analysis) •
[📝 Changelog](#-changelog)

</div>

---

## ✨ Features

<table>
<tr>
<td width="50%">

### 🎬 Annotation Tab
- Load source video via **public URL** or **local file**
- Browse local video files from folder
- Video player with **keyboard shortcuts**
- One-click timestamp capture
- **Video Name** field for segment identification
- Rasa label selector
- Optional notes
- Saves **metadata only** to Supabase — instant

</td>
<td width="50%">

### 🎞️ Extracted Segments Tab
- Summary stats strip with per-Rasa pill cards
- Filter sidebar — all segments or by Rasa
- Interactive table — click row to open detail
- **On-demand video preview** via ffmpeg
- **On-demand audio preview** with waveform
- **Normalized spectral analysis** — 3-panel plot
- Delete with confirmation popup overlay

</td>
</tr>
<tr>
<td width="50%">

### ⬇️ Download Tab
- Download individual audio or video segments
- Batch download all segments for a Rasa as **zip**
- All extraction happens **on demand** from source

</td>
<td width="50%">

### ☁️ Cloud-Native Storage
- **Zero local file storage** for extracted segments
- All annotation metadata in **Supabase** (PostgreSQL)
- No Supabase Storage buckets required
- Source videos accessed by URL — no upload needed

</td>
</tr>
</table>

---

## 🏗 Architecture

### Data Flow

```
┌──────────────────────────────────────────────────────────────┐
│                        Browser                                │
│                                                               │
│   Annotation Tab    Segments Tab    Download Tab              │
└─────────┬──────────────┬──────────────┬──────────────────────┘
          │              │              │
          ▼              ▼              ▼
┌──────────────────────────────────────────────────────────────┐
│               FastAPI + Gradio Server                         │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Streaming Routes                                        │ │
│  │  GET /segment/audio/{id}          inline audio          │ │
│  │  GET /segment/video/{id}          inline video          │ │
│  │  GET /segment/download/audio/{id} audio attachment      │ │
│  │  GET /segment/download/video/{id} video attachment      │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  controllers/                                                 │
│    extractor.py           metadata only — no file writes      │
│    media_extractor.py     ffmpeg on-demand — temp files only  │
│    spectrogram_analysis.py librosa + matplotlib pipeline     │
│    supabase_sync.py       all database operations             │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                       Supabase                                │
│                                                               │
│  Table: annotations                                           │
│  ┌────────────────┬──────────┬──────────────────────────┐    │
│  │ id             │ TEXT PK  │ video_Rasa_YYYYMMDD_...  │    │
│  │ source_video   │ TEXT     │ URL or path to source    │    │
│  │ start_time     │ NUMERIC  │ seconds                  │    │
│  │ end_time       │ NUMERIC  │ seconds                  │    │
│  │ duration       │ NUMERIC  │ seconds                  │    │
│  │ label          │ TEXT     │ Rasa category name       │    │
│  │ notes          │ TEXT     │ free text                │    │
│  │ audio_file     │ TEXT     │ empty (reserved)         │    │
│  │ video_file     │ TEXT     │ empty (reserved)         │    │
│  │ timestamp      │ TEXT     │ ISO 8601                 │    │
│  └────────────────┴──────────┴──────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

| Decision | Reason |
|---|---|
| Metadata-only at annotation time | Instant save, no ffmpeg wait |
| On-demand extraction for preview | No storage cost, always fresh |
| No Supabase Storage buckets | Size limits, simpler architecture |
| TEXT id (not UUID) | Readable, carries semantic meaning |
| Conda environment | Reproducible, handles native libs cleanly |

---

## ⚡ Quick Start

### Prerequisites

<details>
<summary><strong>1. Install Conda</strong></summary>

<br/>

Download and install [Miniconda](https://docs.conda.io/en/latest/miniconda.html)
(recommended — minimal install) or
[Anaconda](https://www.anaconda.com/products/distribution).

Verify installation:
```bash
conda --version
```

</details>

<details>
<summary><strong>2. Install ffmpeg</strong></summary>

<br/>

**macOS:**
```bash
brew install ffmpeg
```

**Ubuntu / Debian:**
```bash
sudo apt update && sudo apt install ffmpeg
```

**Windows:**
```bash
# Using conda (easiest — no PATH setup needed)
conda install -c conda-forge ffmpeg
```

**Verify:**
```bash
ffmpeg -version
```

</details>

<details>
<summary><strong>3. Create Supabase Project</strong></summary>

<br/>

1. Go to [supabase.com](https://supabase.com) and create a free account
2. Create a new project
3. Go to **SQL Editor** and run the schema — see
   [Supabase Setup](#-supabase-setup) below
4. Go to **Settings → API** and copy your **Project URL** and **anon key**

</details>

---

### Installation

```bash
# 1. Clone the repository
git clone <repository-url>
cd natak-annotation-tool

# 2. Create conda environment
conda create -n natak python=3.11 -y

# 3. Activate environment
conda activate natak

# 4. Install ffmpeg via conda (skip if already installed system-wide)
conda install -c conda-forge ffmpeg -y

# 5. Install Python dependencies
pip install -r requirements.txt

# 6. Configure environment
cp .env.example .env
# Edit .env with your Supabase credentials
```

> 💡 **Why Conda?**
> Conda manages native library dependencies (like those needed by
> `librosa` and `soundfile`) more reliably than pip alone,
> especially on Windows and macOS. It also keeps your project
> environment fully isolated and reproducible.

---

### Environment Management

```bash
# Activate environment
conda activate natak

# Deactivate when done
conda deactivate

# List all environments
conda env list

# Export environment for sharing
conda env export > environment.yml

# Recreate from export
conda env create -f environment.yml

# Remove environment (if needed)
conda env remove -n natak
```

---

## 🗄 Supabase Setup

<details>
<summary><strong>Step 1 — Create the Table (click to expand SQL)</strong></summary>

<br/>

Run this in your Supabase **SQL Editor**:

```sql
-- Annotations table
create table if not exists annotations (
    id           text primary key,
    source_video text,
    start_time   numeric,
    end_time     numeric,
    duration     numeric,
    label        text,
    notes        text        default '',
    audio_file   text        default '',
    video_file   text        default '',
    timestamp    text
);

-- Index for faster Rasa filtering
create index if not exists idx_annotations_label
    on annotations (label);

-- Index for timestamp ordering
create index if not exists idx_annotations_timestamp
    on annotations (timestamp desc);
```

</details>

<details>
<summary><strong>Step 2 — Get Your API Credentials</strong></summary>

<br/>

1. Open your Supabase project dashboard
2. Navigate to **Settings** → **API**
3. Copy **Project URL** → this is your `SUPABASE_URL`
4. Copy **anon / public** key → this is your `SUPABASE_KEY`

> ⚠️ Use the **anon** key for client-side access.
> If running server-side with elevated permissions, you may use
> the **service_role** key — but never expose it to the browser.

</details>

<details>
<summary><strong>Step 3 — Configure Your .env File</strong></summary>

<br/>

```bash
cp .env.example .env
```

Edit `.env`:
```bash
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-anon-key-here
SUPABASE_TABLE=annotations
```

</details>

> **Schema Notes**
>
> - `id` is `TEXT`, not UUID — the Python backend controls ID generation
> - `audio_file` and `video_file` are reserved columns, always stored
>   as empty strings — segments are extracted on demand, never stored
> - All numeric columns use `NUMERIC` to handle fractional seconds

---

## 🔧 Configuration

All configuration is via environment variables. Copy `.env.example` to `.env`:

| Variable | Required | Default | Description |
|---|---|---|---|
| `SUPABASE_URL` | ✅ Yes | — | Your Supabase project URL |
| `SUPABASE_KEY` | ✅ Yes | — | Your Supabase anon/service key |
| `SUPABASE_TABLE` | No | `annotations` | Table name |
| `APP_HOST` | No | `0.0.0.0` | Server bind host |
| `APP_PORT` | No | `7860` | Server port |
| `APP_SHARE` | No | `false` | Create public Gradio share link |
| `APP_TITLE` | No | `Natak Annotation Tool` | App title |

---

## 🚀 Running the Application

```bash
# Make sure conda environment is active
conda activate natak

# Start the server
python app.py
```

Open your browser at **http://localhost:7860**

---

## 📖 Usage Guide

<details>
<summary><strong>🎬 Creating an Annotation</strong></summary>

<br/>

1. Open the **Annotation Tab**
2. Choose your source:
   - **URL** — paste a public video URL (YouTube, direct link)
   - **Local** — browse files from your configured folder
3. Play the video to find your segment
4. Click to capture **Start Time** and **End Time**
5. Fill in the **Video Name** field — this is required and becomes
   part of the segment ID (e.g. `lalyo_laptayo`, `v1`, `natak2`)
6. Select the **Rasa** label from the dropdown
7. Add optional **Notes**
8. Click **Extract Segment**

> ✅ The annotation is saved to Supabase immediately.
> No audio or video files are created at this point.

</details>

<details>
<summary><strong>🎞️ Browsing and Previewing Segments</strong></summary>

<br/>

1. Open the **Extracted Segments Tab**
2. Click **🔄 Refresh** to load annotations from Supabase
3. Use the filter sidebar:
   - **View** — All segments or By Rasa
   - **Rasa** — Filter to a specific Rasa category
4. Click any row to open the **Detail Panel**
5. In the detail panel:
   - View segment metadata (label, timing, source, ID)
   - Click **▶ Load Video Preview** — ffmpeg extracts the clip
     on demand and loads it in the video player
   - Click **▶ Load Audio Preview** — ffmpeg extracts audio,
     displays as interactive waveform
   - Click **📊 Analyse Spectrum** — runs full spectral analysis
6. To delete, click **🗑️ Delete Annotation** — a confirmation
   popup appears with full segment details before deletion

</details>

<details>
<summary><strong>⬇️ Downloading Segments</strong></summary>

<br/>

**Individual Segments:**
Use the download links in the segment detail panel.
Each click triggers on-demand extraction via ffmpeg.

**Batch Download by Rasa:**
1. Open the **Download Tab**
2. Select a Rasa category
3. Click Download — a zip file is created on demand containing
   all audio and video clips for that Rasa

> ⏱️ Download time depends on the number of segments and the
> speed of access to the source videos.

</details>

<details>
<summary><strong>⌨️ Keyboard Shortcuts (Annotation Tab)</strong></summary>

<br/>

Read the Annotation Tab UI for the current keyboard shortcut
bindings — they are displayed in the interface.

</details>

---

## 🆔 Segment ID Format

```
{video_name}_{label}_{YYYYMMDD}_{HHMMSS}_{microseconds}
```

| Component | Example | Notes |
|---|---|---|
| `video_name` | `lalyo_laptayo` | User-provided, sanitized |
| `label` | `Hasya` | Rasa category |
| `YYYYMMDD` | `20260718` | Date |
| `HHMMSS` | `143022` | Time |
| `microseconds` | `847291` | Uniqueness within second |

**Full example:** `lalyo_laptayo_Hasya_20260718_143022_847291`

**Sanitization rules:**
- Spaces → underscores
- Special characters removed
- Multiple underscores collapsed
- `[object Object]`, `undefined`, `null` → rejected, shows error

---

## 📊 Spectral Analysis

<details>
<summary><strong>How It Works</strong></summary>

<br/>

The spectral analysis module implements a normalized spectrum
analysis pipeline based on acoustic research methodology for
Rasa classification:

**Pipeline:**

```
Source Video (URL or path)
    │
    ▼ ffmpeg (on demand)
Audio WAV (temp file)
    │
    ▼ librosa.load()
Audio Array (amp, sr=22050)
    │
    ▼ Random sampling
Up to 40 non-silent 0.1s segments
    │
    ▼ For each segment: FFT
Normalized spectrum:
  Fn = F / Fm  (normalized frequency ratio)
  An = A / Am  (normalized amplitude)
    │
    ▼ Interpolate onto common grid [1, 8]
Mean spectrum + 95% CI
    │
    ▼ matplotlib (Agg backend, dark theme)
Three-panel PNG figure:
  A. Full waveform
  B. Mean normalized spectrum Fn 1–8 with 95% CI
  C. Zoomed octave Fn 1–2
    │
    ▼ Gradio gr.Image
Displayed inline in browser
```

</details>

<details>
<summary><strong>Interpretation</strong></summary>

<br/>

- **Fn = 1.0** is the fundamental frequency (F0)
- **Fn = 2.0** is the first harmonic (one octave up)
- The **shaded region** shows the 95% confidence interval
  across all sampled segments
- The **zoomed panel (C)** shows the critical octave range
  where Rasa-specific spectral characteristics appear

</details>

---

## 📁 Project Structure

```
natak-annotation-tool/
│
├── 📄 app.py                       Entry point — FastAPI + Gradio
│                                   Streaming routes for segments
│
├── ⚙️  config/
│   └── settings.py                 All configuration settings
│                                   Loaded from environment variables
│
├── 🎛️  controllers/
│   ├── extractor.py                Annotation metadata creation
│   │                               Validates input, generates ID
│   │                               Inserts to Supabase — no file writes
│   │
│   ├── media_extractor.py          On-demand ffmpeg extraction
│   │                               Audio/video to temp files
│   │                               Bytes for streaming responses
│   │                               Zip packaging for batch download
│   │
│   ├── spectrogram_analysis.py     Normalized spectrum pipeline
│   │                               librosa + numpy + matplotlib
│   │                               Returns PNG temp file path
│   │
│   └── supabase_sync.py            All Supabase operations
│                                   fetch, insert, delete, filter
│
├── 🖥️  views/
│   ├── ui.py                       Gradio UI layout — all tabs
│   │                               Annotation, Segments, Download
│   │
│   └── handlers.py                 All Gradio event handlers
│                                   HTML builders, filter logic
│
├── 📋 requirements.txt             Python dependencies (pip)
├── 🔑 .env.example                 Environment variable template
├── 🚫 .gitignore                   Git ignore rules
└── 📖 README.md                    This file
```

> **Note:** The `models/` directory has been removed. The
> `Annotation` model class was an isolated wrapper with no active
> use in the current pipeline. All data flows as plain Python
> dicts through the system.

---

## 📦 Dependencies

| Package | Purpose |
|---|---|
| `gradio>=4.0` | Browser UI framework |
| `fastapi` | HTTP server, streaming routes |
| `uvicorn` | ASGI server |
| `supabase` | Supabase Python client |
| `librosa>=0.10` | Audio loading and analysis |
| `numpy` | Numerical arrays |
| `scipy>=1.10` | Signal processing |
| `matplotlib>=3.7` | Spectrogram plots |
| `soundfile` | Audio file I/O |
| `python-dotenv` | `.env` file loading |
| `requests` | HTTP requests for zip downloads |

---

## 🔄 On-Demand Extraction Details

<details>
<summary><strong>How preview loading works</strong></summary>

<br/>

```python
# User clicks "Load Audio Preview"
handle_load_audio_preview(segment_id, segments)
    → _find_segment_by_id(segments, segment_id)
    → extract_audio_to_tempfile(source_video, start, end, id)
        → tempfile.mkstemp(suffix='.wav')
        → ffmpeg -ss {start} -i {source} -t {duration} ...
        → returns temp_file_path (NOT deleted — Gradio needs it)
    → gr.Audio(value=temp_file_path, type='filepath')
    → Gradio serves file → browser waveform player
```

```python
# User clicks download link (anchor tag)
GET /segment/download/audio/{segment_id}
    → fetch_annotation_by_id(segment_id)     # Supabase lookup
    → extract_audio_bytes(source, start, end) # ffmpeg → bytes
        → tempfile.mkstemp() → ffmpeg → read → os.unlink()
    → StreamingResponse(bytes, attachment)    # browser downloads
```

</details>

<details>
<summary><strong>Source video requirements</strong></summary>

<br/>

| Source Type | Requirement |
|---|---|
| **HTTP/HTTPS URL** | Must be publicly accessible from the server |
| **Local file path** | Must exist on the server's filesystem |
| **YouTube URL** | Not directly supported by ffmpeg without yt-dlp |

> If using YouTube URLs, consider hosting the video file directly
> or using a video hosting service with direct MP4 links.

</details>

---

## 🚨 Troubleshooting

<details>
<summary><strong>Preview shows error: "ffmpeg not found"</strong></summary>

<br/>

ffmpeg is not in the system PATH.

```bash
# Install via conda (recommended)
conda install -c conda-forge ffmpeg -y

# Verify
ffmpeg -version
```

</details>

<details>
<summary><strong>Supabase connection fails</strong></summary>

<br/>

1. Check `.env` has correct `SUPABASE_URL` and `SUPABASE_KEY`
2. Verify the `annotations` table exists (run the SQL from setup)
3. Check Supabase project is not paused (free tier pauses after inactivity)

</details>

<details>
<summary><strong>Spectrogram shows "Audio file is empty"</strong></summary>

<br/>

The source video could not be accessed by ffmpeg.

- If using a URL: verify it is publicly accessible
- If using a local path: verify the file exists on the server
- Check the server logs for the ffmpeg error message

</details>

<details>
<summary><strong>Video Name shows [object Object] in segment ID</strong></summary>

<br/>

This was a bug in earlier versions — now fixed. The validation
layer rejects `[object Object]`, `undefined`, `null`, and empty
strings, and shows a clear error message requiring the user to
provide a valid name.

</details>

---

## 📝 Changelog

<details open>
<summary><strong>[2.1.0] — Model Removal and Clean Pipeline</strong></summary>

<br/>

**Removed**
- `models/annotation.py` — isolated class with no active use
  in the current pipeline. All data flows as plain Python dicts.
- `models/` directory — now empty after model removal
- All imports of `models.annotation` from every file
- All instantiation of `Annotation` class — replaced with dicts

**Changed**
- `controllers/extractor.py` — builds annotation dict directly,
  no model class instantiation
- Environment setup documentation — switched to **Conda**
  from virtualenv/venv across all instructions
- `README.md` — full rewrite with interactive collapsible sections,
  badges, tables, architecture diagram, and conda-first setup

**Added**
- `environment.yml` export instructions for reproducible setup
- Comprehensive troubleshooting section in README
- Dependency table with purpose descriptions

</details>

<details>
<summary><strong>[2.0.0] — Cloud Migration Release</strong></summary>

<br/>

**Breaking Changes**
- Removed all local file storage for extracted segments
- Removed `annotations/annotations.csv`
- Removed `OUTPUT_DIR` and `ANNOTATIONS_CSV` settings

**Added**
- `controllers/media_extractor.py` — on-demand ffmpeg extraction
- `controllers/spectrogram_analysis.py` — spectrum analysis pipeline
- FastAPI streaming routes for audio/video
- `fetch_annotation_by_id` in `supabase_sync.py`
- On-demand zip download for all segments in a Rasa
- Delete confirmation popup overlay
- Spectral Analysis panel in segment detail view
- Video Name field (mandatory, part of segment ID)
- Hardened video name validation
- Waveform audio player

**Changed**
- `extractor.py` — metadata only, no ffmpeg at annotation time
- `supabase_sync.py` — confirmed column names throughout
- `handle_segment_row_selected` — streaming URLs to players
- Segment ID format to include video name

**Removed**
- Local audio/video file extraction at annotation time
- `annotations/` directory and CSV
- `OUTPUT_DIR` and `ANNOTATIONS_CSV` settings
- `_resolve_segment_path` — replaced by URL-based approach
- Audio Only / Video Only filter modes
- Download buttons from detail panel (now via routes)
- Supabase Storage bucket usage

</details>

<details>
<summary><strong>[1.5.0] — Extracted Segments Tab Overhaul</strong></summary>

<br/>

**Added**
- Stats strip with per-Rasa pill cards
- Filter sidebar with view mode and Rasa dropdown
- Segment identity card with timing badges
- Load Audio / Load Video preview buttons
- Enhanced Analyse Spectrum button
- Global CSS for all button and table styles

**Changed**
- `_build_segments_summary_html` — rasa color palette
- `_build_segment_detail_html` — identity card layout
- `_build_segments_dataframe` — columns: `#, Rasa, Duration, Timing, Source, Annotated`

**Removed**
- Download Audio / Download Video buttons from detail panel
- Audio Only / Video Only filter options

</details>

<details>
<summary><strong>[1.4.0] — Delete Confirmation Popup</strong></summary>

<br/>

**Added**
- Full-screen fixed overlay popup for delete confirmation
- Segment details shown in confirmation dialog
- Hidden Gradio buttons triggered via JavaScript
- CSS accessibility hiding pattern

**Fixed**
- Delete button was locking UI — popup buttons now functional
- JavaScript selector pattern using `getElementById` + `querySelector`

</details>

<details>
<summary><strong>[1.3.0] — Spectrogram Analysis Module</strong></summary>

<br/>

**Added**
- `controllers/spectrogram_analysis.py`
- Three-panel normalized spectrum plot
- `handle_analyse_spectrum` handler
- `librosa`, `scipy`, `matplotlib` dependencies

</details>

<details>
<summary><strong>[1.2.0] — On-Demand Streaming</strong></summary>

<br/>

**Added**
- `controllers/media_extractor.py`
- FastAPI streaming routes
- Load Audio / Load Video handlers
- `_check_source_available`, `_find_segment_by_id`

</details>

<details>
<summary><strong>[1.1.0] — Supabase Schema Alignment</strong></summary>

<br/>

**Fixed**
- Rasa and Source showing as N/A in segments table
- Wrong column names in Supabase queries
- All references updated to confirmed schema columns

</details>

<details>
<summary><strong>[1.0.0] — Initial Release</strong></summary>

<br/>

**Added**
- Annotation Tab with video player
- Segment extraction via ffmpeg to local disk
- `annotations.csv` for local storage
- Supabase sync for cloud backup
- Basic Extracted Segments Tab
- Download Tab

</details>

---

<div align="center">

**Built for the study of Rasa in Gujarati theatrical speech**

*Hasya · Karuna · Rudra · Shant · Bhayanak · Veer · Adbhuta · Shringara*

<br/>

[![Made with Gradio](https://img.shields.io/badge/Made%20with-Gradio-ff7c00?style=flat-square&logo=gradio)](https://gradio.app)
[![Powered by Supabase](https://img.shields.io/badge/Powered%20by-Supabase-3ecf8e?style=flat-square&logo=supabase)](https://supabase.com)

</div>
