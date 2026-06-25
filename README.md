# 🎬 Video Annotator

A Gradio‑based application for annotating video segments with Rasa emotion labels.
The tool lets you **download videos from any URL** (YouTube, Vimeo, direct `.mp4`, etc.), load a local file, set start/end timestamps, choose a label, and automatically extract the corresponding audio and video clips. All extracts are saved under a structured `annotations/` directory for easy downstream use.

The UI is split into two tabs — **📥 Download Video** for fetching remote videos via `yt-dlp`, and **🎬 Annotate** for the annotation workflow itself.

---

## 📋 Table of Contents
1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [One-Shot Installer](#one-shot-installer)
4. [Configuration](#configuration)
5. [Running the App](#running-the-app)
6. [Environment Variables](#environment-variables)
7. [User Interface Overview](#ui-overview)
8. [Keyboard Shortcuts](#keyboard-shortcuts)
9. [Output Structure](#output-structure)
10. [Stopping the Server](#stopping-the-server)
11. [FAQ / Troubleshooting](#faq--troubleshooting)
12. [Contributing & Development](#contributing--development)

---

## Prerequisites

| Requirement | Minimum version / details |
|------------|---------------------------|
| **Python** | 3.10 or newer (tested on 3.10‑3.12) |
| **ffmpeg** | 4.4+ (must be reachable via `PATH`) |
| **yt-dlp** | 2024.1.0+ (CLI on `PATH` or importable) |
| **Git**   | Optional, for cloning the repo |

> **Note:** On most Linux/macOS systems `ffmpeg` and `yt-dlp` can be installed via the package manager (`apt`, `brew`, `pip`, etc.). On Windows download a static build and add its folder to the `PATH`. The [one-shot installer](#one-shot-installer) below handles all of this automatically.

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-org/gujarati-natak.git
cd gujarati-natak
```

> If you just need the code, you can also copy the folder locally; no Git required.

### 2. Install Python dependencies

```bash
python -m pip install --upgrade pip          # recommended
pip install -r requirements.txt
```

`requirements.txt` pulls in:
* `gradio>=4.0`
* `pandas>=1.5`
* `yt-dlp>=2024.1.0`

---

## One-Shot Installer

For a fresh machine (or to repair a broken setup), `install.sh` handles everything automatically — Python ≥ 3.10, pip, ffmpeg, tmux, the Python packages from `requirements.txt`, and initial creation of the output directories:

```bash
bash install.sh
```

Supported on Ubuntu / Debian / macOS (with Homebrew). After it finishes, launch with `bash run.sh` and open <http://localhost:PORT>.

The installer is idempotent — safe to re-run if something is missing.

---

## Configuration

The application uses a single `config/settings.py` to read environment variables and defaults.
All source videos and downloaded videos live in `dataset/` (set via `VIDEO_DIR` / `DATASET_DIR`).
Extracted clips and the CSV log live in `annotations/`.

You can override any value in three ways:

| Method | Example |
|--------|---------|
| **Shell export** | `export PORT=8080` |
| **Command‑line argument** (to `run.sh`) | `bash run.sh /path/to/videos` |
| **Environment variable** | `PORT=8080 bash run.sh` |

### Labels

The supported Rasa emotion labels are defined in `config/settings.py` → `LABELS`:

```
["Shant", "Hasya", "Bhayanak", "Karuna", "Rudra"]
```

One sub‑folder per label is created under `annotations/` automatically on startup.

---

## Running the App

### Quick start (Linux / macOS)

```bash
# Start with default dataset/ folder and default port
bash run.sh

# Use a custom video directory (saved into VIDEO_DIR)
bash run.sh /path/to/your/videos

# Change the listening port (e.g., 8080)
PORT=8080 bash run.sh

# Run in foreground without tmux (logs visible directly)
NO_TMUX=1 bash run.sh
```

### Direct launch (any OS)

```bash
python app.py
```

> This starts the UI directly without the tmux session handling that `run.sh` provides.

### Windows

```cmd
pip install -r requirements.txt
python app.py
```

> The `run.sh` script is a *cross‑platform* wrapper; on Windows you can execute the same commands inside Git‑Bash or WSL.

### First launch

On startup `app.py` checks for `gradio`, `pandas`, and `yt-dlp`, auto-installs any missing Python package (then re‑executes), verifies `ffmpeg` is on `PRINT`, and warns if the `yt-dlp` CLI is absent.

After the server starts you'll see:

```
==================================================
🎬 VIDEO ANNOTATOR
==================================================
🌐 http://localhost:7860
==================================================
```

Open that URL in your browser.

---

## Environment Variables (expanded)

You can view the full list of configurable variables in **`config/settings.py`**. Below is a concise reference:

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `7860` | Port number for the Gradio server. |
| `HOST` | `0.0.0.0` | IP address to bind. Use `127.0.0.1` for localhost‑only access. |
| `VIDEO_DIR` | `dataset/` | Base directory where your video files reside. Videos downloaded via the **📥 Download Video** tab are saved here. |
| `DATASET_DIR` | `dataset/` | Alias of `VIDEO_DIR`; the canonical source folder. |
| `OUTPUT_DIR` | `annotations/` | Root folder for all extracted clips & CSV logs. |
| `ANNOTATION_DIR` | `annotations` | Legacy alias of `OUTPUT_DIR`. |
| `LOG_LEVEL` *(optional)* | `INFO` | Python logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `MAX_WORKERS` *(optional)* | `4` | Number of parallel extraction workers (useful on multi‑core machines). |

You can export any of these before running `run.sh`:

```bash
export PORT=9000
export HOST=127.0.0.1
export LOG_LEVEL=DEBUG
```

The `run.sh` launcher also accepts `NO_TMUX=1` (run in foreground) and an optional first positional argument (custom video folder).

---

## UI Overview

The app has **two tabs** at the top. Tabs share the same backend; downloaded videos appear in the Annotate tab immediately.

### Tab 1 — 📥 Download Video

| Element | Purpose |
|---------|---------|
| **🔗 Video URL** textbox | Paste any YouTube, Vimeo, or direct `.mp4` URL. |
| **⬇️ Download** button | Runs `yt-dlp`, streams progress into the log box below. |
| **📋 Download Log** box | Scrolling monospace log showing yt-dlp's live progress. |
| **Status markdown** | Shows `✅ Downloaded: <path>` on success, `❌ Error: …` on failure. |
| **🎬 Go to Annotate Tab →** button | (Appears after download) switches to the Annotate tab and auto‑loads the new video. |

Tips (shown under the tab):
* Paste any YouTube, Vimeo, or direct `.mp4` URL.
* `yt-dlp` automatically picks the best quality and merges into MP4.
* After download, the video is auto‑loaded in the **Annotate** tab and added to the "Available Videos" list.

Behind the scenes: videos are saved directly into `dataset/` — the same folder the **Annotate** tab scans — so no manual move is needed.

### Tab 2 — 🎬 Annotate

| Element | Purpose |
|---------|---------|
| **📁 Video Path** textbox | Paste relative/absolute path to a `.mp4` file. Press **Enter** or click **📂 Load Video**. |
| **Available Videos** accordion | Lists every `.mp4` found in `dataset/` (collapsible, auto‑refreshed after download). |
| **Video Player** | Main player (height 400). |
| **Start / End number inputs** | `A` sets start, `D` sets end via keyboard shortcuts; updated live. |
| **Duration** textbox | Read‑only — e.g. `10.0s (00:00 → 00:10)`. |
| **🏷️ Rasa Label** radio | Pick one of `Shant`, `Hasya`, `Bhayanak`, `Karuna`, `Rudra`. |
| **Notes** textbox | Free‑form notes attached to the segment on extraction. |
| **✂️ EXTRACT (E)** button | Cuts the segment and saves audio + video into `annotations/<label>/`. |
| **Stats markdown** | Live counter — total clips, total seconds, per‑label breakdown. |
| **📋 All Segments** radio | Newly extracted items appear at the top (newest first). Clicking one populates the **Preview** column. |
| **🔄 Refresh** button | Re‑scans `annotations.csv` and rebuilds the segment list. |
| **🗑️ Delete Selected** button | Opens a **⚠️ Confirm Deletion** panel before removing audio + video from disk and dropping the row from the CSV. |
| **Yes, Delete Permanently** / ❌ Cancel | Confirmation buttons (hidden until delete is first clicked). |
| **👁️ Preview** column | Shows label, source, time range, ID, plus an audio player and a video preview for the selected segment. |

All actions are captured in the console logs and visualized through Gradio's live update mechanism. The segment list is sorted newest-first; the unique `id` field is the stable delete key (so multi-select race conditions can't delete the wrong segment).

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| **Space** | Play / Pause |
| **A** | Set *start* time (cursor jumps to selected point) |
| **D** | Set *end* time |
| **E** | Extract current segment (uses the label you selected) |
| **← / →** | Seek backward / forward by **5 seconds** |
| **Shift+← / Shift+→** | Seek backward / forward by **1 second** |
| **Ctrl+R** | Reload UI (useful after changing environment variables) |
| **Enter** (in Video Path box) | Same as clicking **📂 Load Video** |

Shortcuts fire only when no text input has focus (so typing a URL or notes won't accidentally seek the player). The **A / D / E** keys use the **main player** (the larger video in the Annotate tab), not the preview.

These shortcuts work regardless of whether the UI has focus; Gradio forwards global key events to the underlying components.

---

## Output Structure

```
project_root/
│
├─ dataset/                   ← source & downloaded videos
│   ├─ v1.mp4
│   └─ <downloaded_title>.mp4
│
├─ annotations/
│   ├─ Shant/
│   │   ├─ audio/        ← .wav clips (one per segment)
│   │   └─ video/        ← .mp4 clips (one per segment)
│   ├─ Hasya/
│   │   ├─ audio/
│   │   └─ video/
│   ├─ Bhayanak/
│   ├─ Karuna/
│   ├─ Rudra/
│   └─ annotations.csv        ← CSV log with columns:
│       id, source_video, start_time, end_time,
│       duration, label, notes,
│       audio_file, video_file, timestamp
│
└─ /tmp/video_annotator*      ← temp copies for clean Gradio serving & preview cache
```

* The **`id`** column holds a unique identifier for each segment, automatically generated (see the *Naming convention* section below).
* The **CSV** is continuously updated; you can open it with any spreadsheet tool or load it into pandas for further analysis.
* Audio is extracted as 16-bit PCM WAV, 16 kHz, mono. Video is re‑encoded as H.264 + AAC with faststart for browser-friendly streaming.

### Naming convention for `id`

```
<clean_stem>_<label>_<YYYYMMDD_HHMMSS_ffffff>
```

* `<clean_stem>` — sanitized source video filename (UUID prefix from Gradio is stripped; illegal filesystem characters are replaced with `_`; truncated to 60 chars).
* `<label>` — the emotion label (e.g., `Shant`).
* `<YYYYMMDD_HHMMSS_ffffff>` — local timestamp at extraction time, including microseconds for uniqueness.

---

## Stopping the Server

When you launched the app via `run.sh`, it runs inside a **tmux** session named `annotator`. To stop it cleanly:

```bash
tmux kill-session -t annotator
```

If you started the app manually (e.g., `python app.py` or `NO_TMUX=1 bash run.sh`), simply press `Ctrl+C` in the terminal where it is running.

To inspect logs after the fact:

```bash
tail -40 ~/annotator.log
```

---

## FAQ / Troubleshooting

| Problem | Solution |
|---------|----------|
| **`ffmpeg: command not found`** | Install ffmpeg and make sure it is on your `PATH`. On Ubuntu: `sudo apt-get install ffmpeg`. On macOS: `brew install ffmpeg`. |
| **`yt-dlp: command not found`** | Install with `pip install yt-dlp` (or `brew install yt-dlp` on macOS). The app auto-installs the Python package if missing, but the CLI is also required for the Download tab. |
| **Port already in use** | Change the `PORT` environment variable (`PORT=8081 bash run.sh`). `run.sh` also auto-kills anything already on the chosen port before launching. |
| **No videos are detected** | Verify that your videos are placed under `dataset/` (or set `VIDEO_DIR` explicitly before launching). The **📥 Download Video** tab saves directly into `dataset/`. |
| **Extraction fails on a specific video** | Check that the file is a valid `.mp4` and not corrupted. You can also run `python -c "import subprocess, sys; subprocess.run(['ffmpeg','-i', 'path/to/file.mp4'], check=True)"` to verify ffmpeg can read it. |
| **CSV not updating** | Ensure the process has write permissions to the `annotations/` directory. If you ran the app inside a restricted environment (e.g., Docker without volume mounts), mount a writable host path. |
| **Want faster extraction on many videos** | Increase `MAX_WORKERS` (default 4) by setting it in the environment before launching: `export MAX_WORKERS=8`. The extractor will then spawn a pool of worker processes. |
| **Downloaded video doesn't appear in Annotate tab** | Click the **🎬 Go to Annotate Tab →** button that appears after a successful download — it auto-populates the path and refreshes the "Available Videos" list. |
| **Segment delete removes the wrong clip** | Deletion is keyed by the unique `id` field (not positional index), so it cannot delete the wrong segment even if the list re-sorts between selection and confirmation. |
| **Preview video stutters / won't seek** | The app re-muxes the clip with `-movflags +faststart` on first preview and caches the result in `/tmp/video_annotator_preview/`. If the cache is stale, restart the app to clear it. |
| **`install.sh` fails on Python check** | Ensure Python 3.10+ is installed (`python3 --version`). The installer will try to install it via `apt` / `brew` if missing. |
| **Want to run without tmux** | Use `NO_TMUX=1 bash run.sh` — the server runs in the foreground and `Ctrl+C` stops it. |

---

## Contributing & Development

1. **Fork** the repository and clone your copy.
2. Create a **feature branch** (`git checkout -b feat/your-feature`).
3. Write **unit tests** for any new functions (use `pytest`).
4. Run the **test suite**: `pytest -q`.
5. Submit a **Pull Request** with a clear description of the change.

### Coding conventions

* Follow **PEP 8** for Python style.
* Use **type hints** (`-> None`, `Dict[str, Any]`, etc.) throughout.
* Keep all UI strings in `constants.py` to avoid duplication.
* Log important events with the standard library `logging` module at `INFO` level; switch to `DEBUG` for local troubleshooting.

### Architecture

The project follows a layered MVC-style layout:

```
app.py                  ← entry point; checks deps, launches UI
run.sh                  ← launcher (tmux, port sanity, foreground mode)
install.sh              ← one-shot installer for fresh machines
config/settings.py      ← central config, paths, labels, env vars
controllers/
  downloader.py         ← yt-dlp video download (yt-dlp CLI wrapper)
  extractor.py          ← ffmpeg extraction, preview cache, video scan
models/
  annotation.py         ← CSV read/write, segment list, stats, delete-by-id
views/
  ui.py                 ← Gradio layout, two tabs, CSS, JS shortcuts
  handlers.py           ← event wiring (no business logic)
```

Business logic stays out of `views/` — handlers only translate UI events into controller calls and format results back into Gradio updates.

---

*Last updated: 2026‑06‑25*

---

*If you have suggestions or find bugs, please open an issue on the GitHub repository.*
