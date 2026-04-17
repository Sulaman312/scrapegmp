import logging
import re
import hashlib
import os
import json
import time
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
from datetime import datetime

from playwright.sync_api import Page

from scraper.tab_extractors import click_tab


REVIEW_CARD_SELECTOR = ', '.join([
    'div[data-review-id]',
    'div.jftiEf',
])


def _normalize_review_text(value: str) -> str:
    return re.sub(r'\s+', ' ', (value or '').strip().lower())


def _normalize_review_value(value: str) -> str:
    return (value or '').strip().lower()


def _find_scrollable_panel(page: Page):
    """Find the best scrollable container for reviews in Maps UI variants."""
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
                is_scrollable = candidate.evaluate(
                    "el => (el.scrollHeight - el.clientHeight) > 120"
                )
                if is_scrollable:
                    return candidate, sel
            except Exception:
                continue
    return None, ""


def _review_elements(page: Page):
    """Return review card elements for both old and new Maps DOMs."""
    return page.locator(REVIEW_CARD_SELECTOR).all()


def _debug_enabled() -> bool:
    return os.getenv('SCRAPER_DEBUG_REVIEWS', '0').strip().lower() in {'1', 'true', 'yes', 'on'}


def _debug_screenshot_enabled() -> bool:
    return os.getenv('SCRAPER_DEBUG_REVIEWS_SCREENSHOT', '0').strip().lower() in {'1', 'true', 'yes', 'on'}


def _dump_review_debug(page: Page, debug_dir: str | None, stage: str):
    if not debug_dir or not _debug_enabled():
        return

    try:
        os.makedirs(debug_dir, exist_ok=True)
        stamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')
        safe_stage = re.sub(r'[^a-zA-Z0-9_-]+', '_', stage).strip('_') or 'stage'
        base_name = f"{stamp}_{safe_stage}"

        html_path = os.path.join(debug_dir, f"{base_name}.html")
        meta_path = os.path.join(debug_dir, f"{base_name}.json")

        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(page.content())

        meta = {
            'stage': stage,
            'url': page.url,
            'review_cards_visible': page.locator(REVIEW_CARD_SELECTOR).count(),
            'feed_nodes': page.locator('div[role="feed"]').count(),
            'limited_view_mode': _is_limited_view_mode(page),
            'timestamp_utc': datetime.utcnow().isoformat() + 'Z',
        }
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        if _debug_screenshot_enabled():
            png_path = os.path.join(debug_dir, f"{base_name}.png")
            page.screenshot(path=png_path, full_page=True)

        logging.info(f"🧪 Review debug snapshot saved: {html_path}")
    except Exception as e:
        logging.warning(f"⚠ Failed to save review debug snapshot at '{stage}': {e}")


def _open_reviews_feed_surface(page: Page) -> bool:
    """Best-effort open for actual reviews list surface (not write-review actions)."""
    selectors = [
        'button[aria-label*=" reviews" i]',
        'button[aria-label*="review" i][jsaction]',
        'div[role="tab"][aria-label*="review" i]',
        'button:has-text("reviews")',
        'button:has-text("Reviews")',
        'button:has-text("avis")',
        'button:has-text("reseñas")',
        'button:has-text("rezension")',
    ]

    blocked = (
        'write a review', 'post a review', 'add a review', 'be the first',
        'donner un avis', 'écrire un avis', 'escribir una reseña',
    )

    for sel in selectors:
        try:
            loc = page.locator(sel)
            count = loc.count()
            for idx in range(count):
                candidate = loc.nth(idx)
                label = (candidate.get_attribute('aria-label') or candidate.inner_text() or '').strip().lower()
                if not label:
                    continue
                if any(b in label for b in blocked):
                    continue
                if 'review' not in label and 'reviews' not in label and 'avis' not in label and 'reseñ' not in label and 'rezension' not in label:
                    continue
                candidate.click(force=True)
                page.wait_for_timeout(2200)
                if page.locator(REVIEW_CARD_SELECTOR).count() > 0:
                    return True
        except Exception:
            continue

    # JS fallback: choose best review-list candidate by score.
    try:
        clicked = page.evaluate(
            """
            () => {
                const blocked = ['write a review','post a review','add a review','be the first','donner un avis','écrire un avis','escribir una reseña'];
                const isReviewText = (t) => /review|reviews|avis|reseñ|rezension|avalia|отзы|评价|리뷰/i.test(t || '');
                const nodes = Array.from(document.querySelectorAll('button,[role="tab"],a'));
                let best = null;
                let bestScore = -1;
                for (const el of nodes) {
                    const txt = (((el.getAttribute('aria-label') || '') + ' ' + (el.textContent || '')).trim());
                    if (!txt) continue;
                    const low = txt.toLowerCase();
                    if (!isReviewText(low)) continue;
                    if (blocked.some(b => low.includes(b))) continue;
                    let score = 0;
                    if (/\\d/.test(low)) score += 5;
                    if (/(reviews|review|avis|reseñ|rezension)/i.test(low)) score += 3;
                    if (el.getAttribute('role') === 'tab') score += 2;
                    if (score > bestScore) {
                        best = el;
                        bestScore = score;
                    }
                }
                if (!best) return false;
                best.click();
                return true;
            }
            """
        )
        if clicked:
            page.wait_for_timeout(2200)
            return page.locator(REVIEW_CARD_SELECTOR).count() > 0
    except Exception:
        pass

    return False


