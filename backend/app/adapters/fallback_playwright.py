from __future__ import annotations

import logging
import random
from urllib.parse import urlparse

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import Page, async_playwright

logger = logging.getLogger(__name__)

DESKTOP_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

MOBILE_USER_AGENTS = [
    "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36",
]


def _normalize_profile(device_profile: str) -> str:
    profile = (device_profile or "desktop").strip().lower()
    if profile not in {"desktop", "mobile"}:
        return "desktop"
    return profile


def _pick_user_agent(device_profile: str) -> str:
    profile = _normalize_profile(device_profile)
    if profile == "mobile":
        return random.choice(MOBILE_USER_AGENTS)
    return random.choice(DESKTOP_USER_AGENTS)


def _context_profile(device_profile: str) -> dict[str, object]:
    profile = _normalize_profile(device_profile)
    if profile == "mobile":
        return {
            "viewport": {"width": 412, "height": 915},
            "is_mobile": True,
            "has_touch": True,
            "device_scale_factor": 2,
        }
    return {
        "viewport": {"width": 1440, "height": 2200},
        "is_mobile": False,
        "has_touch": False,
        "device_scale_factor": 1,
    }


def _playwright_proxy(proxy_url: str | None) -> dict[str, str] | None:
    if not proxy_url:
        return None

    parsed = urlparse(proxy_url)
    if not parsed.scheme or not parsed.hostname or not parsed.port:
        return None

    output: dict[str, str] = {
        "server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}",
    }
    if parsed.username:
        output["username"] = parsed.username
    if parsed.password:
        output["password"] = parsed.password
    return output


async def _scroll_for_lazy_content(page: Page, passes: int = 5, step: int = 1600) -> None:
    for _ in range(passes):
        await page.evaluate(
            """
            (distance) => {
                window.scrollBy(0, distance);
            }
            """,
            step,
        )
        await page.wait_for_timeout(350)

    await page.evaluate("window.scrollTo(0, 0)")
    await page.wait_for_timeout(120)


async def render_page(
    url: str,
    timeout_ms: int = 20000,
    wait_selectors: list[str] | None = None,
    proxy_url: str | None = None,
    scroll: bool = True,
    device_profile: str = "desktop",
    user_agent: str | None = None,
) -> str:
    wait_selectors = wait_selectors or []
    profile = _normalize_profile(device_profile)
    context_profile = _context_profile(profile)
    selected_user_agent = user_agent or _pick_user_agent(profile)

    async with async_playwright() as pw:
        launch_kwargs: dict[str, object] = {"headless": True}
        proxy = _playwright_proxy(proxy_url)
        if proxy:
            launch_kwargs["proxy"] = proxy

        browser = await pw.chromium.launch(**launch_kwargs)
        try:
            context = await browser.new_context(
                user_agent=selected_user_agent,
                locale="ru-RU",
                viewport=context_profile["viewport"],
                is_mobile=bool(context_profile["is_mobile"]),
                has_touch=bool(context_profile["has_touch"]),
                device_scale_factor=float(context_profile["device_scale_factor"]),
                extra_http_headers={
                    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                },
            )
            page = await context.new_page()
            page.set_default_timeout(timeout_ms)

            await page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")

            try:
                await page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 9000))
            except PlaywrightTimeoutError:
                pass

            for selector in wait_selectors:
                try:
                    await page.wait_for_selector(selector, state="attached", timeout=min(timeout_ms, 7000))
                    break
                except PlaywrightTimeoutError:
                    continue

            if scroll:
                await _scroll_for_lazy_content(page)

            html = await page.content()
            return html
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Playwright render failed: url=%s profile=%s proxy=%s err=%s",
                url,
                profile,
                proxy_url,
                exc,
            )
            raise
        finally:
            await browser.close()
