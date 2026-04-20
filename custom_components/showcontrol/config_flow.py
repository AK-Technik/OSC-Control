"""Config flow for Show Control integration."""
from __future__ import annotations

import json
import logging
import os
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    CONF_HOST,
    CONF_PORT,
    CONF_PROFILE_NAME,
    CONF_PROFILE_CONTENT,
    DEFAULT_PORT,
    PROFILES_DIR,
)
from .profile_loader import list_builtin_profiles, load_profile, ProfileError
from .transports import OscUdpTransport

_LOGGER = logging.getLogger(__name__)

UPLOAD_OPTION = "__upload__"


def _profiles_dir(hass: HomeAssistant) -> str:
    return os.path.join(os.path.dirname(__file__), PROFILES_DIR)


def _user_profiles_dir(hass: HomeAssistant) -> str:
    return os.path.join(hass.config.config_dir, "showcontrol_profiles")


def _all_profiles(hass: HomeAssistant) -> dict[str, str]:
    profiles: dict[str, str] = {}
    profiles.update(list_builtin_profiles(_profiles_dir(hass)))
    profiles.update(list_builtin_profiles(_user_profiles_dir(hass)))
    return profiles


class ShowControlConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Show Control config flow."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> ShowControlOptionsFlow:
        """Return the options flow handler."""
        return ShowControlOptionsFlow(config_entry)

    def __init__(self) -> None:
        self._host: str = ""
        self._port: int = DEFAULT_PORT
        self._profile_name: str = ""
        self._profile_data: dict = {}

    # ------------------------------------------------------------------
    # Step 1: Host / Port
    # ------------------------------------------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            self._host = user_input[CONF_HOST].strip()
            self._port = user_input[CONF_PORT]
            if not self._host:
                errors[CONF_HOST] = "invalid_host"
            else:
                return await self.async_step_profile()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
                    int, vol.Range(min=1, max=65535)
                ),
            }),
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Step 2: Profile selection or upload
    # ------------------------------------------------------------------

    async def async_step_profile(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            choice = user_input.get("profile_choice", "")
            uploaded = user_input.get("profile_upload", "").strip()

            if choice == UPLOAD_OPTION:
                if not uploaded:
                    errors["profile_upload"] = "profile_upload_empty"
                else:
                    try:
                        profile = load_profile(uploaded, is_content=True)
                        self._profile_data = profile
                        self._profile_name = profile.get("name", "Custom Profile")
                    except (ProfileError, json.JSONDecodeError, Exception) as exc:
                        _LOGGER.warning("Profile upload failed: %s", exc)
                        errors["profile_upload"] = "profile_invalid"
            else:
                profiles = await self.hass.async_add_executor_job(_all_profiles, self.hass)
                path = profiles.get(choice)
                if not path:
                    errors["profile_choice"] = "profile_not_found"
                else:
                    try:
                        profile = await self.hass.async_add_executor_job(load_profile, path)
                        self._profile_data = profile
                        self._profile_name = choice
                    except (ProfileError, Exception) as exc:
                        _LOGGER.warning("Profile load failed: %s", exc)
                        errors["profile_choice"] = "profile_invalid"

            if not errors:
                return await self.async_step_test()

        profiles = await self.hass.async_add_executor_job(_all_profiles, self.hass)
        profile_options = list(profiles.keys()) + [UPLOAD_OPTION]
        default = profile_options[0] if profile_options else UPLOAD_OPTION

        return self.async_show_form(
            step_id="profile",
            data_schema=vol.Schema({
                vol.Required("profile_choice", default=default): vol.In(profile_options),
                vol.Optional("profile_upload", default=""): str,
            }),
            description_placeholders={
                "upload_hint": (
                    "Wähle ein Profil aus der Liste — oder wähle '__upload__' "
                    "und füge dein JSON-Profil in das Textfeld unten ein."
                )
            },
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Step 3: Connection test  (FIX: was "or True" — always passed)
    # ------------------------------------------------------------------

    async def async_step_test(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show test step; on submit actually test the connection."""
        errors: dict[str, str] = {}

        # user_input is None on first render (GET), not None on submit (POST)
        if user_input is not None:
            ping_cfg = self._profile_data.get("ping", {})
            ping_addr = ping_cfg.get("address")
            workarounds = self._profile_data.get("workarounds", [])

            reachable = True
            if ping_addr and "skip_ping" not in workarounds:
                try:
                    transport = OscUdpTransport(self._host, self._port)
                    # FIX: use socket-level ping — UDP send never raises even if host is down
                    reachable = await transport.ping()
                    await transport.close()
                except Exception as exc:
                    _LOGGER.warning("Ping failed for %s:%d — %s", self._host, self._port, exc)
                    reachable = False

            if not reachable:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=f"{self._profile_data.get('name', 'Show Control')} @ {self._host}",
                    data={
                        CONF_HOST: self._host,
                        CONF_PORT: self._port,
                        CONF_PROFILE_NAME: self._profile_name,
                        CONF_PROFILE_CONTENT: json.dumps(self._profile_data),
                    },
                )

        return self.async_show_form(
            step_id="test",
            data_schema=vol.Schema({}),
            description_placeholders={
                "host": self._host,
                "port": str(self._port),
            },
            errors=errors,
        )


# ------------------------------------------------------------------
# Options Flow — change host/port/profile after setup
# ------------------------------------------------------------------

class ShowControlOptionsFlow(config_entries.OptionsFlow):
    """Allow reconfiguring host, port and profile after initial setup."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry
        self._profile_data: dict = {}
        self._profile_name: str = ""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            new_host = user_input[CONF_HOST].strip()
            new_port = user_input[CONF_PORT]
            choice = user_input.get("profile_choice", "")
            uploaded = user_input.get("profile_upload", "").strip()

            profile_data = None
            if choice == UPLOAD_OPTION:
                if not uploaded:
                    errors["profile_upload"] = "profile_upload_empty"
                else:
                    try:
                        profile_data = load_profile(uploaded, is_content=True)
                        self._profile_name = profile_data.get("name", "Custom Profile")
                    except Exception as exc:
                        _LOGGER.warning("Options profile upload failed: %s", exc)
                        errors["profile_upload"] = "profile_invalid"
            else:
                profiles = await self.hass.async_add_executor_job(
                    _all_profiles, self.hass
                )
                path = profiles.get(choice)
                if path:
                    try:
                        profile_data = await self.hass.async_add_executor_job(
                            load_profile, path
                        )
                        self._profile_name = choice
                    except Exception as exc:
                        errors["profile_choice"] = "profile_invalid"
                        _LOGGER.warning("Options profile load failed: %s", exc)
                else:
                    errors["profile_choice"] = "profile_not_found"

            if not errors and profile_data is not None:
                self.hass.config_entries.async_update_entry(
                    self._entry,
                    data={
                        **self._entry.data,
                        CONF_HOST: new_host,
                        CONF_PORT: new_port,
                        CONF_PROFILE_NAME: self._profile_name,
                        CONF_PROFILE_CONTENT: json.dumps(profile_data),
                    },
                )
                return self.async_create_entry(title="", data={})

        current_host = self._entry.data.get(CONF_HOST, "")
        current_port = self._entry.data.get(CONF_PORT, DEFAULT_PORT)
        current_profile = self._entry.data.get(CONF_PROFILE_NAME, "")

        profiles = await self.hass.async_add_executor_job(_all_profiles, self.hass)
        profile_options = list(profiles.keys()) + [UPLOAD_OPTION]
        default_profile = current_profile if current_profile in profile_options else profile_options[0]

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST, default=current_host): str,
                vol.Required(CONF_PORT, default=current_port): vol.All(
                    int, vol.Range(min=1, max=65535)
                ),
                vol.Required("profile_choice", default=default_profile): vol.In(profile_options),
                vol.Optional("profile_upload", default=""): str,
            }),
            errors=errors,
        )
