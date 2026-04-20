"""Diagnostics support for Show Control — exposed via HA UI and download."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, COORDINATOR, PROFILE_DATA, CONF_PROFILE_CONTENT

# Redact sensitive fields before exposing diagnostics
TO_REDACT = set()  # No secrets in this integration, but keep the pattern


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry (shown in HA UI → device → diagnostics)."""
    entry_data = hass.data[DOMAIN].get(entry.entry_id, {})
    coordinator = entry_data.get(COORDINATOR)
    profile: dict = entry_data.get(PROFILE_DATA, {})

    # Build entity state snapshot from coordinator cache
    state_snapshot: dict[str, Any] = {}
    if coordinator:
        for uid, value in coordinator._state_cache.items():
            state_snapshot[uid] = value

    # Count entities per platform
    platform_counts: dict[str, int] = {}
    for ent in profile.get("entities", []):
        plat = ent.get("platform", "unknown")
        platform_counts[plat] = platform_counts.get(plat, 0) + 1

    # Feedback map (address → uid)
    feedback_map = {}
    if coordinator:
        feedback_map = dict(coordinator._feedback_map)

    # Keepalive status
    keepalive_info: dict[str, Any] = {}
    if coordinator and coordinator._keepalive_task:
        keepalive_info = {
            "running": not coordinator._keepalive_task.done(),
            "config": profile.get("keepalive"),
        }

    # Transport info (no secrets to redact here)
    transport_info: dict[str, Any] = {}
    if coordinator and coordinator.transport:
        t = coordinator.transport
        transport_info = {
            "type": profile.get("transport", {}).get("type"),
            "host": getattr(t, "_host", None),
            "default_port": getattr(t, "_default_port", None),
            "active_client_ports": list(getattr(t, "_clients", {}).keys()),
            "feedback_listener_active": getattr(t, "_feedback_transport", None) is not None,
        }

    diag: dict[str, Any] = {
        "entry": {
            "title": entry.title,
            "entry_id": entry.entry_id,
            "version": entry.version,
            "data": async_redact_data(
                {k: v for k, v in entry.data.items() if k != CONF_PROFILE_CONTENT},
                TO_REDACT,
            ),
        },
        "profile": {
            "name": profile.get("name"),
            "description": profile.get("description"),
            "device": profile.get("device"),
            "transport_config": profile.get("transport"),
            "keepalive_config": profile.get("keepalive"),
            "workarounds": profile.get("workarounds", []),
            "entity_count": len(profile.get("entities", [])),
            "entity_platform_counts": platform_counts,
        },
        "coordinator": {
            "available": coordinator.available if coordinator else None,
            "transport": transport_info,
            "keepalive": keepalive_info,
            "feedback_address_count": len(feedback_map),
            "feedback_map": feedback_map,
        },
        "state_cache": state_snapshot,
        "entity_list": [
            {
                "name": e.get("name"),
                "platform": e.get("platform"),
                "osc_address": e.get("osc_address"),
                "feedback_address": e.get("feedback_address"),
            }
            for e in profile.get("entities", [])
        ],
    }
    return diag
