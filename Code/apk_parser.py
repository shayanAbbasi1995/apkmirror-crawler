import base64
import csv
import os
import re
import time
from urllib.parse import parse_qs, unquote, urljoin, urlparse

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from unidecode import unidecode

from ad_handler import handle_fullscreen_ads
from config import LOGO_DIR, OUTPUT_CSV, SOURCE_FILES_DIR
from utils import human_like_scroll, save_webpage_source


def sanitize_text(text):
    """Normalize *text* to ASCII-safe characters, removing filename-forbidden chars."""
    text = unquote(text)
    text = unidecode(text)
    text = re.sub(r'[<>:"/\\|?*]', "_", text)
    return text.strip()


def _ensure_directories():
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    os.makedirs(LOGO_DIR, exist_ok=True)


def _get_soup(driver):
    """Return a BeautifulSoup for the current page after dismissing any ads."""
    handle_fullscreen_ads(driver)
    return BeautifulSoup(driver.page_source, "html.parser")


def extract_basic_info(soup):
    """Return (full_title, developer) from the page, sanitized."""
    title_tag = soup.find("h1", class_="app-title")
    dev_tag = soup.find("h3", class_="dev-title")
    full_title = title_tag.text.strip() if title_tag else "Unknown"
    developer = dev_tag.text.replace("By ", "").strip() if dev_tag else "Unknown"
    return sanitize_text(full_title), sanitize_text(developer)


def extract_breadcrumbs(soup):
    """Return app name, version, and variant from the breadcrumb navigation."""
    breadcrumbs = soup.find("div", id="breadcrumbs")
    links = breadcrumbs.find_all("a") if breadcrumbs else []
    return {
        "app_name":    links[1].text.strip() if len(links) > 1 else "Unknown",
        "app_version": links[2].text.strip() if len(links) > 2 else "Unknown",
        "app_variant": links[3].text.strip() if len(links) > 3 else "Unknown",
    }


def extract_category(soup):
    """Return the app category string."""
    tag = soup.find("a", class_="play-category")
    return tag.text.strip() if tag else "Unknown"


def extract_details(soup):
    """Return a dict of APK technical details (version, package, size, OS)."""
    defaults = {
        "app_version_check": "Unknown",
        "package_name":       "Unknown",
        "apk_size":           "Unknown",
        "apk_size_bytes":     "Unknown",
        "minimum_required_os": "Unknown",
        "target_os":          "Unknown",
    }
    details = soup.find("div", class_="apk-detail-table")
    if not details:
        return defaults

    result = dict(defaults)
    for row in details.find_all("div", class_="appspec-row"):
        text = row.get_text(separator=" ").strip()
        if "Version:" in text:
            result["app_version_check"] = text.split("Version:")[-1].split("(")[0].strip()
        if "Package:" in text:
            result["package_name"] = text.split("Package:")[-1].strip()
        if "Min: Android" in text:
            result["minimum_required_os"] = text.split("Min: Android")[-1].strip()
        if "Target: Android" in text:
            result["target_os"] = text.split("Target: Android")[-1].strip()
        if "MB" in text and "bytes" in text:
            result["apk_size"] = text.split(" (")[0].strip() if " (" in text else text.strip()
            result["apk_size_bytes"] = (
                text.split("(")[-1].replace(" bytes)", "").replace(",", "").strip()
                if " (" in text else "Unknown"
            )
    return result


def extract_upload_date(soup):
    """Return the upload date string from the page."""
    tag = soup.find("span", class_="datetime_utc")
    return tag.text.strip() if tag else "Unknown"


def extract_whats_new(soup):
    """Return the What's New header and body text."""
    for div in soup.find_all("div", {"role": "tabpanel", "class": "tab-pane"}):
        if div.find("a", {"name": "whatsnew"}):
            header = div.find("h3").get_text(strip=True) if div.find("h3") else "Unknown"
            body = "\n".join(p.get_text(strip=True) for p in div.find_all("p"))
            return {"whats_new_header": header, "whats_new_text": body}
    return {"whats_new_header": "Unknown", "whats_new_text": "Unknown"}


def extract_about(soup):
    """Return the About / description header and body text."""
    for div in soup.find_all("div", {"role": "tabpanel", "class": "tab-pane"}):
        if div.find("a", {"name": "description"}):
            header = div.find("h3").get_text(strip=True) if div.find("h3") else "Unknown"
            body = "\n".join(p.get_text(strip=True) for p in div.find_all("p"))
            return {"about_header": header, "about_text": body}
    return {"about_header": "Unknown", "about_text": "Unknown"}


