"""Show Control select entities (preset selector, mode selector)."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

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
        ShowControlSelect(coordinator, entry, profile, entity_cfg)
        for entity_cfg in profile.get("entities", [])
        if entity_cfg.get("platform") == "select"
    ]
    async_add_entities(entities, True)


class ShowControlSelect(SelectEntity, RestoreEntity):
    """Select entity mapping human-readable options to OSC values."""

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

        name = config.get("name", "select")
        self._attr_name = config.get("friendly_name", name)
        self._attr_unique_id = f"{entry.entry_id}_{name}"
        self._osc_address = config.get("osc_address", "")
        self._port_override = config.get("port")

        # options_map: {"Option Label": osc_value, ...}
        self._options_map: dict[str, Any] = config.get("options_map", {})
        self._attr_options = list(self._options_map.keys())
        self._attr_current_option = self._attr_options[0] if self._attr_options else None
        self._attr_icon = config.get("icon")

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

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            if last.state in self._attr_options:
                self._attr_current_option = last.state

        cached = self._coordinator.get_cached_state(self._attr_unique_id)
        if cached is not None:
            # Try to find option by value
            for label, val in self._options_map.items():
                if str(val) == str(cached):
                    self._attr_current_option = label
                    break

        self._coordinator.register_feedback_listener(
            self._attr_unique_id, self._on_feedback
        )

    async def async_will_remove_from_hass(self) -> None:
        self._coordinator.unregister_feedback_listener(
            self._attr_unique_id, self._on_feedback
        )

    def _on_feedback(self) -> None:
        value = self._coordinator.get_cached_state(self._attr_unique_id)
        if value is not None:
            for label, val in self._options_map.items():
                if str(val) == str(value):
                    self._attr_current_option = label
                    break
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        if option not in self._options_map:
            _LOGGER.warning("Unknown select option: %s", option)
            return
        self._attr_current_option = option
        osc_value = self._options_map[option]
        args = [osc_value] if not isinstance(osc_value, list) else osc_value
        await self._coordinator.async_send(self._osc_address, args, port=self._port_override)
        self._coordinator.set_cached_state(self._attr_unique_id, osc_value)
        self.async_write_ha_state()
