# Changelog

Alle wichtigen Änderungen werden hier dokumentiert.
Format: [Semantic Versioning](https://semver.org/) — `MAJOR.MINOR.PATCH`

## [1.0.0] — 2026-04-20

### Neu
- Platforms: `number` (Fader), `switch` (Mute), `button` (Scene), `select` (Preset)
- OSC UDP Transport mit asyncio Feedback-Listener (Push, kein Polling)
- Keepalive-Loop (z.B. `/xremote` für X32)
- Profile: Behringer X32/M32, XR18/MR18, XR16/XR12, XR8, Wing, QLC+ Generic
- `bool_inverted` für X32-Mute-Semantik
- Port-Override pro Entity (Multi-Instanz QLC+)
- Services: `showcontrol.send`, `showcontrol.request`, `showcontrol.keepalive_reset`
- Diagnostics-Seite im HA UI
- OptionsFlow: Profil/Host nach Setup änderbar
- Channel-Name-Sync: X32 Kanalnamen → Entity-Aliases
- HACS-ready: `hacs.json`, `info.md`
- Config Flow: 3-Schritte (Host/Port → Profil → Verbindungstest)
- Eigene Profile unter `<HA config>/showcontrol_profiles/` möglich

---

## Versionsschema

| Typ | Wann | Beispiel |
|-----|------|---------|
| `PATCH` (x.x.**1**) | Bugfix, Profil-Korrektur | `1.0.1` |
| `MINOR` (x.**1**.0) | Neues Geräteprofil, neue Entity-Plattform | `1.1.0` |
| `MAJOR` (**2**.0.0) | Breaking Change (Profil-Format, Config-Schema) | `2.0.0` |
