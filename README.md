# APKMirror Crawler

A Selenium-based web crawler that collects APK metadata from [APKMirror](https://www.apkmirror.com), with automatic Cloudflare challenge handling and Tor-based session rotation.

## What it does

- Navigates a list of app URLs from a CSV input file
- Extracts structured metadata per APK: title, developer, category, version, package name, size, OS requirements, permissions, supported languages, upload date, What's New, and description
- Downloads app logos
- Handles fullscreen ad overlays, human-verification (Cloudflare) pages, DMCA takedowns, and 404s
- Saves all collected data to a CSV, with a separate log of visited links to support resumable crawling

## Structure

```
Code/
├── main.py               # Entry point — orchestrates the crawl loop
├── config.py             # All file paths, browser settings, and crawl parameters
├── connect.py            # Browser management (launch, attach, restart, APK navigation)
├── apk_parser.py         # Metadata extraction from APK detail pages
├── ad_handler.py         # Fullscreen popup / ad detection and dismissal
├── cookie_maker.py       # Load Chromium cookies into Selenium sessions
└── utils.py              # Logging, verification handling, file utilities
```

## Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Update `Code/config.py` with your Chromium path and profile directory
3. Prepare `Input/Crawling links.csv` with an `app_link` column

## Usage

```bash
# Start from the beginning
python Code/main.py

# Resume from 50% through the input list
python Code/main.py 50
```
