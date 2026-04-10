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
            # Wait for any of the expected selectors
            interval = 0.5
            max_iter = int(timeout_ms / (interval * 1000))
            for _ in range(max_iter):
                found = False
                
                # Check for anti-bot
                try:
                    html_check = await page.evaluate("document.body.innerText || ''")
                    if html_check and any(x in html_check.lower() for x in ["такой страницы не существует", "почти готово", "доступ ограничен"]):
                        logger.info("Captcha detected.. trying CapMonster...")
                        try:
                            site_key = await page.evaluate("document.querySelector('b[data-site-key]') ? document.querySelector('b[data-site-key]').getAttribute('data-site-key') : null")
                            if site_key:
                                import httpx
                                api_key = "38f9f6159a0572d125b8f393b80e6cd8"
                                async with httpx.AsyncClient() as client:
                                    res = await client.post("https://api.capmonster.cloud/createTask", json={
                                        "clientKey": api_key,
                                        "task": {
                                            "type": "TurnstileTaskProxyless",
                                            "websiteURL": url,
                                            "websiteKey": site_key,
                                            "action": "managed"
                                        }
                                    })
                                    task_id = res.json().get("taskId")
                                    if task_id:
                                        for _poll in range(12):
                                            await asyncio.sleep(5)
                                            ans = await client.post("https://api.capmonster.cloud/getTaskResult", json={"clientKey": api_key, "taskId": task_id})
                                            poll_data = ans.json()
                                            if poll_data.get("status") == "ready":
                                                token = poll_data.get("solution", {}).get("token")
                                                if token:
                                                    await page.evaluate(f"""
                                                        document.cookie = "wlbc={token}; path=/; max-age=3600";
                                                        document.cookie = "cf_clearance={token}; path=/; max-age=3600";
                                                    """)
                                                    logger.info("CapMonster Turnstile token inserted!")
                                                break
                        except Exception as e:
                            logger.error(f"CapMonster error: {e}")
                        break
                except Exception:
                    pass

                for selector in wait_selectors:
                    try:
                        node = await page.evaluate(f'document.querySelector("{selector}")')
                        if node:
                            found = True
                            break
                    except Exception:
                        pass
                if found:
                    break
                await page.sleep(interval)
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