# 🎬 Video Annotator — How to Run

## First Time on a New Machine

```bash
# 1. Copy the rasa_pipeline/ folder to the new machine
# 2. Open terminal inside rasa_pipeline/
# 3. Run the installer — handles everything automatically:
bash install.sh

# 4. Start the server:
bash run.sh

# 5. Open in browser:
#    http://localhost:7860
```

---

## Starting the Server (Every Time After)

```bash
cd /path/to/rasa_pipeline
bash run.sh
```

Then open **http://localhost:7860** in your browser.

---

## Stopping the Server

```bash
tmux kill-session -t annotator
```

---

## Checking if Server is Running

```bash
# See all tmux sessions
tmux ls

# Watch live logs
tmux attach -t annotator
# To detach without stopping: press Ctrl+B then D

# Quick HTTP check
curl -I http://localhost:7860
```

---

## Custom Options

```bash
# Use a different video folder
VIDEO_DIR=/path/to/your/videos bash run.sh

# Use a different port
PORT=8080 bash run.sh

# Run in foreground (no tmux, logs visible directly)
NO_TMUX=1 bash run.sh

# Combine
PORT=8080 VIDEO_DIR=/data/videos bash run.sh
```

---

## Using the App

```
1.  Paste a video path into the path box → press Enter or click Load
2.  Press Space to play/pause the video
3.  Navigate to the start of the segment you want
4.  Press A to mark the start time
5.  Navigate to the end of the segment
6.  Press D to mark the end time
7.  Select a Rasa label (Shant, Hasya, Bhayanak, Karuna, Rudra)
8.  Press E or click EXTRACT to save the segment
9.  The segment appears in the list below
10. Click any segment in the list to preview it
11. Select a segment and click 🗑️ DELETE to remove it from disk
```

---

## Keyboard Shortcuts

| Key            | Action           |
|----------------|------------------|
| `Space`        | Play / Pause     |
| `A`            | Set start time   |
| `D`            | Set end time     |
| `E`            | Extract segment  |
| `← →`         | Seek ±5 seconds  |
| `Shift + ← →` | Seek ±1 second   |

---

## Where Files Are Saved

```
rasa_pipeline/
└── annotations/
    ├── annotations.csv        ← log of every extraction
    ├── Shant/
    │   ├── audio/  ← .wav clips
    │   └── video/  ← .mp4 clips
    ├── Hasya/
    ├── Bhayanak/
    ├── Karuna/
    └── Rudra/
```

---

## If the Server Won't Start

```bash
# Port already in use — kill it
fuser -k 7860/tcp
bash run.sh

# Check what went wrong
tail -40 ~/annotator.log

# Re-run installer to fix missing packages
bash install.sh

# Try a different port
PORT=7861 bash run.sh
# Then open http://localhost:7861
```

---

## If Extraction Fails

```bash
# Verify ffmpeg works
ffmpeg -version

# Test extraction manually
ffmpeg -ss 5 -t 5 -i /path/to/video.mp4 /tmp/test.wav

# Check annotations folder is writable
ls -la annotations/
```
