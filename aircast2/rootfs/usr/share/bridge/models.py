"""Data models for the AirCast 2 bridge."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class StreamState(Enum):
    """State of an AirPlay-to-Chromecast stream."""

    IDLE = "idle"
    ACTIVE = "active"
    DRAINING = "draining"


@dataclass
class ChromecastDevice:
    """A discovered Chromecast device."""

    name: str
    uuid: str
    host: str
    port: int
    cast_type: str = "cast"
    group_uuids: list[str] = field(default_factory=list)


@dataclass
class ChromecastGroup:
    """A discovered Chromecast speaker group."""

    name: str
    uuid: str
    host: str
    port: int
    member_uuids: list[str] = field(default_factory=list)
    member_names: list[str] = field(default_factory=list)


@dataclass
class AirPlayInstance:
    """A shairport-sync instance bridging to one Chromecast."""

    device_name: str
    chromecast_uuid: str
    pipe_path: str
    config_path: str
    mqtt_topic: str
    airplay_port: int
    process: Optional[asyncio.subprocess.Process] = None
    state: StreamState = StreamState.IDLE
    client_ip: Optional[str] = None
    http_port: int = 0
    active_since: Optional[float] = None


@dataclass
class CastTarget:
    """Resolved target for casting audio."""

    is_group: bool
    device: Optional[ChromecastDevice] = None
    group: Optional[ChromecastGroup] = None
    mute_uuids: list[str] = field(default_factory=list)
    unmute_uuids: list[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        if self.group:
            return self.group.name
        if self.device:
            return self.device.name
        return "unknown"
