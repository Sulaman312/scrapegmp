import json
import logging
import os
import platform
import shutil
import tempfile
import time
import traceback
from dataclasses import asdict
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright

from scraper.media_downloader import collect_and_download_images, collect_videos
from scraper.models import Place
from scraper.place_extractor import extract_place
from scraper.review_extractor import extract_all_reviews
from scraper.storage import load_existing_places, save_place_to_csv
from scraper.tab_extractors import (
    click_tab,
    extract_about_tab,
    extract_popular_times,
    extract_qa,
    extract_related_places,
    extract_review_keywords,
    extract_updates,
    extract_web_results,
)
from scraper.utils import sanitize_filename


def check_end_of_list(page) -> bool:
    """Check if we've reached the end of the list."""
    end_message_patterns = [
        "you've reached the end of the list",
        "you have reached the end of the list",
        "reached the end of the list",
        "no more results",
        "that's all the results"
    ]

    try:
        page_text = page.locator('body').inner_text().lower()
        for pattern in end_message_patterns:
            if pattern in page_text:
                logging.info(f"🏁 Detected end-of-list message: '{pattern}'")
                return True
    except Exception as e:
        logging.warning(f"⚠ Error checking for end of list: {e}")

    return False


def scrape_places_until_end(search_for: str, output_path: str, max_results: int = 10000, extract_emails: bool = True) -> int:
    """
    Scrape places until 'You've reached the end of the list' message appears.
    Returns the number of places successfully scraped.
    """
    extracted_identifiers = load_existing_places(output_path)
    places_scraped = 0

    with sync_playwright() as p:
        logging.info(f"🖥 Platform: {platform.system()}")

        # Run headless in production (non-Windows), with GUI on Windows for debugging
        is_headless = platform.system() != "Windows"

        if platform.system() == "Windows":
            browser_path = r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
            logging.info(f"🌐 Launching Chrome from: {browser_path} (headless={is_headless})")
            browser = p.chromium.launch(executable_path=browser_path, headless=is_headless)
        else:
            logging.info(f"🌐 Launching Chromium (headless={is_headless})")
            browser = p.chromium.launch(headless=is_headless, args=['--no-sandbox', '--disable-setuid-sandbox'])

        logging.info("✅ Browser launched successfully")
        page = browser.new_page()
        logging.info("✅ New page created")

        try:
            logging.info("🌐 Opening Google Maps...")
            page.goto("https://www.google.com/maps", timeout=60000)
            page.wait_for_timeout(5000)

            logging.info("🍪 Checking for cookie consent...")
            try:
                cookie_selectors = [
                    'button:has-text("Accept all")',
                    'button:has-text("I agree")',
                    'button:has-text("Reject all")',
                    '//button[contains(., "Accept")]',
                    '//button[contains(@aria-label, "Accept")]',
                    'form[action*="consent"] button'
                ]
                for selector in cookie_selectors:
                    try:
                        if page.locator(selector).count() > 0:
                            page.locator(selector).first.click()
                            logging.info("✅ Clicked cookie consent button")
                            page.wait_for_timeout(2000)
                            break
                    except Exception:
                        continue
            except Exception as e:
                logging.info(f"ℹ Cookie consent handling: {e}")

            page.wait_for_timeout(2000)

            logging.info(f"🔍 Looking for search box...")
            search_box = None
            search_selectors = [
                'input#searchboxinput',
                'input[aria-label*="Search"]',
                'input[placeholder*="Search"]',
                'input[name="q"]',
                '//input[@id="searchboxinput"]',
                '//input[@aria-label="Search Google Maps"]'
            ]
            for selector in search_selectors:
                try:
                    if page.locator(selector).count() > 0:
                        search_box = page.locator(selector).first
                        logging.info(f"✅ Found search box with selector: {selector}")
                        break
                except Exception:
                    continue

            if not search_box:
                logging.error("❌ Could not find search box! Taking screenshot for debugging...")
                page.screenshot(path="debug_screenshot.png")
                raise Exception("Search box not found on Google Maps")

            logging.info(f"🔍 Searching for: {search_for}")
            search_box.click()
            page.wait_for_timeout(500)
            search_box.fill(search_for)
            page.wait_for_timeout(500)
            page.keyboard.press("Enter")
            page.wait_for_timeout(3000)

            logging.info("⏳ Waiting for search results to load...")
            results_loaded = False
            for attempt in range(3):
                try:
                    page.wait_for_selector('//a[contains(@href, "https://www.google.com/maps/place")]', timeout=20000)
                    results_loaded = True
                    logging.info("✅ Search results loaded successfully")
                    break
                except Exception:
                    logging.warning(f"⚠ Results not loaded yet, attempt {attempt + 1}/3")
                    if attempt < 2:
                        page.wait_for_timeout(3000)

            if not results_loaded:
                logging.error("❌ Could not load search results after 3 attempts")
                page.screenshot(path="search_failed.png")
                raise Exception("Search results did not load")

            page.wait_for_timeout(2000)
            logging.info("🚀 Starting extract-as-you-scroll process...")

            scrollable_element = page.locator('//div[@role="feed"]')

            logging.info("⚡ Pre-loading listings with initial scrolls...")
            initial_count = page.locator('//a[contains(@href, "https://www.google.com/maps/place")]').count()
            logging.info(f"📊 Initial listings visible: {initial_count}")

            for pre_scroll in range(5):
                try:
                    scrollable_element.evaluate("element => element.scrollBy(0, 3000)")
                except Exception:
                    page.mouse.wheel(0, 3000)
                page.wait_for_timeout(1500)
                after_scroll = page.locator('//a[contains(@href, "https://www.google.com/maps/place")]').count()
                if after_scroll > initial_count:
                    logging.info(f"✅ Pre-scroll {pre_scroll + 1}: Loaded {after_scroll - initial_count} more listings (total: {after_scroll})")
                    initial_count = after_scroll
                else:
                    logging.info(f"⚠ Pre-scroll {pre_scroll + 1}: No new listings")

            logging.info(f"✅ Pre-loading complete! Total listings loaded: {initial_count}")

            last_processed_index = 0
            scroll_attempts = 0
            max_scroll_attempts = 500
            no_new_listings_count = 0
            consecutive_errors = 0
            max_consecutive_errors = 10
            end_of_list_reached = False

            while not end_of_list_reached and places_scraped < max_results and scroll_attempts < max_scroll_attempts:
                current_listings = page.locator('//a[contains(@href, "https://www.google.com/maps/place")]').count()
                logging.info(f"💓 Heartbeat: Scraped={places_scraped}, Listings={current_listings}, Scrolls={scroll_attempts}")

                if current_listings > last_processed_index:
                    listings_to_process = page.locator('//a[contains(@href, "https://www.google.com/maps/place")]').all()[last_processed_index:current_listings]
                    logging.info(f"📝 Processing {len(listings_to_process)} new listings (Total visible: {current_listings})")

                    for idx, listing in enumerate(listings_to_process):
                        if places_scraped >= max_results:
                            logging.info(f"🎯 Reached maximum of {max_results} places!")
                            break

                        actual_index = last_processed_index + idx + 1

                        try:
                            logging.info(f"📍 Processing listing {actual_index} (Scraped: {places_scraped})")

                            try:
                                listing.scroll_into_view_if_needed(timeout=5000)
                                page.wait_for_timeout(500)
                            except Exception:
                                pass

                            click_success = False
                            for attempt in range(3):
                                try:
                                    if attempt == 0:
                                        listing.click(timeout=8000)
                                    elif attempt == 1:
                                        listing.click(force=True, timeout=8000)
                                    else:
                                        listing.evaluate('element => element.click()')
                                    click_success = True
                                    break
                                except Exception as e:
                                    logging.warning(f"⚠ Click attempt {attempt + 1} failed: {str(e)[:100]}")
                                    if attempt < 2:
                                        page.wait_for_timeout(1500)
                                        try:
                                            listing.scroll_into_view_if_needed(timeout=5000)
                                        except Exception:
                                            pass

                            if not click_success:
                                logging.warning(f"❌ Failed to click listing {actual_index}, skipping")
                                consecutive_errors += 1
                                if consecutive_errors >= max_consecutive_errors:
                                    logging.error(f"💥 Too many consecutive errors ({consecutive_errors}), stopping...")
                                    break
                                continue

                            try:
                                page.wait_for_selector('//div[@class="TIHn2 "]//h1[@class="DUwDvf lfPIob"]', timeout=15000)
                            except Exception:
                                logging.warning(f"⚠ Details panel did not load for listing {actual_index}, skipping")
                                continue

                            page.wait_for_timeout(2000)

                            try:
                                google_maps_url = listing.get_attribute('href') or page.url
                            except Exception:
                                google_maps_url = page.url

                            place = extract_place(page, google_maps_url, browser, extract_emails)

                            if place.name:
                                place_identifier = f"{place.name.lower()}|{place.address.lower()}"

                                if place_identifier not in extracted_identifiers:
                                    if save_place_to_csv(place, output_path):
                                        extracted_identifiers.add(place_identifier)
                                        places_scraped += 1
                                        consecutive_errors = 0
                                        logging.info(f"✅ Saved ({places_scraped}): {place.name}")
                                    else:
                                        logging.warning(f"⚠ Failed to save: {place.name}")
                                        consecutive_errors += 1
                                else:
                                    logging.info(f"⊗ Duplicate skipped: {place.name}")
                                    consecutive_errors = 0
                            else:
                                logging.warning(f"⚠ No name found for listing {actual_index}, skipping")

                            page.wait_for_timeout(500)

                        except Exception as e:
                            logging.error(f"❌ Failed to extract listing {actual_index}: {e}")
                            consecutive_errors += 1
                            if consecutive_errors >= max_consecutive_errors:
                                logging.error(f"💥 Too many consecutive errors ({consecutive_errors}), stopping...")
                                break
                            continue

                    last_processed_index = current_listings
                    no_new_listings_count = 0
                else:
                    if current_listings == last_processed_index and current_listings > 0:
                        logging.info(f"ℹ All {current_listings} visible listings already processed")
                        if check_end_of_list(page):
                            end_of_list_reached = True
                            logging.info(f"🏁 End of list confirmed (all listings processed)")
                            break

                if consecutive_errors >= max_consecutive_errors:
                    logging.error(f"💥 Stopping due to {consecutive_errors} consecutive errors")
                    break

                if places_scraped >= max_results:
                    logging.info(f"🎯 Maximum reached! Successfully scraped {places_scraped} places")
                    break

                logging.info(f"🔄 Scrolling to load more... (Scraped: {places_scraped}, Scroll: {scroll_attempts + 1})")
                try:
                    scrollable_element.evaluate("element => element.scrollBy(0, 3000)")
                except Exception as e:
                    try:
                        page.mouse.wheel(0, 3000)
                    except Exception:
                        logging.warning(f"⚠ Scroll failed: {e}")

                page.wait_for_timeout(2500)

                new_count = page.locator('//a[contains(@href, "https://www.google.com/maps/place")]').count()
                logging.info(f"📊 Listings count after scroll: {new_count} (previous: {current_listings})")

                if new_count == current_listings:
                    no_new_listings_count += 1
                    logging.info(f"⚠ No new listings detected ({no_new_listings_count} times in a row)")

                    if no_new_listings_count >= 1:
                        if check_end_of_list(page):
                            end_of_list_reached = True
                            logging.info(f"🏁 Confirmed: Reached end of available listings")
                            break

                    if no_new_listings_count >= 5:
                        logging.info("💪 Trying aggressive scroll strategy...")

                        for aggressive_attempt in range(3):
                            logging.info(f"💪 Aggressive scroll attempt {aggressive_attempt + 1}/3")
                            try:
                                scrollable_element.evaluate("element => element.scrollBy(0, 10000)")
                            except Exception:
                                try:
                                    page.mouse.wheel(0, 10000)
                                except Exception:
                                    pass
                            page.wait_for_timeout(3000)

                            if check_end_of_list(page):
                                end_of_list_reached = True
                                logging.info(f"🏁 End of list detected during aggressive scroll")
                                break

                            after_aggressive = page.locator('//a[contains(@href, "https://www.google.com/maps/place")]').count()
                            logging.info(f"📊 After aggressive scroll: {after_aggressive} listings")

                            if after_aggressive > new_count:
                                logging.info(f"✅ Aggressive scroll worked! {after_aggressive - new_count} new listings")
                                new_count = after_aggressive
                                no_new_listings_count = 0
                                break

                        if end_of_list_reached:
                            break

                        if no_new_listings_count >= 5:
                            logging.info("🔍 Checking if truly at end of list...")
                            if check_end_of_list(page):
                                end_of_list_reached = True
                                logging.info(f"🏁 Confirmed: Reached end of available listings")
                                break
                            elif new_count == current_listings:
                                logging.info(f"✅ No more listings after multiple scroll attempts. Total scraped: {places_scraped}")
                                break
                            else:
                                no_new_listings_count = 0
                else:
                    no_new_listings_count = 0
                    logging.info(f"✅ Found {new_count - current_listings} new listings")

                scroll_attempts += 1

            logging.info("=" * 60)
            logging.info("📊 SCRAPING SUMMARY")
            logging.info("=" * 60)
            if end_of_list_reached:
                logging.info(f"✅ Reached end of list: {places_scraped} places scraped")
            elif places_scraped >= max_results:
                logging.info(f"✅ Maximum reached: {places_scraped}/{max_results} places")
            elif scroll_attempts >= max_scroll_attempts:
                logging.warning(f"⚠ Max scroll attempts reached: {scroll_attempts}/{max_scroll_attempts}")
            elif consecutive_errors >= max_consecutive_errors:
                logging.error(f"❌ Stopped due to consecutive errors: {consecutive_errors}")
            else:
                logging.info(f"✅ Reached end of available listings")
            logging.info(f"📈 Total places scraped: {places_scraped}")
            logging.info(f"📊 Total listings processed: {last_processed_index}")
            logging.info(f"🔄 Total scroll attempts: {scroll_attempts}")
            logging.info("=" * 60)

        except KeyboardInterrupt:
            logging.warning("⚠ Scraping interrupted by user (Ctrl+C)")
            logging.info(f"💾 Progress saved: {places_scraped} places scraped so far")
        except Exception as e:
            logging.error(f"💥 Critical error during scraping: {e}")
            logging.error(f"🔍 Full traceback:\n{traceback.format_exc()}")
        finally:
            logging.info("🔒 Closing browser...")
            try:
                browser.close()
                logging.info("✅ Browser closed successfully")
            except Exception as e:
                logging.warning(f"⚠ Error closing browser: {e}")

    return places_scraped


