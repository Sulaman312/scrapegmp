import logging
import os
import re
import time
from io import BytesIO

import requests
from PIL import Image
from playwright.sync_api import Page

from scraper.tab_extractors import click_tab
from scraper.utils import sanitize_filename


def _env_int(name: str, default: int, min_value: int = 1) -> int:
    """Read an integer env var with sane fallback and minimum guard."""
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except Exception:
        return default
    return max(min_value, value)


def _find_scrollable_panel(page: Page):
    selectors = [
        'div[role="feed"]',
        'div.m6QErb.DxyBCb.kA9KIf.dS8AEf',
        'div.m6QErb.DxyBCb',
        'div.m6QErb',
    ]
    for sel in selectors:
        loc = page.locator(sel)
        count = loc.count()
        if count == 0:
            continue
        for idx in range(count):
            candidate = loc.nth(idx)
            try:
                if sel == 'div[role="feed"]':
                    return candidate, sel
                is_scrollable = candidate.evaluate(
                    "el => (el.scrollHeight - el.clientHeight) > 120"
                )
                if is_scrollable:
                    return candidate, sel
            except Exception:
                continue
    return None, ""


def _open_full_photos_gallery(page: Page) -> bool:
    """Try to open the dedicated photos gallery view (not the single-photo preview)."""
    selectors = [
        'button:has-text("See photos")',
        'button:has-text("All photos")',
        'button:has-text("Photos")',
        'a:has-text("See photos")',
        'a:has-text("All photos")',
        '//button[contains(., "See photos")]',
        '//button[contains(., "All photos")]',
        '//button[contains(., "Photos")]',
        '//a[contains(., "See photos")]',
        '//a[contains(., "All photos")]',
        '//button[contains(@aria-label, "See photos")]',
        '//button[contains(@aria-label, "All photos")]',
        '//button[contains(@aria-label, "photos")]',
    ]

    for sel in selectors:
        try:
            loc = page.locator(sel)
            if loc.count() > 0:
                loc.first.click(force=True)
                page.wait_for_timeout(3000)
                return True
        except Exception:
            continue

    # Last resort: if this is a place page, try direct /photos URL.
    try:
        current = page.url
        if '/maps/place/' in current and '/photos' not in current:
            target = current.split('?')[0].rstrip('/') + '/photos'
            page.goto(target, timeout=30000)
            page.wait_for_timeout(3000)
            return True
    except Exception:
        pass

    return False


def _download_one_image(base_url: str, dest_path: str) -> bool:
    """
    Try several Google size-suffix variants, convert the first successful
    response (> 25 KB) to WebP and write it to dest_path (always .webp).
    25 KB floor filters out avatar/icon images while keeping real photos.
    """
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        ),
        'Referer': 'https://www.google.com/',
    }
    dest_path = os.path.splitext(dest_path)[0] + '.webp'
    for suffix in ['=s1600', '=w2048-h2048-k-no', '=w1024-h1024-k-no', '=s800', '']:
        try:
            resp = requests.get(base_url + suffix, timeout=20, headers=headers)
            if resp.status_code == 200 and len(resp.content) > 25000:
                img = Image.open(BytesIO(resp.content))
                if img.mode not in ('RGB', 'RGBA'):
                    img = img.convert('RGB')
                img.save(dest_path, 'WEBP', quality=85, method=4)
                return True
        except Exception:
            continue
    return False


def _dom_scan_images(page, seen: set, category: str, category_urls: dict) -> int:
    """
    Scan the current DOM for all googleusercontent images not yet captured.
    Returns the number of new URLs added.
    Handles cached photos that won't fire network response events.
    """
    raw = page.evaluate(r"""
    () => {
        const srcs = new Set();
        document.querySelectorAll('img[src*="googleusercontent.com"]').forEach(img => {
            if (img.src) srcs.add(img.src);
        });
        document.querySelectorAll('img[data-src*="googleusercontent.com"]').forEach(img => {
            srcs.add(img.getAttribute('data-src'));
        });
        document.querySelectorAll('[style*="googleusercontent"]').forEach(el => {
            const m = (el.getAttribute('style') || '')
                .match(/url\(["']?(https?[^"')]+)["']?\)/);
            if (m) srcs.add(m[1]);
        });
        return Array.from(srcs);
    }
    """) or []

    added = 0
    for src in raw:
        # Filter out unwanted images (same as network interceptor)
        if any(x in src for x in ['/a-/', '/a/', 's32-', 's48-', 's64-', 's96-', 's128-', '/logo/', 'avatar']):
            continue

        # Only capture images from lh3, lh4, lh5, lh6 (place photo domains)
        if not any(x in src for x in ['lh3.googleusercontent.com', 'lh4.googleusercontent.com',
                                       'lh5.googleusercontent.com', 'lh6.googleusercontent.com']):
            continue

        base = re.sub(r'=.*$', '', src)
        if base and base not in seen:
            seen.add(base)
            category_urls.setdefault(category, []).append(base)
            added += 1
    return added


