# Show Control (OSC) for Home Assistant

Control your lighting and audio show equipment from Home Assistant via OSC (Open Sound Control).

## Supported Devices

| Device | Profile |
|--------|---------|
| **Behringer X32 / Midas M32** | Full — CH 1–32, Bus 1–16, DCA 1–8, FX, Matrix, Aux, Mono |
| **Behringer XR18 / X18 / Midas MR18** | Full — 16 CH, 6 Bus, 4 FX, 4 DCA |
| **Behringer XR16 / XR12** | Full — 12/8 CH, 4 Bus, 4 FX, 4 DCA |
| **Behringer XR8** | Full — 8 CH, 2 Bus, 2 FX, 2 DCA |
| **Behringer Wing** | Full — 48 CH, 24 Bus, 8 Matrix, 16 DCA |
| **QLC+** | Generic template (paths adjustable) |
| **Any OSC Device** | Custom JSON profile |

## Features

- 🎛️ **Faders** as HA number entities (slider)
- 🔇 **Mute** as HA switch (`bool_inverted` for X32 semantics)
- 🎬 **Scene triggers** as HA buttons
- 🎚️ **Preset selects** with options map
- 📡 **Live feedback** — state updates without polling
- 🔁 **Keepalive** loop (e.g. `/xremote` for X32)
- 🔧 **Services**: `showcontrol.send`, `showcontrol.request`, `showcontrol.keepalive_reset`
- 🩺 **Diagnostics** page in HA UI

## Quick Start

1. Install via HACS or copy `custom_components/showcontrol/` to your HA config
2. Restart Home Assistant
3. **Settings → Devices & Services → Add Integration → Show Control**
4. Enter device IP, port, select profile, test connection
