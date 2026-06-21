# 🎬 Video Annotator

A Gradio‑based application for annotating video segments with Rasa emotion labels.  
The tool lets you load a video, set start/end timestamps, choose a label, and automatically extract the corresponding audio and video clips. All extracts are saved under a structured `annotations/` directory for easy downstream use.

---

## 📋 Table of Contents
1. [Prerequisites](#prerequisites)  
2. [Installation](#installation)  
3. [Configuration](#configuration)  
4. [Running the App](#running-the-app)  
5. [Environment Variables](#environment-variables)  
6. [User Interface Overview](#ui-overview)  
7. [Keyboard Shortcuts](#keyboard-shortcuts)  
8. [Output Structure](#output-structure)  
9. [Stopping the Server](#stopping-the-server)  
10. [FAQ / Troubleshooting](#faq--troubleshooting)  
11. [Contributing & Development](#contributing--development)  

---

## Prerequisites

| Requirement | Minimum version / details |
|------------|---------------------------|
| **Python** | 3.10 or newer (tested on 3.10‑3.12) |
| **ffmpeg** | 4.4+ (must be reachable via `PATH`) |
| **Git**   | Optional, for cloning the repo |

> **Note:** On most Linux/macOS systems `ffmpeg` can be installed via the package manager (`apt`, `brew`, etc.). On Windows download a static build and add its folder to the `PATH`.

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
* `pandas>=2.0`
* (any additional packages you may add later)

---

## Configuration

The application uses a single `settings.py` (imported via `config.settings`) to read environment variables and defaults.  
You can override any of these values in three ways:

| Method | Example |
|--------|---------|
| **Shell export** | `export PORT=8080` |
| **`.env` file** (created automatically on first run) | `PORT=8080` |
| **Command‑line flag** (when launching `run.sh`) | `bash run.sh /path/to/videos` |

| Variable | Default | Description |
|----------|---------|-------------|
| `VIDEO_DIR` | Auto‑detected (searches `videos/`, `dataset/video/`, `~/videos/`) | Root folder containing source `.mp4` files. |
| `PORT` | `7860` | TCP port the Gradio UI will listen on. |
| `HOST` | `0.0.0.0` | Network interface to bind to (`0.0.0.0` = all interfaces). |
| `LOG_LEVEL` *(optional)* | `INFO` | Verbosity of internal logging. |

---

## Running the App

### Quick start (Linux / macOS)

```bash
# Start with auto‑detected video folder and default port
bash run.sh

# Use a custom video directory
bash run.sh /path/to/your/videos

# Change the listening port (e.g., 8080)
PORT=8080 bash run.sh
```

### Windows

```cmd
pip install -r requirements.txt
python stable_annotator.py
```

> The `run.sh` script is a *cross‑platform* wrapper; on Windows you can execute the same commands inside Git‑Bash or WSL.

### Manual launch (any OS)

```bash
python stable_annotator.py
```

> This starts the UI directly without the tmux session handling that `run.sh` provides.

---

## Environment Variables (expanded)

You can view the full list of configurable variables in **`config/settings.py`**. Below is a concise reference:

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `7860` | Port number for the Gradio server. |
| `HOST` | `0.0.0.0` | IP address to bind. Use `127.0.0.1` for localhost‑only access. |
| `VIDEO_DIR` | Auto‑detect | Base directory where your video files reside. |
| `ANNOTATION_DIR` | `annotations` | Root folder for all extracted clips & CSV logs. |
| `LOG_LEVEL` | `INFO` | Python logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `MAX_WORKERS` *(optional)* | `4` | Number of parallel extraction workers (useful on multi‑core machines). |

You can export any of these before running `run.sh`:

```bash
export PORT=9000
export HOST=127.0.0.1
export LOG_LEVEL=DEBUG
```

---

## UI Overview

1. **Video path box** – Paste the relative/absolute path to a `.mp4` file.  
2. **Load button** – Retrieves the video metadata (duration, available shortcuts).  
3. **Play / Pause** – Space key toggles playback.  
4. **Start / End markers** – `A` sets the start point, `D` sets the end point.  
5. **Label selector** – Choose a Rasa emotion (e.g., `Shant`, `Hasya`, `Bhayanak`).  
6. **Extract** – Press `E` (or click the button) to cut the segment and save it.  
6. **Segment list** – Newly extracted items appear at the bottom; clicking one loads a preview.  

All actions are captured in the console logs and visualized through Gradio’s live update mechanism.

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

These shortcuts work regardless of whether the UI has focus; Gradio forwards global key events to the underlying components.

---

## Output Structure

```
project_root/
│
├─ annotations/
│   ├─ Shant/
│   │   ├─ audio/        ← .wav clips (one per segment)
│   │   └─ video/        ← .mp4 clips (one per segment)
│   ├─ Hasya/
│   │   ├─ audio/
│   │   └─ video/
│   └─ ... (one sub‑folder per selected label)
│
└─ annotations.csv        ← CSV log with columns:
    id, source_video, start_time, end_time,
    duration, label, notes, audio_file, video_file,
    timestamp, audio_path, video_path
```

* The **`id`** column holds a unique identifier for each segment, automatically generated (see the *Naming convention* section below).  
* The **CSV** is continuously updated; you can open it with any spreadsheet tool or load it into pandas for further analysis.  

### Naming convention for `id`

```
v<source_index>_<label>_<YYYYMMDD>_<HHMMSS>_<unique_suffix>
```

* `v1`, `v2`, … – derived from the source video filename (`v1.mp4`, `v2.mp4`, …).  
* `<label>` – the emotion label (e.g., `Shant`).  
* `<YYYYMMDD>` – date the extraction took place.  
* `<HHMMSS>` – time (24‑h) when extraction started.  
* `<unique_suffix>` – short UUID or counter to guarantee uniqueness (e.g., `330365`).

---

## Stopping the Server

When you launched the app via `run.sh`, it runs inside a **tmux** session named `annotator`. To stop it cleanly:

```bash
tmux kill-session -t annotator
```

If you started the app manually (e.g., `python stable_annotator.py`), simply press `Ctrl+C` in the terminal where it is running.

---

## FAQ / Troubleshooting

| Problem | Solution |
|---------|----------|
| **`ffmpeg: command not found`** | Install ffmpeg and make sure it is on your `PATH`. On Ubuntu: `sudo apt-get install ffmpeg`. On macOS: `brew install ffmpeg`. |
| **Port already in use** | Change the `PORT` environment variable (`PORT=8081 bash run.sh`). |
| **No videos are detected** | Verify that your videos are placed under one of the default directories (`videos/`, `dataset/video/`, `~/videos/`). Or set `VIDEO_DIR` explicitly before launching. |
| **Extraction fails on a specific video** | Check that the file is a valid `.mp4` and not corrupted. You can also run `python -c "import subprocess, sys; subprocess.run(['ffmpeg','-i', 'path/to/file.mp4'], check=True)"` to verify ffmpeg can read it. |
| **CSV not updating** | Ensure the process has write permissions to the `annotations/` directory. If you ran the app inside a restricted environment (e.g., Docker without volume mounts), mount a writable host path. |
| **Want faster extraction on many videos** | Increase `MAX_WORKERS` (default 4) by setting it in the environment before launching: `export MAX_WORKERS=8`. The extractor will then spawn a pool of worker processes. |

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

---

*Last updated: 2025‑11‑02*  

--- 

*If you have suggestions or find bugs, please open an issue on the GitHub repository.*