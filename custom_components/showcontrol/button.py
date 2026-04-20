"""Show Control button entities (scene triggers, etc.)."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, COORDINATOR, PROFILE_DATA
from .coordinator import ShowControlCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: ShowControlCoordinator = data[COORDINATOR]
    profile: dict = data[PROFILE_DATA]

    entities = [
        ShowControlButton(coordinator, entry, profile, entity_cfg)
        for entity_cfg in profile.get("entities", [])
        if entity_cfg.get("platform") == "button"
    ]
    async_add_entities(entities, True)


class ShowControlButton(ButtonEntity):
    """An OSC-triggered button (scene, preset, etc.)."""

    _attr_should_poll = False

    def __init__(
        self,
        coordinator: ShowControlCoordinator,
        entry: ConfigEntry,
        profile: dict,
        config: dict,
    ) -> None:
        self._coordinator = coordinator
        self._entry = entry
        self._config = config
        self._profile = profile

        name = config.get("name", "button")
        self._attr_name = config.get("friendly_name", name)
        self._attr_unique_id = f"{entry.entry_id}_{name}"
        self._osc_address = config.get("osc_address", "")
        self._port_override = config.get("port")
        self._osc_args: list[Any] = config.get("osc_args", [1])
        self._attr_icon = config.get("icon", "mdi:play")

    @property
    def device_info(self) -> DeviceInfo:
        dev = self._profile.get("device", {})
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=dev.get("name", self._profile.get("name", "Show Control Device")),
            manufacturer=dev.get("manufacturer", "Unknown"),
            model=dev.get("model", "OSC Device"),
            sw_version=dev.get("sw_version"),
        )

    @property
    def available(self) -> bool:
        return self._coordinator.available

    async def async_press(self) -> None:
        _LOGGER.debug("Button pressed: %s → %s %s", self._attr_name, self._osc_address, self._osc_args)
        await self._coordinator.async_send(
            self._osc_address, self._osc_args, port=self._port_override
        )