def scrape_multiple_cities(cities: list, search_template: str = "Clinique vétérinaire {city}",
                           output_folder: str = "ScrapeData", extract_emails: bool = True) -> dict:
    """
    Scrape Google Maps for multiple cities.
    Returns a dict with city names as keys and scraped counts as values.
    """
    output_path = Path(output_folder)
    output_path.mkdir(exist_ok=True)
    logging.info(f"📁 Output folder: {output_path.absolute()}")

    results = {}

    for idx, city in enumerate(cities, 1):
        logging.info("")
        logging.info("=" * 80)
        logging.info(f"🏙 PROCESSING CITY {idx}/{len(cities)}: {city}")
        logging.info("=" * 80)

        search_query = search_template.format(city=city)
        safe_city_name = sanitize_filename(city)
        output_file = output_path / f"{safe_city_name}.csv"

        logging.info(f"🔍 Search Query: {search_query}")
        logging.info(f"💾 Output File: {output_file}")

        try:
            places_count = scrape_places_until_end(search_query, str(output_file), extract_emails=extract_emails)
            results[city] = places_count
            logging.info("")
            logging.info(f"✅ Completed {city}: {places_count} places scraped")
            logging.info(f"💾 Saved to: {output_file}")
        except Exception as e:
            logging.error(f"❌ Failed to scrape {city}: {e}")
            results[city] = 0

        if idx < len(cities):
            logging.info(f"⏳ Waiting 5 seconds before next city...")
            time.sleep(5)

    logging.info("")
    logging.info("=" * 80)
    logging.info("🎉 ALL CITIES COMPLETED")
    logging.info("=" * 80)
    for city, count in results.items():
        status = "✅" if count > 0 else "❌"
        logging.info(f"{status} {city}: {count} places")
    logging.info(f"📊 Total places scraped: {sum(results.values())}")
    logging.info("=" * 80)

    return results


