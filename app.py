# app.py
"""
Entry point.
Boot dependency installer, initializes config, launches the UI.
Nothing else lives here.
"""

import subprocess
import sys
import os


def check_dependencies():
    missing = []
    try:
        import gradio   # noqa: F401
    except ImportError:
        missing.append("gradio")
    try:
        import pandas   # noqa: F401
    except ImportError:
        missing.append("pandas")

    if missing:
        print(f"Installing: {missing}")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--break-system-packages"] + missing
        )
        os.execv(sys.executable, [sys.executable] + sys.argv)

    if subprocess.run(
        ["ffmpeg", "-version"], capture_output=True
    ).returncode != 0:
        print("⚠️  ffmpeg not found.")
        print("  Ubuntu : sudo apt install ffmpeg")
        print("  Mac    : brew install ffmpeg")
        sys.exit(1)


if __name__ == "__main__":
    check_dependencies()

    from config.settings import makeDir, PORT, HOST
    from config.settings import (
        TEMP_VIDEO_DIR, OUTPUT_DIR,
        PREVIEW_CACHE_DIR, VIDEO_DIR
    )
    makeDir()

    from views.ui import build_ui, CUSTOM_CSS, CUSTOM_JS
    app = build_ui()

    print(f"\n{'='*50}")
    print(f"🎬 VIDEO ANNOTATOR")
    print(f"{'='*50}")
    print(f"🌐 http://localhost:{PORT}")
    print(f"{'='*50}\n")

    from config.settings import SCRIPT_DIR
    app.launch(
        server_name=HOST,
        server_port=PORT,
        share=False,
        js=CUSTOM_JS,
        css=CUSTOM_CSS,
        allowed_paths=[
            str(TEMP_VIDEO_DIR),
            str(OUTPUT_DIR),
            str(PREVIEW_CACHE_DIR),
            str(VIDEO_DIR),
            str(SCRIPT_DIR),
        ]
    )
