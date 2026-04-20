# QLC+ — OSC Protocol Notes

## Transport

- **Protocol:** OSC over UDP
- **Default output port (Kazi / universe 1):** `7700`
- **Garten port (universe 2):** `7701`
- **Alternative:** WebSocket on port `9999` (see below)

No subscription or keepalive is required. QLC+ is a fire-and-forget target; it does not push state back unless you configure feedback in QLC+'s OSC input plugin.

---

## Virtual Console widget mapping

QLC+ maps incoming OSC messages to Virtual Console widgets via the **Auto-Detect** mechanism:

1. In QLC+ Virtual Console, right-click a widget → **Properties** → **External Input**.
2. Click **Auto-Detect**.
3. Send an OSC message from HA (or any OSC client) to the QLC+ OSC port.
4. QLC+ captures the path and assigns it to the widget.

Alternatively, enter the path manually in the widget properties. The path must match exactly (case-sensitive, including leading `/`).

---

## Value ranges

### Sliders / Faders (number entities)

QLC+ Virtual Console sliders expect an **integer value 0–255**:

- `0` = minimum (0% DMX intensity)
- `255` = maximum (100% DMX intensity)

Use `value_type: int` in showcontrol profiles.

> **Note:** Some QLC+ versions also accept a float 0.0–1.0 depending on the OSC plugin configuration. The FSK setup uses integers consistently.

### Buttons (switch entities)

QLC+ buttons are triggered by value:

- `255` → button pressed (activates the function/scene)
- `0` → button released

For color switches in FSK, sending `255` activates the color channel and `0` deactivates it. Use:

```json
"value_on": 255,
"value_off": 0,
"value_type": "int"
```

There is no need to hold the value; a `255` trigger followed by `0` (or just `255` once if the function is a toggle) is sufficient depending on how the QLC+ function is configured.

---

## Two-universe FSK setup

FSK runs two QLC+ universes on the same QLC+ machine (`192.168.181.136`):

| Universe | Space | OSC Port | Path prefix |
|---|---|---|---|
| Universe 1 | Kazi | `7700` | `/qlc/down/`, `/qlc/roof/`, `/qlc/galerie/`, `/qlc/washer/`, `/qlc/floor`, etc. |
| Universe 2 | Garten | `7701` | `/qlc/garten/{group}/{color}` |

Each universe has its own OSC plugin instance in QLC+ listening on its respective port. The showcontrol coordinator sends to port 7700 or 7701 per entity (using the `port` override field in the profile).

### Kazi paths

| Path | Type | Description |
|---|---|---|
| `/qlc/down/rot` | switch (0/255) | Downlights red |
| `/qlc/down/blau` | switch (0/255) | Downlights blue |
| `/qlc/down/weiss` | switch (0/255) | Downlights white |
| `/qlc/down/pink` | switch (0/255) | Downlights pink |
| `/qlc/roof/rot` | switch (0/255) | Roof lights red |
| `/qlc/roof/blau` | switch (0/255) | Roof lights blue |
| `/qlc/roof/weiss` | switch (0/255) | Roof lights white |
| `/qlc/roof/pink` | switch (0/255) | Roof lights pink |
| `/qlc/galerie/rot` | switch (0/255) | Gallery red |
| `/qlc/galerie/blau` | switch (0/255) | Gallery blue |
| `/qlc/galerie/weiss` | switch (0/255) | Gallery white |
| `/qlc/galerie/pink` | switch (0/255) | Gallery pink |
| `/qlc/washer/rot` | switch (0/255) | Washer red |
| `/qlc/washer/blau` | switch (0/255) | Washer blue |
| `/qlc/washer/weiss` | switch (0/255) | Washer white |
| `/qlc/washer/pink` | switch (0/255) | Washer pink |
| `/qlc/floor` | fader (0–255) | Floor dimmer |
| `/qlc/roof_dim` | fader (0–255) | Roof dimmer |
| `/qlc/galerie_dim` | fader (0–255) | Gallery dimmer |
| `/qlc/washer_dim` | fader (0–255) | Washer dimmer |
| `/qlc/haengelampen` | fader (0–255) | Pendant lights dimmer |

### Garten paths

Pattern: `/qlc/garten/{group}/{color_or_dim}`

Groups: `truss`, `klo`, `baeume`, `empore`, `piazza`
Colors: `rot`, `gruen`, `blau`, `amber`, `pink`
Dimmer: `dim`

---

## WebSocket alternative (port 9999)

QLC+ also exposes a WebSocket API on port `9999`. This allows a different control paradigm:

- Connect to `ws://192.168.181.136:9999`
- Send commands as plain text: `QLC+API|setWidgetValue|<widgetID>|<value>|0`

The WebSocket API uses **widget IDs** (integers), not OSC paths. This is harder to maintain since widget IDs change when the QLC+ workspace is reorganized. The OSC path approach (ports 7700/7701) is preferred for the FSK setup.

The WebSocket API is documented at: `http://192.168.181.136:9999/api` when QLC+ is running.

---

## Feedback from QLC+

QLC+ can send OSC feedback when widget values change (e.g. from the QLC+ UI or a chase). To enable:

1. In QLC+, open the OSC plugin for the relevant universe.
2. Set **Feedback IP** to the HA/Raspberry Pi IP.
3. Set **Feedback Port** to your listener port.

Feedback is not currently used in the FSK showcontrol setup (HA is the sole control source).

---

## No keepalive required

Unlike the Behringer X32, QLC+ does not require subscription renewal. Messages are processed immediately upon receipt with no session state.
