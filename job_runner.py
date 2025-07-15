import asyncio
from playwright.async_api import async_playwright
import random
import requests
from datetime import datetime
import logging
import time
from typing import Optional, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === CONFIG ===
BUZZ_LINKS_URL = "https://verceredirect.vercel.app/links.txt"
PROXIES_URL = "https://verceredirect.vercel.app/proxies.txt"
DOWNLOAD_TIMEOUT = 60  # Increased timeout
PAGE_LOAD_TIMEOUT = 30
RETRY_ATTEMPTS = 3
DELAY_BETWEEN_DOWNLOADS = 5  # seconds

# Global state
_running = False
_current_stats = {
    "total_processed": 0,
    "successful_downloads": 0,
    "failed_downloads": 0,
    "current_link": "",
    "start_time": None,
    "last_updated": None
}

def is_running() -> bool:
    """Check if downloader is currently running"""
    return _running

def stop_downloader():
    """Stop the downloader"""
    global _running
    _running = False
    logger.info("Downloader stop requested")

def get_current_stats() -> Dict[str, Any]:
    """Get current statistics"""
    return _current_stats.copy()

def update_stats(**kwargs):
    """Update statistics"""
    global _current_stats
    _current_stats.update(kwargs)
    _current_stats["last_updated"] = datetime.utcnow().isoformat()

async def fetch_links_and_proxies():
    """Fetch links and proxies with error handling"""
    try:
        logger.info("Fetching buzz links...")
        response = requests.get(BUZZ_LINKS_URL, timeout=10)
        response.raise_for_status()
        buzz_links = [link.strip() for link in response.text.strip().splitlines() if link.strip()]
        logger.info(f"Fetched {len(buzz_links)} buzz links")
    except Exception as e:
        logger.error(f"Failed to fetch buzz links: {e}")
        buzz_links = []

    try:
        logger.info("Fetching proxies...")
        response = requests.get(PROXIES_URL, timeout=10)
        response.raise_for_status()
        proxies = [proxy.strip() for proxy in response.text.strip().splitlines() if proxy.strip()]
        logger.info(f"Fetched {len(proxies)} proxies")
    except Exception as e:
        logger.error(f"Failed to fetch proxies: {e}")
        proxies = []

    return buzz_links, proxies

async def download_with_retry(playwright, url: str, proxy: Optional[str], logs_col, max_retries: int = 1):
    """Download with retry logic for a single attempt"""
    for attempt in range(max_retries):
        try:
            result = await run_single_download(playwright, url, proxy, logs_col, attempt + 1)
            if result["success"]:
                return result
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed for {url}: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
    
    # All attempts failed
    return {"success": False, "error": "All retry attempts failed"}

async def run_single_download(playwright, url: str, proxy: Optional[str], logs_col, attempt: int = 1):
    """Run a single download attempt"""
    browser = None
    log_entry = {
        "url": url,
        "proxy": proxy or "direct",
        "timestamp": datetime.utcnow().isoformat(),
        "attempt": attempt,
        "result": "unknown",
        "duration": 0
    }
    
    start_time = time.time()
    
    try:
        # Browser setup with proxy
        browser_args = {
            "headless": True,
            "args": [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-default-apps"
            ]
        }
        
        if proxy:
            browser_args["proxy"] = {"server": proxy}
        
        browser = await playwright.chromium.launch(**browser_args)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        # Navigate to the page
        logger.info(f"Navigating to {url} (attempt {attempt})")
        await page.goto(url, timeout=PAGE_LOAD_TIMEOUT * 1000, wait_until="domcontentloaded")
        
        # Wait for and click first download button
        logger.info("Waiting for download button...")
        download_selector = "text=Download"
        await page.wait_for_selector(download_selector, timeout=15000)
        await page.click(download_selector)
        
        # Wait a bit for any popups/redirects
        await asyncio.sleep(3)
        
        # Close any popup windows
        if len(context.pages) > 1:
            for popup in context.pages[1:]:
                try:
                    await popup.close()
                except:
                    pass
        
        # Click download again if still available
        try:
            await page.click(download_selector, timeout=5000)
            await asyncio.sleep(2)
        except:
            pass  # Download button might not be available anymore
        
        # Wait for download to start/complete
        await asyncio.sleep(DELAY_BETWEEN_DOWNLOADS)
        
        log_entry["result"] = "success"
        log_entry["duration"] = round(time.time() - start_time, 2)
        logger.info(f"Successfully processed {url} in {log_entry['duration']}s")
        
        return {"success": True, "log_entry": log_entry}
        
    except asyncio.TimeoutError:
        error_msg = f"Timeout after {PAGE_LOAD_TIMEOUT}s"
        log_entry["result"] = f"timeout: {error_msg}"
        log_entry["duration"] = round(time.time() - start_time, 2)
        logger.warning(f"Timeout for {url}: {error_msg}")
        return {"success": False, "log_entry": log_entry, "error": error_msg}
        
    except Exception as e:
        error_msg = str(e)
        log_entry["result"] = f"error: {error_msg}"
        log_entry["duration"] = round(time.time() - start_time, 2)
        logger.error(f"Error processing {url}: {error_msg}")
        return {"success": False, "log_entry": log_entry, "error": error_msg}
        
    finally:
        if browser:
            try:
                await browser.close()
            except:
                pass
        
        # Log the attempt
        if logs_col:
            try:
                logs_col.insert_one(log_entry)
            except Exception as e:
                logger.error(f"Failed to log entry: {e}")

