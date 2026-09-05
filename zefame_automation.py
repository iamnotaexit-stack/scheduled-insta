import asyncio
import atexit
import ctypes
import os
import random
import re
import sys
import time

if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(SCRIPT_DIR, "automation.log")

class OutputTee:
    def __init__(self, stream, log_path):
        self.stream = stream
        self.log_path = log_path

    def write(self, data):
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(data)
                f.flush()
        except Exception:
            pass
        try:
            if self.stream:
                self.stream.write(data)
                self.stream.flush()
        except Exception:
            pass

    def flush(self):
        try:
            if self.stream:
                self.stream.flush()
        except Exception:
            pass

sys.stdout = OutputTee(sys.stdout, LOG_FILE)

def log(msg):
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {msg}", flush=True)

MUTEX_NAME = "Global\\ZefameInstagramAutomationSingleInstance"
_MUTEX_HANDLE = None

def enforce_single_instance():
    global _MUTEX_HANDLE
    if sys.platform == "win32":
        _MUTEX_HANDLE = ctypes.windll.kernel32.CreateMutexW(None, False, MUTEX_NAME)
        if ctypes.windll.kernel32.GetLastError() == 183:
            log("Another instance of Zefame automation is already running. Exiting duplicate.")
            sys.exit(0)

def release_single_instance():
    global _MUTEX_HANDLE
    if _MUTEX_HANDLE and sys.platform == "win32":
        try:
            ctypes.windll.kernel32.CloseHandle(_MUTEX_HANDLE)
            _MUTEX_HANDLE = None
        except Exception:
            pass

atexit.register(release_single_instance)

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import importlib
import config
import state

DRIVER_PATH = os.path.join(os.environ.get('APPDATA', ''), 'undetected_chromedriver', 'undetected_chromedriver.exe')

class SafeChrome(uc.Chrome):
    def __del__(self):
        pass

    def quit(self):
        try:
            super().quit()
        except Exception:
            pass

def clean_url(url_string):
    clean = url_string.split('?')[0]
    if not clean.endswith('/'):
        clean += '/'
    return clean

def parse_wait_time(msg):
    h_match = re.search(r'(\d+)\s*h(?:eures?|ours?)?', msg, re.IGNORECASE)
    m_match = re.search(r'(\d+)\s*(?:m|min|minutes?)', msg, re.IGNORECASE)
    s_match = re.search(r'(\d+)\s*s(?:ec|econdes?|econds?)?', msg, re.IGNORECASE)

    total = 0
    found = False
    if h_match:
        total += int(h_match.group(1)) * 3600
        found = True
    if m_match:
        total += int(m_match.group(1)) * 60
        found = True
    if s_match:
        total += int(s_match.group(1))
        found = True

    return total + 15 if found else None

def submit_link_sync(url, link):
    target_link = clean_url(link)
    log(f"Submitting to: {url}")
    log(f"Target link: {target_link}")

    options = uc.ChromeOptions()
    options.headless = False
    options.add_argument("--disable-notifications")
    options.add_argument("--mute-audio")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1200,800")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-renderer-backgrounding")

    driver_kwargs = {"options": options}
    if os.path.exists(DRIVER_PATH):
        driver_kwargs["driver_executable_path"] = DRIVER_PATH

    driver = None
    try:
        driver = SafeChrome(**driver_kwargs)
        driver.set_page_load_timeout(45)
        try:
            driver.get(url)
        except Exception:
            pass

        time.sleep(1)
        if "502 Bad Gateway" in driver.title or "Error 502" in driver.title or "502 Bad Gateway" in driver.page_source:
            log("Notice: Zefame returned 502 Bad Gateway. Server is temporarily unreachable.")
            return False, 120, "Server 502 Bad Gateway"

        wait = WebDriverWait(driver, 20)
        input_elem = wait.until(EC.presence_of_element_located((By.ID, "instagram-link")))
        input_elem.clear()
        input_elem.send_keys(target_link)

        submit_btn = driver.find_element(By.ID, "submit-btn")
        submit_btn.click()
        log("Form submitted. Awaiting timer and verification...")

        for s in range(85):
            time.sleep(1)
            err_visible = False
            succ_visible = False
            try:
                err_el = driver.find_element(By.ID, "error-page")
                err_visible = err_el.is_displayed()
            except Exception:
                pass
            try:
                succ_el = driver.find_element(By.ID, "success-page")
                succ_visible = succ_el.is_displayed()
            except Exception:
                pass

            if err_visible:
                err_msg = driver.find_element(By.ID, "error-message").text.strip()
                log(f"Notice from Zefame: {err_msg}")
                wait_time = parse_wait_time(err_msg)
                return False, wait_time, err_msg
            if succ_visible:
                succ_msg = driver.find_element(By.ID, "success-page").text.replace("\n", " ").strip()
                log(f"SUCCESS: {succ_msg}")
                return True, None, succ_msg

        log("Verification timed out after 85 seconds.")
        return False, None, "Timed out"
    except Exception as e:
        first_line = str(e).strip().split('\n')[0]
        log(f"Exception during submission: {first_line}")
        return False, None, first_line
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

