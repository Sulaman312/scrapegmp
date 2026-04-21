import logging
import re

from playwright.sync_api import Page

from scraper.models import Place
from scraper.utils import extract_text, extract_coordinates_from_url
from scraper.email_extractor import extract_email_from_website


REVIEW_CONTEXT_KEYWORDS = [
    'review', 'reviews', 'avis', 'rezension', 'reseñ', 'recension', 'avalia',
    'отзы', '评价', '리뷰', 'bewertung', 'opini', 'comentario',
]


def _parse_reviews_count_from_text(raw: str) -> int | None:
    if not raw:
        return None
    candidates = re.findall(r'\d[\d\s.,\u00a0\u202f]*', raw)
    best = None
    for token in candidates:
        digits = re.sub(r'\D', '', token)
        if not digits:
            continue
        value = int(digits)
        if best is None or value > best:
            best = value
    return best


def _parse_reviews_average_from_text(raw: str) -> float | None:
    if not raw:
        return None

    # Common forms: "4.4", "4,4", "4.4/5", "4,4 sur 5"
    match = re.search(r'([0-5](?:[.,]\d)?)\s*(?:/\s*5)?', raw)
    if not match:
        return None

    token = match.group(1).replace(',', '.')
    try:
        value = float(token)
    except Exception:
        return None
    if 0.0 <= value <= 5.0:
        return value
    return None


def _extract_reviews_summary_multilang(page: Page) -> tuple[float | None, int | None]:
    """Best-effort multilingual extraction of average rating and reviews count."""
    selectors = [
        '//div[@class="TIHn2 "]//div[@class="fontBodyMedium dmRWX"]',
        '//button[contains(@aria-label, "review") or contains(@aria-label, "Review")]',
        '//button[contains(@aria-label, "avis") or contains(@aria-label, "Avis")]',
        '//button[contains(@aria-label, "rese") or contains(@aria-label, "Rez")]',
        '//button[contains(@aria-label, "отзы") or contains(@aria-label, "评价") or contains(@aria-label, "리뷰")]',
    ]

    snippets: list[str] = []
    for selector in selectors:
        try:
            loc = page.locator(selector)
            count = min(loc.count(), 3)
            for i in range(count):
                text = (loc.nth(i).inner_text() or '').strip()
                if text:
                    snippets.append(text)
                aria = (loc.nth(i).get_attribute('aria-label') or '').strip()
                if aria:
                    snippets.append(aria)
        except Exception:
            continue

    try:
        dom_texts = page.evaluate(
            """
            () => {
                const out = [];
                const nodes = document.querySelectorAll('button,[role="button"],span,div');
                const limit = Math.min(nodes.length, 1200);
                for (let i = 0; i < limit; i++) {
                    const el = nodes[i];
                    const aria = (el.getAttribute && el.getAttribute('aria-label')) || '';
                    const txt = (el.textContent || '').trim();
                    if (aria) out.push(aria);
                    if (txt && txt.length <= 120) out.push(txt);
                }
                return out;
            }
            """
        )
        if isinstance(dom_texts, list):
            snippets.extend([str(t) for t in dom_texts if t])
    except Exception:
        pass

    rating_value = None
    count_value = None
    for snippet in snippets:
        low = snippet.lower()
        if not any(k in low for k in REVIEW_CONTEXT_KEYWORDS):
            continue

        parsed_rating = _parse_reviews_average_from_text(snippet)
        if rating_value is None and parsed_rating is not None:
            rating_value = parsed_rating

        parsed_count = _parse_reviews_count_from_text(snippet)
        if parsed_count is not None and (count_value is None or parsed_count > count_value):
            count_value = parsed_count

        if rating_value is not None and count_value is not None:
            break

    return rating_value, count_value


