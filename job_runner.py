import asyncio
import random
from datetime import datetime
from playwright.async_api import async_playwright
import requests
from pymongo import MongoClient
import os

# === ENV & SETTINGS ===
BUZZ_LINKS_FILE = os.getenv("BUZZ_LINKS_FILE", "https://verceredirect.vercel.app/links.txt")
PROXIES_FILE = os.getenv("PROXIES_FILE", "https://verceredirect.vercel.app/proxies.txt")
DOWNLOAD_TIMEOUT = 45  # seconds
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["buzzheavier"]
logs_collection = db["logs"]

# === Run a single link with a proxy ===
async def run_with_proxy(playwright, url, proxy=None):
    try:
        browser = await playwright.chromium.launch(
            headless=True,
            proxy={"server": proxy} if proxy else None
        )
        context = await browser.new_context()
        page = await context.new_page()

        print(f"\n🌐 Visiting: {url} with proxy: {proxy or 'None'}")
        await page.goto(url, timeout=DOWNLOAD_TIMEOUT * 1000)

        await page.wait_for_selector("text=Download", timeout=15000)
        await page.click("text=Download")
        await asyncio.sleep(2)

        if len(context.pages) > 1:
            for popup in context.pages[1:]:
                await popup.close()

        await page.click("text=Download")
        await asyncio.sleep(4)

        logs_collection.insert_one({
            "url": url,
            "proxy": proxy,
            "result": "success",
            "timestamp": datetime.utcnow()
        })

        print("✅ Success")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        await browser.close()


# === Master run loop ===
async def run_downloader():
    print("🚀 Starting Buzzheavier simulator...")

    buzz_links = requests.get(BUZZ_LINKS_FILE).text.strip().splitlines()
    raw_proxies = requests.get(PROXIES_FILE).text.strip().splitlines()
    proxies = [p.strip() for p in raw_proxies if p.strip()]

    async with async_playwright() as playwright:
        for link in buzz_links:
            print(f"\n🔗 Processing: {link}")
            attempts = 0
            success = False

            while not success and proxies:
                proxy = random.choice(proxies)
                success = await run_with_proxy(playwright, link, proxy)

                if success:
                    break
                else:
                    print(f"🧹 Removing bad proxy: {proxy}")
                    proxies.remove(proxy)

            if not proxies and not success:
                print("❌ No working proxies left, stopping early.")
                break

    print("\n✅ All done!")


# === Control flags for FastAPI dashboard ===
is_running = False
runner_task = None

async def start_downloader():
    global is_running, runner_task
    if not is_running:
        is_running = True
        runner_task = asyncio.create_task(run_downloader())

async def stop_downloader():
    global is_running, runner_task
    if is_running and runner_task:
        runner_task.cancel()
        is_running = False

def get_logs():
    return list(logs_collection.find({}, {"_id": 0}).sort("timestamp", -1).limit(50))