def collect_and_download_images(page: Page, images_dir: str) -> int:
    """
    Download ALL place photos from a Google Maps place page.

    Strategy
    --------
    1. Intercept network responses to capture every URL that matches the
       Google user-content PLACE PHOTO pattern.
    2. Open the Photos panel and scroll through every visible category tab.
    3. Also scan the DOM for any images that loaded before the interceptor was attached.
    4. Download every unique base URL at the highest available resolution.

    Returns the total number of saved files.
    """
    os.makedirs(images_dir, exist_ok=True)
    downloaded = 0
    seen_base_urls: set = set()

    category_urls: dict = {}
    current_category = ["All"]

    def _on_response(response):
        try:
            url = response.url
            if 'googleusercontent.com' in url:
                # Filter out unwanted images:
                # - Reviewer profile pictures (contain '/a-/' or '/a/')
                # - Small icons and UI elements (contain 's32', 's48', 's64')
                # - Logo images (contain 'logo')
                if any(x in url for x in ['/a-/', '/a/', 's32-', 's48-', 's64-', 's96-', 's128-', '/logo/', 'avatar']):
                    return

                # Only capture images from lh3, lh4, lh5, lh6 (place photo domains)
                if not any(x in url for x in ['lh3.googleusercontent.com', 'lh4.googleusercontent.com',
                                               'lh5.googleusercontent.com', 'lh6.googleusercontent.com']):
                    return

                base = re.sub(r'=.*$', '', url)
                if base and base not in seen_base_urls:
                    seen_base_urls.add(base)
                    cat = current_category[0]
                    category_urls.setdefault(cat, []).append(base)
        except Exception:
            pass

    page.on('response', _on_response)

    try:
        initial_scrolls = _env_int('SCRAPER_INITIAL_SCROLLS', 5, 1)
        max_category_scrolls = _env_int('SCRAPER_MAX_CATEGORY_SCROLLS', 60, 1)
        max_no_new_scrolls = _env_int('SCRAPER_MAX_NO_NEW_SCROLLS', 5, 1)
        max_photos = int(os.getenv('SCRAPER_MAX_PHOTOS', '20'))
        max_seconds = float(os.getenv('SCRAPER_IMAGES_MAX_SECONDS', '180'))
        deadline = time.monotonic() + max_seconds

        photos_opened = False
        logging.info("🔍 Attempting to open Photos panel...")
        for label in ["Photos", "Photo", "All photos", "See photos",
                       "Fotos", "Foto", "Alle Fotos", "Photos & vidéos", "Galerie"]:
            logging.info(f"  Trying label: '{label}'")
            if click_tab(page, label):
                logging.info(f"  ✅ Photos panel opened with label: '{label}'")
                photos_opened = True
                break

        if not photos_opened:
            logging.info("  Labels failed, trying XPath selectors...")
            for sel in [
                '//button[contains(@aria-label, "photo")]',
                '//button[contains(@aria-label, "Photo")]',
                '//button[contains(@aria-label, "Foto")]',
                '//a[contains(@aria-label, "photo")]',
                '//div[@class="RZ66Rb YU2qld"]',
            ]:
                try:
                    count = page.locator(sel).count()
                    logging.info(f"  Selector '{sel[:50]}...' found {count} elements")
                    if count > 0:
                        page.locator(sel).first.click(force=True)
                        page.wait_for_timeout(3000)
                        logging.info(f"  ✅ Photos panel opened with selector: '{sel[:50]}...'")
                        photos_opened = True
                        break
                except Exception as e:
                    logging.debug(f"  ⚠ Selector '{sel[:50]}...' failed: {e}")
                    continue

        if not photos_opened:
            logging.warning("⚠ Could not open Photos panel - all attempts failed")

        # Ensure we are in full photos gallery (not single preview/lightbox).
        if _open_full_photos_gallery(page):
            logging.info("✅ Opened full photos gallery view")
        else:
            logging.info("ℹ Could not explicitly open full gallery; continuing with current photos view")

        page.wait_for_timeout(1500)

        scrollable, panel_sel = _find_scrollable_panel(page)
        if scrollable:
            logging.info(f"✅ Photos scrollable panel found: {panel_sel}")
        else:
            logging.warning("⚠ No scrollable photos panel detected; using mouse wheel fallback")

        # Initial scrolling to load more photos - scroll aggressively
        logging.info("📜 Performing initial scroll to load photos...")
        visible_target = max(max_photos * 2, max_photos + 5) if max_photos > 0 else 40
        for i in range(initial_scrolls):
            if time.monotonic() > deadline:
                logging.warning(f"⚠ Image scraping time limit reached ({int(max_seconds)}s) during preload")
                break
            if scrollable:
                try:
                    scrollable.evaluate("el => el.scrollBy(0, 5000)")
                except Exception:
                    page.mouse.wheel(0, 5000)
            else:
                page.mouse.wheel(0, 5000)
            page.wait_for_timeout(1200)

            # Check how many images are visible after this scroll
            img_count = page.locator('img[src*="googleusercontent.com"]').count()
            logging.info(f"  Scroll {i+1}/{initial_scrolls} - Images visible: {img_count}")
            if max_photos > 0 and img_count >= visible_target:
                logging.info(
                    f"✅ Image card target reached during preload ({img_count} >= {visible_target}); stopping early"
                )
                break
        logging.info("📜 Initial scroll complete - waiting for images to load...")
        page.wait_for_timeout(1200)

        KNOWN_CATEGORIES = [
            "All", "By owner", "Videos", "Street View & 360°",
            "Latest", "Menu", "Food & drink", "Atmosphere",
            "Tout", "Par le propriétaire", "Vidéos", "Street View et 360°",
            "Dernières", "Menu", "Nourriture et boissons", "Ambiance",
            "Alle", "Vom Inhaber", "Videos", "Street View & 360°",
            "Neueste", "Menü", "Essen & Trinken", "Atmosphäre",
        ]
        detected_tabs = page.evaluate(r"""
        () => Array.from(document.querySelectorAll(
            'button[role="tab"], div[role="tab"], button[aria-selected]'
        )).map(b => b.textContent.trim()).filter(t => t.length > 0 && t.length < 60)
        """) or []

        categories = [c for c in KNOWN_CATEGORIES if c in detected_tabs]
        if not categories:
            logging.info("ℹ No category tabs detected — scraping current view only")
            categories = ["All"]
        else:
            logging.info(f"📸 Tabs found: {categories}")

        for category in categories:
            if time.monotonic() > deadline:
                logging.warning(f"⚠ Image scraping time limit reached ({int(max_seconds)}s), stopping category scan")
                break
            # Check if we already have enough URLs
            total_urls_collected = sum(len(v) for v in category_urls.values())
            if max_photos > 0 and total_urls_collected >= max_photos:
                logging.info(f"✅ Already have {total_urls_collected} photo URLs - stopping collection (limit={max_photos})")
                break

            current_category[0] = category
            logging.info(f"  ▶ Category: '{category}'")

            if category != "All":
                tab_clicked = False
                for sel in [
                    f'//button[@role="tab"][normalize-space()="{category}"]',
                    f'//div[@role="tab"][normalize-space()="{category}"]',
                    f'//button[contains(@aria-label, "{category}")]',
                    f'//button[contains(., "{category}")]',
                ]:
                    try:
                        if page.locator(sel).count() > 0:
                            page.locator(sel).first.click(force=True)
                            page.wait_for_timeout(2500)
                            tab_clicked = True
                            break
                    except Exception:
                        continue
                if not tab_clicked:
                    logging.info(f"    ⚠ Tab '{category}' not clickable, skipping")
                    continue

            prev_count = sum(len(v) for v in category_urls.values())
            no_new = 0
            scrolls = 0
            # Continue until no-new threshold or max per-category scrolls.
            while no_new < max_no_new_scrolls and scrolls < max_category_scrolls:
                if time.monotonic() > deadline:
                    logging.warning(f"⚠ Image scraping time limit reached ({int(max_seconds)}s) inside category '{category}'")
                    break
                # Check if we have enough URLs
                total_urls_collected = sum(len(v) for v in category_urls.values())
                if max_photos > 0 and total_urls_collected >= max_photos:
                    logging.info(f"✅ Collected {total_urls_collected} photo URLs - stopping scroll (limit={max_photos})")
                    break

                if scrollable:
                    try:
                        scrollable.evaluate("el => el.scrollBy(0, 4000)")
                    except Exception:
                        page.mouse.wheel(0, 4000)
                else:
                    page.mouse.wheel(0, 4000)
                page.wait_for_timeout(2500)
                scrolls += 1

                _dom_scan_images(page, seen_base_urls, category, category_urls)

                cur_count = sum(len(v) for v in category_urls.values())
                if cur_count > prev_count:
                    logging.info(f"    📸 {cur_count} URLs captured so far")
                    prev_count = cur_count
                    no_new = 0
                else:
                    no_new += 1

                if max_photos > 0 and cur_count >= max_photos:
                    logging.info(f"✅ Reached target photo URL count ({cur_count}) during category scan")
                    break

            if scrolls >= max_category_scrolls:
                logging.info(f"    ℹ Reached max category scrolls ({max_category_scrolls}) for '{category}'")

            _dom_scan_images(page, seen_base_urls, category, category_urls)
            cat_count = len(category_urls.get(category, []))
            logging.info(f"  ✅ '{category}': {cat_count} photo URLs found")

    finally:
        page.remove_listener('response', _on_response)

    total_found = sum(len(v) for v in category_urls.values())
    max_photos = int(os.getenv('SCRAPER_MAX_PHOTOS', '20'))
    if max_photos > 0:
        logging.info(f"📷 Downloading up to {max_photos} photos from {total_found} unique URLs found…")
    else:
        logging.info(f"📷 Downloading all photos from {total_found} unique URLs found…")

    for cat, urls in category_urls.items():
        if max_photos > 0 and downloaded >= max_photos:
            logging.info(f"✅ Reached maximum of {max_photos} photos - stopping download")
            break
        cat_dir = os.path.join(images_dir, sanitize_filename(cat))
        os.makedirs(cat_dir, exist_ok=True)
        for base in urls:
            if max_photos > 0 and downloaded >= max_photos:
                break
            dest = os.path.join(cat_dir, f'{downloaded + 1:04d}.webp')
            if _download_one_image(base, dest):
                downloaded += 1
                logging.info(f"  📷 [{cat}] saved #{downloaded}: {os.path.basename(dest)}")
            else:
                logging.debug(f"  ⚠ Could not download: {base}")

    if downloaded == 0:
        logging.warning(
            "⚠ No place photos downloaded.  "
            "This place may have no photos uploaded to Google Maps."
        )

    logging.info(f"✅ Total images downloaded: {downloaded}")
    return downloaded


