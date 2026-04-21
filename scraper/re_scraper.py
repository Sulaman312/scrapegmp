"""Re-scrape dynamic business data from Google Maps (hours, contact, location)"""
import logging
from dataclasses import asdict
from playwright.sync_api import sync_playwright
from scraper.place_extractor import extract_place

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def _apply_stealth(page):
    try:
        page.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            """
        )
    except Exception:
        pass


def re_scrape_business_data(google_maps_url: str, extract_emails: bool = True) -> dict:
    """
    Re-scrape only dynamic fields from Google Maps using exact same logic as original scraper.
    Returns dict with: phone, email, address, latitude, longitude, plus_code, hours
    """
    logging.info(f"🔄 Re-scraping dynamic data from: {google_maps_url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        page = browser.new_page(
            user_agent=DEFAULT_USER_AGENT,
            locale="en-US",
            timezone_id="Asia/Karachi",
        )
        page.set_viewport_size({"width": 1366, "height": 900})
        _apply_stealth(page)

        try:
            # Follow exact same flow as original scraper (scraper.py lines 603-626)
            page.goto(google_maps_url, timeout=60000)
            page.wait_for_timeout(5000)  # 5 seconds like original, not 4

            # Handle cookie consent (same as original - 4 selectors)
            for sel in [
                'button:has-text("Accept all")',
                'button:has-text("I agree")',
                '//button[contains(., "Accept")]',
                'form[action*="consent"] button',
            ]:
                try:
                    if page.locator(sel).count() > 0:
                        page.locator(sel).first.click()
                        page.wait_for_timeout(2000)
                        break
                except Exception:
                    continue

            # Wait for place panel to load (same as original)
            try:
                page.wait_for_selector('h1.DUwDvf', timeout=20000)
                logging.info("✅ Place panel loaded")
            except Exception:
                logging.warning("⚠ Place header not found; attempting to continue")

            page.wait_for_timeout(3000)

            # Scroll sidebar to ensure all elements are loaded
            try:
                page.evaluate('document.querySelector(\'div[role="main"]\')?.scrollTo(0, 0)')
                page.wait_for_timeout(2000)
            except:
                pass

            # Use the exact same extract_place function as original scraper
            place = extract_place(page, google_maps_url, browser, extract_emails)

            # Convert to dict and return only the fields we need
            data = {
                'phone': place.phone_number or '',
                'email': place.email or '',
                'address': place.address or '',
                'latitude': place.latitude or '',
                'longitude': place.longitude or '',
                'plus_code': place.plus_code or '',
                'hours': {
                    'monday': place.monday or 'Not available',
                    'tuesday': place.tuesday or 'Not available',
                    'wednesday': place.wednesday or 'Not available',
                    'thursday': place.thursday or 'Not available',
                    'friday': place.friday or 'Not available',
                    'saturday': place.saturday or 'Not available',
                    'sunday': place.sunday or 'Not available'
                }
            }

            logging.info(f"✅ Phone   : {data['phone']}")
            logging.info(f"✅ Email   : {data['email']}")
            logging.info(f"✅ Address : {data['address']}")
            days_found = sum(1 for v in data['hours'].values() if v and v != 'Not available')
            logging.info(f"✅ Hours   : {days_found}/7 days")

        except Exception as e:
            logging.error(f"❌ Re-scrape failed: {e}")
            raise
        finally:
            browser.close()

    return data
