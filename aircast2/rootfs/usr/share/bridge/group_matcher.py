"""Smart group matching — maps active AirPlay selections to Chromecast groups."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from .chromecast_discovery import ChromecastDiscovery
from .config import BridgeConfig
from .models import CastTarget, ChromecastGroup

log = logging.getLogger(__name__)

# How long to wait for additional AirPlay activations before resolving
GROUPING_WINDOW_SECONDS = 3.0


class GroupMatcher:
    """Detects multi-device AirPlay selection and resolves cast targets."""

    def __init__(self, config: BridgeConfig, discovery: ChromecastDiscovery):
        self._config = config
        self._discovery = discovery
        # Pending activations per client IP: {client_ip: set(device_names)}
        self._pending: dict[str, set[str]] = {}
        self._timers: dict[str, asyncio.TimerHandle] = {}
        self._resolve_callback: Optional[callable] = None

    def on_resolve(self, callback: callable) -> None:
        """Register callback for when a cast target is resolved.

        callback(client_ip: str, target: CastTarget, active_names: set[str])
        """
        self._resolve_callback = callback

    async def on_instance_active(
        self, device_name: str, client_ip: str
    ) -> None:
        """Called when a shairport-sync instance becomes active."""
        if not client_ip:
            log.warning(
                "Instance '%s' active but no client IP known", device_name
            )
            return

        if client_ip not in self._pending:
            self._pending[client_ip] = set()
        self._pending[client_ip].add(device_name)

        # Cancel existing timer for this client and restart
        if client_ip in self._timers:
            self._timers[client_ip].cancel()

        loop = asyncio.get_event_loop()
        self._timers[client_ip] = loop.call_later(
            GROUPING_WINDOW_SECONDS,
            lambda: asyncio.ensure_future(self._resolve(client_ip)),
        )

        log.debug(
            "Activation pending for client %s: %s",
            client_ip,
            self._pending[client_ip],
        )

    async def on_instance_inactive(self, device_name: str) -> None:
        """Called when a shairport-sync instance becomes inactive."""
        # Remove from all pending sets
        for client_ip, names in list(self._pending.items()):
            names.discard(device_name)
            if not names:
                del self._pending[client_ip]
                if client_ip in self._timers:
                    self._timers[client_ip].cancel()
                    del self._timers[client_ip]

    async def _resolve(self, client_ip: str) -> None:
        """Resolve the pending activations for a client into a cast target."""
        active_names = self._pending.pop(client_ip, set())
        self._timers.pop(client_ip, None)

        if not active_names:
            return

        log.info(
            "Resolving cast target for client %s, devices: %s",
            client_ip,
            active_names,
        )

        target = self._find_target(active_names)

        if target and self._resolve_callback:
            await self._resolve_callback(client_ip, target, active_names)

    def _find_target(self, active_names: set[str]) -> Optional[CastTarget]:
        """Find the best cast target for the given active device names."""
        # Map device names to UUIDs
        active_uuids: set[str] = set()
        name_to_uuid: dict[str, str] = {}
        for name in active_names:
            device = self._discovery.get_device_by_name(name)
            if device:
                active_uuids.add(device.uuid)
                name_to_uuid[name] = device.uuid

        if not active_uuids:
            log.warning("No Chromecast UUIDs found for active devices")
            return None

        # Single device — cast directly
        if len(active_uuids) == 1:
            uuid = next(iter(active_uuids))
            device = self._discovery.get_device_by_uuid(uuid)
            if device:
                log.info("Single device target: '%s'", device.name)
                return CastTarget(is_group=False, device=device)
            return None

        # Multiple devices — try group matching
        if self._config.mode == "advanced":
            target = self._resolve_advanced(active_uuids)
            if target:
                return target
            log.info("No group match in advanced mode, falling back to easy")

        # Easy mode (or advanced fallback)
        return self._resolve_easy(active_uuids)

    def _resolve_advanced(
        self, active_uuids: set[str]
    ) -> Optional[CastTarget]:
        """Advanced mode: find the best matching Chromecast group."""
        groups = self._discovery.get_groups()

        best_group: Optional[ChromecastGroup] = None
        best_score = 0.0

        for group in groups.values():
            member_set = set(group.member_uuids)
            if not member_set:
                continue

            intersection = member_set & active_uuids
            union = member_set | active_uuids
            score = len(intersection) / len(union) if union else 0.0

            if score > best_score:
                best_score = score
                best_group = group

        if best_group and best_score >= 0.5:
            member_set = set(best_group.member_uuids)
            # Devices in the group but not selected → mute
            mute = list(member_set - active_uuids)
            # Devices selected but not in the group (shouldn't happen with
            # exact match, but handle partial)
            log.info(
                "Advanced mode: group '%s' (score=%.2f, muting %d members)",
                best_group.name,
                best_score,
                len(mute),
            )
            return CastTarget(
                is_group=True,
                group=best_group,
                mute_uuids=mute,
            )

        return None

    def _resolve_easy(self, active_uuids: set[str]) -> Optional[CastTarget]:
        """Easy mode: use whole house group with muting."""
        # Find the whole house group
        group: Optional[ChromecastGroup] = None

        if self._config.whole_house_group:
            group = self._discovery.get_group_by_name(
                self._config.whole_house_group
            )
            if not group:
                log.warning(
                    "Configured whole_house_group '%s' not found",
                    self._config.whole_house_group,
                )

        # Auto-detect: use largest group
        if not group:
            group = self._discovery.find_largest_group()
            if group:
                log.info(
                    "Auto-detected largest group: '%s' (%d members)",
                    group.name,
                    len(group.member_uuids),
                )

        if not group:
            log.error(
                "No Chromecast group available for multi-device casting. "
                "Create a group in the Google Home app."
            )
            return None

        member_set = set(group.member_uuids)
        mute = list(member_set - active_uuids)

        log.info(
            "Easy mode: group '%s', muting %d of %d members",
            group.name,
            len(mute),
            len(member_set),
        )
        return CastTarget(
            is_group=True, group=group, mute_uuids=mute
        )
