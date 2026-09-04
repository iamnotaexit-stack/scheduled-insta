import asyncio
import random
import sys
import time
from playwright.async_api import async_playwright

from config import REEL_LINKS, PROFILE_LINK

def clean_url(url_string):
    clean = url_string.split('?')[0]
    if not clean.endswith('/'):
        clean += '/'
    return clean

async def submit_link(url, link):
    target_link = clean_url(link)
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] Navigating to {url} with link: {target_link}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            
            input_field = page.locator("#instagram-link")
            await input_field.wait_for(timeout=10000)
            await input_field.fill(target_link)
            
            submit_btn = page.locator("#submit-btn")
            await submit_btn.click()
            
            print(f"[{timestamp}] Clicked submit button. Waiting 80 seconds for countdown to finish...")
            await page.wait_for_timeout(80000)
            
            success_visible = await page.locator("#success-page").is_visible()
            error_visible = await page.locator("#error-page").is_visible()
            
            if success_visible:
                print(f"[{timestamp}] SUCCESS: Submission verified and completed for {url}")
            elif error_visible:
                err_text = await page.locator("#error-message").inner_text()
                print(f"[{timestamp}] ERROR response from Zefame: {err_text}")
            else:
                print(f"[{timestamp}] Finished 80-second wait cycle on {url}")
        except Exception as e:
            print(f"[{timestamp}] Exception during submission to {url}: {e}")
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
