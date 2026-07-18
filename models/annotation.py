# models/annotation.py
"""
Data layer.
Handling stats based on Supabase is now moved, this module just keeps a skeleton for get_stats 
to avoid breaking UI dependencies.
No Gradio imports. No ffmpeg calls.
"""

def get_stats() -> str:
    return "Cloud Sync enabled. View Extracted Segments tab for stats."

