"""HA services for Show Control: osc.send, osc.keepalive_reset, osc.request."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, COORDINATOR

_LOGGER = logging.getLogger(__name__)

# Service names
SERVICE_SEND = "send"
SERVICE_KEEPALIVE_RESET = "keepalive_reset"
SERVICE_REQUEST = "request"

# Schema fields
ATTR_ENTRY_ID = "entry_id"
ATTR_ADDRESS = "address"
ATTR_ARGS = "args"
ATTR_PORT = "port"

SERVICE_SEND_SCHEMA = vol.Schema({
    vol.Required(ATTR_ADDRESS): cv.string,
    vol.Optional(ATTR_ARGS, default=[]): list,
    vol.Optional(ATTR_PORT): vol.All(int, vol.Range(min=1, max=65535)),
    vol.Optional(ATTR_ENTRY_ID): cv.string,
})

SERVICE_KEEPALIVE_RESET_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTRY_ID): cv.string,
})

SERVICE_REQUEST_SCHEMA = vol.Schema({
    vol.Required(ATTR_ADDRESS): cv.string,
    vol.Optional(ATTR_ARGS, default=[]): list,
    vol.Optional(ATTR_PORT): vol.All(int, vol.Range(min=1, max=65535)),
    vol.Optional(ATTR_ENTRY_ID): cv.string,
})


def _get_coordinators(hass: HomeAssistant, entry_id: str | None):
    """Return list of coordinators — all entries if entry_id is None."""
    domain_data = hass.data.get(DOMAIN, {})
    if entry_id:
        entry = domain_data.get(entry_id)
        return [entry[COORDINATOR]] if entry and COORDINATOR in entry else []
    return [v[COORDINATOR] for v in domain_data.values() if COORDINATOR in v]


async def async_register_services(hass: HomeAssistant) -> None:
    """Register all Show Control services."""

    async def handle_send(call: ServiceCall) -> None:
        """Send an arbitrary OSC message to one or all Show Control devices."""
        address: str = call.data[ATTR_ADDRESS]
        args: list[Any] = call.data.get(ATTR_ARGS, [])
        port: int | None = call.data.get(ATTR_PORT)
        entry_id: str | None = call.data.get(ATTR_ENTRY_ID)

        coordinators = _get_coordinators(hass, entry_id)
        if not coordinators:
            _LOGGER.warning("showcontrol.send: no matching device found (entry_id=%s)", entry_id)
            return

        for coordinator in coordinators:
            _LOGGER.debug(
                "Service send → %s %s (port=%s, device=%s)",
                address, args, port, coordinator.profile.get("name"),
            )
            await coordinator.async_send(address, args, port=port)

    async def handle_keepalive_reset(call: ServiceCall) -> None:
        """Force-restart the keepalive task (useful after network glitch)."""
        entry_id: str | None = call.data.get(ATTR_ENTRY_ID)
        coordinators = _get_coordinators(hass, entry_id)
        for coordinator in coordinators:
            keepalive_cfg = coordinator.profile.get("keepalive")
            if not keepalive_cfg:
                continue
            # Cancel existing task
            if coordinator._keepalive_task and not coordinator._keepalive_task.done():
                coordinator._keepalive_task.cancel()
            # Restart
            coordinator._keepalive_task = hass.async_create_background_task(
                coordinator._keepalive_loop(keepalive_cfg),
                name=f"showcontrol_keepalive_{coordinator._entry.entry_id}",
            )
            _LOGGER.info(
                "Keepalive reset for %s", coordinator.profile.get("name")
            )

    async def handle_request(call: ServiceCall) -> None:
        """Send an OSC message expecting a feedback response (fire-and-forget, logged)."""
        address: str = call.data[ATTR_ADDRESS]
        args: list[Any] = call.data.get(ATTR_ARGS, [])
        port: int | None = call.data.get(ATTR_PORT)
        entry_id: str | None = call.data.get(ATTR_ENTRY_ID)

        coordinators = _get_coordinators(hass, entry_id)
        for coordinator in coordinators:
            _LOGGER.debug(
                "Service request → %s %s (device=%s)", address, args,
                coordinator.profile.get("name"),
            )
            await coordinator.async_send(address, args, port=port)
            # Feedback arrives automatically via the registered OSC listener

    if not hass.services.has_service(DOMAIN, SERVICE_SEND):
        hass.services.async_register(
            DOMAIN, SERVICE_SEND, handle_send, schema=SERVICE_SEND_SCHEMA
        )
    if not hass.services.has_service(DOMAIN, SERVICE_KEEPALIVE_RESET):
        hass.services.async_register(
            DOMAIN, SERVICE_KEEPALIVE_RESET, handle_keepalive_reset,
            schema=SERVICE_KEEPALIVE_RESET_SCHEMA,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_REQUEST):
        hass.services.async_register(
            DOMAIN, SERVICE_REQUEST, handle_request, schema=SERVICE_REQUEST_SCHEMA
        )
    _LOGGER.debug("Show Control services registered")


async def async_unregister_services(hass: HomeAssistant) -> None:
    """Remove services when last entry is unloaded."""
    if hass.data.get(DOMAIN):
        return  # other entries still active
    for service in (SERVICE_SEND, SERVICE_KEEPALIVE_RESET, SERVICE_REQUEST):
        hass.services.async_remove(DOMAIN, service)
