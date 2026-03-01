"""Configuration management for the bridge service."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class BridgeConfig:
    """Bridge configuration read from environment variables."""

    log_level: str = "info"
    mode: str = "easy"
    latency_offset: int = 0
    airplay_mode: str = "classic"
    whole_house_group: str = ""
    mqtt_host: str = "127.0.0.1"
    mqtt_port: int = 1883
    http_port_base: int = 8089
    excluded_devices: list[str] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> BridgeConfig:
        """Create config from environment variables set by the s6 run script."""
        excluded_raw = os.environ.get("BRIDGE_EXCLUDED_DEVICES", "")
        excluded = [
            d.strip() for d in excluded_raw.split(",") if d.strip()
        ]

        return cls(
            log_level=os.environ.get("BRIDGE_LOG_LEVEL", "info"),
            mode=os.environ.get("BRIDGE_MODE", "easy"),
            latency_offset=int(os.environ.get("BRIDGE_LATENCY_OFFSET", "0")),
            airplay_mode=os.environ.get("BRIDGE_AIRPLAY_MODE", "classic"),
            whole_house_group=os.environ.get("BRIDGE_WHOLE_HOUSE_GROUP", ""),
            mqtt_host=os.environ.get("BRIDGE_MQTT_HOST", "127.0.0.1"),
            mqtt_port=int(os.environ.get("BRIDGE_MQTT_PORT", "1883")),
            http_port_base=int(
                os.environ.get("BRIDGE_HTTP_PORT_BASE", "8089")
            ),
            excluded_devices=excluded,
        )