def scrape_place_by_url(
    url: str,
    output_dir: str = "ScrapeData",
    extract_emails: bool = True,
    chrome_profile: str = "",
) -> dict:
    """
    Full scrape of a single Google Maps place identified by its URL.

    Collects:
      • All overview fields  (name, address, phone, website, hours Mon-Sun,
                              coordinates, Google Maps URL, email)
      • ALL reviews          (author, rating, date, full text, Local Guide badge)
      • ALL photos           (downloaded at high resolution to images/ subfolder)
      • Web results / related places  (requires --chrome-profile for logged-in view)

    Output written to:
        <output_dir>/<PlaceName>/
            place_data.json   – complete place details
            place_data.csv    – same data as CSV
            reviews.csv       – every review
            images/           – 0001.jpg, 0002.jpg, …
    """
    result = {
        'url': url,
        'place_data': {},
        'related_places': [],
        'web_results': [],
        'about': {},
        'popular_times': {},
        'qa': [],
        'updates': [],
        'review_keywords': [],
        'reviews': [],
        'images_count': 0,
        'output_dir': output_dir,
    }

    with sync_playwright() as p:
        if chrome_profile:
            profile_copy = tempfile.mkdtemp(prefix="scraper_profile_")
            try:
                logging.info(f"🔑 Copying Chrome profile for logged-in scraping…")
                default_src = os.path.join(chrome_profile, "Default")
                default_dst = os.path.join(profile_copy, "Default")
                if os.path.isdir(default_src):
                    shutil.copytree(default_src, default_dst,
                                    ignore=shutil.ignore_patterns(
                                        "Cache", "Code Cache", "GPUCache",
                                        "Service Worker", "CacheStorage",
                                    ))
                else:
                    logging.warning("⚠ Could not find Default profile — using profile dir directly")
                    profile_copy = chrome_profile

                is_headless = platform.system() != "Windows"
                if platform.system() == "Windows":
                    browser_path = r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
                    context = p.chromium.launch_persistent_context(
                        user_data_dir=profile_copy,
                        executable_path=browser_path,
                        headless=is_headless,
                        args=["--profile-directory=Default"],
                    )
                else:
                    context = p.chromium.launch_persistent_context(
                        user_data_dir=profile_copy,
                        headless=is_headless,
                        args=["--profile-directory=Default", "--no-sandbox", "--disable-setuid-sandbox"],
                    )
                logging.info("✅ Launched Chrome with profile (logged-in mode)")
            except Exception as e:
                logging.warning(f"⚠ Could not use Chrome profile ({e}) — falling back to anonymous mode")
                context = None
                profile_copy = None
        else:
            context = None
            profile_copy = None

        if context is not None:
            page = context.new_page()
            browser = None
        else:
            is_headless = platform.system() != "Windows"
            if platform.system() == "Windows":
                browser_path = r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
                logging.info(f"🌐 Launching Chrome: {browser_path} (headless={is_headless})")
                browser = p.chromium.launch(executable_path=browser_path, headless=is_headless)
            else:
                logging.info(f"🌐 Launching Chromium (headless={is_headless})")
                browser = p.chromium.launch(headless=is_headless, args=['--no-sandbox', '--disable-setuid-sandbox'])
            page = browser.new_page()

        try:
            logging.info(f"🗺  Opening: {url}")
            page.goto(url, timeout=60000)
            page.wait_for_timeout(5000)

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

            try:
                page.wait_for_selector('h1.DUwDvf', timeout=20000)
                logging.info("✅ Place panel loaded")
            except Exception:
                logging.warning("⚠ Place header not found; attempting to continue")

            page.wait_for_timeout(2000)

            # ── STEP 1: Overview data ─────────────────────────────────────────
            logging.info("")
            logging.info("=" * 70)
            logging.info("STEP 1/3 — Place overview data")
            logging.info("=" * 70)

            place = extract_place(page, url, browser, extract_emails)
            result['place_data'] = asdict(place)
            logging.info(f"✅ Name    : {place.name}")
            logging.info(f"   Address : {place.address}")
            logging.info(f"   Phone   : {place.phone_number}")
            logging.info(f"   Website : {place.website}")
            logging.info(f"   Email   : {place.email}")
            logging.info(f"   Rating  : {place.reviews_average} ({place.reviews_count} reviews)")

            folder_name = sanitize_filename(place.name) if place.name else f"place_{time.strftime('%Y%m%d_%H%M%S')}"
            place_dir = os.path.join(output_dir, folder_name)
            os.makedirs(place_dir, exist_ok=True)
            result['output_dir'] = place_dir

            json_path = os.path.join(place_dir, 'place_data.json')
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(result['place_data'], f, ensure_ascii=False, indent=2)
            logging.info(f"💾 Saved  : {json_path}")

            csv_path = os.path.join(place_dir, 'place_data.csv')
            pd.DataFrame([result['place_data']]).to_csv(csv_path, index=False, encoding='utf-8-sig')
            logging.info(f"💾 Saved  : {csv_path}")

            # ── STEP 1b: Related places + Web results ─────────────────────────
            logging.info("")
            logging.info("=" * 70)
            logging.info("STEP 1b — Overview extras: related places + web results")
            logging.info("=" * 70)

            click_tab(page, "Overview")
            page.wait_for_timeout(1500)

            related_places = extract_related_places(page)
            result['related_places'] = related_places
            if related_places:
                rp_path = os.path.join(place_dir, 'related_places.csv')
                pd.DataFrame(related_places).to_csv(rp_path, index=False, encoding='utf-8-sig')
                logging.info(f"💾 Saved  : {rp_path}  ({len(related_places)} related places)")
                for rp in related_places:
                    logging.info(f"   • {rp.get('name','')} — {rp.get('place_type','')} {rp.get('rating','')}")
            else:
                logging.info("ℹ No related places found")

            web_results = extract_web_results(page)
            result['web_results'] = web_results
            if web_results:
                wr_path = os.path.join(place_dir, 'web_results.csv')
                pd.DataFrame(web_results).to_csv(wr_path, index=False, encoding='utf-8-sig')
                logging.info(f"💾 Saved  : {wr_path}  ({len(web_results)} web results)")
                for wr in web_results[:5]:
                    logging.info(f"   🌐 {wr.get('title','')} — {wr.get('url','')[:60]}")
            else:
                logging.info("ℹ No web results found")

            # ── STEP 1c: About tab ────────────────────────────────────────────
            logging.info("")
            logging.info("=" * 70)
            logging.info("STEP 1c — About tab (amenities, features, social links)")
            logging.info("=" * 70)

            about_data = extract_about_tab(page)
            result['about'] = about_data
            if about_data.get('attributes') or about_data.get('social_links'):
                about_path = os.path.join(place_dir, 'about.json')
                with open(about_path, 'w', encoding='utf-8') as f:
                    json.dump(about_data, f, ensure_ascii=False, indent=2)
                logging.info(f"💾 Saved  : {about_path}")
                rows = []
                for cat, items in about_data.get('attributes', {}).items():
                    for item in items:
                        rows.append({'category': cat, 'feature': item})
                if rows:
                    pd.DataFrame(rows).to_csv(
                        os.path.join(place_dir, 'about_attributes.csv'),
                        index=False, encoding='utf-8-sig')
                if about_data.get('social_links'):
                    pd.DataFrame(about_data['social_links']).to_csv(
                        os.path.join(place_dir, 'social_links.csv'),
                        index=False, encoding='utf-8-sig')
            else:
                logging.info("ℹ About tab: no data extracted")

            # ── STEP 1d: Popular times ────────────────────────────────────────
            logging.info("")
            logging.info("=" * 70)
            logging.info("STEP 1d — Popular times (busiest hours by day)")
            logging.info("=" * 70)

            popular_times = extract_popular_times(page)
            result['popular_times'] = popular_times
            if popular_times:
                pt_path = os.path.join(place_dir, 'popular_times.json')
                with open(pt_path, 'w', encoding='utf-8') as f:
                    json.dump(popular_times, f, ensure_ascii=False, indent=2)
                logging.info(f"💾 Saved  : {pt_path}")
                rows = []
                for day, hours in popular_times.items():
                    for h in hours:
                        rows.append({'day': day, 'hour': h.get('hour', ''), 'busyness': h.get('busyness', '')})
                if rows:
                    pd.DataFrame(rows).to_csv(
                        os.path.join(place_dir, 'popular_times.csv'),
                        index=False, encoding='utf-8-sig')
            else:
                logging.info("ℹ Popular times: not available")

            # ── STEP 1e: Q&A ──────────────────────────────────────────────────
            logging.info("")
            logging.info("=" * 70)
            logging.info("STEP 1e — Questions & Answers")
            logging.info("=" * 70)

            qa_list = extract_qa(page)
            result['qa'] = qa_list
            if qa_list:
                qa_path = os.path.join(place_dir, 'qa.csv')
                pd.DataFrame(qa_list).to_csv(qa_path, index=False, encoding='utf-8-sig')
                logging.info(f"💾 Saved  : {qa_path}  ({len(qa_list)} Q&As)")
            else:
                logging.info("ℹ No Q&A found")

            # ── STEP 1f: Business updates/posts ──────────────────────────────
            logging.info("")
            logging.info("=" * 70)
            logging.info("STEP 1f — Business updates / posts")
            logging.info("=" * 70)

            updates_list = extract_updates(page)
            result['updates'] = updates_list
            if updates_list:
                upd_path = os.path.join(place_dir, 'updates.csv')
                pd.DataFrame(updates_list).to_csv(upd_path, index=False, encoding='utf-8-sig')
                logging.info(f"💾 Saved  : {upd_path}  ({len(updates_list)} posts)")
            else:
                logging.info("ℹ No business updates/posts found")

            # ── STEP 2: Reviews ───────────────────────────────────────────────
            logging.info("")
            logging.info("=" * 70)
            logging.info("STEP 2 — Extracting all reviews + keywords")
            logging.info("=" * 70)

            review_keywords = extract_review_keywords(page)
            result['review_keywords'] = review_keywords
            if review_keywords:
                kw_path = os.path.join(place_dir, 'review_keywords.csv')
                pd.DataFrame([{'keyword': k} for k in review_keywords]).to_csv(
                    kw_path, index=False, encoding='utf-8-sig')
                logging.info(f"💾 Saved  : {kw_path}  ({len(review_keywords)} keywords)")

            reviews = extract_all_reviews(page, max_reviews=20)
            result['reviews'] = reviews
            if reviews:
                reviews_path = os.path.join(place_dir, 'reviews.csv')
                pd.DataFrame(reviews).to_csv(reviews_path, index=False, encoding='utf-8-sig')
                logging.info(f"💾 Saved  : {reviews_path}  ({len(reviews)} reviews)")
            else:
                logging.warning("⚠ No reviews found / extracted")

            # ── STEP 3: Images ────────────────────────────────────────────────
            logging.info("")
            logging.info("=" * 70)
            logging.info("STEP 3 — Downloading all images")
            logging.info("=" * 70)

            page.goto(url, timeout=60000)
            page.wait_for_timeout(4000)

            for sel in [
                'button:has-text("Accept all")',
                'button:has-text("I agree")',
                '//button[contains(., "Accept")]',
            ]:
                try:
                    if page.locator(sel).count() > 0:
                        page.locator(sel).first.click()
                        page.wait_for_timeout(1500)
                        break
                except Exception:
                    continue

            images_dir = os.path.join(place_dir, 'images')
            images_count = collect_and_download_images(page, images_dir)
            result['images_count'] = images_count
            logging.info(f"💾 Images : {images_dir}  ({images_count} files)")

            videos_dir = os.path.join(place_dir, 'videos')
            videos_count = collect_videos(page, videos_dir)
            result['videos_count'] = videos_count
            if videos_count:
                logging.info(f"💾 Videos : {videos_dir}  ({videos_count} files)")

        except KeyboardInterrupt:
            logging.warning("⚠ Interrupted by user (Ctrl+C)")
        except Exception as e:
            logging.error(f"❌ Fatal error during single-place scrape: {e}")
            logging.error(traceback.format_exc())
        finally:
            try:
                if context is not None:
                    context.close()
                elif browser is not None:
                    browser.close()
                logging.info("🔒 Browser closed")
            except Exception:
                pass
            if profile_copy and profile_copy != chrome_profile:
                try:
                    shutil.rmtree(profile_copy, ignore_errors=True)
                except Exception:
                    pass

    logging.info("")
    logging.info("=" * 70)
    logging.info("🎉 SINGLE-PLACE SCRAPE COMPLETE")
    logging.info("=" * 70)
    _pd = result['place_data']
    logging.info(f"📍 Place          : {_pd.get('name', 'Unknown')}")
    logging.info(f"📍 Address        : {_pd.get('address', '')}")
    logging.info(f"📍 Phone          : {_pd.get('phone_number', '')}")
    logging.info(f"📍 Plus Code      : {_pd.get('plus_code', '')}")
    logging.info(f"📍 Price range    : {_pd.get('price_range', '')}")
    logging.info(f"📍 Email          : {_pd.get('email', '')}")
    logging.info(f"🔗 Related places : {len(result['related_places'])}")
    logging.info(f"🌐 Web results    : {len(result['web_results'])}")
    attr_count = sum(len(v) for v in result['about'].get('attributes', {}).values())
    logging.info(f"ℹ️  About attrs    : {attr_count}")
    logging.info(f"🕐 Popular times  : {len(result['popular_times'])} days")
    logging.info(f"❓ Q&A            : {len(result['qa'])}")
    logging.info(f"📢 Updates/posts  : {len(result['updates'])}")
    logging.info(f"🏷️  Review keywords: {len(result['review_keywords'])}")
    logging.info(f"💬 Reviews        : {len(result['reviews'])}")
    logging.info(f"📷 Images         : {result['images_count']}")
    logging.info(f"📁 Output         : {result['output_dir']}")
    logging.info("=" * 70)
    return result
