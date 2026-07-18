"""
controllers/media_extractor.py

On-demand media extraction for browser serving.

When a user requests a preview or download of an annotated segment,
this module extracts the audio or video clip from the source video
using ffmpeg, returns the bytes, and cleans up immediately.

No files are stored permanently. Every extraction is ephemeral.
"""

import os
import subprocess
import tempfile
import logging
from typing import Optional

_logger = logging.getLogger('natak.media_extractor')


def _run_ffmpeg(cmd: list, description: str) -> tuple:
    """
    Runs an ffmpeg command.
    
    Returns:
        (success: bool, stderr: str)
    """
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            timeout=300,  # 5 minute timeout
        )
        return True, ''
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode('utf-8', errors='replace') if e.stderr else ''
        _logger.error(f"ffmpeg failed for {description}: {stderr[-500:]}")
        return False, stderr
    except subprocess.TimeoutExpired:
        _logger.error(f"ffmpeg timeout for {description}")
        return False, "ffmpeg timeout"
    except FileNotFoundError:
        _logger.error("ffmpeg not found in PATH")
        return False, "ffmpeg not found"


def extract_audio_bytes(
    source_video: str,
    start_time: float,
    end_time: float,
    segment_id: str = 'segment',
) -> tuple:
    """
    Extracts audio segment from source video.
    
    Runs ffmpeg, reads result bytes, deletes temp file.
    
    Args:
        source_video: path or URL to the source video
        start_time: start in seconds
        end_time: end in seconds
        segment_id: used for logging only
    
    Returns:
        (audio_bytes: bytes | None, error: str | None)
        Returns (None, error_message) on failure.
    """
    if not source_video:
        return None, "No source video provided."
    
    duration = end_time - start_time
    if duration <= 0:
        return None, "Invalid time range."
    
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            suffix='.wav',
            prefix=f'natak_audio_{segment_id}_',
            delete=False,
        ) as tmp:
            tmp_path = tmp.name
        
        cmd = [
            'ffmpeg', '-y',
            '-ss', str(start_time),
            '-i', str(source_video),
            '-t', str(duration),
            '-vn',
            '-acodec', 'pcm_s16le',
            '-ar', '44100',
            '-ac', '2',
            tmp_path,
        ]
        
        success, err = _run_ffmpeg(cmd, f"audio/{segment_id}")
        
        if not success:
            return None, f"Audio extraction failed: {err}"
        
        if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
            return None, "Audio extraction produced empty file."
        
        with open(tmp_path, 'rb') as f:
            audio_bytes = f.read()
        
        _logger.info(
            f"Extracted audio for {segment_id}: "
            f"{len(audio_bytes)} bytes, "
            f"{start_time:.2f}s-{end_time:.2f}s"
        )
        return audio_bytes, None
        
    except Exception as e:
        _logger.error(f"extract_audio_bytes error for {segment_id}: {e}")
        return None, str(e)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


def extract_video_bytes(
    source_video: str,
    start_time: float,
    end_time: float,
    segment_id: str = 'segment',
) -> tuple:
    """
    Extracts video segment from source video.
    
    Runs ffmpeg, reads result bytes, deletes temp file.
    
    Args:
        source_video: path or URL to the source video
        start_time: start in seconds
        end_time: end in seconds
        segment_id: used for logging only
    
    Returns:
        (video_bytes: bytes | None, error: str | None)
    """
    if not source_video:
        return None, "No source video provided."
    
    duration = end_time - start_time
    if duration <= 0:
        return None, "Invalid time range."
    
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            suffix='.mp4',
            prefix=f'natak_video_{segment_id}_',
            delete=False,
        ) as tmp:
            tmp_path = tmp.name
        
        cmd = [
            'ffmpeg', '-y',
            '-ss', str(start_time),
            '-i', str(source_video),
            '-t', str(duration),
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-movflags', '+faststart',
            tmp_path,
        ]
        
        success, err = _run_ffmpeg(cmd, f"video/{segment_id}")
        
        if not success:
            return None, f"Video extraction failed: {err}"
        
        if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
            return None, "Video extraction produced empty file."
        
        with open(tmp_path, 'rb') as f:
            video_bytes = f.read()
        
        _logger.info(
            f"Extracted video for {segment_id}: "
            f"{len(video_bytes)} bytes, "
            f"{start_time:.2f}s-{end_time:.2f}s"
        )
        return video_bytes, None
        
    except Exception as e:
        _logger.error(f"extract_video_bytes error for {segment_id}: {e}")
        return None, str(e)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


