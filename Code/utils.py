import csv
import os
import re
import time
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup
import pandas as pd
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

from ad_handler import handle_fullscreen_ads
from config import (
    LOGS_FILE,
    MAX_VERIFICATION_ATTEMPTS,
    MISSING_LINKS_CSV,
    OUTPUT_CSV,
    SOURCE_FILES_DIR,
    VERIFICATION_LOG_FILE,
)
from connect import connect_to_existing_browser, restart_browser, start_chromium
from tor_handler import renew_tor_ip


def ensure_directories_exist():
    """Create all required output directories if they do not already exist."""
    os.makedirs(SOURCE_FILES_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    os.makedirs(os.path.dirname(LOGS_FILE), exist_ok=True)
    os.makedirs(os.path.dirname(VERIFICATION_LOG_FILE), exist_ok=True)


def read_visited_links():
    """Return a set of URLs already recorded in the visited-links log."""
    if not os.path.exists(LOGS_FILE):
        return set()
    with open(LOGS_FILE, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header
        return {row[0].strip() for row in reader if row}


def save_visited_link(url):
    """Append *url* with a timestamp to the visited-links CSV log."""
    os.makedirs(os.path.dirname(LOGS_FILE), exist_ok=True)
    file_exists = os.path.isfile(LOGS_FILE)
    with open(LOGS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["URL", "Timestamp"])
        writer.writerow([url, time.strftime("%Y-%m-%d %H:%M:%S")])
    print(f"Saved visited URL: {url}")


def sanitize_filename(url, max_length=100):
    """Derive a safe filesystem name from *url*, capped at *max_length* chars."""
    url = unquote(url)
    path_parts = urlparse(url).path.strip("/").split("/")
    if len(path_parts) > 3:
        path_parts = path_parts[-3:]
    filename = "_".join(path_parts)
    filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
    return filename[:max_length]


def save_webpage_source(driver, save_dir):
    """Save the current page's HTML source to *save_dir* for debugging."""
    os.makedirs(save_dir, exist_ok=True)
    handle_fullscreen_ads(driver)
    filename = sanitize_filename(driver.current_url) + "_source.html"
    file_path = os.path.join(save_dir, filename)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    print(f"Webpage source saved: {file_path}")


def human_like_scroll(driver, target_percent=10):
    """Gradually scroll the page to *target_percent* of its total height."""
    scroll_height = driver.execute_script("return document.body.scrollHeight")
    target_position = (target_percent / 100) * scroll_height
    current_position = 0
    step = 20
    while current_position < target_position:
        driver.execute_script(f"window.scrollTo(0, {current_position});")
        current_position += step
        time.sleep(0.01)
    print(f"Scrolled to {target_percent}% of the page.")


def _save_verification_url(url):
    """Record *url* in the human-verification log."""
    file_exists = os.path.isfile(VERIFICATION_LOG_FILE)
    with open(VERIFICATION_LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["URL", "Timestamp"])
        writer.writerow([url, time.strftime("%Y-%m-%d %H:%M:%S")])
    print(f"Saved verification URL: {url}")


def handle_human_verification(driver, current_url):
    """Detect Cloudflare challenges and restart the browser if needed.

    Returns a (possibly new) driver on success, or None if unrecoverable.
    """
    title = driver.title.lower()
    source = driver.page_source.lower()
    if "just a moment" not in title and "verify you are human" not in source:
        return driver

    print(f"Human verification detected at: {current_url}")
    _save_verification_url(current_url)

    print("Waiting 5 seconds for auto-resolution...")
    time.sleep(5)

    title = driver.title.lower()
    source = driver.page_source.lower()
    if "just a moment" not in title and "verify you are human" not in source:
        print("Verification resolved automatically.")
        return driver

    print("Closing browser due to persistent verification...")
    driver.quit()

    if not restart_browser():
        print("Browser restart failed.")
        return None

    new_driver = connect_to_existing_browser()
    if not new_driver:
        print("Failed to reconnect to browser.")
        return None

    for attempt in range(1, 4):
        try:
            new_driver.get(current_url)
            print(f"Resumed at: {current_url}")
            return new_driver
        except Exception as e:
            print(f"Failed to reload {current_url} (attempt {attempt}/3): {e}")
            time.sleep(2)

    print("Unable to reload page. Skipping.")
    return None


def handle_verification_and_rotate(driver, app_link, connection, visited_links):
    """Run verification handling and rotate the Tor proxy if verification persists.

    Returns the (possibly new) driver, or None if the link should be skipped.
    """
    for attempt in range(MAX_VERIFICATION_ATTEMPTS):
        new_driver = handle_human_verification(driver, app_link)
        if new_driver:
            return new_driver

        print(f"Attempt {attempt + 1}/{MAX_VERIFICATION_ATTEMPTS} – rotating proxy...")
        if "control_port" in connection:
            renew_tor_ip(connection["control_port"])
        else:
            print("Skipping Tor IP renewal – no control_port for this connection.")

        driver.quit()
        start_chromium()
        driver = connect_to_existing_browser()
        if not driver:
            print("Failed to reconnect. Skipping this link.")
            save_visited_link(app_link)
            visited_links.add(app_link)
            return None

    return driver


def check_for_dmca_removal(driver, app_link):
    """Return True and log *app_link* if the page shows a DMCA takedown notice."""
    if driver is None:
        return False

    soup = BeautifulSoup(driver.page_source, "html.parser")
    dmca_paragraph = soup.find("p", string=lambda t: t and "because of a DMCA" in t)
    if not dmca_paragraph:
        return False

    print(f"DMCA takedown detected for {app_link}.")
    os.makedirs(os.path.dirname(MISSING_LINKS_CSV), exist_ok=True)
    file_exists = os.path.exists(MISSING_LINKS_CSV)
    with open(MISSING_LINKS_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["app_link"])
        writer.writerow([app_link])
    return True


def log_missing_apk_link(driver, app_link, logs_folder="Logs"):
    """Return True and log *app_link* if the current page is a 404 error page."""
    if driver is None:
        return False

    soup = BeautifulSoup(driver.page_source, "html.parser")
    error_div = soup.find("div", class_="errorLeft table-cell")
    if not (error_div and error_div.find("h1", string="404")):
        return False

    os.makedirs(logs_folder, exist_ok=True)
    log_file = os.path.join(logs_folder, "missing_apk_links.csv")
    with open(log_file, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([app_link])
    print(f"Logged missing APK link: {app_link}")
    return True


def clean_app_data():
    """Remove rows with unknown titles or permissions from the output CSV,
    and un-mark their URLs in the visited-links log.
    """
    df = pd.read_csv(OUTPUT_CSV)
    unknown_mask = (df["full_title"] == "Unknown") | (df["permissions"] == "Unknown")
    unknown_rows = df[unknown_mask]

    if not unknown_rows.empty:
        urls_to_remove = set(unknown_rows[["app_link", "current_link"]].values.flatten())
        try:
            with open(LOGS_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
            kept = [l for l in lines if l.split(",")[0].strip() not in urls_to_remove]
            with open(LOGS_FILE, "w", encoding="utf-8") as f:
                f.writelines(kept)
            print(f"Removed {len(lines) - len(kept)} entries from visited log.")
        except FileNotFoundError:
            print("Visited log not found; skipping URL removal.")
        except Exception as e:
            print(f"Error processing visited log: {e}")

    df_cleaned = df[~unknown_mask]
    df_cleaned.to_csv(OUTPUT_CSV, index=False)
    print(f"Cleaned data saved. Removed {len(unknown_rows)} rows.")
    return df_cleaned
