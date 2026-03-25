import logging
from urllib.parse import urljoin

from scraper.utils import extract_email_from_text


def extract_email_from_website(website_url: str, browser) -> str:
    """
    Extract email from website using multiple strategies:
    1. Check main page source code
    2. Try /contact page
    3. Try /kontakt page (German)
    4. Try /impressum page (German)

    Uses a separate browser page to avoid interfering with Google Maps scraping
    """
    if not website_url or website_url == "":
        return ""

    skip_domains = [
        'yellow.local.ch', 'local.ch', 'search.ch', 'tel.search.ch',
        'cylex.ch', 'tupalo.com', 'yelp.ch', 'yelp.com',
        'facebook.com', 'instagram.com', 'maps.google.com',
        'google.com', 'goo.gl'
    ]

    for skip_domain in skip_domains:
        if skip_domain in website_url.lower():
            logging.info(f"⊗ Skipping directory/listing site: {website_url}")
            return ""

    if not website_url.startswith('http'):
        website_url = 'https://' + website_url

    email = ""
    email_page = None

    try:
        logging.info(f"🔍 Attempting to extract email from: {website_url}")

        email_page = browser.new_page()
        email_page.set_default_timeout(10000)

        try:
            email_page.goto(website_url, timeout=12000, wait_until="domcontentloaded")
            email_page.wait_for_timeout(1500)

            page_content = email_page.content()
            email = extract_email_from_text(page_content)

            if email:
                logging.info(f"✅ Found email on main page: {email}")
                return email

            logging.info("⚠ No email found on main page, trying contact pages...")

        except Exception as e:
            logging.warning(f"⚠ Failed to load main page: {e}")
            return ""

        contact_pages = ['/contact', '/kontakt', '/impressum', '/contact-us', '/fr/contact', '/de/kontakt']

        for contact_path in contact_pages:
            try:
                contact_url = urljoin(website_url, contact_path)
                logging.info(f"🔍 Trying: {contact_url}")

                email_page.goto(contact_url, timeout=10000, wait_until="domcontentloaded")
                email_page.wait_for_timeout(1000)

                page_content = email_page.content()
                email = extract_email_from_text(page_content)

                if email:
                    logging.info(f"✅ Found email on {contact_path}: {email}")
                    return email

            except Exception as e:
                logging.debug(f"⚠ Failed to check {contact_path}: {e}")
                continue

        logging.info("⚠ No email found on any page")

    except Exception as e:
        logging.warning(f"⚠ Failed to extract email from website: {e}")
    finally:
        if email_page:
            try:
                email_page.close()
            except Exception:
                pass

    return email