def clear_db_after_completion(logs_col, stats_col):
    if logs_col:
        try:
            logs_col.delete_many({})
            logger.info("Logs cleared from database after job completion")
        except Exception as e:
            logger.error(f"Failed to clear logs: {e}")
    if stats_col:
        try:
            stats_col.delete_many({})
            logger.info("Stats cleared from database after job completion")
        except Exception as e:
            logger.error(f"Failed to clear stats: {e}")

async def run_job(logs_col, stats_col):
    global _running, _current_stats
    
    logger.info("Starting download job...")
    update_stats(
        total_processed=0,
        successful_downloads=0,
        failed_downloads=0,
        start_time=datetime.utcnow().isoformat(),
        current_link=""
    )
    
    buzz_links, proxies = await fetch_links_and_proxies()
    
    if not buzz_links:
        logger.error("No buzz links available, stopping job")
        _running = False
        return
    
    logger.info(f"Starting processing of {len(buzz_links)} links with {len(proxies)} proxies")
    
    working_proxies = proxies.copy() if proxies else []
    
    async with async_playwright() as playwright:
        for i, link in enumerate(buzz_links):
            if not _running:
                logger.info("Job stopped by user request")
                break
            
            update_stats(current_link=link)
            logger.info(f"Processing link {i+1}/{len(buzz_links)}: {link}")
            
            available_proxies = working_proxies.copy() if working_proxies else []
            result = None
            retry_attempts = 0
            
            while retry_attempts < RETRY_ATTEMPTS:
                proxy = random.choice(available_proxies) if available_proxies else None
                result = await download_with_retry(playwright, link, proxy, logs_col, max_retries=1)
                if result["success"]:
                    break
                else:
                    error_msg = result.get("error", "").lower()
                    if proxy and ("timeout" in error_msg or "connection" in error_msg):
                        if proxy in available_proxies:
                            available_proxies.remove(proxy)
                            logger.info(f"Removed dead proxy: {proxy}")
                    retry_attempts += 1
            
            _current_stats["total_processed"] += 1
            if result and result.get("success"):
                _current_stats["successful_downloads"] += 1
            else:
                _current_stats["failed_downloads"] += 1
            
            update_stats()
            
            if _running and i < len(buzz_links) - 1:
                await asyncio.sleep(2)
    
    logger.info("Download job completed")
    update_stats(current_link="")
    _running = False
    
    clear_db_after_completion(logs_col, stats_col)

def run_downloader(logs_col, stats_col):
    global _running
    
    if _running:
        logger.warning("Downloader is already running")
        return
    
    _running = True
    try:
        asyncio.run(run_job(logs_col, stats_col))
    except Exception as e:
        logger.error(f"Downloader job failed: {e}")
        _running = False
    finally:
        _running = False
