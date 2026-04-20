# ha-showcontrol

> **Status: Beta — under active development. Not yet recommended for production use.**

A Home Assistant add-on that bridges OSC-capable show-control devices (lighting consoles, audio mixers, etc.) into Home Assistant entities. Devices are controlled via OSC (Open Sound Control) over UDP. The add-on exposes a local web UI for configuration and provides a custom HA integration that creates entities automatically from device profiles.

---

## What it does

```
HA Automations / Dashboards
        │
        ▼
 showcontrol Integration   ←──── profiles/{device_id}.json
        │
        ▼
   ha-showcontrol Add-on  (Flask, Port 7755)
        │  OSC/UDP
        ▼
  QLC+  /  X32  /  Wing  /  XR18  / …
```

- **Device management** — add, test and delete OSC devices through a guided wizard
- **Profile editor** — define Home Assistant entities (number, switch, button, select) per device, each mapped to an OSC path
- **OSC monitor** — live stream of all outgoing and incoming OSC packets, filterable by device and path
- **Diagnostics** — TCP reachability test with latency measurement per device
- **Auto-reload** — after every profile save the HA integration is reloaded automatically so new entities appear immediately

---

## Supported device types

| Type | Example devices | Notes |
|------|----------------|-------|
| `qlcplus` | QLC+ (any platform) | value range 0–255 typical |
| `x32` | Behringer X32, Midas M32 | fader range 0.0–1.0 |
| `xr18` / `xr16` / `xr12` / `xr8` | Behringer X-Air series | fader range 0.0–1.0 |
| `wing` | Behringer Wing | fader range 0.0–1.0 |
| `generic` | any OSC-capable device | free path input |

---

## Entity types

Each entity in a profile maps one HA entity to one OSC path.

| HA platform | OSC behaviour | Extra fields |
|-------------|--------------|--------------|
| `number` | sends float/int value | `min`, `max`, `step` |
| `switch` | sends `value_on` or `value_off` | `value_on`, `value_off` |
| `button` | sends a trigger (value 1) | — |
| `select` | sends index or string per option | `options` (list) |

### Profile file format

Profiles are stored as JSON under `config/ha-showcontrol/profiles/{device_id}.json`.

```json
{
  "name": "Main Console",
  "device_type": "x32",
  "version": "1.0",
  "entities": [
    {
      "id": "main_fader_1234",
      "name": "Main Fader",
      "type": "number",
      "osc_path": "/main/st/mix/fader",
      "min": 0.0,
      "max": 1.0,
      "step": 0.01
    },
    {
      "id": "main_mute_1234",
      "name": "Main Mute",
      "type": "switch",
      "osc_path": "/main/st/mix/on",
      "value_on": 1,
      "value_off": 0
    },
    {
      "id": "scene_go_1234",
      "name": "Scene Go",
      "type": "button",
      "osc_path": "/qlc/function/run"
    }
  ]
}
```

---

## Installation

### Prerequisites

- Home Assistant OS or Supervised
- The `showcontrol` custom integration installed under `custom_components/showcontrol/`
- OSC device reachable on the same network (UDP)

### Add-on install

1. In HA go to **Settings → Add-ons → Add-on Store**
2. Click the three-dot menu → **Repositories** → add this repo URL:
   ```
   https://github.com/AK-Technik/OSC-Control
   ```
3. Find **ShowControl** in the list → **Install**
4. Configure the add-on options (see below) → **Start**

### Add-on configuration

```yaml
ha_token: "YOUR_LONG_LIVED_ACCESS_TOKEN"
```

Generate a token in HA under **Profile → Long-Lived Access Tokens**.

---

## Web UI

After starting, the UI is available at `http://<ha-ip>:7755`.

| Page | Path | Description |
|------|------|-------------|
| Dashboard | `/` | All devices with online status and packet counters |
| Add device | `/add` | 3-step wizard (type → connection → profile) |
| Profile editor | `/device/<id>/profile` | Add, edit, delete entities for a device |
| OSC Monitor | `/monitor` | Live OSC packet log |
| Diagnostics | `/diagnose` | TCP test and latency per device |

---

## File structure

```
ha-showcontrol/
├── app/
│   ├── main.py               # Flask application, all routes and API
│   ├── requirements.txt
│   ├── static/
│   │   ├── style.css         # Dark stage theme
│   │   └── app.js            # Shared JS utilities (showToast etc.)
│   └── templates/
│       ├── base.html
│       ├── dashboard.html
│       ├── profile_editor.html
│       ├── osc_monitor.html
│       ├── diagnose.html
│       └── wizard_step{1,2,3}.html
├── config.yaml               # Add-on manifest
├── Dockerfile
└── run.sh

config/ha-showcontrol/        # Created at runtime (outside repo)
├── devices.json              # List of all configured devices
├── profiles/                 # One JSON file per device
│   └── {device_id}.json
└── library/                  # Reusable profile templates
    ├── qlcplus_standard.json
    ├── x32_standard.json
    └── …
```

---

## API reference

All endpoints return JSON. The web UI uses these internally; they can also be called directly for automation or debugging.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/device/<id>/profile` | Get full profile JSON |
| `POST` | `/api/device/<id>/profile` | Save full profile JSON → triggers HA reload |
| `POST` | `/api/device/<id>/entity/add` | Add a single entity |
| `POST` | `/api/device/<id>/entity/<eid>/delete` | Delete an entity |
| `GET` | `/api/device/<id>/test` | TCP reachability test |
| `POST` | `/api/device/<id>/delete` | Remove device and profile |
| `POST` | `/api/add-device` | Create new device (wizard step 3) |
| `POST` | `/api/reload` | Manually trigger HA integration reload |
| `GET` | `/api/osc/stream` | SSE stream of OSC events |
| `POST` | `/api/osc/send` | Send a test OSC message |
| `GET` | `/api/diagnose/<id>` | Latency + packet stats |

---

## Known limitations (Beta)

- OSC receive (inbound) is not yet implemented — entities are write-only
- No authentication on the web UI — only use on a trusted local network
- `select` entity type is defined in profiles but not yet fully implemented in the HA integration
- Library profiles are read-only templates; editing them requires direct file access

---

## Contributing

PRs and issues welcome. Please open an issue before starting larger changes.

Tech stack: Python 3.11, Flask, python-osc, vanilla JS, no frontend build step required.
