import logging

from playwright.sync_api import Page

from scraper.models import Place
from scraper.utils import extract_text, extract_coordinates_from_url
from scraper.email_extractor import extract_email_from_website


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
                        except Exception:
                            try:
                                page.locator(selector).first.evaluate('element => element.click()')
                                button_clicked = True
                            except Exception:
                                pass

                        if button_clicked:
                            page.wait_for_timeout(1000)
                            break
                except Exception:
                    continue

        for day in days:
            day_row_xpath = f'//tr[@class="y0skZc"]//td[contains(@class, "ylH6lf")]//div[text()="{day}"]/ancestor::tr'

            if page.locator(day_row_xpath).count() > 0:
                hours_xpath = f'{day_row_xpath}//td[@class="mxowUb"]'
                hours_text = extract_text(page, hours_xpath)

                if hours_text:
                    hours_text = hours_text.replace('\n', ' ').strip()
                    weekly_hours[day.lower()] = hours_text
                else:
                    weekly_hours[day.lower()] = "Not available"
            else:
                weekly_hours[day.lower()] = "Not available"

        return weekly_hours

    except Exception:
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
            temp = reviews_count_raw.replace('\xa0', '').replace('(', '').replace(')', '').replace(',', '')
            place.reviews_count = int(temp)
        except Exception as e:
            logging.warning(f"Failed to parse reviews count: {e}")

    reviews_avg_raw = extract_text(page, reviews_average_xpath)
    if reviews_avg_raw:
        try:
            temp = reviews_avg_raw.replace(' ', '').replace(',', '.')
            place.reviews_average = float(temp)
        except Exception as e:
            logging.warning(f"Failed to parse reviews average: {e}")

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