def _is_limited_view_mode(page: Page) -> bool:
    """Detect Google Maps limited-view mode where full review feed is unavailable."""
    checks = [
        'text="You\'re seeing a limited view of Google Maps"',
        'button[aria-label*="limited view" i]',
        'button:has-text("Learn more about limited view")',
    ]
    for sel in checks:
        try:
            if page.locator(sel).count() > 0:
                return True
        except Exception:
            continue
    return False


def _dismiss_cookie_banners(page: Page) -> None:
    for sel in [
        'button:has-text("Accept all")',
        'button:has-text("I agree")',
        '//button[contains(., "Accept")]',
        'form[action*="consent"] button',
    ]:
        try:
            loc = page.locator(sel)
            if loc.count() > 0:
                loc.first.click()
                page.wait_for_timeout(1200)
                break
        except Exception:
            continue


def _build_limited_view_recovery_urls(current_url: str) -> list[str]:
    urls: list[str] = []
    try:
        parsed = urlparse(current_url)
        if not parsed.scheme or not parsed.netloc:
            return urls

        params = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k.lower() not in {'entry', 'g_ep', 'dg'}]
        cleaned_query = urlencode(params)
        cleaned = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, cleaned_query, ''))
        if cleaned and cleaned != current_url:
            urls.append(cleaned)

        no_query = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, '', ''))
        if no_query and no_query not in urls and no_query != current_url:
            urls.append(no_query)

        if no_query:
            with_hl = f"{no_query}?hl=en"
            if with_hl not in urls and with_hl != current_url:
                urls.append(with_hl)
    except Exception:
        return urls
    return urls


def _try_recover_from_limited_view(page: Page, debug_dir: str | None = None) -> bool:
    current_url = page.url or ''
    candidates = _build_limited_view_recovery_urls(current_url)
    if not candidates:
        return False

    for idx, target in enumerate(candidates, start=1):
        try:
            logging.info(f"🔁 Limited-view recovery attempt {idx}/{len(candidates)}: {target}")
            page.goto(target, timeout=60000)
            page.wait_for_timeout(3500)
            _dismiss_cookie_banners(page)
            _dump_review_debug(page, debug_dir, f'05a_recovery_nav_{idx}')

            if not _is_limited_view_mode(page):
                logging.info("✅ Limited-view banner cleared after recovery navigation")
                return True
        except Exception as e:
            logging.warning(f"⚠ Limited-view recovery navigation failed: {e}")

    return False


