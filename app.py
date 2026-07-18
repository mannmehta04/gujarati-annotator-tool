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
    try:
        import yt_dlp   # noqa: F401
    except ImportError:
        missing.append("yt-dlp")

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

    # yt-dlp CLI check (warn only — Python package still works)
    import shutil
    if not shutil.which("yt-dlp"):
        print("⚠️  yt-dlp CLI not found on PATH.")
        print("   Attempting to install via pip...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--break-system-packages", "yt-dlp"],
            check=False
        )



if __name__ == "__main__":
    check_dependencies()

    from config.settings import makeDir, PORT, HOST
    from config.settings import (
        TEMP_VIDEO_DIR,
        PREVIEW_CACHE_DIR, VIDEO_DIR, DATASET_DIR
    )
    makeDir()

    from views.ui import build_ui, CUSTOM_CSS, CUSTOM_JS
    app = build_ui()

    print(f"\n{'='*50}")
    print(f"🎬 VIDEO ANNOTATOR")
    print(f"{'='*50}")
    print(f"🌐 http://localhost:{PORT}")
    print(f"{'='*50}\n")

    from fastapi import FastAPI, Request
    from fastapi.responses import StreamingResponse, Response
    import urllib.parse
    import httpx
    import uvicorn
    import gradio as gr

    fastapi_app = FastAPI()

    @fastapi_app.get("/proxy/video")
    async def proxy_video_stream(request: Request, url: str):
        """
        Proxies video stream from a remote URL through the Gradio server.
        
        Correctly handles:
        - Initial full GET requests (returns 200)
        - Browser range requests for seeking (returns 206 with Content-Range)
        - Upstream URLs that respond with 206 to any request
        - CORS restrictions on YouTube CDN URLs
        
        No data is written to disk at any point.
        Data passes through server memory in chunks only.
        """
        decoded_url = urllib.parse.unquote(url)
        
        # Headers for upstream request — mimic a legitimate browser
        upstream_headers = {
            'User-Agent': (
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ),
            'Accept': '*/*',
            'Accept-Encoding': 'identity',  # Critical: disable compression for video streaming
            'Connection': 'keep-alive',
        }
        
        # Only forward Range header if the browser explicitly sent one
        # Do NOT add a Range header if the browser did not send one
        browser_range = request.headers.get('range')
        if browser_range:
            upstream_headers['Range'] = browser_range
            
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=15.0),
            follow_redirects=True,
        )
        
        try:
            # Use a single streaming request — do NOT do a HEAD request first
            # Instead, make the actual GET request and read headers from it directly
            upstream_request = client.build_request('GET', decoded_url, headers=upstream_headers)
            upstream_response = await client.send(upstream_request, stream=True)
            
            # Build response headers from actual upstream response
            response_headers = {
                'Accept-Ranges': 'bytes',
                'Access-Control-Allow-Origin': '*',
                'Cache-Control': 'no-cache',
            }
            
            # Forward Content-Type from upstream
            content_type = upstream_response.headers.get('content-type', 'video/mp4')
            response_headers['Content-Type'] = content_type
            
            # Forward Content-Length if upstream provides it
            content_length = upstream_response.headers.get('content-length')
            if content_length:
                response_headers['Content-Length'] = content_length
            
            # Forward Content-Range if upstream provides it
            # This happens when browser sent a Range header and upstream honored it
            content_range = upstream_response.headers.get('content-range')
            if content_range:
                response_headers['Content-Range'] = content_range
            
            # Determine correct status code:
            upstream_status = upstream_response.status_code
            if browser_range and upstream_status == 206:
                # Legitimate range response — browser asked for range, upstream gave range
                response_status = 206
            else:
                # Either no range was requested, or upstream returned full content
                # Always serve as 200 to avoid confusing the browser or Gradio
                response_status = 200

            async def stream_chunks():
                """
                Streams response body from upstream to browser in chunks.
                Never accumulates the full response — pure pass-through.
                No disk writes at any point.
                """
                try:
                    async for chunk in upstream_response.aiter_bytes(chunk_size=65536):
                        yield chunk
                finally:
                    await upstream_response.aclose()
                    await client.aclose()

            return StreamingResponse(
                stream_chunks(),
                status_code=response_status,
                headers=response_headers,
                media_type=content_type,
            )
            
        except httpx.TimeoutException:
            await client.aclose()
            return Response(content="Proxy timeout: upstream server did not respond in time.", status_code=504)
        except httpx.RequestError as e:
            await client.aclose()
            return Response(content=f"Proxy connection error: {str(e)}", status_code=502)
        except Exception as e:
            await client.aclose()
            return Response(content=f"Proxy error: {str(e)}", status_code=500)

    from fastapi import Query
    import shlex
    import asyncio
    from fastapi.responses import JSONResponse

    # ARCHITECTURE: Zero Server Storage Download
    # 
    # This endpoint implements a zero-storage video download pipeline:
    #
    # 1. yt-dlp Python API (download=False, skip_download=True) — extracts
    #    the direct CDN stream URL for the requested format. No bytes of
    #    video data are written to disk at this step.
    #
    # 2. httpx AsyncClient.stream() — opens an HTTP connection to the CDN
    #    stream URL and reads it in 64KB chunks.
    #
    # 3. FastAPI StreamingResponse — each chunk received from httpx is
    #    immediately forwarded to the browser HTTP response. Chunks are
    #    never accumulated in memory beyond one chunk at a time.
    #
    # 4. Browser receives Content-Disposition: attachment header — triggers
    #    the browser's native Save File dialog. The browser writes the
    #    file directly to the user's chosen download location.
    #
    # Result: Zero bytes written to any server disk. Zero temp files.
    #         The server acts as a transparent streaming proxy only.
    #
    # Do NOT add ydl.download() or any file write operation here.
    # Do NOT use tempfile, open(), or any I/O operation on video data.
    @fastapi_app.get("/download/video")
    async def stream_download_to_browser(
        request: Request,
        url: str = Query(...),
        format_id: str = Query(default="auto"),
        quality: str = Query(default="best"),
        ext: str = Query(default="mp4"),
    ):
        decoded_url = urllib.parse.unquote(url)
        
        try:
            stream_url, title, actual_ext, requires_wav_conversion = (
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: _extract_download_stream_url(
                        decoded_url, format_id, quality, ext
                    )
                )
            )
        except Exception as e:
            return Response(
                content=f"Failed to resolve video: {str(e)}",
                status_code=400,
                media_type="text/plain",
            )
        
        safe_title = _sanitize_filename(title)
        encoded_filename = urllib.parse.quote(f"{safe_title}.{actual_ext}")
        
        response_headers = {
            'Content-Disposition': (
                f'attachment; '
                f'filename="{safe_title}.{actual_ext}"; '
                f"filename*=UTF-8''{encoded_filename}"
            ),
            'Content-Type': (
                'audio/wav' if actual_ext == 'wav'
                else f'video/{actual_ext}'
            ),
            'Accept-Ranges': 'bytes',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Expose-Headers': 'Content-Disposition, Content-Length',
            'Cache-Control': 'no-cache, no-store',
            'X-Accel-Buffering': 'no',
            'X-Content-Type-Options': 'nosniff',
        }
        
        if requires_wav_conversion:
            # WAV conversion: pipe audio stream through ffmpeg to convert to WAV
            # ffmpeg reads from the stream URL and writes WAV to stdout
            # No temp files — pure pipe
            
            async def wav_conversion_generator():
                """
                Runs ffmpeg as subprocess to convert audio stream to WAV.
                ffmpeg reads from URL directly (-i url) and writes WAV to stdout (-).
                No temp files at any point.
                """
                cmd = [
                    'ffmpeg',
                    '-reconnect', '1',
                    '-reconnect_streamed', '1',
                    '-reconnect_delay_max', '5',
                    '-i', stream_url,
                    '-vn',                    # No video
                    '-acodec', 'pcm_s16le',  # WAV PCM format
                    '-ar', '44100',           # Sample rate
                    '-ac', '2',               # Stereo
                    '-f', 'wav',              # Output format
                    '-',                      # Write to stdout
                ]
                
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                
                try:
                    chunk_size = 65536
                    while True:
                        chunk = await process.stdout.read(chunk_size)
                        if not chunk:
                            break
                        yield chunk
                except asyncio.CancelledError:
                    process.kill()
                    await process.wait()
                    return
                except Exception:
                    process.kill()
                    await process.wait()
                    return
                finally:
                    try:
                        await process.wait()
                    except Exception:
                        pass
            
            return StreamingResponse(
                content=wav_conversion_generator(),
                status_code=200,
                headers=response_headers,
                media_type='audio/wav',
            )
        
        # Standard video/audio streaming via httpx
        upstream_headers = {
            'User-Agent': (
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ),
            'Accept': '*/*',
            'Accept-Encoding': 'identity',
            'Connection': 'keep-alive',
            'Referer': 'https://www.youtube.com/',
        }
        
        browser_range = request.headers.get('range')
        if browser_range:
            upstream_headers['Range'] = browser_range
        
        async def video_stream_generator():
            """
            Streams video from upstream URL directly to browser.
            Client lifecycle is owned by generator — never closes prematurely.
            """
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=15.0,
                    read=300.0,
                    write=60.0,
                    pool=300.0,
                ),
                follow_redirects=True,
            ) as client:
                try:
                    async with client.stream(
                        'GET',
                        stream_url,
                        headers=upstream_headers,
                    ) as upstream_response:
                        if upstream_response.status_code >= 400:
                            return
                        async for chunk in upstream_response.aiter_bytes(65536):
                            yield chunk
                except (asyncio.CancelledError, Exception):
                    return
        
        # Get content length via HEAD request
        content_length = None
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(10.0),
                follow_redirects=True,
            ) as hc:
                hr = await hc.head(stream_url, headers=upstream_headers)
                content_length = hr.headers.get('content-length')
                ct = hr.headers.get('content-type')
                if ct:
                    response_headers['Content-Type'] = ct
        except Exception:
            pass
        
        if content_length:
            response_headers['Content-Length'] = content_length
        
        return StreamingResponse(
            content=video_stream_generator(),
            status_code=200,
            headers=response_headers,
            media_type=response_headers.get('Content-Type', f'video/{actual_ext}'),
        )


    @fastapi_app.get("/download/info")
    async def get_video_info(
        url: str = Query(..., description="Video URL to fetch info for"),
    ):
        """
        Fetches video metadata (title, available formats, duration, thumbnail)
        using yt-dlp without downloading anything.
        """
        decoded_url = urllib.parse.unquote(url)
        
        try:
            import yt_dlp
            
            ydl_opts = {
                'skip_download': True,
                'quiet': True,
                'no_warnings': True,
                'cachedir': False,
                'nopart': True,
                'writethumbnail': False,
                'writeinfojson': False,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(decoded_url, download=False)
                
                if 'entries' in info:
                    info = next(iter(info['entries']), None)
                    if info is None:
                        return JSONResponse({'error': 'Playlist is empty'}, status_code=400)
                
                formats = []
                for f in info.get('formats', []):
                    format_entry = {
                        'format_id': f.get('format_id', ''),
                        'ext': f.get('ext', ''),
                        'resolution': f.get('resolution') or f.get('format_note', ''),
                        'filesize': f.get('filesize') or f.get('filesize_approx'),
                        'vcodec': f.get('vcodec', ''),
                        'acodec': f.get('acodec', ''),
                        'tbr': f.get('tbr'),
                        'format_note': f.get('format_note', ''),
                    }
                    formats.append(format_entry)
                
                return JSONResponse({
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration'),
                    'thumbnail': info.get('thumbnail'),
                    'uploader': info.get('uploader', ''),
                    'formats': formats,
                    'webpage_url': info.get('webpage_url', decoded_url),
                })
                
        except Exception as e:
            return JSONResponse({'error': str(e)}, status_code=500)


    def _build_safe_format_string(format_id: str, quality: str, ext: str) -> str:
        """
        Builds yt-dlp format string selecting only pre-muxed or audio streams.
        Handles WAV as a special case requiring audio extraction.
        Never uses '+' operator to avoid merge requirement.
        """
        # WAV requires audio-only stream selection
        # Conversion is handled separately via ffmpeg post-processing
        if ext == 'wav':
            if format_id and format_id not in ("auto", "best", "", "none"):
                return f"{format_id}/bestaudio"
            return "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio"
        
        # When quality and ext are defaults, use format_id primarily
        if quality == "best" and ext == "mp4":
            if format_id and format_id not in ("auto", "best", "", "none"):
                return format_id
            return "best"
        
        # Audio only quality selection
        if quality == "audio":
            if ext in ('m4a', 'mp3'):
                return f"bestaudio[ext={ext}]/bestaudio"
            return "bestaudio[ext=m4a]/bestaudio"
        
        # Specific format ID selected by user
        if format_id and format_id not in ("auto", "best", "", "none"):
            return f"{format_id}/best[ext={ext}]/best"
        
        # Quality-based pre-muxed selection
        height_map = {
            "1080p": 1080,
            "720p": 720,
            "480p": 480,
            "360p": 360,
            "240p": 240,
        }
        height = height_map.get(quality)
        
        if height:
            return (
                f"best[height<={height}][ext={ext}]"
                f"/best[height<={height}]"
                f"/best[ext={ext}]"
                f"/best"
            )
        
        return f"best[ext={ext}]/best"

    # ARCHITECTURE: Zero Server Storage Download
    #
    # Do NOT add ydl.download() or any file write operation here.
    # Do NOT use tempfile, open(), or any I/O operation on video data.
    def _extract_download_stream_url(
        url: str,
        format_id: str,
        quality: str,
        ext: str,
    ) -> tuple:
        """
        Extracts stream URL for direct streaming downloads.
        For WAV format, returns a special marker since WAV requires conversion.
        Returns (stream_url_or_marker, title, actual_ext, requires_conversion)
        """
        import yt_dlp
        
        is_wav = ext == 'wav'
        format_string = _build_safe_format_string(format_id, quality, ext)
        
        ydl_opts = {
            'format': format_string,
            'skip_download': True,
            'quiet': True,
            'no_warnings': True,
            'cachedir': False,
            'nopart': True,
            'writethumbnail': False,
            'writeinfojson': False,
            'writedescription': False,
            'writesubtitles': False,
            'writeautomaticsub': False,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if 'entries' in info:
                info = next(iter(info['entries']), None)
                if info is None:
                    raise ValueError("Playlist is empty or unavailable.")
            
            stream_url = info.get('url')
            
            if not stream_url:
                requested = info.get('requested_formats', [])
                if requested:
                    stream_url = requested[0].get('url')
            
            if not stream_url:
                raise ValueError("Could not extract a direct stream URL.")
            
            title = info.get('title', 'video')
            actual_ext = 'wav' if is_wav else info.get('ext', ext)
            
            return stream_url, title, actual_ext, is_wav

    def _sanitize_filename(title: str) -> str:
        """
        Sanitizes a video title for use as a download filename.
        Removes characters that are invalid in filenames across OS platforms.
        """
        import re
        # Replace invalid filename characters with underscore
        sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', title)
        # Replace multiple consecutive underscores/spaces with single space
        sanitized = re.sub(r'[\s_]+', ' ', sanitized).strip()
        # Limit length
        return sanitized[:100] if sanitized else 'video'

    from config.settings import SCRIPT_DIR
    import starlette.background
    import os

    @fastapi_app.get("/segment/audio/{segment_id}")
    async def stream_segment_audio(segment_id: str):
        """Streams extracted audio for preview."""
        from controllers.supabase_sync import fetch_annotation_by_id
        from controllers.media_extractor import extract_audio_bytes
        
        row, err = fetch_annotation_by_id(segment_id)
        if not row:
            return Response(status_code=404, content=err or "Not found")
            
        audio_bytes, extract_err = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: extract_audio_bytes(
                row.get('source_video'),
                float(row.get('start_time')),
                float(row.get('end_time')),
                segment_id
            )
        )
        
        if not audio_bytes:
            return Response(status_code=500, content=extract_err or "Extraction failed")
            
        return Response(content=audio_bytes, media_type="audio/wav")

    @fastapi_app.get("/segment/video/{segment_id}")
    async def stream_segment_video(segment_id: str):
        """Streams extracted video for preview."""
        from controllers.supabase_sync import fetch_annotation_by_id
        from controllers.media_extractor import extract_video_bytes
        
        row, err = fetch_annotation_by_id(segment_id)
        if not row:
            return Response(status_code=404, content=err or "Not found")
            
        video_bytes, extract_err = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: extract_video_bytes(
                row.get('source_video'),
                float(row.get('start_time')),
                float(row.get('end_time')),
                segment_id
            )
        )
        
        if not video_bytes:
            return Response(status_code=500, content=extract_err or "Extraction failed")
            
        return Response(content=video_bytes, media_type="video/mp4")

    @fastapi_app.get("/segment/download/audio/{segment_id}")
    async def download_segment_audio(segment_id: str):
        from controllers.supabase_sync import fetch_annotation_by_id
        from controllers.media_extractor import extract_audio_to_tempfile
        from fastapi.responses import FileResponse
        
        row, err = fetch_annotation_by_id(segment_id)
        if not row:
            return Response(status_code=404, content=err or "Not found")
            
        tmp_path, extract_err = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: extract_audio_to_tempfile(
                row.get('source_video'),
                float(row.get('start_time')),
                float(row.get('end_time')),
                segment_id
            )
        )
        
        if not tmp_path:
            return Response(status_code=500, content=extract_err or "Extraction failed")
            
        filename = f"{segment_id}.wav"
        return FileResponse(
            path=tmp_path,
            media_type='audio/wav',
            filename=filename,
            background=starlette.background.BackgroundTask(lambda: os.unlink(tmp_path) if os.path.exists(tmp_path) else None)
        )

    @fastapi_app.get("/segment/download/video/{segment_id}")
    async def download_segment_video(segment_id: str):
        from controllers.supabase_sync import fetch_annotation_by_id
        from controllers.media_extractor import extract_video_to_tempfile
        from fastapi.responses import FileResponse
        
        row, err = fetch_annotation_by_id(segment_id)
        if not row:
            return Response(status_code=404, content=err or "Not found")
            
        tmp_path, extract_err = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: extract_video_to_tempfile(
                row.get('source_video'),
                float(row.get('start_time')),
                float(row.get('end_time')),
                segment_id
            )
        )
        
        if not tmp_path:
            return Response(status_code=500, content=extract_err or "Extraction failed")
            
        filename = f"{segment_id}.mp4"
        return FileResponse(
            path=tmp_path,
            media_type='video/mp4',
            filename=filename,
            background=starlette.background.BackgroundTask(lambda: os.unlink(tmp_path) if os.path.exists(tmp_path) else None)
        )
    
    app.queue(api_open=False)
    fastapi_app = gr.mount_gradio_app(
        fastapi_app,
        app,
        path="/",
        js=CUSTOM_JS,
        css=CUSTOM_CSS,
        allowed_paths=[
            str(TEMP_VIDEO_DIR),
            str(PREVIEW_CACHE_DIR),
            str(VIDEO_DIR),
            str(DATASET_DIR),
            str(SCRIPT_DIR),
        ]
    )

    uvicorn.run(fastapi_app, host=HOST, port=PORT)

