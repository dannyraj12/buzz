import asyncio
from playwright.async_api import async_playwright
import random
import requests
from datetime import datetime

# === CONFIG ===
BUZZ_LINKS_URL = "https://verceredirect.vercel.app/links.txt"
PROXIES_URL = "https://verceredirect.vercel.app/proxies.txt"
DOWNLOAD_TIMEOUT = 45

# State tracker
_running = False

def is_running():
    return _running

def stop_downloader():
    global _running
    _running = False

async def run_with_proxy(playwright, url, proxy, logs_col):
    browser = await playwright.chromium.launch(headless=True, proxy={"server": proxy} if proxy else None)
    context = await browser.new_context()
    page = await context.new_page()

    log_entry = {
        "url": url,
        "proxy": proxy,
        "timestamp": datetime.utcnow().isoformat(),
        "result": "unknown"
    }

    try:
        await page.goto(url, timeout=DOWNLOAD_TIMEOUT * 1000)
        await page.wait_for_selector("text=Download", timeout=15000)
        await page.click("text=Download")
        await asyncio.sleep(2)
        if len(context.pages) > 1:
            for popup in context.pages[1:]:
                await popup.close()
        await page.click("text=Download")
        await asyncio.sleep(4)
        log_entry["result"] = "success"
    except Exception as e:
        log_entry["result"] = f"fail: {str(e)}"
    finally:
        await browser.close()
        logs_col.insert_one(log_entry)

async def run_job(logs_col):
    global _running
    _running = True

    buzz_links = requests.get(BUZZ_LINKS_URL).text.strip().splitlines()
    try:
        proxies = requests.get(PROXIES_URL).text.strip().splitlines()
    except:
        proxies = []

    async with async_playwright() as p:
        for link in buzz_links:
            if not _running:
                break
            proxy = random.choice(proxies) if proxies else None
            await run_with_proxy(p, link, proxy, logs_col)

    _running = False


def run_downloader(logs_col):
    asyncio.run(run_job(logs_col))