def extract_all_reviews(page: Page, max_reviews: int = 20, debug_dir: str | None = None) -> list:
    """
    Click the Reviews tab then scroll through the reviews panel until no new
    reviews appear, extracting every review found.
    Returns a list of dicts (one per review).
    """
    reviews = []
    seen_ids: set = set()
    seen_signatures: set = set()

    _dump_review_debug(page, debug_dir, '00_start_before_open')

    pre_visible = page.locator(REVIEW_CARD_SELECTOR).count()
    if pre_visible > 0:
        logging.info(f"✅ Reviews appear already visible ({pre_visible} cards) — skipping tab click")
    else:
        logging.info("🔍 Attempting to open Reviews tab...")
        if click_tab(page, "Reviews"):
            logging.info("  ✅ Reviews tab clicked successfully")
        else:
            logging.warning("  ⚠ Reviews tab click failed")
        page.wait_for_timeout(2500)
        _dump_review_debug(page, debug_dir, '01_after_tab_click')

        if page.locator(REVIEW_CARD_SELECTOR).count() == 0:
            logging.info("🔁 Attempting dedicated reviews-feed opener...")
            if _open_reviews_feed_surface(page):
                logging.info("  ✅ Reviews feed surface opened")
            else:
                logging.warning("  ⚠ Dedicated reviews-feed opener could not confirm visible review cards")
            _dump_review_debug(page, debug_dir, '02_after_dedicated_feed_open')

    if page.locator(REVIEW_CARD_SELECTOR).count() == 0 and _is_limited_view_mode(page):
        logging.warning(
            "⚠ Google Maps is in limited-view mode for this page; attempting URL-based recovery."
        )
        _dump_review_debug(page, debug_dir, '05_limited_view_mode_detected')

        recovered = _try_recover_from_limited_view(page, debug_dir=debug_dir)
        if recovered:
            logging.info("🔁 Re-trying reviews feed open after limited-view recovery...")
            if click_tab(page, "Reviews"):
                logging.info("  ✅ Reviews tab clicked after recovery")
                page.wait_for_timeout(2200)
            if page.locator(REVIEW_CARD_SELECTOR).count() == 0 and _open_reviews_feed_surface(page):
                logging.info("  ✅ Dedicated reviews-feed opener succeeded after recovery")
            _dump_review_debug(page, debug_dir, '05b_after_recovery_retry')

        if page.locator(REVIEW_CARD_SELECTOR).count() == 0 and _is_limited_view_mode(page):
            logging.warning(
                "⚠ Limited-view mode persists after recovery attempts; review feed unavailable in DOM."
            )
            return reviews

    scrollable, panel_sel = _find_scrollable_panel(page)
    if scrollable:
        logging.info(f"✅ Reviews panel found: {panel_sel}")
    else:
        logging.warning("⚠ No scrollable reviews panel detected; falling back to page wheel")
    _dump_review_debug(page, debug_dir, '03_after_panel_detect')

    try:
        page.wait_for_selector(REVIEW_CARD_SELECTOR, timeout=5000)
    except Exception:
        logging.info("ℹ Reviews not yet visible after initial tab open; continuing with scroll-based loading")

    # Initial scrolling to load more reviews - scroll aggressively
    logging.info("📜 Performing initial scroll to load reviews...")
    initial_scrolls = 5
    visible_target = max(max_reviews * 2, max_reviews + 5)
    for i in range(initial_scrolls):
        if scrollable:
            try:
                scrollable.evaluate("el => el.scrollBy(0, 5000)")
            except Exception:
                page.mouse.wheel(0, 5000)
        else:
            page.mouse.wheel(0, 5000)
        page.wait_for_timeout(1200)

        # Check how many reviews are visible after this scroll
        review_count = page.locator(REVIEW_CARD_SELECTOR).count()
        logging.info(f"  Scroll {i+1}/{initial_scrolls} - Reviews visible: {review_count}")
        if review_count >= visible_target:
            logging.info(
                f"✅ Review card target reached during preload ({review_count} >= {visible_target}); stopping early"
            )
            break
    logging.info("📜 Initial scroll complete - waiting for reviews to load...")
    page.wait_for_timeout(1200)
    _dump_review_debug(page, debug_dir, '04_after_initial_scrolls')

    no_new_count = 0
    max_seconds = float(os.getenv('SCRAPER_REVIEWS_MAX_SECONDS', '180'))
    deadline = time.monotonic() + max_seconds
    last_scan_end = 0  # Track where we left off scanning

    while len(reviews) < max_reviews and no_new_count < 6:
        if time.monotonic() > deadline:
            logging.warning(f"⚠ Review extraction time limit reached ({int(max_seconds)}s), stopping early")
            break

        review_locator = page.locator(REVIEW_CARD_SELECTOR)
        visible_count = review_locator.count()
        remaining = max_reviews - len(reviews)

        # Scan all visible reviews, or at least a reasonable window past where we left off
        scan_start = last_scan_end
        scan_end = min(visible_count, max(last_scan_end + 40, visible_count))

        if scan_start >= visible_count:
            # We've scanned all visible reviews, need to scroll for more
            no_new_count += 1
            logging.info(f"⚠ No new review cards to scan ({no_new_count}/6 attempts) - scanned up to {scan_start}/{visible_count}")
            page.wait_for_timeout(1200)
            continue

        logging.info(f"🔎 Parsing reviews: visible={visible_count}, scanning={scan_start}-{scan_end}, remaining={remaining}")
        new_this_pass = 0

        for idx in range(scan_start, scan_end):
            # Check if we've reached the limit
            if len(reviews) >= max_reviews:
                logging.info(f"✅ Reached maximum reviews ({max_reviews}) - stopping collection")
                break

            if time.monotonic() > deadline:
                logging.warning(f"⚠ Review extraction time limit reached during parsing ({int(max_seconds)}s)")
                break

            elem = review_locator.nth(idx)

            try:
                # Quick check for reviews with explicit IDs
                quick_review_id = elem.get_attribute('data-review-id') or elem.get_attribute('id')
                if quick_review_id and quick_review_id in seen_ids:
                    continue

                # Get minimal identifying info to create fingerprint BEFORE clicking "More"
                author = ""
                for sel in ['div.d4r55', 'button.al6Kxe', 'a.al6Kxe']:
                    try:
                        e = elem.locator(sel)
                        if e.count() > 0:
                            author = e.first.inner_text().strip()
                            break
                    except Exception:
                        pass

                date = ""
                for sel in ['span.rsqaWe', 'span[class*="rsqaWe"]']:
                    try:
                        e = elem.locator(sel)
                        if e.count() > 0:
                            date = e.first.inner_text().strip()
                            break
                    except Exception:
                        pass

                # Get visible text snippet (without clicking More yet)
                text_snippet = ""
                for sel in ['span.wiI7pd', 'div.MyEned span', 'span[class*="wiI7pd"]']:
                    try:
                        e = elem.locator(sel)
                        if e.count() > 0:
                            text_snippet = e.first.inner_text().strip()[:120]
                            break
                    except Exception:
                        pass

                # Create fingerprint ID early to check if already seen
                if not quick_review_id:
                    fingerprint = f"{author}|{date}|{text_snippet}"
                    quick_review_id = hashlib.md5(fingerprint.encode('utf-8', errors='ignore')).hexdigest()
                    if quick_review_id in seen_ids:
                        continue

                # Now safe to get full data for NEW reviews only
                author_url = ""
                try:
                    href_elem = elem.locator('a[href*="maps/contrib"]')
                    if href_elem.count() > 0:
                        author_url = href_elem.first.get_attribute('href') or ""
                except Exception:
                    pass

                rating = 0.0
                # Try extracting rating from star aria-labels first
                for sel in ['span.kvMYJc', 'span[role="img"][aria-label*="star"]', 'span[role="img"]']:
                    try:
                        e = elem.locator(sel)
                        if e.count() > 0:
                            aria = e.first.get_attribute('aria-label') or ""
                            m = re.search(r'(\d+(?:\.\d+)?)', aria)
                            if m:
                                rating = float(m.group(1))
                                break
                    except Exception:
                        pass

                # Fallback: Try extracting from text format like "5/5", "4/5", etc.
                if rating == 0.0:
                    for sel in ['span.fontBodyLarge.fzvQIb', 'span.fzvQIb', 'span[class*="fzvQIb"]']:
                        try:
                            e = elem.locator(sel)
                            if e.count() > 0:
                                rating_text = e.first.inner_text().strip()
                                # Parse "X/Y" format, extract numerator (X)
                                m = re.match(r'(\d+(?:\.\d+)?)\s*/\s*\d+', rating_text)
                                if m:
                                    rating = float(m.group(1))
                                    break
                        except Exception:
                            pass

                # Get full text (click More if needed)
                text = text_snippet
                if not text:
                    try:
                        more_btn = elem.locator('button.w8nwRe')
                        if more_btn.count() > 0:
                            more_btn.first.click(force=True, timeout=700)
                            page.wait_for_timeout(80)
                            e = elem.locator('span.wiI7pd')
                            if e.count() > 0:
                                text = e.first.inner_text().strip()
                    except Exception:
                        pass
                elif text_snippet:
                    # We had a snippet, try to get full text by clicking More
                    try:
                        more_btn = elem.locator('button.w8nwRe')
                        if more_btn.count() > 0:
                            more_btn.first.click(force=True, timeout=700)
                            page.wait_for_timeout(80)
                            e = elem.locator('span.wiI7pd')
                            if e.count() > 0:
                                full_text = e.first.inner_text().strip()
                                if full_text and len(full_text) > len(text):
                                    text = full_text
                    except Exception:
                        pass

                local_guide = ""
                try:
                    lg = elem.locator('span[class*="RfnDt"]')
                    if lg.count() > 0:
                        local_guide = lg.first.inner_text().strip()
                except Exception:
                    pass

                likes = 0
                try:
                    like_elem = elem.locator('span[class*="pkWtMe"]')
                    if like_elem.count() > 0:
                        like_text = like_elem.first.inner_text().strip()
                        m = re.search(r'\d+', like_text)
                        if m:
                            likes = int(m.group())
                except Exception:
                    pass

                review_images = []
                try:
                    imgs = elem.locator('img[src*="googleusercontent.com"]').all()
                    for img in imgs:
                        src = img.get_attribute('src') or ''
                        base = re.sub(r'=.*$', '', src)
                        if base and base not in review_images:
                            review_images.append(base + '=s800')
                except Exception:
                    pass

                # Use the quick_review_id we already created/checked earlier
                review_id = quick_review_id

                if not text:
                    continue

                normalized_author = _normalize_review_value(author)
                normalized_date = _normalize_review_value(date)
                normalized_text = _normalize_review_text(text)
                rating_key = f"{rating:.1f}"

                # Build robust content signatures to collapse duplicate/partial cards.
                signature_candidates = []
                if normalized_author and normalized_date and normalized_text:
                    signature_candidates.append(f"a|{normalized_author}|{normalized_date}|{normalized_text}")
                if normalized_date and normalized_text:
                    signature_candidates.append(f"d|{normalized_date}|{rating_key}|{normalized_text}")
                if len(normalized_text) >= 40:
                    signature_candidates.append(f"t|{rating_key}|{normalized_text}")

                if any(sig in seen_signatures for sig in signature_candidates):
                    continue

                # Incomplete cards are often nested duplicates of real cards.
                if not normalized_author and not normalized_date and review_id and len(normalized_text) < 40:
                    continue

                # Final safety check (should not hit this due to early check)
                if review_id in seen_ids:
                    continue

                seen_ids.add(review_id)
                for sig in signature_candidates:
                    seen_signatures.add(sig)
                new_this_pass += 1

                reviews.append({
                    'review_id': review_id,
                    'author_name': author,
                    'author_url': author_url,
                    'rating': rating,
                    'date': date,
                    'text': text,
                    'local_guide': local_guide,
                    'likes': likes,
                    'images': '; '.join(review_images),
                })

                if len(reviews) % 10 == 0:
                    logging.info(f"💬 Parsed {len(reviews)} reviews so far")

            except Exception as e:
                logging.debug(f"Error parsing review: {e}")
                continue

        # Update where we left off scanning
        last_scan_end = scan_end

        # Check if we've reached the limit after processing all elements
        if len(reviews) >= max_reviews:
            logging.info(f"✅ Collected {len(reviews)} reviews - reached maximum, stopping")
            break

        if new_this_pass == 0:
            no_new_count += 1
            logging.info(f"⚠ No new reviews ({no_new_count}/6 attempts)")
        else:
            no_new_count = 0
            logging.info(f"💬 Reviews collected so far: {len(reviews)}")

        if scrollable:
            try:
                scrollable.evaluate("el => el.scrollBy(0, 3000)")
            except Exception:
                page.mouse.wheel(0, 3000)
        else:
            page.mouse.wheel(0, 3000)
        page.wait_for_timeout(2000)

    logging.info(f"✅ Total reviews extracted: {len(reviews)}")
    if not reviews:
        _dump_review_debug(page, debug_dir, '99_no_reviews_extracted')
    return reviews