def extract_audio_to_tempfile(
    source_video: str,
    start_time: float,
    end_time: float,
    segment_id: str = 'segment',
) -> tuple:
    """
    Extracts audio segment and returns path to a temp file.
    
    Unlike extract_audio_bytes, this does NOT delete the temp file —
    the caller is responsible for deletion after Gradio serves it.
    
    Used for gr.File download where Gradio needs a file path.
    
    Returns:
        (temp_file_path: str | None, error: str | None)
    """
    if not source_video:
        return None, "No source video provided."
    
    duration = end_time - start_time
    if duration <= 0:
        return None, "Invalid time range."
    
    try:
        with tempfile.NamedTemporaryFile(
            suffix='.wav',
            prefix=f'natak_dl_audio_{segment_id}_',
            delete=False,
        ) as tmp:
            tmp_path = tmp.name
        
        cmd = [
            'ffmpeg', '-y',
            '-ss', str(start_time),
            '-i', str(source_video),
            '-t', str(duration),
            '-vn',
            '-acodec', 'pcm_s16le',
            '-ar', '44100',
            '-ac', '2',
            tmp_path,
        ]
        
        success, err = _run_ffmpeg(cmd, f"audio_dl/{segment_id}")
        
        if not success:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            return None, f"Audio extraction failed: {err}"
        
        if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            return None, "Audio extraction produced empty file."
        
        return tmp_path, None
        
    except Exception as e:
        _logger.error(f"extract_audio_to_tempfile error: {e}")
        return None, str(e)


def extract_video_to_tempfile(
    source_video: str,
    start_time: float,
    end_time: float,
    segment_id: str = 'segment',
) -> tuple:
    """
    Extracts video segment and returns path to a temp file.
    
    Caller is responsible for deletion after Gradio serves it.
    
    Returns:
        (temp_file_path: str | None, error: str | None)
    """
    if not source_video:
        return None, "No source video provided."
    
    duration = end_time - start_time
    if duration <= 0:
        return None, "Invalid time range."
    
    try:
        with tempfile.NamedTemporaryFile(
            suffix='.mp4',
            prefix=f'natak_dl_video_{segment_id}_',
            delete=False,
        ) as tmp:
            tmp_path = tmp.name
        
        cmd = [
            'ffmpeg', '-y',
            '-ss', str(start_time),
            '-i', str(source_video),
            '-t', str(duration),
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-movflags', '+faststart',
            tmp_path,
        ]
        
        success, err = _run_ffmpeg(cmd, f"video_dl/{segment_id}")
        
        if not success:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            return None, f"Video extraction failed: {err}"
        
        if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            return None, "Video extraction produced empty file."
        
        return tmp_path, None
        
    except Exception as e:
        _logger.error(f"extract_video_to_tempfile error: {e}")
        return None, str(e)


def extract_zip_for_rasa(
    segments: list,
    rasa_label: str,
) -> tuple:
    """
    Extracts all audio and video clips for a rasa and packages into a zip.
    
    For each segment in the list:
    - Extracts audio bytes using extract_audio_bytes
    - Extracts video bytes using extract_video_bytes
    - Adds both to zip with path: {rasa_label}/{segment_id}/{segment_id}.wav etc
    
    Args:
        segments: list of segment dicts (from parse_annotations_to_segments)
        rasa_label: rasa name (used for zip folder naming)
    
    Returns:
        (zip_temp_file_path: str | None, error: str | None)
    """
    import zipfile
    import io
    
    if not segments:
        return None, f"No segments found for {rasa_label}."
    
    zip_buffer = io.BytesIO()
    errors = []
    success_count = 0
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for seg in segments:
            seg_id      = str(seg.get('id', 'unknown'))
            source      = str(seg.get('source_video', ''))
            start_t     = float(seg.get('start_time', 0))
            end_t       = float(seg.get('end_time', 0))
            folder_path = f"{rasa_label}/{seg_id}/"
            
            if not source:
                errors.append(f"{seg_id}: no source_video")
                continue
            
            # Extract audio
            audio_bytes, audio_err = extract_audio_bytes(
                source, start_t, end_t, seg_id
            )
            if audio_bytes:
                zf.writestr(f"{folder_path}{seg_id}.wav", audio_bytes)
                success_count += 1
            else:
                errors.append(f"{seg_id} audio: {audio_err}")
            
            # Extract video
            video_bytes, video_err = extract_video_bytes(
                source, start_t, end_t, seg_id
            )
            if video_bytes:
                zf.writestr(f"{folder_path}{seg_id}.mp4", video_bytes)
                success_count += 1
            else:
                errors.append(f"{seg_id} video: {video_err}")
    
    if success_count == 0:
        return None, f"All extractions failed: {'; '.join(errors[:5])}"
    
    zip_buffer.seek(0)
    
    try:
        with tempfile.NamedTemporaryFile(
            suffix='.zip',
            prefix=f'natak_{rasa_label}_',
            delete=False,
        ) as tmp:
            tmp.write(zip_buffer.read())
            tmp_path = tmp.name
        
        _logger.info(
            f"Zip created for {rasa_label}: {tmp_path}, "
            f"{success_count} files, {len(errors)} errors"
        )
        
        if errors:
            _logger.warning(f"Zip errors: {errors}")
        
        return tmp_path, None
        
    except Exception as e:
        _logger.error(f"Zip write failed: {e}")
        return None, str(e)
