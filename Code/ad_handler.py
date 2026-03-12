from selenium.common.exceptions import WebDriverException

_CLOSE_SELECTORS = [
    "button",
    '[role="button"]',
    ".close",
    ".dismiss",
    '[aria-label="Close"]',
    "[data-dismiss]",
    '[class*="close"]',
    '[class*="dismiss"]',
]

_DETECT_POPUP_SCRIPT = """
    for (const el of document.querySelectorAll('*')) {
        const s = window.getComputedStyle(el);
        const z = parseInt(s.zIndex, 10) || 0;
        if (
            s.position === 'fixed' &&
            z > 1000 &&
            el.offsetWidth  > window.innerWidth  / 2 &&
            el.offsetHeight > window.innerHeight / 2
        ) return el;
    }
    return null;
"""


def _find_close_button(driver, popup):
    """Return the first close-like element inside *popup*, or None."""
    script = """
        const popup = arguments[0];
        const selectors = arguments[1];
        for (const sel of selectors) {
            const el = popup.querySelector(sel);
            if (el) return el;
        }
        return null;
    """
    return driver.execute_script(script, popup, _CLOSE_SELECTORS)


def handle_fullscreen_ads(driver):
    """Detect and dismiss fullscreen ad overlays or popups."""
    try:
        popup = driver.execute_script(_DETECT_POPUP_SCRIPT)
        if not popup:
            return

        print("Popup detected. Attempting to close...")
        close_btn = _find_close_button(driver, popup)

        if close_btn:
            try:
                driver.execute_script("arguments[0].click();", close_btn)
                print("Popup closed via close button.")
            except Exception as e:
                print(f"Error clicking close button: {e}")
        else:
            try:
                driver.execute_script(
                    "arguments[0].parentNode.removeChild(arguments[0]);", popup
                )
                print("Popup removed from DOM.")
            except Exception as e:
                print(f"Could not remove popup programmatically: {e}")
                input("Please close the popup manually, then press Enter...")

    except WebDriverException as e:
        print(f"Error during popup handling: {e}")