def _download_video(url: str, dest_path: str) -> bool:
    """
    Download a direct video URL (mp4/webm) and write it to dest_path.
    Streams in chunks so large files don't exhaust RAM.
    Returns True on success (downloaded file > 50 KB).
    """
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        ),
        'Referer': 'https://www.google.com/',
    }
    try:
        resp = requests.get(url, timeout=90, headers=headers, stream=True)
        if resp.status_code != 200:
            return False
        size = 0
        with open(dest_path, 'wb') as fh:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    fh.write(chunk)
                    size += len(chunk)
        if size > 50_000:
            return True
        os.remove(dest_path)
    except Exception:
        try:
            os.remove(dest_path)
        except Exception:
            pass
    return False


def collect_videos(page: Page, videos_dir: str) -> int:
    """
    Download the actual video files (.mp4 / .webm) from the Google Maps
    'Videos' category tab.

    Returns the number of video files successfully downloaded.
    """
    os.makedirs(videos_dir, exist_ok=True)
    downloaded = 0
    seen_video_urls: set = set()
    intercepted: list = []

    def _on_response(response):
        try:
            url = response.url
            ct = (response.headers.get('content-type') or '').lower()
            is_video = (
                'video/' in ct
                or url.lower().endswith('.mp4')
                or url.lower().endswith('.webm')
                or ('googleusercontent.com' in url and
                    any(x in url.lower() for x in ['=m3', '=m4', 'video', '.mp4', '.webm']))
            )
            if is_video:
                clean = re.sub(r'[?&](?:token|auth|sig|exp)[^&]*', '', url)
                if clean not in seen_video_urls:
                    seen_video_urls.add(clean)
                    intercepted.append(url)
                    logging.info(f"  🎥 (net intercept) {url[:90]}…")
        except Exception:
            pass

    page.on('response', _on_response)

    try:
        for label in ["Photos", "Photo", "All photos"]:
            if click_tab(page, label):
                break
        page.wait_for_timeout(3000)

        tab_clicked = False
        for sel in [
            '//button[@role="tab"][normalize-space()="Videos"]',
            '//div[@role="tab"][normalize-space()="Videos"]',
            '//button[contains(., "Videos")]',
            '//div[contains(., "Videos")][@role="tab"]',
        ]:
            try:
                loc = page.locator(sel)
                if loc.count() > 0:
                    loc.first.click(force=True)
                    page.wait_for_timeout(3000)
                    tab_clicked = True
                    break
            except Exception:
                continue

        if not tab_clicked:
            logging.warning("⚠ 'Videos' tab not found — no videos to download")
            return 0

        for _ in range(3):
            page.mouse.wheel(0, 2000)
            page.wait_for_timeout(800)
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(500)

        thumb_selectors = [
            'button[data-photo-index]',
            'button[jsaction*="click"][style*="googleusercontent"]',
            'div[role="button"][style*="googleusercontent"]',
        ]
        thumbnails = []
        for sel in thumb_selectors:
            found = page.query_selector_all(sel)
            if found:
                thumbnails = found
                logging.info(f"  🎞 Found {len(thumbnails)} thumbnail(s) via '{sel}'")
                break

        thumbnails = thumbnails[:20]
        if not thumbnails:
            logging.info("  ℹ No video thumbnails found in Videos tab")
        else:
            logging.info(f"🎬 Attempting to open {len(thumbnails)} video thumbnail(s)…")

        already_have: set = set()
        consecutive_misses = 0

        for idx, thumb in enumerate(thumbnails):
            try:
                thumb.scroll_into_view_if_needed()
                thumb.click(force=True)
                page.wait_for_timeout(1500)

                video_url = page.evaluate("""
                () => {
                    const v = document.querySelector('video[src]');
                    if (v && v.src && !v.src.startsWith('blob:')) return v.src;
                    const s = document.querySelector('video source[src]');
                    if (s && s.src && !s.src.startsWith('blob:')) return s.src;
                    return null;
                }
                """)

                if video_url and video_url not in seen_video_urls and video_url not in already_have:
                    consecutive_misses = 0
                    already_have.add(video_url)
                    logging.info(f"  🎥 (DOM) #{idx+1}: {video_url[:90]}…")
                    ext = 'webm' if 'webm' in video_url.lower() else 'mp4'
                    dest = os.path.join(videos_dir, f'{downloaded + 1:04d}.{ext}')
                    if _download_video(video_url, dest):
                        downloaded += 1
                        seen_video_urls.add(video_url)
                        logging.info(f"  ✅ Saved video #{downloaded}: {os.path.basename(dest)}")
                else:
                    consecutive_misses += 1
                    if consecutive_misses >= 3:
                        logging.info("  ℹ 3 consecutive non-video clicks — stopping early")
                        page.keyboard.press('Escape')
                        break

                page.wait_for_timeout(600)
                page.keyboard.press('Escape')
                page.wait_for_timeout(400)

            except Exception as e:
                logging.debug(f"  ⚠ Error on thumbnail #{idx+1}: {e}")
                try:
                    page.keyboard.press('Escape')
                except Exception:
                    pass
                continue

        remaining = [u for u in intercepted if u not in seen_video_urls]
        if remaining:
            logging.info(f"🎬 Downloading {len(remaining)} fallback-intercepted video(s)…")
        for video_url in remaining:
            seen_video_urls.add(video_url)
            ext = 'webm' if 'webm' in video_url.lower() else 'mp4'
            dest = os.path.join(videos_dir, f'{downloaded + 1:04d}.{ext}')
            if _download_video(video_url, dest):
                downloaded += 1
                logging.info(f"  ✅ Saved video #{downloaded}: {os.path.basename(dest)}")

    finally:
        page.remove_listener('response', _on_response)

    if downloaded == 0:
        logging.warning(
            "⚠ No actual videos downloaded — Google Maps may serve videos "
            "as blob: streams that can't be captured this way."
        )
    else:
        logging.info(f"🎬 Total videos downloaded: {downloaded}")

    return downloaded
