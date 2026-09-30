"""Jina Reader web content extraction — plugin form.

Subclasses :class:`agent.web_search_provider.WebSearchProvider`. One
capability advertised:

- ``supports_extract()`` -> True (Jina ``r.jina.ai``)

Search-only — pair with DDGS, Brave Free, SearXNG, or any other search
backend for `web_search`. Jina Reader is a clean, minimal extraction API
that prepends ``https://r.jina.ai/`` to any URL and returns LLM-ready
markdown. Handles JS-rendered pages server-side, strips sidebar/nav noise,
and is free for moderate use.

Config keys this provider responds to::

    web:
      extract_backend: "jina"     # explicit per-capability

Env vars::

    JINA_API_KEY=...              # optional — removes anonymous rate limits
                                  # and domain blocks (free key at jina.ai)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import httpx

from agent.web_search_provider import WebSearchProvider, get_provider_env

logger = logging.getLogger(__name__)

JINA_BASE_URL = "https://r.jina.ai"


def _jina_extract_one(url: str, api_key: str) -> Dict[str, Any]:
    """Fetch a single URL through Jina Reader and return a result dict.

    Returns the legacy extract result shape::

        {
            "url": str,
            "title": str,
            "content": str,
            "raw_content": str,
            "metadata": dict,
        }

    On per-URL failure, the dict has an ``error`` field instead.
    """
    # Pass the URL with its scheme intact — Jina normalizes the
    # ``URL Source`` it returns to http:// when the scheme is stripped,
    # which then makes relative links in the markdown resolve as http://.
    target = f"{JINA_BASE_URL}/{url}"
    headers = {
        "Accept": "text/plain",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        response = httpx.get(target, headers=headers, timeout=60, follow_redirects=True)
        response.raise_for_status()
        text = response.text
    except httpx.HTTPStatusError as exc:
        return {
            "url": url,
            "title": "",
            "content": "",
            "raw_content": "",
            "error": f"Jina Reader HTTP {exc.response.status_code}: {exc.response.text[:200]}",
            "metadata": {"sourceURL": url, "status": exc.response.status_code},
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "url": url,
            "title": "",
            "content": "",
            "raw_content": "",
            "error": f"Jina Reader request failed: {exc}",
            "metadata": {"sourceURL": url},
        }

    # Parse the structured response Jina returns.
    # Format:
    #   Title: <title>
    #   URL Source: <original_url>
    #   Published Time: <iso>   (optional)
    #   Markdown Content:
    #   <actual markdown>
    title = ""
    published = ""
    content_start = 0
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("Title:"):
            title = line[len("Title:"):].strip()
        elif line.startswith("URL Source:"):
            # update URL to the original (pre-redirect) form if present
            parsed = line[len("URL Source:"):].strip()
            if parsed:
                url = parsed
        elif line.startswith("Published Time:"):
            published = line[len("Published Time:"):].strip()
        elif line.startswith("Markdown Content:"):
            content_start = i + 1
            break

    content = "\n".join(lines[content_start:]).strip()

    return {
        "url": url,
        "title": title,
        "content": content,
        "raw_content": content,
        "metadata": {
            "sourceURL": url,
            "title": title,
            "publishedTime": published,
        },
    }


class JinaReaderProvider(WebSearchProvider):
    """Jina Reader extract-only provider."""

    @property
    def name(self) -> str:
        return "jina"

    @property
    def display_name(self) -> str:
        return "Jina Reader"

    def is_available(self) -> bool:
        """Always available — works with or without an API key.

        Without a key: ~20 RPM, some domains blocked for anonymous abuse.
        With JINA_API_KEY set: 500 RPM, full access, 1M free tokens/mo.
        """
        return True

    def supports_search(self) -> bool:
        return False

    def supports_extract(self) -> bool:
        return True

    def extract(self, urls: List[str], **kwargs: Any) -> List[Dict[str, Any]]:
        """Extract content from one or more URLs via Jina Reader.

        Sync — underlying calls are ``httpx.get(...)`` per URL. Sequential
        to stay well under the anonymous rate limit (20 RPM); the
        dispatcher's ``asyncio.to_thread`` wrapper handles the event loop.
        """
        try:
            from tools.interrupt import is_interrupted

            if is_interrupted():
                return [
                    {"url": u, "error": "Interrupted", "title": ""} for u in urls
                ]
        except ImportError:
            pass

        api_key = get_provider_env("JINA_API_KEY")
        logger.info(
            "Jina Reader extract: %d URL(s) (api_key=%s)",
            len(urls),
            "set" if api_key else "anonymous",
        )

        results = []
        for url in urls:
            results.append(_jina_extract_one(url, api_key))
        return results

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "Jina Reader",
            "badge": "free",
            "tag": "r.jina.ai — clean markdown extraction, handles JS pages, free tier with 1M tokens/mo.",
            "env_vars": [
                {
                    "key": "JINA_API_KEY",
                    "prompt": "Jina API key (optional — free at jina.ai)",
                    "url": "https://jina.ai/reader/",
                },
            ],
        }