# showcontrol Profile Format Reference

A profile is a JSON file that describes a single controllable device (or logical grouping of devices). The integration reads profiles at startup and creates HA entities from them.

---

## Top-level structure

```json
{
  "device": { ... },
  "transport": { ... },
  "keepalive": { ... },       // optional
  "workarounds": [ ... ],     // optional
  "entities": [ ... ],        // flat entity list  (use this OR entity_templates)
  "entity_templates": [ ... ] // range-expanded entities (use this OR entities)
}
```

You may mix `entities` and `entity_templates` in the same file; the coordinator merges them.

---

## `device` block

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | ✅ | Unique machine ID. Used as prefix for all entity unique_ids. |
| `name` | string | ✅ | Human-readable device name shown in HA. |
| `manufacturer` | string | ❌ | Shown in HA device info. |
| `model` | string | ❌ | Shown in HA device info. |
| `firmware_tested` | string | ❌ | For documentation only. |
| `notes` | string | ❌ | Free-text notes embedded in the profile for future readers. Not surfaced in HA. |

---

## `transport` block

Defines how the coordinator connects to the device.

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | string | ✅ | Transport type. See below. |
| `default_port` | int | ✅ | Remote port to send messages to. |
| `source_port` | int | ❌ | Local UDP bind port. Required when the device sends feedback to a fixed port. |

### Supported transport types

| `type` | Description |
|---|---|
| `osc_udp` | OSC over UDP. Messages sent via `python-osc`. |
| `osc_tcp` | OSC over TCP (SLIP framing). Rare; mainly older consoles. |
| `midi_rtmidi` | MIDI via `rtmidi`. Entity values map to CC/note values. |
| `http_rest` | HTTP REST. Each entity maps to an endpoint + method. |

> **Port per entity**: Individual entities can override the transport port with a `"port": 7701` field. This is used for QLC+ Garten universe (port 7701) while the profile default is 7700.

---

## `keepalive` block (optional)

Some devices (e.g. Behringer X32) drop their feedback subscription after a timeout unless prodded.

```json
"keepalive": {
  "path": "/xremote",
  "interval": 8.0
}
```

| Field | Type | Description |
|---|---|---|
| `path` | string | OSC path to send. |
| `interval` | float | Seconds between keepalive messages. |
| `args` | array | Optional OSC arguments. Omit for arg-less paths like `/xremote`. |

---

## `workarounds` block (optional)

A documentation list of device-specific quirks. Each entry is an object:

```json
"workarounds": [
  {
    "id": "my_quirk_id",
    "description": "Human-readable explanation."
  }
]
```

The coordinator may key on specific `id` values to enable code-level workarounds. See the coordinator source for recognized IDs.

---

## Entity fields (common to all platforms)

| Field | Type | Required | Description |
|---|---|---|---|
| `unique_id` | string | ✅ | Unique within the profile. The coordinator prefixes with `device.id`. |
| `name` | string | ✅ | HA entity name. |
| `platform` | string | ✅ | `number`, `switch`, `button`, `select`, or `scene`. |
| `osc_path` | string | ✅ | OSC address string, e.g. `/ch/01/mix/fader`. |
| `value_type` | string | ❌ | `int`, `float`, `bool`, `string`. Default: `float`. |
| `port` | int | ❌ | Override transport default_port for this entity. |
| `comment` | string | ❌ | Ignored at runtime; for human readers. |

---

## Platform: `number`

Maps to `homeassistant.components.number.NumberEntity`. Renders as a slider or input box.

| Field | Type | Default | Description |
|---|---|---|---|
| `min` | number | `0` | Minimum value. |
| `max` | number | `1.0` | Maximum value. |
| `step` | number | `0.01` | Step size. |
| `unit` | string | — | Unit of measurement, e.g. `dB`, `%`. |
| `value_type` | string | `float` | Use `int` for 0–255 integer faders (QLC+). |

**Example:**
```json
{
  "unique_id": "ch01_fader",
  "name": "Ch 01 Fader",
  "platform": "number",
  "osc_path": "/ch/01/mix/fader",
  "min": 0.0,
  "max": 1.0,
  "step": 0.01,
  "value_type": "float"
}
```

---

## Platform: `switch`

Maps to `homeassistant.components.switch.SwitchEntity`. On/off with distinct OSC values.

| Field | Type | Default | Description |
|---|---|---|---|
| `value_on` | number | `1` | OSC value sent/expected for ON state. |
| `value_off` | number | `0` | OSC value sent/expected for OFF state. |
| `bool_inverted` | bool | `false` | If `true`, HA "on" maps to `value_off` (and vice versa). Useful when device "on" means "active/unmuted" but you want the switch to represent "muted". |

**Example (QLC+ color button):**
```json
{
  "unique_id": "kazi_down_rot",
  "name": "Kazi Down Rot",
  "platform": "switch",
  "osc_path": "/qlc/down/rot",
  "value_on": 255,
  "value_off": 0,
  "value_type": "int"
}
```

**Example (X32 mute, inverted):**
```json
{
  "unique_id": "ch01_mute",
  "name": "Ch 01 Mute",
  "platform": "switch",
  "osc_path": "/ch/01/mix/on",
  "value_on": 1,
  "value_off": 0,
  "value_type": "int",
  "bool_inverted": true
}
```

---

## Platform: `button`

Maps to `homeassistant.components.button.ButtonEntity`. Pressing sends a fixed OSC message.

| Field | Type | Description |
|---|---|---|
| `osc_args` | array | List of `{"type": "int"/"float"/"string", "value": ...}` objects. If omitted, sends the path with no arguments. |

**Example:**
```json
{
  "unique_id": "scene_recall_5",
  "name": "Scene Recall 5",
  "platform": "button",
  "osc_path": "/-action/goscene",
  "osc_args": [{ "type": "int", "value": 5 }]
}
```

