# AirCast 2 — AirPlay to Chromecast Bridge

[![License][license-shield]](LICENSE.md)
![Supports aarch64 Architecture][aarch64-shield]
![Supports amd64 Architecture][amd64-shield]

AirPlay capabilities for your Chromecast speakers, powered by
[shairport-sync][shairport-sync] and [pychromecast][pychromecast].

## Add to Home Assistant

[![Add repository to Home Assistant][addon-badge]][addon-repo]

Click the button above to add this repository to your Home Assistant instance,
then install the **AirCast 2** addon from the Add-on Store.

### Manual installation

1. Go to **Settings** > **Add-ons** > **Add-on Store**.
2. Click the **three dots** menu (top right) > **Repositories**.
3. Paste this URL and click **Add**:
   ```
   https://github.com/BRid37/app-aircast
   ```
4. Refresh the page. **AirCast 2** will appear in the store.
5. Click **Install**, then **Start**.

## About

AirCast 2 discovers Chromecast devices on your network and creates virtual
AirPlay speakers for each one. Select them from your iPhone, iPad, or Mac
and audio is bridged to the Chromecast.

### Features

- **Classic AirPlay and AirPlay 2** — choose the mode that works best for
  your setup.
- **Smart multi-room** — select multiple AirPlay speakers and the addon
  automatically routes audio to the matching Chromecast group.
- **Easy mode** — create one "Whole House" Chromecast group and the addon
  handles everything. Speakers you didn't select are muted; speakers you
  add are unmuted — audio stays perfectly in sync.
- **Advanced mode** — create multiple Chromecast groups in Google Home for
  different room combinations. The addon picks the best match using
  Jaccard similarity scoring.
- **Auto-discovery** — install and go. No manual configuration required for
  basic single-speaker use.

### How it works

```
iPhone ──AirPlay──> shairport-sync ──FIFO──> Python bridge ──HTTP──> Chromecast
```

1. The addon discovers all Chromecasts and groups on your network via mDNS.
2. A [shairport-sync][shairport-sync] instance is created for each Chromecast.
3. When you play audio, it flows through a named pipe, is encoded to FLAC by
   ffmpeg, served over HTTP, and pulled by the Chromecast.
4. When multiple speakers are selected, the addon detects this via internal
   MQTT and routes audio to the appropriate Chromecast group.

### Architecture

| Component | Role |
|-----------|------|
| [shairport-sync][shairport-sync] | AirPlay receiver (classic + AirPlay 2) |
| [NQPTP][nqptp] | PTP timing for AirPlay 2 synchronization |
| [pychromecast][pychromecast] | Chromecast discovery, control, and group management |
| [Mosquitto][mosquitto] | Internal MQTT broker for IPC (bundled, localhost only) |
| ffmpeg | Real-time PCM to FLAC audio encoding |
| s6-overlay | Service management inside the container |

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `mode` | `easy` | `easy` (whole house + muting) or `advanced` (smart group matching) |
| `airplay_mode` | `classic` | `classic` (reliable) or `airplay2` (experimental, better quality) |
| `whole_house_group` | _(auto)_ | Name of the Chromecast group for easy mode |
| `latency_offset` | `0` | Additional latency offset in ms |
| `excluded_devices` | `[]` | Chromecast names to skip |
| `log_level` | `info` | `trace`, `debug`, `info`, `warning`, `error` |

See the [full documentation][docs] for detailed setup guides.

## Multi-Room Setup

Chromecast groups cannot be created programmatically, so you need to set them
up in the Google Home app first.

**Easy mode**: Create one group with all your speakers (e.g., "Whole House").
The addon casts to that group and mutes speakers you didn't select.

**Advanced mode**: Create groups for common room combinations (e.g.,
"Kitchen + Living Room", "Downstairs"). The addon matches your AirPlay
selection to the best group automatically.

## Credits

This project is a fork of [hassio-addons/app-aircast][original] by
[Franck Nijhof][frenck], reimplemented with AirPlay 2 support.

Built on:
- [shairport-sync][shairport-sync] by Mike Brady (MIT)
- [NQPTP][nqptp] by Mike Brady (GPL-2.0)
- [pychromecast][pychromecast] by Home Assistant team (MIT)

## License

MIT License — see [LICENSE.md](LICENSE.md) for details.

NQPTP is distributed under GPL-2.0 and runs as a separate process within
the container.

[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg
[addon-badge]: https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg
[addon-repo]: https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FBRid37%2Fapp-aircast
[docs]: https://github.com/BRid37/app-aircast/blob/main/aircast2/DOCS.md
[frenck]: https://github.com/frenck
[license-shield]: https://img.shields.io/github/license/BRid37/app-aircast.svg
[mosquitto]: https://mosquitto.org/
[nqptp]: https://github.com/mikebrady/nqptp
[original]: https://github.com/hassio-addons/app-aircast
[pychromecast]: https://github.com/home-assistant-libs/pychromecast
[shairport-sync]: https://github.com/mikebrady/shairport-sync
