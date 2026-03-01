"""Chromecast device and group discovery using pychromecast."""

from __future__ import annotations

import logging
import threading
from typing import Optional

import pychromecast
from pychromecast.controllers.multizone import MultizoneController

from .models import ChromecastDevice, ChromecastGroup

log = logging.getLogger(__name__)


class ChromecastDiscovery:
    """Discovers Chromecast devices and groups on the local network."""

    def __init__(self, excluded_devices: list[str] | None = None):
        self._excluded = set(excluded_devices or [])
        self._devices: dict[str, ChromecastDevice] = {}
        self._groups: dict[str, ChromecastGroup] = {}
        self._browser: Optional[pychromecast.CastBrowser] = None
        self._zconf: Optional[pychromecast.zeroconf.CastZeroconf] = None
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start mDNS discovery (runs in background threads)."""
        log.info("Starting Chromecast discovery...")
        chromecasts, browser = pychromecast.get_chromecasts()
        self._browser = browser

        for cc in chromecasts:
            self._add_cast(cc)

    def stop(self) -> None:
        """Stop discovery and clean up."""
        if self._browser:
            self._browser.stop_discovery()
            log.info("Chromecast discovery stopped.")

    def refresh(self) -> None:
        """Re-scan for devices and groups."""
        if self._browser:
            self.stop()
        self._devices.clear()
        self._groups.clear()
        self.start()

    def _add_cast(self, cc: pychromecast.Chromecast) -> None:
        """Process a discovered Chromecast."""
        name = cc.cast_info.friendly_name
        uuid_str = str(cc.cast_info.uuid)
        host = cc.cast_info.host
        port = cc.cast_info.port
        cast_type = cc.cast_info.cast_type

        if name in self._excluded:
            log.debug("Skipping excluded device: %s", name)
            return

        with self._lock:
            if cast_type == "group":
                group = ChromecastGroup(
                    name=name, uuid=uuid_str, host=host, port=port
                )
                self._groups[uuid_str] = group
                log.info("Discovered Chromecast group: %s", name)
                self._load_group_members(cc, group)
            else:
                device = ChromecastDevice(
                    name=name,
                    uuid=uuid_str,
                    host=host,
                    port=port,
                    cast_type=cast_type,
                )
                self._devices[uuid_str] = device
                log.info("Discovered Chromecast: %s (%s)", name, host)

    def _load_group_members(
        self, cc: pychromecast.Chromecast, group: ChromecastGroup
    ) -> None:
        """Load group member list via MultizoneController."""
        try:
            cc.wait(timeout=10)
            mz = MultizoneController(cc.uuid)
            cc.register_handler(mz)
            mz.update_members()
            # Give it a moment to receive the status
            cc.socket_client.socket.settimeout(5)
            import time
            time.sleep(3)

            for member_uuid, member_name in mz._members.items():
                group.member_uuids.append(str(member_uuid))
                group.member_names.append(member_name)
                log.debug(
                    "  Group '%s' member: %s (%s)",
                    group.name,
                    member_name,
                    member_uuid,
                )
        except Exception:
            log.warning(
                "Failed to load members for group '%s'", group.name,
                exc_info=True,
            )

    def get_devices(self) -> dict[str, ChromecastDevice]:
        """Return discovered devices keyed by UUID."""
        with self._lock:
            return dict(self._devices)

    def get_groups(self) -> dict[str, ChromecastGroup]:
        """Return discovered groups keyed by UUID."""
        with self._lock:
            return dict(self._groups)

    def get_device_by_name(self, name: str) -> Optional[ChromecastDevice]:
        """Find a device by friendly name."""
        with self._lock:
            for dev in self._devices.values():
                if dev.name == name:
                    return dev
        return None

    def get_device_by_uuid(self, uuid: str) -> Optional[ChromecastDevice]:
        """Find a device by UUID."""
        with self._lock:
            return self._devices.get(uuid)

    def get_group_by_name(self, name: str) -> Optional[ChromecastGroup]:
        """Find a group by friendly name."""
        with self._lock:
            for grp in self._groups.values():
                if grp.name == name:
                    return grp
        return None

    def find_best_group(
        self, device_uuids: set[str]
    ) -> Optional[ChromecastGroup]:
        """Find the group whose members best match the given device set.

        Uses Jaccard similarity: |intersection| / |union|.
        Returns the group with the highest score (>= 0.5), or None.
        """
        best_group = None
        best_score = 0.0

        with self._lock:
            for group in self._groups.values():
                member_set = set(group.member_uuids)
                if not member_set:
                    continue

                intersection = member_set & device_uuids
                union = member_set | device_uuids
                score = len(intersection) / len(union) if union else 0.0

                if score > best_score:
                    best_score = score
                    best_group = group

        if best_score >= 0.5 and best_group:
            log.info(
                "Best group match: '%s' (score=%.2f)",
                best_group.name,
                best_score,
            )
            return best_group

        return None

    def find_largest_group(self) -> Optional[ChromecastGroup]:
        """Find the group with the most members (for easy mode auto-detect)."""
        with self._lock:
            if not self._groups:
                return None
            return max(
                self._groups.values(), key=lambda g: len(g.member_uuids)
            )
