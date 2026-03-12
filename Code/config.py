import os

# Base directory is the parent of this Code/ folder.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# -- File paths ---------------------------------------------------------------
INPUT_CSV             = os.path.join(BASE_DIR, "Input", "Crawling links.csv")
OUTPUT_CSV            = os.path.join(BASE_DIR, "App data", "app_data.csv")
SOURCE_FILES_DIR      = os.path.join(BASE_DIR, "Source_files")
LOGO_DIR              = os.path.join(BASE_DIR, "App data", "logos")
LOGS_FILE             = os.path.join(BASE_DIR, "Logs", "visited_links.csv")
MISSING_LINKS_CSV     = os.path.join(BASE_DIR, "Logs", "missing_links.csv")
VERIFICATION_LOG_FILE = os.path.join(BASE_DIR, "Logs", "human_verification_urls.csv")

# -- Chromium settings --------------------------------------------------------
# Update these to match your local Chromium installation.
CHROME_EXECUTABLE     = r"C:\Users\Shay\scoop\shims\chromium.exe"
CHROME_DEBUG_PORT     = 9222
CHROME_USER_DATA_DIR  = r"C:\Users\Shay\AppData\Local\Google\Chrome User Data"
CHROME_PROFILE        = "Profile 1"
CHROMIUM_COOKIES_PATH = r"C:\Users\Shay\AppData\Local\Chromium\User Data\Default\Network\Cookies"

# -- Crawling settings --------------------------------------------------------
PAGE_LOAD_DELAY           = (1, 3)  # Random delay range (seconds)
MAX_RETRIES               = 3
MAX_VERIFICATION_ATTEMPTS = 1

# -- Modal IDs ----------------------------------------------------------------
PERMISSIONS_MODAL_ID = "apkPermissions"
LANGUAGES_MODAL_ID   = "languages"

# -- Tor configuration --------------------------------------------------------
# Update TOR_PATH to match your local Tor Expert Bundle installation.
TOR_PATH = r"C:\Users\Shay\Desktop\Tor Expert\tor\tor.exe"
TOR_DIR  = os.path.dirname(TOR_PATH)

TOR_INSTANCES = [
    {"port": 9050, "control_port": 9051, "torrc": "torrc"},
    {"port": 9052, "control_port": 9053, "torrc": "torrc2"},
    {"port": 9054, "control_port": 9055, "torrc": "torrc3"},
]

CONNECTIONS = [
    {"proxy": None, "type": "own IP"},
    {"proxy": {"http": "socks5h://127.0.0.1:9050", "https": "socks5h://127.0.0.1:9050"}, "type": "Tor (9050)"},
    {"proxy": {"http": "socks5h://127.0.0.1:9052", "https": "socks5h://127.0.0.1:9052"}, "type": "Tor (9052)"},
    {"proxy": {"http": "socks5h://127.0.0.1:9054", "https": "socks5h://127.0.0.1:9054"}, "type": "Tor (9054)"},
]
