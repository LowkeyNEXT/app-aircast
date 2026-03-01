"""MQTT listener for shairport-sync metadata events."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

import paho.mqtt.client as mqtt

from .config import BridgeConfig

log = logging.getLogger(__name__)


@dataclass
class ActiveInfo:
    """Tracking info for an active shairport-sync instance."""

    device_topic: str
    device_name: str
    active: bool = False
    client_ip: Optional[str] = None
    stream_type: Optional[str] = None
    activated_at: Optional[float] = None


ActivationCallback = Callable[[str, str, bool], None]
# (device_name, client_ip, is_active)


class MQTTListener:
    """Subscribes to shairport-sync MQTT topics to track active instances."""

    def __init__(
        self,
        config: BridgeConfig,
        device_names: list[str],
        loop: asyncio.AbstractEventLoop,
    ):
        self._config = config
        self._device_names = device_names
        self._loop = loop
        self._client: Optional[mqtt.Client] = None
        self._active: dict[str, ActiveInfo] = {}
        self._callbacks: list[ActivationCallback] = []

        # Build topic-to-device mapping
        self._topic_map: dict[str, str] = {}

    def on_activation_change(self, callback: ActivationCallback) -> None:
        """Register a callback for activation/deactivation events."""
        self._callbacks.append(callback)

    def start(self) -> None:
        """Connect to MQTT broker and subscribe to shairport topics."""
        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2, client_id="aircast2-bridge"
        )
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message

        try:
            self._client.connect(
                self._config.mqtt_host, self._config.mqtt_port
            )
            self._client.loop_start()
            log.info(
                "MQTT listener connected to %s:%d",
                self._config.mqtt_host,
                self._config.mqtt_port,
            )
        except Exception:
            log.error("Failed to connect to MQTT broker", exc_info=True)

    def stop(self) -> None:
        """Disconnect from MQTT broker."""
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            log.info("MQTT listener disconnected.")

    def get_active_from_client(self, client_ip: str) -> set[str]:
        """Return device names currently active from a given client IP."""
        return {
            info.device_name
            for info in self._active.values()
            if info.active and info.client_ip == client_ip
        }

    def is_active(self, device_name: str) -> bool:
        """Check if a device is currently active."""
        for info in self._active.values():
            if info.device_name == device_name:
                return info.active
        return False

    def _on_connect(
        self, client: mqtt.Client, userdata, flags, rc, properties=None
    ) -> None:
        """Subscribe to all shairport topics on connect."""
        client.subscribe("shairport/+/active")
        client.subscribe("shairport/+/client_ip")
        client.subscribe("shairport/+/stream_type")
        client.subscribe("shairport/+/playing")
        log.info("Subscribed to shairport MQTT topics.")

    def _on_message(
        self, client: mqtt.Client, userdata, msg: mqtt.MQTTMessage
    ) -> None:
        """Handle incoming MQTT messages from shairport-sync instances."""
        try:
            parts = msg.topic.split("/")
            if len(parts) != 3 or parts[0] != "shairport":
                return

            device_topic = parts[1]
            field_name = parts[2]
            value = msg.payload.decode("utf-8", errors="replace").strip()

            # Initialize tracking if needed
            if device_topic not in self._active:
                self._active[device_topic] = ActiveInfo(
                    device_topic=device_topic,
                    device_name=device_topic,
                )

            info = self._active[device_topic]

            if field_name == "client_ip":
                info.client_ip = value

            elif field_name == "stream_type":
                info.stream_type = value

            elif field_name == "active":
                was_active = info.active
                is_active = value == "1" or value.lower() == "yes"
                info.active = is_active

                if is_active and not was_active:
                    info.activated_at = time.monotonic()
                    log.info(
                        "AirPlay active: %s (client: %s)",
                        device_topic,
                        info.client_ip,
                    )
                    self._fire_callback(
                        info.device_name, info.client_ip or "", True
                    )

                elif was_active and not is_active:
                    info.activated_at = None
                    log.info("AirPlay inactive: %s", device_topic)
                    self._fire_callback(
                        info.device_name, info.client_ip or "", False
                    )

        except Exception:
            log.warning(
                "Error processing MQTT message: %s", msg.topic, exc_info=True
            )

    def _fire_callback(
        self, device_name: str, client_ip: str, is_active: bool
    ) -> None:
        """Fire activation callbacks on the asyncio event loop."""
        for cb in self._callbacks:
            self._loop.call_soon_threadsafe(
                self._loop.create_task,
                self._async_callback(cb, device_name, client_ip, is_active),
            )

    @staticmethod
    async def _async_callback(
        cb: ActivationCallback,
        device_name: str,
        client_ip: str,
        is_active: bool,
    ) -> None:
        """Wrapper to call sync callbacks from async context."""
        try:
            result = cb(device_name, client_ip, is_active)
            if asyncio.iscoroutine(result):
                await result
        except Exception:
            log.error("Error in activation callback", exc_info=True)
