# Home Assistant Community App: AirCast 2

AirCast 2 bridges AirPlay to Chromecast, allowing Apple devices to stream
audio to Google Chromecast speakers. Unlike the original AirCast (which uses
AirPlay 1 via AirConnect), AirCast 2 is built on
[shairport-sync][shairport-sync] and supports both classic AirPlay and
AirPlay 2 modes.

It discovers Chromecast devices on your network and creates a virtual AirPlay
speaker for each one. When you select speakers on your iPhone, the bridge
intelligently routes audio to the right Chromecast device or group.

## Installation

1. Click the Home Assistant My button below to open the app on your Home
   Assistant instance.

   [![Open this app in your Home Assistant instance.][app-badge]][app]

1. Click the "Install" button to install the app.
1. Start the "AirCast 2" app.
1. Check the logs to verify Chromecast devices were discovered.

After ~30 seconds, your Chromecast speakers should appear as AirPlay devices
on your iPhone, iPad, or Mac.

## Configuration

**Note**: _Remember to restart the app when the configuration is changed._

Example app configuration:

```yaml
mode: easy
airplay_mode: classic
whole_house_group: Whole House
latency_offset: 0
```

### Option: `mode`

Controls how multi-device casting works. Two modes are available:

- **`easy`** (default): Casts to a single Chromecast group and mutes speakers
  you did not select. Requires one Chromecast group configured in Google Home
  (see "Multi-Room Setup" below). Simplest to set up.

- **`advanced`**: Uses smart group matching to find the best pre-configured
  Chromecast group that matches your AirPlay selection. Requires creating
  multiple Chromecast groups in Google Home for different room combinations.

### Option: `airplay_mode`

- **`classic`** (default): Uses classic AirPlay protocol. Reliable and
  recommended. Each Chromecast appears as a separate AirPlay speaker.

- **`airplay2`**: Uses AirPlay 2 protocol for better audio quality and
  buffered streaming. **Experimental** — multiple speakers on the same
  network may not all appear reliably due to an AirPlay 2 limitation with
  multiple instances on the same IP address.

### Option: `whole_house_group`

Name of the Chromecast group to use in easy mode. This should be a group
containing all your Chromecast speakers, created in the Google Home app.

If not set, the addon auto-detects the largest available Chromecast group.

### Option: `latency_offset`

Additional latency offset in milliseconds. Increase this if you experience
sync issues. Default is `0`.

### Option: `log_level`

Controls log verbosity. Possible values:

- `trace`: Extremely detailed output.
- `debug`: Detailed debug information.
- `info`: Normal events (default).
- `warning`: Exceptional occurrences.
- `error`: Runtime errors only.

### Option: `excluded_devices`

List of Chromecast device names to skip. These will not appear as AirPlay
speakers.

```yaml
excluded_devices:
  - "Bedroom TV"
  - "Office Display"
```

## Multi-Room Setup

AirCast 2 supports casting to multiple Chromecast speakers simultaneously.
Since Chromecast groups cannot be created programmatically, you need to set
them up in the Google Home app first.

### Easy Mode (Recommended)

1. Open the Google Home app on your phone.
2. Create a speaker group containing **all** your Chromecast speakers.
   Name it something like "Whole House".
3. In the AirCast 2 configuration, set `whole_house_group` to the group name.
4. Restart the addon.

When you select multiple AirPlay speakers on your iPhone, the addon casts to
the Whole House group and mutes the speakers you did not select. When you
add or remove speakers, they are unmuted/muted accordingly — audio stays in
sync because all speakers are part of the same Cast group.

### Advanced Mode

1. Create Chromecast groups in Google Home for each combination you commonly
   use (e.g., "Kitchen + Living Room", "Downstairs", "Whole House").
2. Set `mode: advanced` in the addon configuration.
3. Restart the addon.

When you select AirPlay speakers, the addon matches your selection to the
best Chromecast group. If an exact match exists, it casts to that group. If
a partial match exists, it casts to the closest group and mutes extra members.

## How It Works

1. **Discovery**: The addon discovers all Chromecast devices and groups on
   your network using mDNS.

2. **AirPlay Endpoints**: For each Chromecast, a virtual AirPlay speaker is
   created using [shairport-sync][shairport-sync].

3. **Audio Pipeline**: When you play audio, it flows through:
   `iPhone → AirPlay → shairport-sync → FIFO pipe → ffmpeg (FLAC encoding) → HTTP server → Chromecast`

4. **Group Matching**: When multiple speakers are selected, the addon detects
   this via MQTT metadata and routes audio to the appropriate Chromecast group.

## Known Issues and Limitations

- Chromecast has an inherent 5-10 second delay for live audio streams due to
  platform buffering. This is a Chromecast limitation, not an addon issue.
- AirPlay 2 mode (`airplay2`) may not reliably show all speakers on iOS when
  many Chromecast devices are present. Use `classic` mode if this occurs.
- Chromecast groups must be pre-configured in the Google Home app. The addon
  cannot create or modify groups.
- ARM devices must be at least ARMv7 (Raspberry Pi 2 or newer).

## Third-Party Licenses

This addon includes the following open-source components:

- **[shairport-sync][shairport-sync]**: MIT License
- **[NQPTP][nqptp]**: GPL-2.0 License (runs as a separate daemon)
- **[pychromecast][pychromecast]**: MIT License

[app-badge]: https://my.home-assistant.io/badges/supervisor_addon.svg
[app]: https://my.home-assistant.io/redirect/supervisor_addon/?addon=aircast2
[shairport-sync]: https://github.com/mikebrady/shairport-sync
[nqptp]: https://github.com/mikebrady/nqptp
[pychromecast]: https://github.com/home-assistant-libs/pychromecast
