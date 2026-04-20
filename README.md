# OSC Control for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

Control OSC devices (QLC+, Behringer X32/Wing/XR series, Midas M32/MR18, and more) directly from Home Assistant.

## Features

- **QLC+** — control Virtual Console buttons, faders, scenes via OSC
- **Behringer X32 / Midas M32** — channel faders, mutes, DCA, bus, scene recall
- **Behringer Wing / XR series** — full OSC control via profiles
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
3. Profil auswählen oder eigenes JSON hochladen
4. Fertig — Entities erscheinen automatisch

## Built-in Profiles

| Profile | Device | 
|---|---|
| `qlcplus_generic` | QLC+ (any setup) |
| `behringer_x32` | Behringer X32 / Midas M32 |
| `behringer_wing` | Behringer Wing |
| `behringer_xr18` | Behringer X18 / XR18 / Midas MR18 |
| `behringer_xr16` | Behringer XR16 / XR12 |
| `behringer_xr8` | Behringer XR8 |

Custom profiles can be placed in `config/showcontrol_profiles/` or uploaded via the Web UI.

See [docs/profile-format.md](docs/profile-format.md) for the full profile schema.

## Web UI Add-on

The optional Add-on provides a browser-based interface for:
- Adding and configuring devices
- Editing profiles without touching JSON
- Live OSC monitor (outgoing + incoming)
- Connection diagnostics

See `addon/` folder for installation instructions.

## License

MIT
