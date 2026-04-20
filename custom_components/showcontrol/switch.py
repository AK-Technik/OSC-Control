"""Show Control switch entities (mute, on/off)."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
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
        ShowControlSwitch(coordinator, entry, profile, entity_cfg)
        for entity_cfg in profile.get("entities", [])
        if entity_cfg.get("platform") == "switch"
    ]
    async_add_entities(entities, True)


class ShowControlSwitch(SwitchEntity, RestoreEntity):
    """An OSC-controlled switch. Supports bool_inverted for mute semantics."""

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

        name = config.get("name", "switch")
        self._attr_name = config.get("friendly_name", name)
        self._attr_unique_id = f"{entry.entry_id}_{name}"
        self._osc_address = config.get("osc_address", "")
        self._port_override = config.get("port")
        self._bool_inverted = config.get("bool_inverted", False)
        self._on_args: list[Any] = config.get("on_args", [1])
        self._off_args: list[Any] = config.get("off_args", [0])
        self._attr_is_on: bool = False
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
            self._attr_is_on = last.state == "on"

        cached = self._coordinator.get_cached_state(self._attr_unique_id)
        if cached is not None:
            raw_on = bool(cached)
            self._attr_is_on = (not raw_on) if self._bool_inverted else raw_on

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
            raw_on = bool(value)
            self._attr_is_on = (not raw_on) if self._bool_inverted else raw_on
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._attr_is_on = True
        # bool_inverted: "on" in HA = muted = send 1 (mute on)
        args = self._off_args if self._bool_inverted else self._on_args
        await self._coordinator.async_send(self._osc_address, args, port=self._port_override)
        self._coordinator.set_cached_state(self._attr_unique_id, 1 if not self._bool_inverted else 0)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._attr_is_on = False
        args = self._on_args if self._bool_inverted else self._off_args
        await self._coordinator.async_send(self._osc_address, args, port=self._port_override)
        self._coordinator.set_cached_state(self._attr_unique_id, 0 if not self._bool_inverted else 1)
        self.async_write_ha_state()