browser_lock = asyncio.Lock()

async def submit_link(url, link):
    async with browser_lock:
        return await asyncio.to_thread(submit_link_sync, url, link)

async def views_task():
    url = "https://zefame.com/en/free-instagram-views"
    log(f"Views task active: every {config.VIEWS_INTERVAL // 60} minutes.")
    while True:
        try:
            importlib.reload(config)
        except Exception:
            pass

        reel, mode, remaining, target = state.get_eligible_reel_for_views()

        if mode == "VIEWS_CAP_REACHED_WAITING_LIKES":
            log(f"Views: All reels reached view targets ({config.VIEW_CAP_RANGE[0]}-{config.VIEW_CAP_RANGE[1]}). Pausing views until like targets complete.")
            await asyncio.sleep(600)
            continue

        if mode == "HINDER_DAILY_LIMIT_REACHED":
            log(f"Views: Daily hinder limit ({target} views/day) completed for today. Sleeping 1 hour.")
            await asyncio.sleep(3600)
            continue

        if mode == "HINDER_ACTIVATED":
            log(f"Hinder Mode Activated! All view and like caps finished. Daily target: {target} views.")

        if not reel:
            await asyncio.sleep(300)
            continue

        if mode in ("HINDER_RUN", "HINDER_ACTIVATED"):
            log(f"Views (Hinder Mode): Submitting {reel}. Remaining today: {remaining}/{target}")
        else:
            log(f"Views (Normal): Submitting {reel}. Remaining for this reel: {remaining}/{target}")

        success, wait_time, msg = await submit_link(url, reel)
        if success:
            state.record_view_success(reel)
            if mode in ("HINDER_RUN", "HINDER_ACTIVATED"):
                sleep_sec = max(1800, int(86400 / max(1, target)))
                log(f"Views order placed in Hinder Mode. Next spaced run in {sleep_sec // 60} minutes.")
            else:
                sleep_sec = config.VIEWS_INTERVAL
                log(f"Views order placed. Next attempt in {sleep_sec // 60} minutes.")
        elif wait_time:
            sleep_sec = wait_time
            log(f"Views cooldown active. Retrying in {sleep_sec} seconds ({sleep_sec // 60}m {sleep_sec % 60}s).")
        else:
            sleep_sec = 120
            log(f"Views encountered an issue ({msg}). Retrying in {sleep_sec} seconds.")
        await asyncio.sleep(sleep_sec)

