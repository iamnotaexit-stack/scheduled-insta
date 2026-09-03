import asyncio
import random
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
            print(f"[{timestamp}] Error during submission to {url}: {e}")
        finally:
            await browser.close()

async def views_task():
    url = "https://zefame.com/en/free-instagram-views"
    interval = 8 * 60  # 8 minutes
    while True:
        link = random.choice(REEL_LINKS)
        await submit_link(url, link)
        await asyncio.sleep(interval)

async def likes_task():
    url = "https://zefame.com/en/free-instagram-likes"
    interval = 35 * 60  # 35 minutes
    while True:
        link = random.choice(REEL_LINKS)
        await submit_link(url, link)
        await asyncio.sleep(interval)

async def followers_task():
    url = "https://zefame.com/en/free-instagram-followers"
    interval = (24 * 60 + 3) * 60  # 24 hours 3 minutes
    while True:
        await submit_link(url, PROFILE_LINK)
        await asyncio.sleep(interval)

async def main():
    print("Starting Zefame scheduled automation...")
    await asyncio.gather(
        views_task(),
        likes_task(),
        followers_task()
    )

if __name__ == "__main__":
    asyncio.run(main())
