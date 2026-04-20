"""Show Control Home Assistant Integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, PLATFORMS, COORDINATOR, PROFILE_DATA, CONF_PROFILE_CONTENT
from .coordinator import ShowControlCoordinator
from .profile_loader import load_profile, ProfileError
from .services import async_register_services, async_unregister_services

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Show Control from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    profile_content = entry.data.get(CONF_PROFILE_CONTENT, "")
    if not profile_content:
        raise ConfigEntryNotReady("No profile content stored in config entry")

    try:
        profile = await hass.async_add_executor_job(
            lambda: load_profile(profile_content, is_content=True)
        )
    except (ProfileError, Exception) as exc:
        _LOGGER.error("Failed to load Show Control profile: %s", exc)
        raise ConfigEntryNotReady(f"Invalid profile: {exc}") from exc

    coordinator = ShowControlCoordinator(hass, entry, profile)

    try:
        await coordinator.async_setup()
    except Exception as exc:
        _LOGGER.error("ShowControl coordinator setup failed: %s", exc)
        raise ConfigEntryNotReady(f"Device not ready: {exc}") from exc

    hass.data[DOMAIN][entry.entry_id] = {
        COORDINATOR: coordinator,
        PROFILE_DATA: profile,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services (idempotent — only registers once)
    await async_register_services(hass)

    # Register OptionsFlow
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    _LOGGER.info("Show Control integration set up: %s", profile.get("name"))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        entry_data = hass.data[DOMAIN].pop(entry.entry_id, {})
        coordinator: ShowControlCoordinator = entry_data.get(COORDINATOR)
        if coordinator:
            await coordinator.async_teardown()

        # Unregister services only when last entry is removed
        await async_unregister_services(hass)

    return unload_ok
