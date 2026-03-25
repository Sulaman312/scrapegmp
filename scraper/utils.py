import logging
import os
import re
import time

from playwright.sync_api import Page


def setup_logging():
    """Setup logging to both file and console"""
    if not os.path.exists('logs'):
        os.makedirs('logs')

    log_filename = f"logs/scraper_{time.strftime('%Y%m%d_%H%M%S')}.log"

    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    logging.root.setLevel(logging.INFO)
    logging.root.addHandler(file_handler)
    logging.root.addHandler(console_handler)

    logging.info(f"📝 Logging to file: {log_filename}")

    return log_filename


def extract_text(page: Page, xpath: str) -> str:
    try:
        if page.locator(xpath).count() > 0:
            return page.locator(xpath).inner_text()
    except Exception as e:
        logging.warning(f"Failed to extract text for xpath {xpath}: {e}")
    return ""


def extract_coordinates_from_url(url: str) -> tuple:
    """Extract latitude and longitude from Google Maps URL"""
    try:
        pattern1 = r'@(-?\d+\.\d+),(-?\d+\.\d+)'
        match = re.search(pattern1, url)
        if match:
            return match.group(1), match.group(2)

        pattern2 = r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)'
        match = re.search(pattern2, url)
        if match:
            return match.group(1), match.group(2)

        pattern3 = r'/place/[^/]+/@(-?\d+\.\d+),(-?\d+\.\d+)'
        match = re.search(pattern3, url)
        if match:
            return match.group(1), match.group(2)

    except Exception as e:
        logging.warning(f"Failed to extract coordinates from URL: {e}")

    return "", ""


def extract_email_from_text(text: str) -> str:
    """Extract email from text using regex patterns"""
    try:
        email_patterns = [
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            r'mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
        ]

        for pattern in email_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                for email in matches:
                    email = email.lower().strip()

                    if any(ext in email for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico', '.css', '.js', '.woff']):
                        continue

                    if any(x in email for x in ['example.com', 'test.com', 'domain.com', 'email.com', 'your-email', 'youremail', 'noreply@', 'no-reply@']):
                        continue

                    if '@' in email and ('/' in email or '\\' in email or '?' in email or '&' in email):
                        continue

                    if '@' in email and '.' in email.split('@')[1]:
                        domain = email.split('@')[1]
                        if not any(c in domain for c in ['<', '>', '"', "'", ' ', ',']):
                            return email

    except Exception as e:
        logging.warning(f"Failed to extract email from text: {e}")

    return ""


def sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing/replacing invalid characters"""
    invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    sanitized = filename
    for char in invalid_chars:
        sanitized = sanitized.replace(char, '-')
    return sanitized
