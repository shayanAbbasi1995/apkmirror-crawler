import socket
import subprocess
import time

import chromedriver_py
import psutil
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from urllib.parse import urljoin

from ad_handler import handle_fullscreen_ads
from config import (
    CHROME_DEBUG_PORT,
    CHROME_EXECUTABLE,
    CHROME_PROFILE,
    CHROME_USER_DATA_DIR,
)
from cookie_maker import load_cookies_into_selenium


_APK_LINK_SELECTORS = [
    "div.table-cell.rowheight.addseparator.expand.pad.dowrap "
    "a.accent_color[href^='/apk/'][data-google-interstitial='false']",

    "div.table-row.headerFont div.table-cell.rowheight.addseparator.expand.pad.dowrap "
    "a.accent_color[href^='/apk/'][data-google-interstitial='false']",

    "div.table-cell.rowheight.addseparator.expand.pad.dowrap-break-all "
    "a.accent_color[href^='/apk/'][data-google-interstitial='false']",

    "div.variants-table div.table-row div.table-cell "
    "a.accent_color[href^='/apk/'][data-google-interstitial='false']",

    "div.variants-table a.accent_color[href^='/apk/'][data-google-interstitial='false']",

    "ul.download-list li a.accent_color[href^='/apk/'][data-google-interstitial='false']",

    "div.table-cell.rowheight.addseparator.expand.pad.dowrap a.accent_color[href^='/apk/']",

    "div.table-row.headerFont div.table-cell.rowheight.addseparator.expand.pad.dowrap "
    "a.accent_color[href^='/apk/']",

    "div.tab-pane.noPadding div.table-cell "
    "a.accent_color[href^='/apk/'][data-google-interstitial='false']",
]


def check_internet_connection(retries=2, delay=5):
    """Return True if the internet is reachable, retrying up to *retries* times."""
    for attempt in range(1, retries + 1):
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=5)
            print("Internet connection OK.")
            return True
        except (socket.timeout, socket.error):
            print(f"No internet (attempt {attempt}/{retries}). Retrying in {delay}s...")
            time.sleep(delay)
    print("No internet connection after multiple attempts.")
    return False


def start_chromium():
    """Launch Chromium with remote debugging enabled."""
    subprocess.Popen([
        CHROME_EXECUTABLE,
        f"--remote-debugging-port={CHROME_DEBUG_PORT}",
        f"--user-data-dir={CHROME_USER_DATA_DIR}",
        f"--profile-directory={CHROME_PROFILE}",
    ])
    time.sleep(0.5)


def _wait_for_chrome_debugger(port=CHROME_DEBUG_PORT, timeout=5):
    """Block until Chrome's remote debugging port accepts connections."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("localhost", port), timeout=2):
                print("Chrome debugger is ready.")
                return True
        except (ConnectionRefusedError, socket.timeout):
            time.sleep(0.5)
    print("Chrome debugger failed to start.")
    return False


def connect_to_existing_browser(retries=5, wait_time=3):
    """Attach to a running Chrome debug session, retrying up to *retries* times."""
    chromedriver_path = chromedriver_py.binary_path
    for attempt in range(1, retries + 1):
        print(f"Connecting to Chrome (attempt {attempt}/{retries})...")
        try:
            options = webdriver.ChromeOptions()
            options.debugger_address = f"localhost:{CHROME_DEBUG_PORT}"
            driver = webdriver.Chrome(
                service=Service(executable_path=chromedriver_path),
                options=options,
            )
            print(f"Connected. Page title: {driver.title}")
            load_cookies_into_selenium(driver, "apkmirror.com")
            return driver
        except Exception as e:
            print(f"Failed to connect: {e}")
            time.sleep(wait_time)

    print("Unable to connect to Chrome after multiple attempts.")
    return None


def kill_processes_by_name(process_name):
    """Kill every running process whose name contains *process_name*."""
    for proc in psutil.process_iter(attrs=["pid", "name"]):
        try:
            if process_name.lower() in proc.info["name"].lower():
                print(f"Killing {proc.info['name']} (PID {proc.info['pid']})")
                proc.kill()
        except Exception as e:
            print(f"Error killing {process_name}: {e}")


def restart_browser():
    """Kill stale browser processes, relaunch Chromium, and confirm it is ready."""
    print("Restarting browser...")
    for name in ("chromium", "chrome", "chromedriver"):
        kill_processes_by_name(name)

    start_chromium()
    if not _wait_for_chrome_debugger():
        print("Chrome debugger failed to start.")
        return None

    print("Browser restarted successfully.")
    return True


def find_and_navigate_to_apk(driver):
    """Find the first APK download link on the current page and navigate to it.

    Returns the APK URL on success, or None if no link is found.
    """
    if driver is None:
        print("Driver is None; cannot navigate to APK.")
        return None

    try:
        handle_fullscreen_ads(driver)

        apk_element = None
        for selector in _APK_LINK_SELECTORS:
            try:
                apk_element = driver.find_element(By.CSS_SELECTOR, selector)
                if apk_element:
                    break
            except Exception:
                continue

        if apk_element is None:
            print("APK download link not found on this page.")
            return None

        apk_url = urljoin(
            "https://www.apkmirror.com",
            apk_element.get_attribute("href"),
        )
        print(f"APK download URL: {apk_url}")

        driver.set_page_load_timeout(10)
        try:
            driver.get(apk_url)
        except TimeoutException:
            print(f"Timeout loading {apk_url}; stopping and retrying...")
            driver.execute_script("window.stop();")
            time.sleep(3)
            driver.get(apk_url)

        return apk_url

    except Exception as e:
        print(f"Error navigating to APK download page: {e}")
        return None
