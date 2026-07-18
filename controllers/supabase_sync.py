import logging
import os
from typing import Optional

_logger = logging.getLogger('natak.supabase')

if not _logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter(
        '[%(asctime)s] %(name)s %(levelname)s: %(message)s',
        datefmt='%H:%M:%S',
    ))
    _logger.addHandler(_h)
    _logger.setLevel(logging.DEBUG)


# --- Client Management ---

_supabase_client = None


def get_client():
    """
    Returns the Supabase client instance.
    Creates it on first call (singleton pattern).
    Returns None if Supabase is not configured.
    """
    global _supabase_client
    
    if _supabase_client is not None:
        return _supabase_client
    
    try:
        from config import settings
        
        if not settings.SUPABASE_CONFIGURED:
            _logger.warning(
                "Supabase is not configured. "
                "Set SUPABASE_URL and SUPABASE_KEY in config/settings.py"
            )
            return None
        
        from supabase import create_client, Client
        
        _logger.info(f"Creating Supabase client for {settings.SUPABASE_URL}")
        _supabase_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        return _supabase_client
        
    except Exception as e:
        _logger.error(f"Failed to initialize Supabase client: {e}")
        return None

def fetch_all_annotations():
    client = get_client()
    if not client:
        return [], "Supabase not configured"
    try:
        from config import settings
        response = client.table(settings.SUPABASE_TABLE).select("*").order("timestamp", desc=True).execute()
        return response.data, None
    except Exception as e:
        return [], str(e)

def delete_annotation(segment_id: str):
    client = get_client()
    if not client:
        return False, "Supabase not configured"
    try:
        from config import settings
        
        # 1. We no longer use Supabase Storage for files.
        # Just delete the DB row.

        # 2. Delete the DB row
        client.table(settings.SUPABASE_TABLE).delete().eq("id", segment_id).execute()
        return True, "Success"
    except Exception as e:
        return False, str(e)



def insert_annotation(data: dict):
    client = get_client()
    if not client:
        return False, "Supabase not configured"
    try:
        from config import settings
        client.table(settings.SUPABASE_TABLE).insert(data).execute()
        return True, "Success"
    except Exception as e:
        return False, str(e)

def _get_all_rasa_categories():
    try:
        from config import settings
        return getattr(settings, 'RASA_CATEGORIES', getattr(settings, 'EMOTIONS', []))
    except Exception:
        return []

def parse_annotations_to_segments(rows: list) -> dict:
    """
    Parses Supabase rows into structured segments dict.
    
    CONFIRMED column names from Supabase schema:
    id, source_video, start_time, end_time, duration,
    label, notes, audio_file, video_file, timestamp
    
    Every segment dict uses these exact key names so downstream
    code (_build_segments_dataframe, _build_segment_detail_html)
    can read them reliably.
    """
    from config import settings
    rasa_categories = _get_all_rasa_categories()
    
    result = {
        'all': [],
        'by_rasa': {cat: [] for cat in rasa_categories},
        'total_count': 0,
        'rasa_counts': {cat: 0 for cat in rasa_categories},
    }
    
    for row in rows:
        # Read every field using confirmed column name
        # Provide no fallback aliases — use only the confirmed name
        segment = {
            'id':           str(row.get('id', '')),
            'source_video': str(row.get('source_video', '')),
            'start_time':   row.get('start_time', 0),
            'end_time':     row.get('end_time', 0),
            'duration':     row.get('duration', 0),
            'label':        str(row.get('label', '')),
            'notes':        str(row.get('notes', '')),
            'audio_file':   str(row.get('audio_file', '')),
            'video_file':   str(row.get('video_file', '')),
            'timestamp':    str(row.get('timestamp', '')),
            'raw':          row,
        }
        
        result['all'].append(segment)
        result['total_count'] += 1
        
        label_val = segment['label'].strip()
        if label_val in result['by_rasa']:
            result['by_rasa'][label_val].append(segment)
            result['rasa_counts'][label_val] = (
                result['rasa_counts'].get(label_val, 0) + 1
            )
        else:
            # Unknown label — still include it
            if label_val not in result['by_rasa']:
                result['by_rasa'][label_val] = []
                result['rasa_counts'][label_val] = 0
            result['by_rasa'][label_val].append(segment)
            result['rasa_counts'][label_val] += 1
    
    return result

def fetch_annotation_by_id(annotation_id: str) -> tuple:
    """
    Fetches a single annotation by ID.
    Returns: (dict | None, error: str | None)
    """
    client = get_client()
    if not client:
        return None, "Supabase not configured"
    try:
        from config import settings
        response = client.table(settings.SUPABASE_TABLE).select("*").eq("id", annotation_id).execute()
        if response.data:
            return response.data[0], None
        return None, "Not found"
    except Exception as e:
        return None, str(e)


def annotation_object_to_supabase_dict(obj: dict) -> dict:
    """
    Format annotation for insertion into Supabase.
    Leaves audio_file and video_file empty since we do on-demand extraction.
    """
    return {
        'id': str(obj.get('id', '')),
        'source_video': str(obj.get('source_video', '')),
        'start_time': float(obj.get('start_time', 0)),
        'end_time': float(obj.get('end_time', 0)),
        'duration': float(obj.get('duration', 0)),
        'label': str(obj.get('label', '')),
        'notes': str(obj.get('notes', '')),
        'audio_file': '',
        'video_file': '',
        'timestamp': str(obj.get('timestamp', ''))
    }
