from __future__ import annotations

from typing import Protocol

from .models import ChatMessage


class MessageProcessor(Protocol):
    def process(self, message: ChatMessage) -> None: ...


class NoOpMessageProcessor:
    def process(self, message: ChatMessage) -> None:
        """V1 extension point: intentionally performs no external action."""
