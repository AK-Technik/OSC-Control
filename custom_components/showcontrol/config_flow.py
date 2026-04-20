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
from homeassistant.exceptions import HomeAssistantError

from .const import (
    DOMAIN,
    CONF_HOST,
    CONF_PORT,
    CONF_PROFILE,
    CONF_PROFILE_NAME,
    CONF_PROFILE_CONTENT,
    DEFAULT_PORT,
    PROFILES_DIR,
)
from .profile_loader import list_builtin_profiles, load_profile, ProfileError

_LOGGER = logging.getLogger(__name__)

UPLOAD_OPTION = "__upload__"


def _profiles_dir(hass: HomeAssistant) -> str:
    """Return path to bundled profiles directory."""
    integration_dir = os.path.dirname(__file__)
    return os.path.join(integration_dir, PROFILES_DIR)


def _user_profiles_dir(hass: HomeAssistant) -> str:
    """Return path to user-supplied profiles in HA config dir."""
    return os.path.join(hass.config.config_dir, "showcontrol_profiles")


def _all_profiles(hass: HomeAssistant) -> dict[str, str]:
    """Return {display_name: filepath} from bundled + user profiles."""
    profiles = {}
    profiles.update(list_builtin_profiles(_profiles_dir(hass)))
    profiles.update(list_builtin_profiles(_user_profiles_dir(hass)))
    return profiles


class ShowControlConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Show Control config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._host: str = ""
        self._port: int = DEFAULT_PORT
        self._profile_name: str = ""
        self._profile_path: str = ""
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
            return await self.async_step_profile()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
                        int, vol.Range(min=1, max=65535)
                    ),
                }
            ),
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
                # User wants to paste/upload JSON content
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
                # Built-in or user profile selected by name
                profiles = await self.hass.async_add_executor_job(
                    _all_profiles, self.hass
                )
                path = profiles.get(choice)
                if not path:
                    errors["profile_choice"] = "profile_not_found"
                else:
                    try:
                        profile = await self.hass.async_add_executor_job(
                            load_profile, path
                        )
                        self._profile_data = profile
                        self._profile_name = choice
                        self._profile_path = path
                    except (ProfileError, Exception) as exc:
                        _LOGGER.warning("Profile load failed: %s", exc)
                        errors["profile_choice"] = "profile_invalid"

            if not errors:
                return await self.async_step_test()

        profiles = await self.hass.async_add_executor_job(_all_profiles, self.hass)
        profile_options = list(profiles.keys()) + [UPLOAD_OPTION]

        return self.async_show_form(
            step_id="profile",
            data_schema=vol.Schema(
                {
                    vol.Required("profile_choice", default=profile_options[0] if profile_options else UPLOAD_OPTION): vol.In(profile_options),
                    vol.Optional("profile_upload", default=""): str,
                }
            ),
            description_placeholders={
                "upload_hint": "Wähle ein vorhandenes Profil ODER wähle '__upload__' und füge JSON unten ein."
            },
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Step 3: Connection test
    # ------------------------------------------------------------------

    async def async_step_test(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Try to send a ping/xinfo to verify connectivity."""
        errors: dict[str, str] = {}

        if user_input is not None or True:
            # Always attempt test when entering this step
            ping_cfg = self._profile_data.get("ping", {})
            ping_addr = ping_cfg.get("address")
            ping_args = ping_cfg.get("args", [])
            workarounds = self._profile_data.get("workarounds", [])

            reachable = True
            if ping_addr and "skip_ping" not in workarounds:
                try:
                    from .transports import OscUdpTransport
                    transport = OscUdpTransport(self._host, self._port)
                    await transport.send(ping_addr, ping_args)
                    await transport.close()
                except Exception as exc:
                    _LOGGER.warning("Ping failed: %s", exc)
                    reachable = False

            if not reachable:
                errors["base"] = "cannot_connect"
                return self.async_show_form(
                    step_id="test",
                    data_schema=vol.Schema({}),
                    errors=errors,
                    description_placeholders={
                        "host": self._host,
                        "port": str(self._port),
                    },
                )

            # Success — create entry
            profile_storage = json.dumps(self._profile_data)
            return self.async_create_entry(
                title=f"{self._profile_data.get('name', 'Show Control')} @ {self._host}",
                data={
                    CONF_HOST: self._host,
                    CONF_PORT: self._port,
                    CONF_PROFILE_NAME: self._profile_name,
                    CONF_PROFILE_CONTENT: profile_storage,
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
