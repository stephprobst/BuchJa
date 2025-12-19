"""Slim status footer for background tasks.

The footer is hidden by default and becomes visible only while one or more
background tasks are running.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from nicegui import ui


class StatusFooter:
    """A small footer that shows an in-progress status message."""

    def __init__(self) -> None:
        self._tokens: list[str] = []
        self._messages: dict[str, str] = {}

        with ui.footer().classes('bg-gray-100 w-full') as footer:
            with ui.row().classes('w-full items-center justify-between px-4 py-1'):
                self._label = ui.label('').classes('text-xs text-gray-600')
                self._spinner = ui.spinner(size='sm').classes('text-gray-500')

        self._footer = footer
        self._footer.set_visibility(False)

    def _refresh(self) -> None:
        if not self._tokens:
            self._footer.set_visibility(False)
            return

        self._footer.set_visibility(True)
        token = self._tokens[-1]
        self._label.text = self._messages.get(token, 'Working...')

    def start(self, message: str) -> str:
        """Show the footer with the given message.

        Returns a token which must be passed to :meth:`end`.
        """
        token = uuid.uuid4().hex
        self._tokens.append(token)
        self._messages[token] = message
        self._refresh()
        return token

    def update(self, message: str, token: Optional[str] = None) -> None:
        """Update the visible message.

        If token is omitted, updates the most-recent task.
        """
        if not self._tokens:
            return

        if token is None:
            token = self._tokens[-1]

        if token in self._messages:
            self._messages[token] = message

        self._refresh()

    def end(self, token: str) -> None:
        """Hide the footer for the given token.

        If other tasks are still running, the footer stays visible and shows the
        most-recent task message.
        """
        self._messages.pop(token, None)
        if token in self._tokens:
            self._tokens.remove(token)
        self._refresh()

    @asynccontextmanager
    async def busy(self, message: str) -> AsyncIterator[str]:
        """Async context manager which shows the footer for the duration.

        Yields:
            A token that can be used with :meth:`update`.
        """
        token = self.start(message)
        try:
            yield token
        finally:
            self.end(token)
