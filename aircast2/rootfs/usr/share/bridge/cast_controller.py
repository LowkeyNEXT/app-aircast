"""Chromecast playback control using pychromecast."""

from __future__ import annotations

import logging
from typing import Optional

import pychromecast

from .chromecast_discovery import ChromecastDiscovery
from .models import ChromecastDevice, ChromecastGroup

log = logging.getLogger(__name__)

# Default volume to restore when unmuting
DEFAULT_VOLUME = 0.5


class CastController:
    """Controls Chromecast playback — play, stop, mute, unmute, volume."""

    def __init__(self, discovery: ChromecastDiscovery):
        self._discovery = discovery
        self._connections: dict[str, pychromecast.Chromecast] = {}
        self._saved_volumes: dict[str, float] = {}

    async def cast_to_device(
        self, device: ChromecastDevice, audio_url: str
    ) -> None:
        """Start playing audio on a single Chromecast device."""
        cc = self._get_connection(device.host, device.port)
        if not cc:
            return

        cc.wait(timeout=10)
        mc = cc.media_controller
        mc.play_media(audio_url, "audio/flac", stream_type="LIVE")
        mc.block_until_active(timeout=30)

        log.info("Casting to '%s': %s", device.name, audio_url)

    async def cast_to_group(
        self, group: ChromecastGroup, audio_url: str
    ) -> None:
        """Start playing audio on a Chromecast group."""
        cc = self._get_connection(group.host, group.port)
        if not cc:
            return

        cc.wait(timeout=10)
        mc = cc.media_controller
        mc.play_media(audio_url, "audio/flac", stream_type="LIVE")
        mc.block_until_active(timeout=30)

        log.info("Casting to group '%s': %s", group.name, audio_url)

    async def stop_cast_device(self, device: ChromecastDevice) -> None:
        """Stop playback on a device."""
        key = f"{device.host}:{device.port}"
        cc = self._connections.get(key)
        if cc:
            try:
                cc.quit_app()
            except Exception:
                log.debug("Error stopping cast on '%s'", device.name)
            log.info("Stopped casting on '%s'", device.name)

    async def stop_cast_group(self, group: ChromecastGroup) -> None:
        """Stop playback on a group."""
        key = f"{group.host}:{group.port}"
        cc = self._connections.get(key)
        if cc:
            try:
                cc.quit_app()
            except Exception:
                log.debug("Error stopping cast on group '%s'", group.name)
            log.info("Stopped casting on group '%s'", group.name)

    async def mute_device_by_uuid(self, uuid: str) -> None:
        """Mute a Chromecast device (set volume to 0)."""
        device = self._discovery.get_device_by_uuid(uuid)
        if not device:
            log.warning("Cannot mute: device UUID %s not found", uuid)
            return

        cc = self._get_connection(device.host, device.port)
        if not cc:
            return

        cc.wait(timeout=10)

        # Save current volume for later restore
        try:
            current_vol = cc.status.volume_level
            self._saved_volumes[uuid] = current_vol
        except Exception:
            self._saved_volumes[uuid] = DEFAULT_VOLUME

        cc.set_volume(0)
        log.info("Muted '%s'", device.name)

    async def unmute_device_by_uuid(
        self, uuid: str, volume: Optional[float] = None
    ) -> None:
        """Unmute a Chromecast device (restore saved volume)."""
        device = self._discovery.get_device_by_uuid(uuid)
        if not device:
            log.warning("Cannot unmute: device UUID %s not found", uuid)
            return

        cc = self._get_connection(device.host, device.port)
        if not cc:
            return

        cc.wait(timeout=10)

        restore_vol = volume or self._saved_volumes.pop(uuid, DEFAULT_VOLUME)
        cc.set_volume(restore_vol)
        log.info("Unmuted '%s' (volume=%.2f)", device.name, restore_vol)

    async def set_volume_by_uuid(self, uuid: str, volume: float) -> None:
        """Set volume on a specific device."""
        device = self._discovery.get_device_by_uuid(uuid)
        if not device:
            return

        cc = self._get_connection(device.host, device.port)
        if not cc:
            return

        cc.wait(timeout=10)
        cc.set_volume(max(0.0, min(1.0, volume)))

    def _get_connection(
        self, host: str, port: int
    ) -> Optional[pychromecast.Chromecast]:
        """Get or create a pychromecast connection."""
        key = f"{host}:{port}"
        if key in self._connections:
            return self._connections[key]

        try:
            cc = pychromecast.Chromecast(host, port=port)
            self._connections[key] = cc
            return cc
        except Exception:
            log.error(
                "Failed to connect to Chromecast at %s:%d",
                host,
                port,
                exc_info=True,
            )
            return None

    def disconnect_all(self) -> None:
        """Disconnect all Chromecast connections."""
        for key, cc in self._connections.items():
            try:
                cc.disconnect()
            except Exception:
                pass
        self._connections.clear()