def extract_weekly_hours(page: Page) -> dict:
    """Extract full weekly opening hours from Google Maps as separate day columns"""
    weekly_hours = {
        'monday': '',
        'tuesday': '',
        'wednesday': '',
        'thursday': '',
        'friday': '',
        'saturday': '',
        'sunday': ''
    }

    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    try:
        logging.info("🕐 Extracting opening hours...")
        hours_button_selectors = [
            '//div[@class="OMl5r hH0dDd jBYmhd"][@role="button"]',
            '//button[contains(@aria-label, "Hours")]',
            '//div[@role="button"][contains(@aria-label, "hours")]'
        ]

        button_clicked = False
        for selector in hours_button_selectors:
            if page.locator(selector).count() > 0:
                try:
                    is_expanded = page.locator(selector).first.get_attribute('aria-expanded')
                    if is_expanded != 'true':
                        try:
                            page.locator(selector).first.click(force=True, timeout=5000)
                            button_clicked = True
                            logging.info(f"  ✅ Hours popup opened with selector: {selector[:60]}...")
                        except Exception:
                            try:
                                page.locator(selector).first.evaluate('element => element.click()')
                                button_clicked = True
                                logging.info(f"  ✅ Hours popup opened via JS with selector: {selector[:60]}...")
                            except Exception:
                                pass

                        if button_clicked:
                            page.wait_for_timeout(5000)
                            break
                except Exception:
                    continue

        if not button_clicked:
            logging.warning("  ⚠ Could not find or click hours button")

        # Multi-language day names (EN, DE, FR, ES, IT)
        day_translations = {
            'Monday': ['Monday', 'Montag', 'Lundi', 'Lunes', 'Lunedì'],
            'Tuesday': ['Tuesday', 'Dienstag', 'Mardi', 'Martes', 'Martedì'],
            'Wednesday': ['Wednesday', 'Mittwoch', 'Mercredi', 'Miércoles', 'Mercoledì'],
            'Thursday': ['Thursday', 'Donnerstag', 'Jeudi', 'Jueves', 'Giovedì'],
            'Friday': ['Friday', 'Freitag', 'Vendredi', 'Viernes', 'Venerdì'],
            'Saturday': ['Saturday', 'Samstag', 'Samedi', 'Sábado', 'Sabato'],
            'Sunday': ['Sunday', 'Sonntag', 'Dimanche', 'Domingo', 'Domenica']
        }

        # Try to scroll the hours popup to ensure all days are visible
        try:
            page.evaluate("""
                () => {
                    const table = document.querySelector('table.eK4R0e');
                    if (table) {
                        const container = table.closest('div');
                        if (container) container.scrollTop = 0;
                    }
                }
            """)
            page.wait_for_timeout(500)
        except:
            pass

        # Debug: Check what day text actually exists in the popup
        try:
            all_rows = page.locator('//tr[@class="y0skZc"]').all()
            logging.info(f"  🔍 Found {len(all_rows)} rows in hours table")
            for i, row in enumerate(all_rows[:7]):
                day_text = row.locator('//td[contains(@class, "ylH6lf")]').inner_text() if row.locator('//td[contains(@class, "ylH6lf")]').count() > 0 else "?"
                hours_text = row.locator('//td[@class="mxowUb"]').inner_text() if row.locator('//td[@class="mxowUb"]').count() > 0 else "?"
                logging.info(f"  🔍 Row {i}: Day='{day_text}' Hours='{hours_text}'")
        except Exception as e:
            logging.warning(f"  ⚠ Debug extraction failed: {e}")

        extracted_count = 0
        for day in days:
            day_found = False
            for translated_day in day_translations.get(day, [day]):
                day_row_xpath = f'//tr[@class="y0skZc"]//td[contains(@class, "ylH6lf")]//div[text()="{translated_day}"]/ancestor::tr'

                if page.locator(day_row_xpath).count() > 0:
                    hours_xpath = f'{day_row_xpath}//td[@class="mxowUb"]'
                    hours_text = extract_text(page, hours_xpath)

                    if hours_text:
                        hours_text = hours_text.replace('\n', ' ').strip()
                        weekly_hours[day.lower()] = hours_text
                        extracted_count += 1
                        day_found = True
                        logging.debug(f"  ✓ {day}: {hours_text}")
                        break

            if not day_found:
                weekly_hours[day.lower()] = "Not available"
                logging.warning(f"  ⚠ {day}: no row found for any translation")

        logging.info(f"  ✅ Hours extracted: {extracted_count}/7 days with data")
        return weekly_hours

    except Exception as e:
        logging.error(f"  ❌ Hours extraction failed: {e}")
        return weekly_hours


