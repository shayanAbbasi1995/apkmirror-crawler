import os
import sqlite3
from datetime import datetime, timedelta

from config import CHROMIUM_COOKIES_PATH

# Chromium timestamps are microseconds since 1601-01-01.
_CHROMIUM_EPOCH = datetime(1601, 1, 1)


def get_chromium_cookies(domain):
    """Return cookies for *domain* extracted from the Chromium SQLite database."""
    if not os.path.exists(CHROMIUM_COOKIES_PATH):
        print("Cookies file not found.")
        return []

    conn = sqlite3.connect(CHROMIUM_COOKIES_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT host_key, name, value, path, expires_utc, is_secure, is_httponly
            FROM cookies
            WHERE host_key LIKE ?
            """,
            ("%" + domain + "%",),
        )
        cookies = []
        for host, name, value, path, expires, secure, httponly in cursor.fetchall():
            expiry = None
            if expires:
                expiry = int(
                    (_CHROMIUM_EPOCH + timedelta(microseconds=expires)).timestamp()
                )
            cookies.append({
                "name": name,
                "value": value,
                "domain": host,
                "path": path,
                "secure": bool(secure),
                "httpOnly": bool(httponly),
                "expiry": expiry,
            })
        return cookies
    finally:
        conn.close()


def load_cookies_into_selenium(driver, domain):
    """Inject Chromium cookies for *domain* into a Selenium WebDriver session."""
    cookies = get_chromium_cookies(domain)
    if not cookies:
        print(f"No saved cookies found for {domain}")
        return

    driver.get(f"https://{domain}")
    for cookie in cookies:
        try:
            driver.add_cookie(cookie)
        except Exception as e:
            print(f"Could not add cookie {cookie['name']}: {e}")

    driver.refresh()
    print(f"Cookies for {domain} loaded into Selenium.")
