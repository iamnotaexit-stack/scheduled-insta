import asyncio
import random
import sys
import time
from playwright.async_api import async_playwright

from config import REEL_LINKS, PROFILE_LINK

async def submit_link(url, link):
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] Navigating to {url} with link: {link}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            input_field = page.locator("#instagram-link")
            await input_field.wait_for(timeout=10000)
            await input_field.fill(link)
            
            submit_btn = page.locator("#submit-btn")
            await submit_btn.click()
            print(f"[{timestamp}] Submitted link successfully to {url}")
            await page.wait_for_timeout(5000)
        except Exception as e:
            print(f"[{timestamp}] Error submitting to {url}: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    task_type = sys.argv[1] if len(sys.argv) > 1 else "views"
    if task_type == "views":
        asyncio.run(submit_link("https://zefame.com/en/free-instagram-views", random.choice(REEL_LINKS)))
    elif task_type == "likes":
        asyncio.run(submit_link("https://zefame.com/en/free-instagram-likes", random.choice(REEL_LINKS)))
    elif task_type == "followers":
        asyncio.run(submit_link("https://zefame.com/en/free-instagram-followers", PROFILE_LINK))
