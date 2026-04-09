import asyncio
import logging
import nodriver as uc
from nodriver import Config

logger = logging.getLogger(__name__)

async def render_page(
    url: str,
    timeout_ms: int = 20000,
    wait_selectors: list[str] | None = None,
    proxy_url: str | None = None,
    scroll: bool = True,
    device_profile: str = "desktop",
    user_agent: str | None = None,
) -> str:
    config = Config(browser_args=[
        "--disable-blink-features=AutomationControlled",
        "--disable-blink-features",
        "--disable-web-security",
        "--disable-features=IsolateOrigins,site-per-process",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--window-size=1440,2200",
        "--window-position=0,0",
        f"--app={url}",
    ])

    browser = await uc.start(config=config, user_data_dir=False, headless=False, proxy=proxy_url)
    try:
        page = await browser.get(url)

        if wait_selectors:
            # Ждем первый успешный селектор
            for selector in wait_selectors:
                try:
                    await page.select(selector, timeout=min(timeout_ms // 1000, 7))
                    break
                except Exception:
                    continue
        else:
            await page.sleep(2)

        if scroll:
            for _ in range(5):
                await page.evaluate("window.scrollBy(0, 1600);")
                await page.sleep(0.3)

        content = await page.get_content()
        return content
    except Exception as exc:
        logger.warning(f"nodriver render failed: url={url} err={exc}")
        raise
    finally:
        browser.stop()