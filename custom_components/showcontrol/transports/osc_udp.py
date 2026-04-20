"""OSC UDP transport using python-osc."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from pythonosc.udp_client import SimpleUDPClient
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import AsyncIOOSCUDPServer

from .base import AbstractTransport

_LOGGER = logging.getLogger(__name__)


class OscUdpTransport(AbstractTransport):
    """Send/receive OSC over UDP."""

    def __init__(self, host: str, port: int, source_port: int = 0) -> None:
        self._host = host
        self._default_port = port
        self._source_port = source_port
        self._clients: dict[int, SimpleUDPClient] = {}
        self._feedback_transport = None
        self._feedback_protocol = None

    def _get_client(self, port: int) -> SimpleUDPClient:
        if port not in self._clients:
            _LOGGER.debug("Creating OSC UDP client → %s:%d", self._host, port)
            self._clients[port] = SimpleUDPClient(self._host, port)
        return self._clients[port]

    async def send(self, address: str, args: list[Any], *, port: int | None = None) -> None:
        """Send OSC message."""
        target_port = port if port is not None else self._default_port
        client = self._get_client(target_port)
        try:
            _LOGGER.debug("OSC send %s %s → %s:%d", address, args, self._host, target_port)
            loop = asyncio.get_running_loop()  # FIX: was get_event_loop() — deprecated
            await loop.run_in_executor(None, client.send_message, address, args if args else [])
        except Exception as exc:
            _LOGGER.warning("OSC send failed (%s %s): %s", address, args, exc)

    async def start_feedback_listener(
        self,
        listen_port: int,
        callback: Callable[[str, list[Any]], None],
    ) -> None:
        """Start an asyncio OSC UDP server for inbound feedback."""
        dispatcher = Dispatcher()
        dispatcher.set_default_handler(
            lambda address, *args: callback(address, list(args))
        )
        try:
            loop = asyncio.get_running_loop()  # FIX: was get_event_loop()
            server = AsyncIOOSCUDPServer(("0.0.0.0", listen_port), dispatcher, loop)
            self._feedback_transport, self._feedback_protocol = (
                await server.create_serve_endpoint()
            )
            _LOGGER.info("OSC feedback listener started on port %d", listen_port)
        except Exception as exc:
            _LOGGER.warning(
                "Could not start OSC feedback listener on port %d: %s", listen_port, exc
            )

    async def stop_feedback_listener(self) -> None:
        if self._feedback_transport is not None:
            try:
                self._feedback_transport.close()
            except Exception:  # noqa: BLE001
                pass
            self._feedback_transport = None
            self._feedback_protocol = None

    async def close(self) -> None:
        await self.stop_feedback_listener()
        self._clients.clear()
        _LOGGER.debug("OscUdpTransport closed")

    async def ping(self) -> bool:
        """UDP is connectionless — we do a socket reachability check instead of blind send."""
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._check_socket)
            return True
        except Exception:  # noqa: BLE001
            return False

    def _check_socket(self) -> None:
        """Open a UDP socket and attempt a send; raises on hard network errors."""
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2.0)
        try:
            sock.connect((self._host, self._default_port))
        finally:
            sock.close()
