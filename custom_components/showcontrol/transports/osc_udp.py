"""OSC UDP transport using python-osc.

CRITICAL: TX and RX must use the SAME socket. The X32 (and most OSC devices)
sends responses back to the source address+port of the request packet, NOT to
some configured "feedback port". So we bind a single socket on a fixed source
port, send from it, and listen on it.
"""
from __future__ import annotations

import asyncio
import logging
import socket
from typing import Any, Callable

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import AsyncIOOSCUDPServer
from pythonosc.osc_message_builder import OscMessageBuilder

from .base import AbstractTransport

_LOGGER = logging.getLogger(__name__)


class _SharedSocketProtocol(asyncio.DatagramProtocol):
    """Datagram protocol that handles both inbound OSC and provides outbound send."""

    def __init__(self, dispatcher: Dispatcher) -> None:
        self._dispatcher = dispatcher
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:  # type: ignore[override]
        self.transport = transport

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:  # type: ignore[override]
        try:
            self._dispatcher.call_handlers_for_packet(data, addr)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.debug("Failed to dispatch OSC packet from %s: %s", addr, exc)

    def error_received(self, exc: Exception) -> None:  # type: ignore[override]
        _LOGGER.debug("OSC UDP error_received: %s", exc)


class OscUdpTransport(AbstractTransport):
    """Send/receive OSC over UDP using a single shared socket."""

    def __init__(self, host: str, port: int, source_port: int = 0) -> None:
        self._host = host
        self._default_port = port
        self._source_port = source_port
        self._dispatcher: Dispatcher | None = None
        self._transport: asyncio.DatagramTransport | None = None
        self._protocol: _SharedSocketProtocol | None = None
        self._callback: Callable[[str, list[Any]], None] | None = None

    async def _ensure_socket(self) -> None:
        """Make sure the shared UDP socket is open."""
        if self._transport is not None:
            return

        # Build dispatcher even if no callback registered yet — we add later.
        if self._dispatcher is None:
            self._dispatcher = Dispatcher()

        loop = asyncio.get_running_loop()
        bind_port = self._source_port if self._source_port else 0

        # create_datagram_endpoint with local_addr binds the socket; same socket
        # is used for sending via transport.sendto().
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: _SharedSocketProtocol(self._dispatcher),
            local_addr=("0.0.0.0", bind_port),
        )
        self._transport = transport
        self._protocol = protocol

        actual_port = transport.get_extra_info("sockname")[1]
        _LOGGER.info(
            "OSC shared socket bound on 0.0.0.0:%d (target %s:%d)",
            actual_port, self._host, self._default_port,
        )

    async def send(self, address: str, args: list[Any], *, port: int | None = None) -> None:
        """Send OSC message via the shared socket."""
        await self._ensure_socket()
        target_port = port if port is not None else self._default_port

        try:
            builder = OscMessageBuilder(address=address)
            for arg in args or []:
                builder.add_arg(arg)
            packet = builder.build().dgram

            if self._transport is None:
                _LOGGER.warning("OSC transport not ready, dropping %s", address)
                return
            self._transport.sendto(packet, (self._host, target_port))
            _LOGGER.debug("OSC send %s %s → %s:%d", address, args, self._host, target_port)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning("OSC send failed (%s %s): %s", address, args, exc)

    async def start_feedback_listener(
        self,
        listen_port: int,  # ignored — RX uses the same socket as TX
        callback: Callable[[str, list[Any]], None],
    ) -> None:
        """Register feedback callback on the shared socket.

        The listen_port parameter is kept for backwards compatibility but ignored.
        OSC feedback arrives on the same socket we send from.
        """
        self._callback = callback
        if self._dispatcher is None:
            self._dispatcher = Dispatcher()
        self._dispatcher.set_default_handler(
            lambda address, *args: callback(address, list(args))
        )
        await self._ensure_socket()
        _LOGGER.info("OSC feedback listener active on shared socket")

    async def stop_feedback_listener(self) -> None:
        # We keep the socket open (it's also our send socket).
        # Just clear the callback.
        if self._dispatcher is not None:
            self._dispatcher.set_default_handler(lambda *_a, **_kw: None)
        self._callback = None

    async def close(self) -> None:
        if self._transport is not None:
            try:
                self._transport.close()
            except Exception:  # noqa: BLE001
                pass
            self._transport = None
            self._protocol = None
        self._dispatcher = None
        self._callback = None
        _LOGGER.debug("OscUdpTransport closed")

    async def ping(self) -> bool:
        """UDP is connectionless — quick socket reachability check."""
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._check_socket)
            return True
        except Exception:  # noqa: BLE001
            return False

    def _check_socket(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2.0)
        try:
            sock.connect((self._host, self._default_port))
        finally:
            sock.close()