async def likes_task():
    url = "https://zefame.com/en/free-instagram-likes"
    log(f"Likes task active: every {config.LIKES_INTERVAL // 60} minutes.")
    await asyncio.sleep(5)
    while True:
        try:
            importlib.reload(config)
        except Exception:
            pass

        reel, remaining, target = state.get_eligible_reel_for_likes()
        if not reel:
            log(f"Likes: All reels have completed like targets ({config.LIKE_CAP_RANGE[0]}-{config.LIKE_CAP_RANGE[1]}). Likes loop completed.")
            await asyncio.sleep(3600)
            continue

        log(f"Likes: Submitting {reel}. Remaining for this reel: {remaining}/{target}")
        success, wait_time, msg = await submit_link(url, reel)
        if success:
            state.record_like_success(reel)
            sleep_sec = config.LIKES_INTERVAL
            log(f"Likes order placed. Next attempt in {sleep_sec // 60} minutes.")
        elif wait_time:
            sleep_sec = wait_time
            log(f"Likes cooldown active. Retrying in {sleep_sec} seconds ({sleep_sec // 60}m {sleep_sec % 60}s).")
        else:
            sleep_sec = 180
            log(f"Likes encountered an issue ({msg}). Retrying in {sleep_sec} seconds.")
        await asyncio.sleep(sleep_sec)

async def followers_task():
    url = "https://zefame.com/en/free-instagram-followers"
    interval = config.FOLLOWERS_INTERVAL
    h = interval // 3600
    m = (interval % 3600) // 60
    log(f"Followers task active: every {h} hours {m} minutes.")
    await asyncio.sleep(10)
    while True:
        try:
            importlib.reload(config)
        except Exception:
            pass
        success, wait_time, msg = await submit_link(url, config.PROFILE_LINK)
        if success:
            sleep_sec = config.FOLLOWERS_INTERVAL
            log(f"Followers order placed. Next attempt in {h} hours {m} minutes.")
        elif wait_time:
            sleep_sec = wait_time
            qh = sleep_sec // 3600
            qm = (sleep_sec % 3600) // 60
            qs = sleep_sec % 60
            log(f"Followers cooldown active. Retrying in {qh}h {qm}m {qs}s.")
        else:
            sleep_sec = 300
            log(f"Followers encountered an issue ({msg}). Retrying in {sleep_sec} seconds.")
        await asyncio.sleep(sleep_sec)

MAX_RUNTIME_SECONDS = int(os.environ.get("MAX_RUNTIME_SECONDS", "0"))

def trigger_next_workflow():
    token = os.environ.get("GH_PAT")
    repo = os.environ.get("GITHUB_REPOSITORY", "iamnotaexit-stack/scheduled-insta")
    if not token:
        log("No GH_PAT found. Relying on scheduled cron heartbeat.")
        return
    try:
        import requests
        url = f"https://api.github.com/repos/{repo}/actions/workflows/zefame.yml/dispatches"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }
        res = requests.post(url, headers=headers, json={"ref": "main"}, timeout=15)
        if res.status_code in (200, 204):
            log("Successfully dispatched next GitHub Actions runner.")
        else:
            log(f"Workflow dispatch status {res.status_code}: {res.text}")
    except Exception as e:
        log(f"Workflow dispatch error: {e}")

async def watchdog_task():
    if MAX_RUNTIME_SECONDS <= 0:
        return
    log(f"Cloud runner watchdog active: running for {MAX_RUNTIME_SECONDS // 60} minutes.")
    await asyncio.sleep(MAX_RUNTIME_SECONDS)
    log("Max runtime reached for this cloud runner. Dispatching next workflow run...")
    trigger_next_workflow()
    os._exit(0)

async def main():
    enforce_single_instance()
    log("==================================================")
    log("Zefame Multi-Service Automation Started")
    log(f"Views: every {config.VIEWS_INTERVAL // 60} minutes (cap: {config.VIEW_CAP_RANGE[0]}-{config.VIEW_CAP_RANGE[1]} per reel)")
    log(f"Likes: every {config.LIKES_INTERVAL // 60} minutes (cap: {config.LIKE_CAP_RANGE[0]}-{config.LIKE_CAP_RANGE[1]} per reel)")
    log(f"Followers: every {config.FOLLOWERS_INTERVAL // 3600} hours {(config.FOLLOWERS_INTERVAL % 3600) // 60} minutes")
    log("--------------------------------------------------")
    for line in state.get_status_summary().splitlines():
        log(line)
    log("==================================================")
    await asyncio.gather(
        views_task(),
        likes_task(),
        followers_task(),
        watchdog_task()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log("Automation scheduler stopped by user.")
