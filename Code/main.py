import csv
import os
import sys
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from apk_parser import parse_current_page_and_save_to_csv
from config import CONNECTIONS, INPUT_CSV, MAX_VERIFICATION_ATTEMPTS
from connect import (
    check_internet_connection,
    connect_to_existing_browser,
    kill_processes_by_name,
    start_chromium,
)
from ad_handler import handle_fullscreen_ads
from tor_handler import renew_tor_ip, start_tor_instances, stop_tor
from utils import (
    check_for_dmca_removal,
    clean_app_data,
    ensure_directories_exist,
    handle_verification_and_rotate,
    log_missing_apk_link,
    read_visited_links,
    save_visited_link,
)
from connect import find_and_navigate_to_apk


def _parse_start_percentage(args):
    """Return the start percentage from CLI args, or exit on invalid input."""
    if len(args) < 2:
        return 0
    try:
        value = int(args[1])
        if not 0 <= value <= 100:
            raise ValueError
        return value
    except ValueError:
        print("Invalid percentage. Provide an integer between 0 and 100.")
        stop_tor()
        sys.exit(1)


def main():
    """Orchestrate the APKMirror crawling loop."""
    tor_index = 0

    ensure_directories_exist()
    visited_links = read_visited_links()

    start_tor_instances()
    start_chromium()
    check_internet_connection()

    driver = connect_to_existing_browser()
    if not driver:
        print("Failed to connect to browser. Exiting.")
        stop_tor()
        return

    if not os.path.exists(INPUT_CSV):
        print(f"Input file not found: {INPUT_CSV}")
        stop_tor()
        return

    clean_app_data()

    start_percentage = _parse_start_percentage(sys.argv)

    with open(INPUT_CSV, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    total = len(rows)
    start_line = int((start_percentage / 100) * total)
    print(f"Starting from row {start_line + 1} ({start_percentage}% of {total} rows).")

    for row in rows[start_line:]:
        app_link = row["app_link"].strip()

        if app_link in visited_links:
            print(f"Skipping {app_link} – already processed.")
            continue

        tor_index = (tor_index + 1) % len(CONNECTIONS)
        connection = CONNECTIONS[tor_index]
        print(f"Using connection: {connection['type']}")
        print(f"Navigating to: {app_link}")

        driver.set_page_load_timeout(180)
        driver.get(app_link)

        driver = handle_verification_and_rotate(driver, app_link, connection, visited_links)
        if not driver:
            driver = connect_to_existing_browser()
            continue

        time.sleep(0.5)
        check_internet_connection()

        if log_missing_apk_link(driver, app_link) or check_for_dmca_removal(driver, app_link):
            save_visited_link(app_link)
            visited_links.add(app_link)
            continue

        handle_fullscreen_ads(driver)
        check_internet_connection()

        driver = handle_verification_and_rotate(driver, app_link, connection, visited_links)
        if not driver:
            driver = connect_to_existing_browser()
            continue

        apk_link = find_and_navigate_to_apk(driver)
        time.sleep(0.5)

        if log_missing_apk_link(driver, app_link) or check_for_dmca_removal(driver, app_link):
            save_visited_link(app_link)
            visited_links.add(app_link)
            continue

        driver = handle_verification_and_rotate(driver, app_link, connection, visited_links)
        if not driver:
            driver = connect_to_existing_browser()
            continue

        parse_current_page_and_save_to_csv(driver, app_link)
        check_internet_connection()

        driver = handle_verification_and_rotate(driver, app_link, connection, visited_links)
        if not driver:
            driver = connect_to_existing_browser()
            continue

        save_visited_link(app_link)
        visited_links.add(app_link)
        if apk_link is not None:
            save_visited_link(apk_link)
            visited_links.add(apk_link)

        check_internet_connection()

    driver.quit()
    stop_tor()
    print("Crawling completed.")


if __name__ == "__main__":
    while True:
        try:
            main()
            break
        except Exception as e:
            print(f"Error: {e}")
            for proc in ("chromium", "chrome", "chromedriver"):
                kill_processes_by_name(proc)
            time.sleep(5)
