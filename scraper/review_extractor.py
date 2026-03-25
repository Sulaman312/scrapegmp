import logging
import re

from playwright.sync_api import Page

from scraper.tab_extractors import click_tab


def extract_all_reviews(page: Page, max_reviews: int = 20) -> list:
    """
    Click the Reviews tab then scroll through the reviews panel until no new
    reviews appear, extracting every review found.
    Returns a list of dicts (one per review).
    """
    reviews = []
    seen_ids: set = set()

    click_tab(page, "Reviews")
    page.wait_for_timeout(2500)

    scrollable = None
    for sel in ['div.m6QErb.DxyBCb.kA9KIf.dS8AEf', 'div.m6QErb.DxyBCb', 'div.m6QErb']:
        if page.locator(sel).count() > 0:
            scrollable = page.locator(sel).first
            logging.info(f"✅ Reviews panel found: {sel}")
            break

    no_new_count = 0
    while len(reviews) < max_reviews and no_new_count < 6:
        review_elems = page.locator('div[data-review-id]').all()
        new_this_pass = 0

        for elem in review_elems:
            try:
                review_id = elem.get_attribute('data-review-id')
                if not review_id or review_id in seen_ids:
                    continue
                seen_ids.add(review_id)
                new_this_pass += 1

                try:
                    more_btn = elem.locator('button.w8nwRe')
                    if more_btn.count() > 0:
                        more_btn.first.click(force=True)
                        page.wait_for_timeout(300)
                except Exception:
                    pass

                author = ""
                for sel in ['div.d4r55', 'button.al6Kxe', 'a.al6Kxe']:
                    try:
                        e = elem.locator(sel)
                        if e.count() > 0:
                            author = e.first.inner_text().strip()
                            break
                    except Exception:
                        pass

                author_url = ""
                try:
                    href_elem = elem.locator('a[href*="maps/contrib"]')
                    if href_elem.count() > 0:
                        author_url = href_elem.first.get_attribute('href') or ""
                except Exception:
                    pass

                rating = 0.0
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

                date = ""
                for sel in ['span.rsqaWe', 'span[class*="rsqaWe"]']:
                    try:
                        e = elem.locator(sel)
                        if e.count() > 0:
                            date = e.first.inner_text().strip()
                            break
                    except Exception:
                        pass

                text = ""
                for sel in ['span.wiI7pd', 'div.MyEned span', 'span[class*="wiI7pd"]']:
                    try:
                        e = elem.locator(sel)
                        if e.count() > 0:
                            text = e.first.inner_text().strip()
                            break
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

            except Exception as e:
                logging.debug(f"Error parsing review: {e}")
                continue

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
    return reviews
