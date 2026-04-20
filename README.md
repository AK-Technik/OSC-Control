# OSC Control for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

Control OSC devices (QLC+, Behringer X32, Midas M32, and more) directly from Home Assistant.

## Features

- **QLC+** — control Virtual Console buttons, faders, scenes via OSC
- **Behringer X32 / Midas M32** — channel faders, mutes, DCA, bus, scene recall
- **Generic OSC** — any OSC-capable device via custom profiles
- **Live feedback** — device state updates pushed to HA without polling
- **Profile system** — JSON profiles for each device type, community-shareable
- **Web UI** — browser-based setup wizard, OSC monitor, profile editor (via Add-on)

## Installation

### HACS (recommended)

1. In HACS → Custom Repositories → add `https://github.com/AK-Technik/OSC-Control` as **Integration**
2. Install "OSC Control"
3. Restart Home Assistant

### Manual

Copy `custom_components/showcontrol` to your HA `config/custom_components/` folder and restart.

## Setup

1. Einstellungen → Geräte & Dienste → Integration hinzufügen → **Show Control**
2. IP-Adresse und Port des Geräts eingeben
3. Profil auswählen (QLC+, X32, oder eigenes JSON hochladen)
4. Fertig — Entities erscheinen automatisch

## Profiles

Profiles are JSON files that describe a device's OSC interface. Built-in profiles:

| Profile | Device | Entities |
|---|---|---|
| `qlcplus_generic` | QLC+ (any setup) | Customizable |
| `qlcplus_fsk` | QLC+ FSK setup | 51 (Kazi + Garten) |
| `behringer_x32` | Behringer X32 / Midas M32 | 171 |

Custom profiles can be placed in `config/showcontrol_profiles/` or uploaded via the Web UI.

See [docs/profile-format.md](docs/profile-format.md) for the full profile schema.

## Web UI Add-on

The optional Add-on provides a browser-based interface for:
- Adding and configuring devices
- Editing profiles without touching JSON
- Live OSC monitor (outgoing + incoming)
- Connection diagnostics

Install from `/addons/showcontrol_ui` as a local add-on.

## Supported Devices

Any OSC/UDP device. Tested with:
- QLC+ 5.x
- Behringer X32 (firmware 4.06)
- Midas M32 (compatible with X32 profile)

## License

MIT