def extract_place(page: Page, google_maps_url: str = "", browser=None, extract_emails: bool = True) -> Place:
    name_xpath = '//div[@class="TIHn2 "]//h1[@class="DUwDvf lfPIob"]'
    address_xpath = '//button[@data-item-id="address"]//div[contains(@class, "fontBodyMedium")]'
    website_xpath = '//a[@data-item-id="authority"]//div[contains(@class, "fontBodyMedium")]'
    phone_number_xpath = '//button[contains(@data-item-id, "phone:tel:")]//div[contains(@class, "fontBodyMedium")]'
    reviews_count_xpath = '//div[@class="TIHn2 "]//div[@class="fontBodyMedium dmRWX"]//div//span//span//span[@aria-label]'
    reviews_average_xpath = '//div[@class="TIHn2 "]//div[@class="fontBodyMedium dmRWX"]//div//span[@aria-hidden]'
    info1 = '//div[@class="LTs0Rc"][1]'
    info2 = '//div[@class="LTs0Rc"][2]'
    info3 = '//div[@class="LTs0Rc"][3]'
    opens_at_xpath = '//button[contains(@data-item-id, "oh")]//div[contains(@class, "fontBodyMedium")]'
    opens_at_xpath2 = '//div[@class="MkV9"]//span[@class="ZDu9vd"]//span[2]'
    place_type_xpath = '//div[@class="LBgpqf"]//button[@class="DkEaL "]'
    intro_xpath = '//div[@class="WeS02d fontBodyMedium"]//div[@class="PYvSYb "]'

    place = Place()
    place.name = extract_text(page, name_xpath)
    place.address = extract_text(page, address_xpath)
    place.website = extract_text(page, website_xpath)
    place.phone_number = extract_text(page, phone_number_xpath)
    place.place_type = extract_text(page, place_type_xpath)
    place.introduction = extract_text(page, intro_xpath) or "None Found"

    place.google_maps_url = google_maps_url or page.url

    latitude, longitude = extract_coordinates_from_url(place.google_maps_url)
    place.latitude = latitude
    place.longitude = longitude

    reviews_count_raw = extract_text(page, reviews_count_xpath)
    if reviews_count_raw:
        try:
            parsed_count = _parse_reviews_count_from_text(reviews_count_raw)
            if parsed_count is not None:
                place.reviews_count = parsed_count
        except Exception as e:
            logging.warning(f"Failed to parse reviews count: {e}")

    reviews_avg_raw = extract_text(page, reviews_average_xpath)
    if reviews_avg_raw:
        try:
            parsed_avg = _parse_reviews_average_from_text(reviews_avg_raw)
            if parsed_avg is not None:
                place.reviews_average = parsed_avg
        except Exception as e:
            logging.warning(f"Failed to parse reviews average: {e}")

    if place.reviews_average is None or place.reviews_count is None:
        fallback_avg, fallback_count = _extract_reviews_summary_multilang(page)
        if place.reviews_average is None and fallback_avg is not None:
            place.reviews_average = fallback_avg
            logging.info(f"  ✅ Rating fallback parsed (multilang): {place.reviews_average}")
        if place.reviews_count is None and fallback_count is not None:
            place.reviews_count = fallback_count
            logging.info(f"  ✅ Reviews fallback parsed (multilang): {place.reviews_count}")

    for idx, info_xpath in enumerate([info1, info2, info3]):
        info_raw = extract_text(page, info_xpath)
        if info_raw:
            temp = info_raw.split('·')
            if len(temp) > 1:
                check = temp[1].replace("\n", "").lower()
                if 'shop' in check:
                    place.store_shopping = "Yes"
                if 'pickup' in check:
                    place.in_store_pickup = "Yes"
                if 'delivery' in check:
                    place.store_delivery = "Yes"

    opens_at_raw = extract_text(page, opens_at_xpath)
    if opens_at_raw:
        opens = opens_at_raw.split('⋅')
        if len(opens) > 1:
            place.opens_at = opens[1].replace("\u202f", "")
        else:
            place.opens_at = opens_at_raw.replace("\u202f", "")
    else:
        opens_at2_raw = extract_text(page, opens_at_xpath2)
        if opens_at2_raw:
            opens = opens_at2_raw.split('⋅')
            if len(opens) > 1:
                place.opens_at = opens[1].replace("\u202f", "")
            else:
                place.opens_at = opens_at2_raw.replace("\u202f", "")

    weekly_hours = extract_weekly_hours(page)
    place.monday = weekly_hours['monday']
    place.tuesday = weekly_hours['tuesday']
    place.wednesday = weekly_hours['wednesday']
    place.thursday = weekly_hours['thursday']
    place.friday = weekly_hours['friday']
    place.saturday = weekly_hours['saturday']
    place.sunday = weekly_hours['sunday']

    plus_code_xpaths = [
        '//button[@data-item-id="oloc"]//div[contains(@class, "fontBodyMedium")]',
        '//a[@data-item-id="oloc"]//div[contains(@class, "fontBodyMedium")]',
        '//div[@data-item-id="oloc"]//div[contains(@class, "fontBodyMedium")]',
    ]
    for pxp in plus_code_xpaths:
        raw = extract_text(page, pxp)
        if raw:
            place.plus_code = raw.strip()
            break

    try:
        price_raw = page.evaluate(r"""
        () => {
            for (const el of document.querySelectorAll('*')) {
                if (el.children.length === 0) {
                    const t = (el.textContent || '').trim();
                    if (/^\$+$/.test(t) || /^€+$/.test(t) || /^£+$/.test(t)) return t;
                }
            }
            const priceEl = document.querySelector('[aria-label*="Price"]');
            if (priceEl) return priceEl.getAttribute('aria-label');
            return '';
        }
        """) or ""
        place.price_range = price_raw.strip()
    except Exception:
        pass

    desc_xpaths = [
        '//div[@class="WeS02d fontBodyMedium"]//div[@class="PYvSYb "]',
        '//div[contains(@class,"PYvSYb")]',
        '//div[@class="iP2t7d fontBodyMedium"]',
    ]
    for dxp in desc_xpaths:
        raw = extract_text(page, dxp)
        if raw and len(raw) > 20:
            place.description = raw.strip()
            break

    if extract_emails and place.website and browser:
        logging.info(f"🌐 Website found: {place.website}, attempting email extraction...")
        place.email = extract_email_from_website(place.website, browser)
        if place.email:
            logging.info(f"✉️ Email found: {place.email}")
        else:
            logging.info(f"⚠ No email found for {place.website}")
    else:
        if not extract_emails:
            logging.info("⊗ Email extraction disabled")
        elif not place.website:
            logging.info("⚠ No website available for email extraction")

    return place
