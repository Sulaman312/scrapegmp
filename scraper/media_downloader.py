import logging
import os
import re
from io import BytesIO

import requests
from PIL import Image
from playwright.sync_api import Page

from scraper.tab_extractors import click_tab
from scraper.utils import sanitize_filename


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
                base = re.sub(r'=.*$', '', url)
                if base and base not in seen_base_urls:
                    seen_base_urls.add(base)
                    cat = current_category[0]
                    category_urls.setdefault(cat, []).append(base)
        except Exception:
            pass

    page.on('response', _on_response)

    try:
        photos_opened = False
        for label in ["Photos", "Photo", "All photos", "See photos",
                       "Fotos", "Foto", "Alle Fotos", "Photos & vidéos", "Galerie"]:
            if click_tab(page, label):
                photos_opened = True
                break

        if not photos_opened:
            for sel in [
                '//button[contains(@aria-label, "photo")]',
                '//button[contains(@aria-label, "Photo")]',
                '//button[contains(@aria-label, "Foto")]',
                '//a[contains(@aria-label, "photo")]',
                '//div[@class="RZ66Rb YU2qld"]',
            ]:
                try:
                    if page.locator(sel).count() > 0:
                        page.locator(sel).first.click(force=True)
                        page.wait_for_timeout(3000)
                        photos_opened = True
                        break
                except Exception:
                    continue

        if not photos_opened:
            logging.warning("⚠ Could not open Photos panel")

        page.wait_for_timeout(4000)

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
            while no_new < 5 and scrolls < 100:
                page.mouse.wheel(0, 3000)
                page.wait_for_timeout(2000)
                scrolls += 1

                _dom_scan_images(page, seen_base_urls, category, category_urls)

                cur_count = sum(len(v) for v in category_urls.values())
                if cur_count > prev_count:
                    logging.info(f"    📸 {cur_count} URLs captured so far")
                    prev_count = cur_count
                    no_new = 0
                else:
                    no_new += 1

            _dom_scan_images(page, seen_base_urls, category, category_urls)
            cat_count = len(category_urls.get(category, []))
            logging.info(f"  ✅ '{category}': {cat_count} photo URLs found")

        extra = _dom_scan_images(page, seen_base_urls, "All", category_urls)
        if extra:
            logging.info(f"📸 Final DOM pass added {extra} extra URLs")

    finally:
        page.remove_listener('response', _on_response)

    total_found = sum(len(v) for v in category_urls.values())
    logging.info(f"📷 Downloading {total_found} unique place photos …")

    for cat, urls in category_urls.items():
        cat_dir = os.path.join(images_dir, sanitize_filename(cat))
        os.makedirs(cat_dir, exist_ok=True)
        for base in urls:
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

        thumbnails = thumbnails[:10]
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
