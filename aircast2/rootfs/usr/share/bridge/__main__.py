"""AirCast 2 bridge — main entry point."""

from __future__ import annotations

import asyncio
import logging
import signal
import socket
import sys
from typing import Optional

from .cast_controller import CastController
from .chromecast_discovery import ChromecastDiscovery
from .config import BridgeConfig
from .group_matcher import GroupMatcher
from .models import CastTarget
from .mqtt_listener import MQTTListener
from .shairport_manager import ShairportManager
from .stream_pipeline import StreamPipeline

log = logging.getLogger("bridge")

# How long to wait for Chromecast discovery on startup
DISCOVERY_TIMEOUT = 15


def setup_logging(level: str) -> None:
    """Configure logging."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


def get_host_ip() -> str:
    """Get the host's IP address for serving audio."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "0.0.0.0"


async def main() -> None:
    """Main bridge orchestration loop."""
    config = BridgeConfig.from_env()
    setup_logging(config.log_level)

    log.info("AirCast 2 starting...")
    log.info("Mode: %s | AirPlay: %s", config.mode, config.airplay_mode)

    host_ip = get_host_ip()
    log.info("Host IP: %s", host_ip)

    # --- 1. Discover Chromecasts ---
    discovery = ChromecastDiscovery(excluded_devices=config.excluded_devices)
    discovery.start()

    log.info(
        "Waiting %ds for Chromecast discovery...", DISCOVERY_TIMEOUT
    )
    await asyncio.sleep(DISCOVERY_TIMEOUT)

    devices = discovery.get_devices()
    groups = discovery.get_groups()

    if not devices:
        log.error(
            "No Chromecast devices found! Ensure devices are on the "
            "same network and the addon is using host networking."
        )
        return

    log.info(
        "Found %d Chromecast(s) and %d group(s)", len(devices), len(groups)
    )
    for dev in devices.values():
        log.info("  Device: %s (%s)", dev.name, dev.host)
    for grp in groups.values():
        log.info(
            "  Group: %s (%d members)", grp.name, len(grp.member_uuids)
        )

    # --- 2. Start shairport-sync instances ---
    shairport = ShairportManager(config, devices)
    instances = await shairport.start_all()

    if not instances:
        log.error("No shairport-sync instances started!")
        return

    # --- 3. Start MQTT listener ---
    loop = asyncio.get_event_loop()
    mqtt_listener = MQTTListener(
        config, list(instances.keys()), loop
    )
    mqtt_listener.start()

    # --- 4. Create controllers ---
    cast_ctrl = CastController(discovery)
    matcher = GroupMatcher(config, discovery)

    # Active pipelines: client_ip → StreamPipeline
    active_pipelines: dict[str, StreamPipeline] = {}
    port_counter = config.http_port_base

    async def on_target_resolved(
        client_ip: str, target: CastTarget, active_names: set[str]
    ) -> None:
        """Called when GroupMatcher resolves a cast target."""
        nonlocal port_counter

        # Stop existing pipeline for this client if any
        if client_ip in active_pipelines:
            await active_pipelines[client_ip].stop()
            del active_pipelines[client_ip]

        # Find the "primary" instance (first active one) for the audio source
        primary_name = next(iter(active_names))
        primary_instance = shairport.get_instance(primary_name)
        if not primary_instance:
            log.error("No instance found for '%s'", primary_name)
            return

        # Create and start pipeline
        pipeline = StreamPipeline(
            instance=primary_instance,
            cast_controller=cast_ctrl,
            host_ip=host_ip,
            port=port_counter,
        )
        port_counter += 1

        try:
            await pipeline.start(target)
            active_pipelines[client_ip] = pipeline
        except Exception:
            log.error("Failed to start pipeline", exc_info=True)
            await pipeline.stop()

    matcher.on_resolve(on_target_resolved)

    # --- 5. Wire MQTT events to GroupMatcher ---
    async def on_activation(
        device_name: str, client_ip: str, is_active: bool
    ) -> None:
        """Handle shairport-sync activation/deactivation."""
        if is_active:
            await matcher.on_instance_active(device_name, client_ip)
        else:
            await matcher.on_instance_inactive(device_name)

            # Check if all instances for this client are inactive
            remaining = mqtt_listener.get_active_from_client(client_ip)
            if not remaining and client_ip in active_pipelines:
                log.info(
                    "All devices inactive for client %s, stopping pipeline",
                    client_ip,
                )
                await active_pipelines[client_ip].stop()
                del active_pipelines[client_ip]

    mqtt_listener.on_activation_change(on_activation)

    # --- 6. Wait for shutdown ---
    log.info("AirCast 2 bridge is running. Press Ctrl+C to stop.")

    stop_event = asyncio.Event()

    def _signal_handler() -> None:
        log.info("Shutdown signal received.")
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _signal_handler)

    await stop_event.wait()

    # --- 7. Cleanup ---
    log.info("Shutting down...")

    for pipeline in active_pipelines.values():
        await pipeline.stop()

    mqtt_listener.stop()
    await shairport.stop_all()
    cast_ctrl.disconnect_all()
    discovery.stop()

    log.info("AirCast 2 stopped.")


if __name__ == "__main__":
    asyncio.run(main())
