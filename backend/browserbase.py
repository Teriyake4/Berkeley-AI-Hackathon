"""
Browserbase helper — drives a remote headless browser to gather live web
citations for the research agent.

Design goals (hackathon-grade, demo-safe):
- Fully GATED: does nothing unless BROWSERBASE_API_KEY + BROWSERBASE_PROJECT_ID
  are set AND the `playwright` client package is importable.
- Fully FALLBACK-SAFE: any failure (no key, no playwright, session error,
  navigation timeout, scrape miss) returns None so the research agent falls
  through to its PubMed / curated-mock path. Never raises to the caller.
- The browser runs in Browserbase's cloud, so we only need the playwright
  *client* — no local Chromium download required. We connect over CDP.
"""
from __future__ import annotations

import logging
import os
from typing import List, Optional
from urllib.parse import quote_plus

import httpx

from events import Citation

logger = logging.getLogger(__name__)


def has_browserbase() -> bool:
    return bool(
        os.environ.get("BROWSERBASE_API_KEY")
        and os.environ.get("BROWSERBASE_PROJECT_ID")
    )


async def _get_connect_url() -> Optional[str]:
    """Create a Browserbase session and return a CDP connect URL."""
    api_key = os.environ.get("BROWSERBASE_API_KEY", "")
    project_id = os.environ.get("BROWSERBASE_PROJECT_ID", "")
    if not api_key or not project_id:
        return None

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.browserbase.com/v1/sessions",
                headers={"X-BB-API-Key": api_key, "Content-Type": "application/json"},
                json={"projectId": project_id},
            )
            if not resp.is_success:
                logger.warning("[browserbase] session create failed: %s", resp.status_code)
                return None
            data = resp.json()
    except Exception as e:
        logger.warning("[browserbase] session create error: %s", e)
        return None

    # Different API versions expose the connect URL differently; try both,
    # else construct the canonical wss URL from the session id.
    connect_url = data.get("connectUrl") or data.get("connect_url")
    if connect_url:
        return connect_url
    session_id = data.get("id") or data.get("sessionId")
    if session_id:
        return f"wss://connect.browserbase.com?apiKey={api_key}&sessionId={session_id}"
    return None


async def browserbase_search(query: str, max_results: int = 3) -> Optional[List[Citation]]:
    """
    Run a live web search through a Browserbase cloud browser and return
    citations. Returns None on any failure (caller should fall back).
    """
    if not has_browserbase():
        return None

    try:
        from playwright.async_api import async_playwright  # type: ignore
    except Exception:
        logger.info("[browserbase] playwright client not installed — skipping live search")
        return None

    connect_url = await _get_connect_url()
    if not connect_url:
        return None

    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(connect_url)
            try:
                context = browser.contexts[0] if browser.contexts else await browser.new_context()
                page = context.pages[0] if context.pages else await context.new_page()
                await page.goto(url, timeout=20000, wait_until="domcontentloaded")

                # DuckDuckGo HTML endpoint exposes stable result classes.
                raw = await page.eval_on_selector_all(
                    ".result",
                    """els => els.slice(0, 8).map(el => {
                        const a = el.querySelector('.result__a');
                        const s = el.querySelector('.result__snippet');
                        return {
                            title: a ? a.innerText.trim() : '',
                            url: a ? a.href : '',
                            snippet: s ? s.innerText.trim() : ''
                        };
                    })""",
                )
            finally:
                await browser.close()
    except Exception as e:
        logger.warning("[browserbase] search error: %s", e)
        return None

    citations: List[Citation] = []
    for item in raw or []:
        title = (item.get("title") or "").strip()
        link = (item.get("url") or "").strip()
        if not title or not link:
            continue
        citations.append(
            Citation(
                title=title,
                url=link,
                snippet=(item.get("snippet") or "").strip()[:280] or None,
            )
        )
        if len(citations) >= max_results:
            break

    return citations or None
