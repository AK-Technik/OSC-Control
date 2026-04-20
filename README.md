# ha-showcontrol

Home Assistant Custom Integration für OSC-basierte Show-Control.

Unterstützte Geräte: QLC+, Behringer X32, und jedes weitere Gerät mit OSC/UDP-Support.

## Installation

1. `custom_components/showcontrol/` nach `<HA config>/custom_components/showcontrol/` kopieren
2. HA neu starten
3. Einstellungen → Geräte & Dienste → Integration hinzufügen → "Show Control"

## Eigene Profile

Eigene Profile (JSON) in `<HA config>/showcontrol_profiles/` ablegen.
Im Config Flow erscheinen sie automatisch in der Dropdown-Liste.

## Profile-Format

Vollständige Dokumentation siehe `profiles/qlcplus_generic.json` (kommentiert).

```json
{
  "name": "Mein Gerät",
  "device": { "name": "...", "manufacturer": "...", "model": "..." },
  "transport": { "type": "osc_udp", "port": 7700, "feedback_port": 7701 },
  "keepalive": { "address": "/xremote", "args": [], "interval": 8 },
  "ping": { "address": "/xinfo", "args": [] },
  "workarounds": [],
  "entities": [...],
  "entity_templates": [...]
}
```

### Entity-Plattformen

| Platform | Beschreibung                        |
|----------|-------------------------------------|
| number   | Fader / Level (RestoreNumber)        |
| switch   | Mute / On-Off (bool_inverted möglich)|
| button   | Scene-Trigger, Preset                |
| select   | Preset-Auswahl (options_map)         |

### Range-Templates

```json
{
  "platform": "button",
  "name": "scene_{n}",
  "friendly_name": "Scene {n}",
  "osc_address": "/qlc/scene/{n}",
  "osc_args": [1],
  "range": { "start": 1, "end": 8, "pad": 2 }
}
```

`{n}` und `{ch}` werden substituiert. `pad: 2` → `01, 02, …`

### bool_inverted

Für X32-Mute-Semantik: `on` im OSC = Kanal aktiv (nicht gemutet).
`bool_inverted: true` kehrt die Logik um: HA-Switch ON = Kanal gemutet.

### Port-Override pro Entity

```json
{ "platform": "button", "name": "kazi_scene_1", "port": 7700, ... }
```

Nützlich für QLC+ mit mehreren Instanzen (Kazi=7700, Garten=7701).

## Workarounds

| Workaround           | Effekt                                           |
|----------------------|--------------------------------------------------|
| `skip_ping`          | Verbindungstest im Config Flow überspringen      |
| `ignore_feedback`    | Kein Feedback-Listener starten                   |
| `no_keepalive_check` | Keepalive-Fehler ändern `available`-Status nicht |

