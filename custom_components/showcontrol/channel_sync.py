"""Channel name sync — reads device channel names via OSC and renames entities."""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .coordinator import ShowControlCoordinator

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

_LOGGER = logging.getLogger(__name__)

# OSC addresses that carry channel names (X32/M32/XR series)
# Format: /ch/{n}/config/name → returns a string
_CHANNEL_NAME_PATTERNS = [
    ("/ch/{n}/config/name",  "ch{n}_fader",   32, 2),   # CH 1-32
    ("/bus/{n}/config/name", "bus{n}_fader",  16, 2),   # Bus 1-16
    ("/dca/{n}/config/name", "dca{n}_fader",   8, 0),   # DCA 1-8
    ("/mtx/{n}/config/name", "mtx{n}_fader",   6, 2),   # Matrix 1-6
    ("/fxrtn/{n}/config/name", "fxrtn{n}_fader", 4, 2), # FX Return 1-4
]

WORKAROUND_NO_NAME_SYNC = "no_name_sync"


async def async_sync_channel_names(
    hass: HomeAssistant,
    coordinator: "ShowControlCoordinator",
) -> None:
    """
    Request channel names from the device via OSC and update entity aliases.

    Works for X32/M32/XR series. The device responds with a string value
    on the same address, which arrives via the feedback listener.
    This function sends requests then waits briefly for the responses.
    """
    profile = coordinator.profile
    workarounds = profile.get("workarounds", [])

    if WORKAROUND_NO_NAME_SYNC in workarounds:
        _LOGGER.debug("Channel name sync disabled via workaround")
        return

    # Determine which channel patterns apply based on entity names in profile
    entity_names = {e.get("name") for e in profile.get("entities", [])}

    # Register temporary feedback handler for config/name responses
    received_names: dict[str, str] = {}

    def _on_name_feedback(address: str, args: list) -> None:
        if "/config/name" in address and args:
            received_names[address] = str(args[0]).strip("\x00")

    # Hook into coordinator feedback temporarily
    original_on_feedback = coordinator._on_feedback

    def _patched_feedback(address: str, args: list) -> None:
        _on_name_feedback(address, args)
        original_on_feedback(address, args)

    coordinator._on_feedback = _patched_feedback  # type: ignore[method-assign]

    try:
        requests_sent = 0
        for addr_tmpl, name_tmpl, count, pad in _CHANNEL_NAME_PATTERNS:
            for n in range(1, count + 1):
                n_str = str(n).zfill(pad) if pad else str(n)
                entity_name = name_tmpl.replace("{n}", n_str)
                if entity_name not in entity_names:
                    continue
                osc_addr = addr_tmpl.replace("{n}", n_str)
                await coordinator.async_send(osc_addr, [])
                requests_sent += 1
                await asyncio.sleep(0.01)  # throttle — don't flood the device

        if requests_sent == 0:
            _LOGGER.debug("No matching channels for name sync")
            return

        # Wait for responses (up to 3 seconds)
        _LOGGER.debug("Sent %d name requests, waiting for responses…", requests_sent)
        await asyncio.sleep(3.0)

    finally:
        coordinator._on_feedback = original_on_feedback  # type: ignore[method-assign]

    if not received_names:
        _LOGGER.debug("No channel name responses received")
        return

    _LOGGER.info("Received %d channel names from device", len(received_names))

    # Apply names to entity registry as aliases
    ent_reg = er.async_get(hass)
    entry_id = coordinator._entry.entry_id

    for addr, device_name in received_names.items():
        if not device_name:
            continue

        # Map address back to entity: /ch/01/config/name → entity name ch01_fader
        for addr_tmpl, name_tmpl, count, pad in _CHANNEL_NAME_PATTERNS:
            for n in range(1, count + 1):
                n_str = str(n).zfill(pad) if pad else str(n)
                if addr == addr_tmpl.replace("{n}", n_str):
                    entity_name = name_tmpl.replace("{n}", n_str)
                    unique_id = f"{entry_id}_{entity_name}"
                    entity_entry = ent_reg.async_get_entity_id(
                        "number", "showcontrol", unique_id
                    )
                    if entity_entry:
                        ent_reg.async_update_entity(
                            entity_entry, aliases={device_name}
                        )
                        _LOGGER.debug(
                            "Set alias '%s' for entity %s", device_name, entity_name
                        )
