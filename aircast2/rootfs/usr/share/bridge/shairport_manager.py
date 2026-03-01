"""Manages shairport-sync child processes — one per Chromecast device."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import string
from typing import Optional

from .config import BridgeConfig
from .models import AirPlayInstance, ChromecastDevice

log = logging.getLogger(__name__)

TEMPLATE_PATH = "/etc/shairport-sync.conf.tmpl"
PIPE_DIR = "/run/bridge/pipes"
CONFIG_DIR = "/run/bridge/configs"


def _sanitize_name(name: str) -> str:
    """Create a filesystem-safe identifier from a device name."""
    safe = re.sub(r"[^a-zA-Z0-9]", "_", name).strip("_").lower()
    return safe or "device"


class ShairportManager:
    """Spawns and manages shairport-sync instances."""

    def __init__(
        self, config: BridgeConfig, devices: dict[str, ChromecastDevice]
    ):
        self._config = config
        self._devices = devices
        self._instances: dict[str, AirPlayInstance] = {}
        self._template: str = ""

    async def start_all(self) -> dict[str, AirPlayInstance]:
        """Start a shairport-sync instance for each Chromecast device."""
        self._template = self._read_template()

        port = 5000
        for uuid, device in self._devices.items():
            instance = await self._start_instance(device, port)
            if instance:
                self._instances[device.name] = instance
            port += 1

        log.info(
            "Started %d shairport-sync instances", len(self._instances)
        )
        return dict(self._instances)

    async def stop_all(self) -> None:
        """Stop all shairport-sync instances."""
        for name, instance in self._instances.items():
            await self._stop_instance(instance)
        self._instances.clear()
        log.info("All shairport-sync instances stopped.")

    def get_instance(self, device_name: str) -> Optional[AirPlayInstance]:
        """Get an instance by its AirPlay device name."""
        return self._instances.get(device_name)

    def get_all_instances(self) -> dict[str, AirPlayInstance]:
        """Return all instances."""
        return dict(self._instances)

    async def _start_instance(
        self, device: ChromecastDevice, port: int
    ) -> Optional[AirPlayInstance]:
        """Create config, FIFO, and launch one shairport-sync process."""
        sanitized = _sanitize_name(device.name)
        pipe_path = os.path.join(PIPE_DIR, f"{sanitized}_audio")
        config_path = os.path.join(CONFIG_DIR, f"{sanitized}.conf")

        # Create named pipe (FIFO)
        if not os.path.exists(pipe_path):
            os.mkfifo(pipe_path)

        # Generate config from template
        airplay2_extra = ""
        if self._config.airplay_mode == "airplay2":
            # Generate a unique device ID from UUID
            mac = device.uuid.replace("-", "")[:12]
            mac_formatted = ":".join(
                mac[i : i + 2] for i in range(0, 12, 2)
            )
            airplay2_extra = f'airplay_device_id = "{mac_formatted}";'

        config_content = self._template
        config_content = config_content.replace(
            "${DEVICE_NAME}", device.name
        )
        config_content = config_content.replace("${PIPE_PATH}", pipe_path)
        config_content = config_content.replace(
            "${AIRPLAY_PORT}", str(port)
        )
        config_content = config_content.replace(
            "${MQTT_HOST}", self._config.mqtt_host
        )
        config_content = config_content.replace(
            "${MQTT_PORT}", str(self._config.mqtt_port)
        )
        config_content = config_content.replace(
            "${DEVICE_TOPIC}", sanitized
        )
        config_content = config_content.replace(
            "${AIRPLAY2_EXTRA}", airplay2_extra
        )

        with open(config_path, "w") as f:
            f.write(config_content)

        # Launch shairport-sync
        try:
            process = await asyncio.create_subprocess_exec(
                "shairport-sync", "-c", config_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            instance = AirPlayInstance(
                device_name=device.name,
                chromecast_uuid=device.uuid,
                pipe_path=pipe_path,
                config_path=config_path,
                mqtt_topic=f"shairport/{sanitized}",
                airplay_port=port,
                process=process,
            )

            log.info(
                "Started shairport-sync for '%s' on port %d (PID %d)",
                device.name,
                port,
                process.pid,
            )

            # Start a task to log stderr
            asyncio.create_task(
                self._log_output(device.name, process)
            )

            return instance

        except Exception:
            log.error(
                "Failed to start shairport-sync for '%s'",
                device.name,
                exc_info=True,
            )
            return None

    async def _stop_instance(self, instance: AirPlayInstance) -> None:
        """Stop one shairport-sync process."""
        if instance.process and instance.process.returncode is None:
            log.info("Stopping shairport-sync for '%s'", instance.device_name)
            instance.process.terminate()
            try:
                await asyncio.wait_for(instance.process.wait(), timeout=5)
            except asyncio.TimeoutError:
                log.warning(
                    "Force killing shairport-sync for '%s'",
                    instance.device_name,
                )
                instance.process.kill()
                await instance.process.wait()

        # Clean up FIFO
        if os.path.exists(instance.pipe_path):
            try:
                os.unlink(instance.pipe_path)
            except OSError:
                pass

    async def _log_output(
        self, name: str, process: asyncio.subprocess.Process
    ) -> None:
        """Log stderr output from a shairport-sync process."""
        if not process.stderr:
            return
        while True:
            line = await process.stderr.readline()
            if not line:
                break
            log.debug("[shairport/%s] %s", name, line.decode().rstrip())

    def _read_template(self) -> str:
        """Read the shairport-sync config template."""
        with open(TEMPLATE_PATH) as f:
            return f.read()
