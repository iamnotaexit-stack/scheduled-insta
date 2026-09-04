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

DRIVER_PATH = os.path.join(os.environ.get('APPDATA', ''), 'undetected_chromedriver', 'undetected_chromedriver.exe')

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from config import REEL_LINKS, PROFILE_LINK, get_random_reel

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

def submit_link(url, link):
    target_link = clean_url(link)
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Submitting to: {url}", flush=True)
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Target link: {target_link}", flush=True)

    options = uc.ChromeOptions()
    options.headless = False
    options.add_argument("--disable-notifications")
    options.add_argument("--mute-audio")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-renderer-backgrounding")

    driver_kwargs = {"options": options}
    if os.path.exists(DRIVER_PATH):
        driver_kwargs["driver_executable_path"] = DRIVER_PATH

    driver = None
    try:
        driver = SafeChrome(**driver_kwargs)
        driver.get(url)

        time.sleep(1)
        if "502 Bad Gateway" in driver.title or "Error 502" in driver.title or "502 Bad Gateway" in driver.page_source:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Notice: Zefame returned 502 Bad Gateway. Server is temporarily unreachable.", flush=True)
            return False, 120, "Server 502 Bad Gateway"

        wait = WebDriverWait(driver, 20)
        input_elem = wait.until(EC.presence_of_element_located((By.ID, "instagram-link")))
        input_elem.clear()
        input_elem.send_keys(target_link)

        submit_btn = driver.find_element(By.ID, "submit-btn")
        submit_btn.click()
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Form submitted. Awaiting timer and verification...", flush=True)

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
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Notice from Zefame: {err_msg}", flush=True)
                wait_time = parse_wait_time(err_msg)
                return False, wait_time, err_msg
            if succ_visible:
                succ_msg = driver.find_element(By.ID, "success-page").text.replace("\n", " ").strip()
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] SUCCESS: {succ_msg}", flush=True)
                return True, None, succ_msg

        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Verification timed out.", flush=True)
        return False, None, "Timed out"
    except Exception as e:
        first_line = str(e).strip().split('\n')[0]
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Error during submission: {first_line}", flush=True)
        return False, None, first_line
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

if __name__ == "__main__":
    if sys.platform == "win32":
        import ctypes
        MUTEX_NAME = "Global\\ZefameInstagramAutomationSingleInstance"
        h_mutex = ctypes.windll.kernel32.CreateMutexW(None, False, MUTEX_NAME)
        if ctypes.windll.kernel32.GetLastError() == 183:
            if h_mutex:
                ctypes.windll.kernel32.CloseHandle(h_mutex)
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Zefame automation daemon is actively running. Skipping single run to prevent collisions.", flush=True)
            sys.exit(0)

    task_type = sys.argv[1] if len(sys.argv) > 1 else "views"
    if task_type == "views":
        submit_link("https://zefame.com/en/free-instagram-views", get_random_reel())
    elif task_type == "likes":
        submit_link("https://zefame.com/en/free-instagram-likes", get_random_reel())
    elif task_type == "followers":
        submit_link("https://zefame.com/en/free-instagram-followers", PROFILE_LINK)
