"""HTTP audio server — encodes PCM from FIFO and serves FLAC to Chromecast."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from aiohttp import web

log = logging.getLogger(__name__)

# Read chunks of 8KB from ffmpeg
CHUNK_SIZE = 8192


class AudioServer:
    """Serves encoded audio from a named pipe via HTTP.

    The Chromecast fetches audio from this server. Audio is read from
    a shairport-sync FIFO (raw PCM S16LE 44100Hz stereo), encoded to
    FLAC via ffmpeg, and served as a chunked HTTP stream.
    """

    def __init__(self, host: str, port: int, pipe_path: str):
        self._host = host
        self._port = port
        self._pipe_path = pipe_path
        self._app: Optional[web.Application] = None
        self._runner: Optional[web.AppRunner] = None
        self._ffmpeg: Optional[asyncio.subprocess.Process] = None
        self._serving = False

    @property
    def url(self) -> str:
        """The URL Chromecast should fetch audio from."""
        return f"http://{self._host}:{self._port}/audio.flac"

    async def start(self) -> str:
        """Start the HTTP server. Returns the audio URL."""
        self._app = web.Application()
        self._app.router.add_get("/audio.flac", self._handle_audio)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()

        site = web.TCPSite(self._runner, "0.0.0.0", self._port)
        await site.start()
        self._serving = True

        log.info(
            "Audio server started on port %d, serving %s",
            self._port,
            self._pipe_path,
        )
        return self.url

    async def stop(self) -> None:
        """Stop the HTTP server and ffmpeg process."""
        self._serving = False

        if self._ffmpeg and self._ffmpeg.returncode is None:
            self._ffmpeg.terminate()
            try:
                await asyncio.wait_for(self._ffmpeg.wait(), timeout=3)
            except asyncio.TimeoutError:
                self._ffmpeg.kill()
                await self._ffmpeg.wait()
            self._ffmpeg = None

        if self._runner:
            await self._runner.cleanup()
            self._runner = None

        log.info("Audio server on port %d stopped.", self._port)

    async def _handle_audio(
        self, request: web.Request
    ) -> web.StreamResponse:
        """Handle GET /audio.flac — stream encoded audio from the FIFO."""
        response = web.StreamResponse(
            status=200,
            headers={
                "Content-Type": "audio/flac",
                "Transfer-Encoding": "chunked",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )
        await response.prepare(request)

        # Start ffmpeg: read raw PCM from pipe, encode to FLAC, write to stdout
        self._ffmpeg = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "warning",
            "-f", "s16le",       # input format: signed 16-bit little-endian
            "-ar", "44100",      # sample rate
            "-ac", "2",          # stereo
            "-i", self._pipe_path,
            "-f", "flac",        # output format
            "-compression_level", "0",  # fastest encoding
            "pipe:1",            # output to stdout
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        log.info("ffmpeg encoding started for %s", self._pipe_path)

        # Start a task to log ffmpeg errors
        asyncio.create_task(self._log_ffmpeg_stderr())

        try:
            while self._serving and self._ffmpeg.returncode is None:
                chunk = await self._ffmpeg.stdout.read(CHUNK_SIZE)
                if not chunk:
                    break
                await response.write(chunk)
        except (ConnectionResetError, ConnectionError):
            log.info("Chromecast disconnected from audio stream.")
        except Exception:
            log.warning("Error streaming audio", exc_info=True)
        finally:
            if self._ffmpeg and self._ffmpeg.returncode is None:
                self._ffmpeg.terminate()
                await self._ffmpeg.wait()
            await response.write_eof()

        return response

    async def _log_ffmpeg_stderr(self) -> None:
        """Log ffmpeg stderr output."""
        if not self._ffmpeg or not self._ffmpeg.stderr:
            return
        while True:
            line = await self._ffmpeg.stderr.readline()
            if not line:
                break
            log.debug("[ffmpeg] %s", line.decode().rstrip())
