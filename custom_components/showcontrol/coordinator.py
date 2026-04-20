"""Coordinator for Show Control devices."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    TRANSPORT_OSC_UDP,
    DEFAULT_KEEPALIVE_INTERVAL,
    DEFAULT_FEEDBACK_PORT,
    WORKAROUND_NO_KEEPALIVE_CHECK,
)
from .transports import OscUdpTransport, AbstractTransport

_LOGGER = logging.getLogger(__name__)


class ShowControlCoordinator(DataUpdateCoordinator):
    """Manages a single Show Control device: transport, keepalive, feedback, state cache."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        profile: dict[str, Any],
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
        )
        self._entry = entry
        self.profile = profile
        self.transport: AbstractTransport | None = None

        # entity unique_id → current value (from feedback)
        self._state_cache: dict[str, Any] = {}
        # entity unique_id → list of callbacks (entity.async_write_ha_state)
        self._listeners: dict[str, list[Callable]] = {}
        # OSC address → entity unique_id (for feedback routing)
        self._feedback_map: dict[str, str] = {}

        self._keepalive_task: asyncio.Task | None = None
        self._available = False

    # ------------------------------------------------------------------
    # Setup / Teardown
    # ------------------------------------------------------------------

    async def async_setup(self) -> None:
        """Set up transport and start keepalive."""
        transport_cfg = self.profile.get("transport", {})
        t_type = transport_cfg.get("type", TRANSPORT_OSC_UDP)
        host = self._entry.data["host"]
        port = self._entry.data["port"]
        source_port = transport_cfg.get("source_port", 0)

        if t_type == TRANSPORT_OSC_UDP:
            self.transport = OscUdpTransport(host, port, source_port)
        else:
            raise ValueError(f"Unknown transport type: {t_type}")

        # Build feedback address map
        self._build_feedback_map()

        # Start feedback listener if configured
        feedback_port = transport_cfg.get("feedback_port", DEFAULT_FEEDBACK_PORT)
        workarounds = self.profile.get("workarounds", [])
        if "ignore_feedback" not in workarounds:
            try:
                await self.transport.start_feedback_listener(
                    feedback_port, self._on_feedback
                )
            except Exception as exc:
                _LOGGER.warning("Feedback listener setup failed: %s", exc)

        # Start keepalive
        keepalive_cfg = self.profile.get("keepalive")
        if keepalive_cfg:
            self._keepalive_task = self.hass.async_create_background_task(
                self._keepalive_loop(keepalive_cfg),
                name=f"showcontrol_keepalive_{self._entry.entry_id}",
            )

        self._available = True
        _LOGGER.info("ShowControlCoordinator setup complete for %s", self.profile.get("name"))

    async def async_teardown(self) -> None:
        """Stop keepalive and close transport."""
        if self._keepalive_task and not self._keepalive_task.done():
            self._keepalive_task.cancel()
            try:
                await self._keepalive_task
            except asyncio.CancelledError:
                pass
        if self.transport:
            await self.transport.close()
        self._available = False

    # ------------------------------------------------------------------
    # Keepalive loop
    # ------------------------------------------------------------------

    async def _keepalive_loop(self, cfg: dict) -> None:
        address = cfg.get("address", "/ping")
        args = cfg.get("args", [])
        interval = cfg.get("interval", DEFAULT_KEEPALIVE_INTERVAL)
        workarounds = self.profile.get("workarounds", [])
        check = WORKAROUND_NO_KEEPALIVE_CHECK not in workarounds

        _LOGGER.debug("Keepalive loop started: %s every %ds", address, interval)
        while True:
            try:
                await asyncio.sleep(interval)
                await self.transport.send(address, args)
                if check and not self._available:
                    self._available = True
                    _LOGGER.info("Device back online: %s", self.profile.get("name"))
            except asyncio.CancelledError:
                break
            except Exception as exc:
                _LOGGER.debug("Keepalive send error: %s", exc)
                if check:
                    self._available = False

    # ------------------------------------------------------------------
    # OSC send
    # ------------------------------------------------------------------

    async def async_send(
        self,
        address: str,
        args: list[Any],
        port: int | None = None,
    ) -> None:
        """Send an OSC message via the transport."""
        if not self.transport:
            _LOGGER.warning("Transport not ready, dropping message %s", address)
            return
        await self.transport.send(address, args, port=port)

    # ------------------------------------------------------------------
    # Feedback / state cache
    # ------------------------------------------------------------------

    def _build_feedback_map(self) -> None:
        """Build address → unique_id map for feedback routing."""
        for entity in self.profile.get("entities", []):
            fb_addr = entity.get("feedback_address") or entity.get("osc_address")
            if fb_addr:
                uid = self._entity_unique_id(entity)
                self._feedback_map[fb_addr] = uid

    def _entity_unique_id(self, entity: dict) -> str:
        return f"{self._entry.entry_id}_{entity.get('name', 'unknown')}"

    def _on_feedback(self, address: str, args: list[Any]) -> None:
        """Called by transport when an OSC message arrives."""
        uid = self._feedback_map.get(address)
        if uid is None:
            return
        value = args[0] if args else None
        self._state_cache[uid] = value
        _LOGGER.debug("Feedback %s → %s = %s", address, uid, value)
        for cb in self._listeners.get(uid, []):
            self.hass.loop.call_soon_threadsafe(cb)

    def register_feedback_listener(self, unique_id: str, callback: Callable) -> None:
        self._listeners.setdefault(unique_id, []).append(callback)

    def unregister_feedback_listener(self, unique_id: str, callback: Callable) -> None:
        if unique_id in self._listeners:
            try:
                self._listeners[unique_id].remove(callback)
            except ValueError:
                pass

    def get_cached_state(self, unique_id: str) -> Any:
        return self._state_cache.get(unique_id)

    def set_cached_state(self, unique_id: str, value: Any) -> None:
        self._state_cache[unique_id] = value

    @property
    def available(self) -> bool:
        return self._available

    async def _async_update_data(self) -> dict:
        """No polling — state is updated via feedback callbacks."""
        return self._state_cache