---

## Platform: `select`

Maps to `homeassistant.components.select.SelectEntity`. Each option sends a distinct OSC value.

| Field | Type | Description |
|---|---|---|
| `options` | object | Map of `"Label": osc_value`. |

**Example:**
```json
{
  "unique_id": "ch01_insert_src",
  "name": "Ch 01 Insert Source",
  "platform": "select",
  "osc_path": "/ch/01/insert/source",
  "value_type": "int",
  "options": {
    "Off": 0,
    "Insert": 1,
    "FX1": 2,
    "FX2": 3
  }
}
```

---

## Platform: `scene`

A named scene entity that sends multiple OSC messages simultaneously when activated.

| Field | Type | Description |
|---|---|---|
| `messages` | array | List of `{"osc_path": "...", "value": ..., "value_type": "..."}` objects. |

**Example:**
```json
{
  "unique_id": "scene_stage_reset",
  "name": "Stage Reset",
  "platform": "scene",
  "messages": [
    { "osc_path": "/ch/01/mix/fader", "value": 0.75, "value_type": "float" },
    { "osc_path": "/ch/01/mix/on",    "value": 1,    "value_type": "int"   },
    { "osc_path": "/ch/02/mix/fader", "value": 0.75, "value_type": "float" }
  ]
}
```

---

## Range expansion (`range:` / `entity_templates`)

Instead of repeating 32 nearly-identical fader definitions, use `range:` inside `entity_templates` to generate them automatically.

| Field | Type | Description |
|---|---|---|
| `range.var` | string | The variable name. Use `{var}` in string fields. |
| `range.from` | int | Start of range (inclusive). |
| `range.to` | int | End of range (inclusive). |
| `range.pad` | int | Zero-pad width. `0` = no padding. `2` = "01", "02", … |

The placeholder `{var}` (or whatever name you set) is substituted in: `unique_id`, `name`, `osc_path`, and `osc_args[*].value`.

**Example — 32 channel faders:**
```json
{
  "range": { "var": "ch", "from": 1, "to": 32, "pad": 2 },
  "unique_id": "ch{ch}_fader",
  "name": "Ch {ch} Fader",
  "platform": "number",
  "osc_path": "/ch/{ch}/mix/fader",
  "min": 0.0,
  "max": 1.0,
  "step": 0.01,
  "value_type": "float"
}
```

Expands to 32 entities: `ch01_fader` → `/ch/01/mix/fader`, `ch02_fader` → `/ch/02/mix/fader`, …

---

## `feedback` block (optional)

Defines how the coordinator receives state updates pushed by the device.

```json
"feedback": {
  "enabled": true,
  "listen_port": 10024,
  "comment": "Optional note."
}
```

When feedback is enabled, the coordinator binds a UDP listener on `listen_port` and updates entity states when matching OSC paths arrive. For this to work, the device must know where to send feedback — typically controlled by the `source_port` in the transport block.

---

## Minimal profile example

```json
{
  "device": {
    "id": "my_device",
    "name": "My OSC Device"
  },
  "transport": {
    "type": "osc_udp",
    "default_port": 8000
  },
  "entities": [
    {
      "unique_id": "master_fader",
      "name": "Master Fader",
      "platform": "number",
      "osc_path": "/master/fader",
      "min": 0.0,
      "max": 1.0,
      "step": 0.01,
      "value_type": "float"
    },
    {
      "unique_id": "mute_all",
      "name": "Mute All",
      "platform": "switch",
      "osc_path": "/master/mute",
      "value_on": 1,
      "value_off": 0,
      "value_type": "int"
    }
  ]
}
```

---

## Complex profile example (annotated X32 excerpt)

```json
{
  "device": {
    "id": "x32_foh",
    "name": "X32 FOH",
    "manufacturer": "Behringer",
    "model": "X32"
  },
  "transport": {
    "type": "osc_udp",
    "default_port": 10023,
    "source_port": 10024
  },
  "keepalive": {
    "path": "/xremote",
    "interval": 8.0
  },
  "workarounds": [
    {
      "id": "bool_inverted_mutes",
      "description": "X32 mute OSC: 1=unmuted, 0=muted. bool_inverted maps HA 'on' to muted."
    }
  ],
  "entity_templates": [
    {
      "range": { "var": "ch", "from": 1, "to": 8, "pad": 2 },
      "unique_id": "ch{ch}_fader",
      "name": "Ch {ch} Fader",
      "platform": "number",
      "osc_path": "/ch/{ch}/mix/fader",
      "min": 0.0,
      "max": 1.0,
      "step": 0.01,
      "value_type": "float"
    },
    {
      "range": { "var": "ch", "from": 1, "to": 8, "pad": 2 },
      "unique_id": "ch{ch}_mute",
      "name": "Ch {ch} Mute",
      "platform": "switch",
      "osc_path": "/ch/{ch}/mix/on",
      "value_on": 1,
      "value_off": 0,
      "value_type": "int",
      "bool_inverted": true
    },
    {
      "range": { "var": "n", "from": 0, "to": 4, "pad": 0 },
      "unique_id": "scene_{n}",
      "name": "Scene {n}",
      "platform": "button",
      "osc_path": "/-action/goscene",
      "osc_args": [{ "type": "int", "value": "{n}" }]
    }
  ],
  "entities": [
    {
      "unique_id": "main_lr",
      "name": "Main LR",
      "platform": "number",
      "osc_path": "/main/st/mix/fader",
      "min": 0.0,
      "max": 1.0,
      "step": 0.01,
      "value_type": "float"
    }
  ],
  "feedback": {
    "enabled": true,
    "listen_port": 10024
  }
}
```
