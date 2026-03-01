"""Stream pipeline — ties audio server and cast controller for one active stream."""

from __future__ import annotations

import logging
from typing import Optional

from .audio_server import AudioServer
from .cast_controller import CastController
from .models import AirPlayInstance, CastTarget

log = logging.getLogger(__name__)


class StreamPipeline:
    """Manages the full lifecycle of one audio stream."""

    def __init__(
        self,
        instance: AirPlayInstance,
        cast_controller: CastController,
        host_ip: str,
        port: int,
    ):
        self._instance = instance
        self._cast_ctrl = cast_controller
        self._audio_server = AudioServer(host_ip, port, instance.pipe_path)
        self._target: Optional[CastTarget] = None
        self._active = False

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def target(self) -> Optional[CastTarget]:
        return self._target

    async def start(self, target: CastTarget) -> None:
        """Start the audio pipeline: HTTP server → Chromecast."""
        self._target = target
        self._active = True

        # Start audio server (ffmpeg + HTTP)
        audio_url = await self._audio_server.start()

        # Cast to the target
        if target.is_group and target.group:
            await self._cast_ctrl.cast_to_group(target.group, audio_url)
        elif target.device:
            await self._cast_ctrl.cast_to_device(target.device, audio_url)

        # Apply muting
        for uuid in target.mute_uuids:
            await self._cast_ctrl.mute_device_by_uuid(uuid)

        log.info(
            "Pipeline started: %s → %s",
            self._instance.device_name,
            target.name,
        )

    async def stop(self) -> None:
        """Stop the audio pipeline."""
        self._active = False

        # Unmute all muted devices
        if self._target:
            for uuid in self._target.mute_uuids:
                await self._cast_ctrl.unmute_device_by_uuid(uuid)

            # Stop casting
            if self._target.is_group and self._target.group:
                await self._cast_ctrl.stop_cast_group(self._target.group)
            elif self._target.device:
                await self._cast_ctrl.stop_cast_device(self._target.device)

        # Stop audio server
        await self._audio_server.stop()

        log.info(
            "Pipeline stopped: %s", self._instance.device_name
        )
        self._target = None

    async def update_muting(
        self, mute_uuids: list[str], unmute_uuids: list[str]
    ) -> None:
        """Update muting when AirPlay selection changes mid-stream."""
        for uuid in mute_uuids:
            await self._cast_ctrl.mute_device_by_uuid(uuid)
        for uuid in unmute_uuids:
            await self._cast_ctrl.unmute_device_by_uuid(uuid)

        if self._target:
            self._target.mute_uuids = mute_uuids
