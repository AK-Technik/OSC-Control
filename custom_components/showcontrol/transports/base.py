"""Abstract transport base class."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable


class AbstractTransport(ABC):
    """Abstract base for Show Control transports."""

    @abstractmethod
    async def send(self, address: str, args: list[Any], *, port: int | None = None) -> None:
        """Send a message to the given OSC address."""

    @abstractmethod
    async def start_feedback_listener(
        self,
        listen_port: int,
        callback: Callable[[str, list[Any]], None],
    ) -> None:
        """Start listening for inbound feedback messages."""

    @abstractmethod
    async def stop_feedback_listener(self) -> None:
        """Stop the feedback listener."""

    @abstractmethod
    async def close(self) -> None:
        """Close the transport and release resources."""

    @abstractmethod
    async def ping(self) -> bool:
        """Test connectivity. Returns True if device is reachable."""
