"""Jina Reader web extract plugin — user-installed, opt-in via plugins.enabled."""

from __future__ import annotations

from plugins.web.jina.provider import JinaReaderProvider


def register(ctx) -> None:
    """Register the Jina Reader provider with the plugin context."""
    ctx.register_web_search_provider(JinaReaderProvider())