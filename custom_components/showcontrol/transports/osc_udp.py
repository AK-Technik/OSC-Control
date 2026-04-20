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
        self._feedback_server: AsyncIOOSCUDPServer | None = None
        self._feedback_transport = None
        self._feedback_protocol = None
        self._feedback_task: asyncio.Task | None = None

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
            # python-osc send is blocking but fast (UDP)
            loop = asyncio.get_event_loop()
            if args:
                await loop.run_in_executor(None, client.send_message, address, args)
            else:
                await loop.run_in_executor(None, client.send_message, address, [])
        except Exception as exc:
            _LOGGER.warning("OSC send failed (%s %s): %s", address, args, exc)

    async def start_feedback_listener(
        self,
        listen_port: int,
        callback: Callable[[str, list[Any]], None],
    ) -> None:
        """Start an asyncio OSC UDP server for feedback."""
        dispatcher = Dispatcher()
        dispatcher.set_default_handler(
            lambda address, *args: callback(address, list(args))
        )
        try:
            server = AsyncIOOSCUDPServer(
                ("0.0.0.0", listen_port), dispatcher, asyncio.get_event_loop()
            )
            self._feedback_transport, self._feedback_protocol = await server.create_serve_endpoint()
            _LOGGER.info("OSC feedback listener started on port %d", listen_port)
        except Exception as exc:
            _LOGGER.warning("Could not start OSC feedback listener on port %d: %s", listen_port, exc)

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
        """
        OSC/UDP is connectionless. We attempt a send and consider it OK
        if no socket error is raised. For X32, caller should use /xinfo.
        """
        try:
            await self.send("/ping", [])
            return True
        except Exception:  # noqa: BLE001
            return False