def extract_links(soup):
    """Return (download_link, google_play_link) for the current APK page."""
    dl_tag = soup.find("a", class_="downloadButton")
    download_link = (
        urljoin("https://www.apkmirror.com", dl_tag["href"]) if dl_tag else "No download link found."
    )
    gp_tag = soup.find("a", class_="tab-button", href=True)
    google_play_link = gp_tag["href"] if gp_tag else "No Play Store link."
    return download_link, google_play_link


def extract_logo(driver, full_title):
    """Download the app logo and save it as a PNG. Returns the saved path."""
    try:
        logo_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "primaryimage"))
        )
        raw_url = logo_element.get_attribute("src")
        query_params = parse_qs(urlparse(raw_url).query)
        if "src" not in query_params:
            return "No valid logo URL found"

        logo_url = unquote(query_params["src"][0])
        handle_fullscreen_ads(driver)
        driver.get(logo_url)

        logo_path = os.path.join(LOGO_DIR, f"{full_title}.png")
        with open(logo_path, "wb") as img_file:
            img_file.write(base64.b64decode(driver.get_screenshot_as_base64()))
        return logo_path

    except Exception as e:
        print(f"Error extracting logo: {e}")
        return "Download failed"


def extract_permissions(driver):
    """Click the permissions modal and return a list of permission strings."""
    try:
        handle_fullscreen_ads(driver)
        btn = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a[href='#apkPermissions']"))
        )
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
        driver.execute_script("arguments[0].click();", btn)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "apkPermissions"))
        )

        soup = BeautifulSoup(driver.page_source, "html.parser")
        modal = soup.find("div", id="apkPermissions") or soup.find("div", class_="modal-body")
        if modal:
            permissions = [
                line.strip()
                for line in modal.get_text(separator="\n").split("\n")
                if line.strip() and line.strip() not in ("Permissions", "Features", "Libraries")
            ]
        else:
            permissions = ["Unknown"]

        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        return permissions

    except Exception as e:
        print(f"Error extracting permissions: {e}")
        return ["Unknown"]


def extract_languages(driver):
    """Click the languages modal and return a list of language strings."""
    try:
        handle_fullscreen_ads(driver)
        btn = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a[href='#languages']"))
        )
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
        driver.execute_script("arguments[0].click();", btn)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "languages"))
        )

        soup = BeautifulSoup(driver.page_source, "html.parser")
        modal = soup.find("div", id="languages") or soup.find("div", class_="modal-body")
        if modal:
            text = modal.get_text(separator="\n")
            languages = [
                lang.strip()
                for lang in text.split("\n")
                if lang.strip() and lang.strip() != "Languages"
            ]
        else:
            languages = ["Unknown"]

        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        return languages

    except Exception as e:
        print(f"Error extracting languages: {e}")
        return ["Unknown"]


def parse_current_page_and_save_to_csv(driver, app_link):
    """Extract all APK metadata from the current page and append it to the output CSV."""
    handle_fullscreen_ads(driver)
    _ensure_directories()

    soup = BeautifulSoup(driver.page_source, "html.parser")
    full_title, developer = extract_basic_info(soup)
    if not full_title or not developer:
        return

    save_webpage_source(driver, SOURCE_FILES_DIR)
    current_link = driver.current_url
    download_link, google_play_link = extract_links(soup)

    app_data = {
        "full_title":   full_title,
        "developer":    developer,
        **extract_breadcrumbs(soup),
        "app_category": extract_category(soup),
        **extract_details(soup),
        "upload_date":  extract_upload_date(soup),
        **extract_whats_new(soup),
        **extract_about(soup),
        "download_link":    download_link,
        "google_play_link": google_play_link,
        "current_link":     current_link,
        "permissions":      extract_permissions(driver),
        "languages":        extract_languages(driver),
        "logo_path":        extract_logo(driver, full_title),
        "app_link":         app_link,
    }
    _save_to_csv(app_data)


def _save_to_csv(data):
    """Append *data* to the output CSV, sanitizing all non-URL values."""
    file_exists = os.path.isfile(OUTPUT_CSV)
    with open(OUTPUT_CSV, "a", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(data.keys()))
        if not file_exists:
            writer.writeheader()
        sanitized = {
            k: str(v) if ("link" in k or "url" in k) else sanitize_text(str(v))
            for k, v in data.items()
        }
        writer.writerow(sanitized)
    print(f"Data saved to {OUTPUT_CSV}")
