"""Show Control number entities (faders, levels)."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode, RestoreNumber
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
        ShowControlNumber(coordinator, entry, profile, entity_cfg)
        for entity_cfg in profile.get("entities", [])
        if entity_cfg.get("platform") == "number"
    ]
    async_add_entities(entities, True)


class ShowControlNumber(RestoreNumber):
    """A fader/level controlled via OSC."""

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

        name = config.get("name", "number")
        self._attr_name = config.get("friendly_name", name)
        self._attr_unique_id = f"{entry.entry_id}_{name}"
        self._attr_native_min_value = float(config.get("min", 0.0))
        self._attr_native_max_value = float(config.get("max", 1.0))
        self._attr_native_step = float(config.get("step", 0.01))
        self._attr_mode = NumberMode.SLIDER
        self._attr_native_unit_of_measurement = config.get("unit")
        self._osc_address = config.get("osc_address", "")
        self._port_override = config.get("port")
        self._attr_native_value: float = float(config.get("default", self._attr_native_min_value))
        self._attr_icon = config.get("icon")

        # Determine value type: profile field "value_type" takes priority,
        # then legacy "osc_arg_template", then default float.
        vtype = config.get("value_type") or config.get("osc_arg_template", "float")
        self._value_type = vtype  # "int", "float", "scaled_255"

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
        if (last := await self.async_get_last_number_data()) is not None:
            if last.native_value is not None:
                self._attr_native_value = float(last.native_value)

        cached = self._coordinator.get_cached_state(self._attr_unique_id)
        if cached is not None:
            self._attr_native_value = float(cached)

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
            self._attr_native_value = float(value)
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = value
        self._coordinator.set_cached_state(self._attr_unique_id, value)
        args = self._build_args(value)
        await self._coordinator.async_send(self._osc_address, args, port=self._port_override)
        self.async_write_ha_state()

    def _build_args(self, value: float) -> list[Any]:
        vtype = self._value_type
        if vtype == "int":
            return [int(round(value))]
        if vtype == "scaled_255":
            return [int(round(value * 255))]
        # default: float
        return [float(value)]
