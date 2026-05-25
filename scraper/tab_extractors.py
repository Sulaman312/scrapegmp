import logging
import re

from playwright.sync_api import Page


def click_tab(page: Page, tab_name: str) -> bool:
    """Click a named tab in the Google Maps place panel.

    Tries the supplied name plus all known localisations so the scraper works
    regardless of the browser / Maps UI language.
    """
    _ALIASES: dict[str, list[str]] = {
        "Reviews":  ["Reviews", "Avis", "Rezensionen", "Reseñas", "Recensioni",
                     "Avaliações", "Отзывы", "评价", "리뷰"],
        "Photos":   ["Photos", "Fotos", "Foto", "Фото", "相片", "사진"],
        "Overview": ["Overview", "Aperçu", "Übersicht", "Descripción general",
                     "Panoramica", "Visão geral"],
        "About":    ["About", "À propos", "Über", "Acerca de", "Informazioni",
                     "Sobre", "О заведении"],
        "Menu":     ["Menu", "Menü", "Menú", "Меню"],
        "Updates":  ["Updates", "Mises à jour", "Actualizaciones"],
    }
    candidates = _ALIASES.get(tab_name, [tab_name])
    logging.info(f"🔍 Looking for '{tab_name}' tab - will try: {candidates}")

    # Playwright best-practice path: role/name based locator first.
    # This is generally more stable than class/XPath selectors.
    if tab_name == "Reviews":
        def _is_valid_reviews_control(text: str) -> bool:
            t = (text or "").strip().lower()
            if not t:
                return False
            blocked = [
                "write a review", "post a review", "add a review", "be the first",
                "donner un avis", "écrire un avis", "escribir una reseña",
                "eine rezension", "dejar una reseña", "rate and review",
            ]
            if any(b in t for b in blocked):
                return False

            review_words = [
                "reviews", "review", "avis", "rezension", "reseña", "recension",
                "avalia", "отзы", "评价", "리뷰",
            ]
            return any(w in t for w in review_words)

        role_patterns = [
            re.compile(r"review", re.IGNORECASE),
            re.compile(r"avis", re.IGNORECASE),
            re.compile(r"rezension", re.IGNORECASE),
            re.compile(r"reseña", re.IGNORECASE),
            re.compile(r"recension", re.IGNORECASE),
            re.compile(r"avalia", re.IGNORECASE),
            re.compile(r"отзы", re.IGNORECASE),
            re.compile(r"리뷰", re.IGNORECASE),
            re.compile(r"评价", re.IGNORECASE),
            re.compile(r"\d+[\s\u00a0]*(review|avis|reseña|rezension)", re.IGNORECASE),
        ]
        for pattern in role_patterns:
            try:
                tab_loc = page.get_by_role("tab", name=pattern)
                if tab_loc.count() > 0:
                    for idx in range(tab_loc.count()):
                        candidate = tab_loc.nth(idx)
                        label = (candidate.get_attribute("aria-label") or candidate.inner_text() or "").strip()
                        if not _is_valid_reviews_control(label):
                            continue
                        candidate.click(force=True)
                        page.wait_for_timeout(2200)
                        logging.info(f"  ✅ Clicked Reviews tab via role=tab name~/{pattern.pattern}/")
                        return True
            except Exception:
                pass

            try:
                btn_loc = page.get_by_role("button", name=pattern)
                if btn_loc.count() > 0:
                    for idx in range(btn_loc.count()):
                        candidate = btn_loc.nth(idx)
                        label = (candidate.get_attribute("aria-label") or candidate.inner_text() or "").strip()
                        if not _is_valid_reviews_control(label):
                            continue
                        candidate.click(force=True)
                        page.wait_for_timeout(2200)
                        logging.info(f"  ✅ Clicked Reviews button via role=button name~/{pattern.pattern}/")
                        return True
            except Exception:
                pass

    # Special-case fallback: on many Maps UIs, the reviews entry appears as
    # a dynamic "<number> reviews" button rather than a literal "Reviews" label.
    if tab_name == "Reviews":
        review_count_selectors = [
            'button[aria-label*="reviews" i]',
            'div[role="tab"][aria-label*="review" i]',
            'button[role="tab"][aria-label*="review" i]',
            'div[role="tab"][aria-label*="reviews" i]',
            'button:has-text("reviews")',
            'button:has-text("Reviews")',
            'button:has-text("avis")',
            'button:has-text("reseñas")',
            'button:has-text("rezension")',
            'button:has-text("avaliações")',
            'button:has-text("recensioni")',
            'button:has-text("отзывы")',
            'button:has-text("리뷰")',
            'button:has-text("评价")',
            'text=/\\d+[.,]?\\d*\\s*reviews?/i',
            'text=/\\d+[.,]?\\d*\\s*avis/i',
            'text=/\\d+[.,]?\\d*\\s*reseñas/i',
            'text=/\\d+[.,]?\\d*\\s*rezension/i',
        ]
        for sel in review_count_selectors:
            try:
                loc = page.locator(sel)
                if loc.count() > 0:
                    for idx in range(loc.count()):
                        candidate = loc.nth(idx)
                        label = (candidate.get_attribute("aria-label") or candidate.inner_text() or "").strip()
                        if not _is_valid_reviews_control(label):
                            continue
                        candidate.click(force=True)
                        page.wait_for_timeout(2500)
                        logging.info(f"  ✅ Clicked dynamic Reviews entry via selector: {sel}")
                        return True
            except Exception:
                continue

    for name in candidates:
        selectors = [
            f'//div[@role="tablist"]//button[contains(@aria-label, "{name}")]',
            f'//button[@role="tab"][contains(@aria-label, "{name}")]',
            f'//button[contains(@aria-label, "{name}")]',
            f'//div[@role="tab"][contains(@aria-label, "{name}")]',
            f'//button[@role="tab"][contains(., "{name}")]',
            f'//div[@role="tab"][contains(., "{name}")]',
            f'//button[contains(., "{name}")]',
        ]
        for sel in selectors:
            try:
                elem = page.locator(sel)
                count = elem.count()
                if count > 0:
                    logging.info(f"  ✅ Found {count} element(s) for '{name}' with selector: {sel[:60]}...")
                    elem.first.click(force=True)
                    page.wait_for_timeout(2000)
                    logging.info(f"  ✅ Clicked '{name}' tab (requested: '{tab_name}')")
                    return True
                else:
                    logging.debug(f"  ❌ No elements for '{name}' with selector: {sel[:60]}...")
            except Exception as e:
                logging.debug(f"  ⚠ Exception for selector '{sel[:60]}...': {e}")
                continue

    # Last-resort JS text matcher for role=tab / button nodes.
    try:
        for name in candidates:
            clicked = page.evaluate(
                """
                (needle) => {
                    const n = (needle || '').toLowerCase();
                    const nodes = Array.from(document.querySelectorAll('button, [role="tab"]'));
                    for (const el of nodes) {
                        const txt = ((el.textContent || '') + ' ' + (el.getAttribute('aria-label') || '')).toLowerCase();
                        if (txt.includes(n)) {
                            el.click();
                            return true;
                        }
                    }
                    return false;
                }
                """,
                name,
            )
            if clicked:
                page.wait_for_timeout(2000)
                logging.info(f"  ✅ Clicked '{name}' tab using JS fallback")
                return True
    except Exception:
        pass

    logging.warning(f"⚠ Could not find '{tab_name}' tab (tried: {candidates})")
    return False


def _scroll_place_panel(page: Page, amount: int = 2000):
    """Scroll the left-side place-details panel (not the background map)."""
    page.evaluate(f"""
    () => {{
        const candidates = [
            document.querySelector('div.m6QErb.DxyBCb'),
            document.querySelector('div.m6QErb'),
            document.querySelector('[role="main"] [tabindex="-1"]'),
            document.querySelector('div[role="main"]'),
        ];
        for (const el of candidates) {{
            if (el && el.scrollHeight > el.clientHeight) {{
                el.scrollTop += {amount};
                return;
            }}
        }}
        window.scrollBy(0, {amount});
    }}
    """)


def extract_related_places(page: Page) -> list:
    """
    Scrape the 'People also search for' section from the Overview tab.
    Returns a list of dicts: name, place_type, rating, reviews_count, maps_url.
    """
    related = []
    try:
        for _ in range(10):
            _scroll_place_panel(page, 1500)
            page.wait_for_timeout(400)

        result = page.evaluate(r"""
        () => {
            const results = [];

            let container = null;
            for (const el of document.querySelectorAll('*')) {
                if (
                    el.children.length === 0 &&
                    (el.textContent.trim() === 'People also search for' ||
                     el.textContent.trim() === 'Also search for')
                ) {
                    container = el.closest('div[jsrenderer]') ||
                                el.parentElement?.parentElement?.parentElement;
                    break;
                }
            }

            const placeLinks = container
                ? container.querySelectorAll('a[href*="/maps/place/"]')
                : document.querySelectorAll('a[href*="/maps/place/"]');

            for (const a of placeLinks) {
                const href = a.href || '';
                if (!href || href.includes('dir/') || href.includes('search/')) continue;

                const nameEl = a.querySelector('div.qBF1Pd, div.NrDZNb, div.fontHeadlineSmall, [class*="fontHeadline"]');
                const name = nameEl ? nameEl.textContent.trim()
                                    : a.textContent.trim().slice(0, 60);
                if (!name || name.length < 2) continue;

                const typeEl    = a.querySelector('div.W4Efsd, [class*="fontBody"], div.UY7F9');
                const ratingEl  = a.querySelector('span.MW4etd, span[aria-label*="star"]');
                const reviewsEl = a.querySelector('span.UY7F9, span[aria-label*="review"]');

                results.push({
                    name:          name,
                    place_type:    typeEl    ? typeEl.textContent.trim()    : '',
                    rating:        ratingEl  ? ratingEl.textContent.trim()  : '',
                    reviews_count: reviewsEl ? reviewsEl.textContent.trim() : '',
                    maps_url:      href,
                });
            }
            return results;
        }
        """)

        if result:
            related = result
            logging.info(f"✅ Found {len(related)} related places")
        else:
            logging.info("ℹ 'People also search for' section not found or empty")

    except Exception as e:
        logging.warning(f"⚠ Could not extract related places: {e}")

    return related


def extract_web_results(page: Page) -> list:
    """
    Scrape the 'Web results' section from the Google Maps Overview tab.
    Returns a list of dicts: title, url, source, snippet.
    """
    results = []

    _EXTRACTOR_JS = r"""
    () => {
        function getRealUrl(href) {
            if (!href) return '';
            try {
                if (href.includes('/url?') || href.includes('google.com/url')) {
                    const u = new URL(href);
                    const q = u.searchParams.get('q') || u.searchParams.get('url');
                    if (q && q.startsWith('http')) return q;
                }
            } catch(e) {}
            return href;
        }

        function isInternal(href) {
            if (!href || !href.startsWith('http')) return true;
            return ['google.com/maps','google.com/search','goo.gl',
                    'support.google.com','policies.google.com',
                    'google.com/intl','google.com/help'].some(s => href.includes(s));
        }

        function extractCard(cardEl, seen) {
            let href = '';
            for (const a of cardEl.querySelectorAll('a[href]')) {
                const r = getRealUrl(a.href || '');
                if (!isInternal(r)) { href = r; break; }
            }
            if (!href) {
                for (const attr of ['data-url','data-href','data-value']) {
                    const v = cardEl.getAttribute(attr) || '';
                    if (v.startsWith('http') && !isInternal(v)) { href = v; break; }
                }
            }
            if (!href || seen.has(href)) return null;
            seen.add(href);

            const leaves = [];
            const walker = document.createTreeWalker(cardEl, NodeFilter.SHOW_TEXT, null);
            while (walker.nextNode()) {
                const t = walker.currentNode.textContent.trim();
                if (t.length > 2) leaves.push(t);
            }

            let title = '', snippet = '';
            for (const t of leaves) {
                if (t.startsWith('http') || t.includes(' › ') || t.includes('://')) continue;
                if (!title && t.length > 5) { title = t; }
                else if (!snippet && t.length > 20 && t !== title) { snippet = t; }
            }

            let host = '';
            try { host = new URL(href).hostname; } catch(e) {}
            return { title: title || host, url: href, source: host, snippet };
        }

        let headingEl = null;
        for (const el of document.querySelectorAll('*')) {
            if (el.children.length === 0 &&
                (el.textContent.trim() === 'Web results' ||
                 el.textContent.trim() === 'From the web')) {
                headingEl = el;
                break;
            }
        }
        if (!headingEl) return null;

        const mainPanel = document.querySelector('[role="main"]');
        let section = headingEl;
        while (section.parentElement && section.parentElement !== mainPanel) {
            section = section.parentElement;
            if (section.querySelectorAll('a[href]').length >= 3) break;
        }

        const seen = new Set();
        const results = [];

        for (const a of section.querySelectorAll('a[href]')) {
            let href = getRealUrl(a.href || '');
            if (isInternal(href)) continue;
            if (seen.has(href)) continue;
            const card = a.closest('[jsname]') || a.closest('[jsrenderer]') || a;
            const item = extractCard(card, seen);
            if (item) results.push(item);
        }

        for (const el of section.querySelectorAll('*')) {
            if (el.children.length > 0) continue;
            if (!el.textContent.includes('›')) continue;
            const card = el.closest('[jsname]') || el.closest('[jsrenderer]')
                       || el.parentElement?.parentElement?.parentElement;
            if (!card) continue;
            const item = extractCard(card, seen);
            if (item) results.push(item);
        }

        return results;
    }
    """

    try:
        click_tab(page, "Overview")
        page.wait_for_timeout(1000)

        found = False
        for step in range(12):
            _scroll_place_panel(page, 1500)
            page.wait_for_timeout(450)
            probe = page.evaluate(r"""
            () => {
                for (const el of document.querySelectorAll('*')) {
                    if (el.children.length === 0) {
                        const t = el.textContent.trim();
                        if (t === 'Web results' || t === 'From the web' ||
                            t === 'Résultats web' || t === 'Résultats depuis le web' ||
                            t === 'Web-Ergebnisse' || t === 'Webergebnisse')
                            return true;
                    }
                }
                return false;
            }
            """)
            if probe:
                found = True
                page.wait_for_timeout(800)
                break

        if not found:
            logging.info("ℹ 'Web results' section not visible (may require login — use --chrome-profile)")

        data = page.evaluate(_EXTRACTOR_JS)

        if data is None or data == []:
            if found:
                logging.info("ℹ 'Web results' heading found but no result cards extracted")
        elif data:
            results = data
            logging.info(f"✅ Found {len(results)} web results")

    except Exception as e:
        logging.warning(f"⚠ Could not extract web results: {e}")

    return results


def extract_review_keywords(page: Page) -> list:
    """
    Extract the review keyword/highlight chips shown at the top of the Reviews tab.
    Returns a list of keyword strings.
    """
    keywords = []
    try:
        click_tab(page, "Reviews")
        page.wait_for_timeout(1500)
        kw_data = page.evaluate(r"""
        () => {
            const results = [];
            const selectors = [
                'button.EBe2gf',
                'div[data-chip-value]',
                'div.m6QErb button[jsaction]',
                'button[data-value]',
            ];
            const seen = new Set();
            for (const sel of selectors) {
                for (const el of document.querySelectorAll(sel)) {
                    const t = (el.textContent || '').trim();
                    if (t && t.length > 2 && t.length < 60 && !seen.has(t)) {
                        if (!/^\d+$/.test(t) && t !== 'Sort' && t !== 'Filter') {
                            seen.add(t);
                            results.push(t);
                        }
                    }
                }
                if (results.length > 0) break;
            }
            for (const el of document.querySelectorAll('[data-topic-id], [jsdata*="mention"]')) {
                const t = (el.textContent || '').trim();
                if (t && t.length > 2 && t.length < 60 && !seen.has(t)) {
                    seen.add(t);
                    results.push(t);
                }
            }
            return results;
        }
        """) or []
        keywords = [k for k in kw_data if k]
        if keywords:
            logging.info(f"✅ Review keywords: {', '.join(keywords[:10])}")
        else:
            logging.info("ℹ No review keywords found")
    except Exception as e:
        logging.warning(f"⚠ Could not extract review keywords: {e}")
    return keywords


def extract_about_tab(page: Page) -> dict:
    """
    Scrape the 'About' tab of a Google Maps place.
    Returns a dict with:
      - attributes: dict of category_name → list of feature strings
      - social_links: list of {platform, url}
    """
    about = {'attributes': {}, 'social_links': []}
    try:
        if not click_tab(page, "About"):
            logging.info("ℹ 'About' tab not found")
            return about
        page.wait_for_timeout(2000)

        data = page.evaluate(r"""
        () => {
            const result = { attributes: {}, social_links: [] };

            const main = document.querySelector('[role="main"]') || document;
            const allHeadings = [];
            for (const el of main.querySelectorAll('*')) {
                if (el.children.length === 0) continue;
                const tag = el.tagName;
                const cls = el.className || '';
                if ((cls.includes('fontTitle') || cls.includes('fontHeadline')) &&
                    el.textContent.trim().length > 1 &&
                    el.textContent.trim().length < 60) {
                    allHeadings.push(el);
                }
            }

            for (const hEl of allHeadings) {
                const category = hEl.textContent.trim();
                if (!category) continue;
                const parent = hEl.parentElement;
                if (!parent) continue;
                const items = [];
                let inSection = false;
                for (const child of parent.children) {
                    if (child === hEl || child.contains(hEl)) { inSection = true; continue; }
                    if (!inSection) continue;
                    const childCls = child.className || '';
                    if (childCls.includes('fontTitle') || childCls.includes('fontHeadline')) break;
                    const walker = document.createTreeWalker(child, NodeFilter.SHOW_TEXT, null);
                    while (walker.nextNode()) {
                        const t = walker.currentNode.textContent.trim();
                        if (t.length > 2 && !items.includes(t)) items.push(t);
                    }
                }
                if (items.length > 0) result.attributes[category] = items;
            }

            if (Object.keys(result.attributes).length === 0) {
                for (const el of main.querySelectorAll('[aria-label][role="img"]')) {
                    const label = el.getAttribute('aria-label') || '';
                    if (label.length > 5 && label.length < 100) {
                        result.attributes['Features'] = result.attributes['Features'] || [];
                        if (!result.attributes['Features'].includes(label))
                            result.attributes['Features'].push(label);
                    }
                }
            }

            for (const a of main.querySelectorAll('a[href]')) {
                const href = a.href || '';
                const socialPlatforms = [
                    ['facebook.com', 'Facebook'],
                    ['instagram.com', 'Instagram'],
                    ['twitter.com', 'Twitter / X'],
                    ['x.com', 'Twitter / X'],
                    ['linkedin.com', 'LinkedIn'],
                    ['youtube.com', 'YouTube'],
                    ['tiktok.com', 'TikTok'],
                    ['pinterest.com', 'Pinterest'],
                    ['tripadvisor.com', 'TripAdvisor'],
                    ['yelp.com', 'Yelp'],
                ];
                for (const [domain, platform] of socialPlatforms) {
                    if (href.includes(domain) &&
                        !result.social_links.some(l => l.url === href)) {
                        result.social_links.push({ platform, url: href });
                    }
                }
            }

            return result;
        }
        """) or {}

        if data.get('attributes'):
            about['attributes'] = data['attributes']
            total = sum(len(v) for v in data['attributes'].values())
            logging.info(f"✅ About tab: {len(data['attributes'])} sections, {total} attributes")
        else:
            logging.info("ℹ About tab: no attribute sections found")

        if data.get('social_links'):
            about['social_links'] = data['social_links']
            logging.info(f"✅ Social links: {', '.join(l['platform'] for l in data['social_links'])}")

    except Exception as e:
        logging.warning(f"⚠ Could not extract About tab: {e}")
    return about


def extract_popular_times(page: Page) -> dict:
    """
    Extract 'Popular times' data from the Overview tab.
    Returns a dict: { 'Monday': [{'hour':'6 AM','busyness':'Normal busy'}, ...], ... }
    """
    popular_times = {}
    try:
        click_tab(page, "Overview")
        page.wait_for_timeout(1000)
        for _ in range(6):
            _scroll_place_panel(page, 1200)
            page.wait_for_timeout(400)
        page.wait_for_timeout(600)

        data = page.evaluate(r"""
        () => {
            const days = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
            const result = {};

            for (const el of document.querySelectorAll('[aria-label]')) {
                const label = el.getAttribute('aria-label') || '';
                for (const day of days) {
                    if (!label.startsWith(day + ';')) continue;
                    const hours = [];
                    const hourMatches = label.matchAll(/(\d{1,2}\s*(?:AM|PM))[:\s]*([^;.]+)/gi);
                    for (const m of hourMatches) {
                        hours.push({ hour: m[1].trim(), busyness: m[2].trim() });
                    }
                    if (hours.length > 0) result[day] = hours;
                }
            }

            if (Object.keys(result).length === 0) {
                let ptSection = null;
                for (const el of document.querySelectorAll('*')) {
                    if (el.children.length === 0 &&
                        (el.textContent.trim() === 'Popular times' ||
                         el.textContent.trim() === 'Heures de grande affluence')) {
                        ptSection = el.closest('[jsrenderer]') || el.parentElement?.parentElement;
                        break;
                    }
                }
                if (ptSection) {
                    let currentDay = null;
                    for (const el of ptSection.querySelectorAll('[aria-label]')) {
                        const label = el.getAttribute('aria-label') || '';
                        for (const day of days) {
                            if (label === day || label.startsWith(day)) {
                                currentDay = day;
                                result[currentDay] = result[currentDay] || [];
                                break;
                            }
                        }
                        if (currentDay && /\d{1,2}\s*(AM|PM)/i.test(label) && label.includes('%')) {
                            const hm = label.match(/(\d{1,2}\s*(?:AM|PM))/i);
                            const pm = label.match(/(\d+)%/);
                            if (hm) {
                                result[currentDay].push({
                                    hour: hm[1].trim(),
                                    busyness: pm ? pm[1] + '% busy' : label.trim(),
                                });
                            }
                        }
                    }
                }
            }

            return result;
        }
        """) or {}

        if data:
            popular_times = data
            days_found = list(data.keys())
            logging.info(f"✅ Popular times: data for {len(days_found)} days")
        else:
            logging.info("ℹ Popular times: not available (may require login or place doesn't have data)")

    except Exception as e:
        logging.warning(f"⚠ Could not extract popular times: {e}")
    return popular_times


def extract_qa(page: Page) -> list:
    """
    Extract the 'Questions & answers' section from a Google Maps place page.
    Returns list of dicts: {question, answer, additional}.
    """
    qa_list = []
    try:
        click_tab(page, "Overview")
        page.wait_for_timeout(1000)

        for _ in range(8):
            _scroll_place_panel(page, 1200)
            page.wait_for_timeout(400)

        for sel in [
            'button:has-text("See all questions")',
            'button:has-text("All questions")',
            'a:has-text("See all questions")',
            '//button[contains(.,"question")]',
        ]:
            try:
                if page.locator(sel).count() > 0:
                    page.locator(sel).first.click()
                    page.wait_for_timeout(2000)
                    break
            except Exception:
                pass

        data = page.evaluate(r"""
        () => {
            const results = [];
            const seen = new Set();

            const qaSelectors = [
                'div[jsrenderer*="QA"]',
                'div[data-question-id]',
                '[class*="questions"] > div',
            ];

            for (const sel of qaSelectors) {
                const items = document.querySelectorAll(sel);
                if (items.length === 0) continue;
                for (const item of items) {
                    const texts = [];
                    const walker = document.createTreeWalker(item, NodeFilter.SHOW_TEXT, null);
                    while (walker.nextNode()) {
                        const t = walker.currentNode.textContent.trim();
                        if (t.length > 5) texts.push(t);
                    }
                    if (texts.length >= 2) {
                        const key = texts[0];
                        if (!seen.has(key)) {
                            seen.add(key);
                            results.push({
                                question: texts[0],
                                answer: texts[1] || '',
                                additional: texts.slice(2).join(' | '),
                            });
                        }
                    }
                }
                if (results.length > 0) break;
            }

            if (results.length === 0) {
                for (const el of document.querySelectorAll('*')) {
                    if (el.children.length > 0) continue;
                    const t = (el.textContent || '').trim();
                    if (t.endsWith('?') && t.length > 10 && t.length < 300) {
                        const parent = el.closest('[jsrenderer]') || el.parentElement?.parentElement;
                        if (!parent || seen.has(t)) continue;
                        seen.add(t);
                        const allText = (parent.innerText || parent.textContent || '').trim();
                        const parts = allText.split('\n').map(s => s.trim()).filter(s => s.length > 3);
                        results.push({
                            question: t,
                            answer: parts.find(p => p !== t && p.length > 5) || '',
                            additional: '',
                        });
                    }
                }
            }

            return results;
        }
        """) or []

        qa_list = data
        if qa_list:
            logging.info(f"✅ Q&A: {len(qa_list)} questions found")
        else:
            logging.info("ℹ Q&A: no questions found")

    except Exception as e:
        logging.warning(f"⚠ Could not extract Q&A: {e}")
    return qa_list


def extract_updates(page: Page) -> list:
    """
    Scrape business posts/updates from a Google Maps place page.
    Returns list of dicts with post body, image, CTA/action URL, and share URL.
    """
    updates = []
    try:
        def _extract_posts_from_dom() -> list:
            return page.evaluate(r"""
            () => {
                function clean(value) {
                    return (value || '').replace(/\s+/g, ' ').trim();
                }

                function normalizeImage(src) {
                    if (!src) return '';
                    if (src.includes('googleusercontent.com')) {
                        if (src.includes('/geougc/') || /=/.test(src)) {
                            return src.replace(/=.*$/, '') + '=s1200';
                        }
                    }
                    return src;
                }

                function backgroundImageUrl(el) {
                    const style = el ? window.getComputedStyle(el).backgroundImage || '' : '';
                    const match = style.match(/url\(["']?(.+?)["']?\)/);
                    return match ? match[1] : '';
                }

                function linkFromCard(card) {
                    const cta = card.querySelector('.ABZ6xb, .dsrqad a');
                    if (cta) {
                        const dataLink = cta.getAttribute('data-link') || '';
                        if (dataLink) return dataLink;
                        const href = cta.href || cta.getAttribute('href') || '';
                        if (href) return href;
                        const tel = cta.getAttribute('data-tel') || '';
                        if (tel) return tel;
                    }
                    const firstLink = card.querySelector('a[data-link], a[href], a[data-tel]');
                    if (firstLink) {
                        return firstLink.getAttribute('data-link') ||
                               firstLink.href ||
                               firstLink.getAttribute('data-tel') ||
                               '';
                    }
                    return '';
                }

                const expandedCards = Array.from(document.querySelectorAll('.cKbrCd'));
                const overviewCards = Array.from(document.querySelectorAll(
                    '.S3NLN button, button[jsaction*="local-post.expand"], button[aria-label*="local posts" i]'
                ));
                const candidates = expandedCards.length ? expandedCards : overviewCards;
                const cards = [];

                for (const card of candidates) {
                    const title = clean(card.querySelector('.kf0LHf')?.textContent) ||
                                  clean(card.querySelector('.fontTitleSmall')?.textContent) ||
                                  '';
                    const date = clean(card.querySelector('.mgX1W')?.textContent) ||
                                 clean(card.querySelector('.lqMB')?.textContent) ||
                                 '';
                    const body = clean(card.querySelector('.hfJtQe')?.textContent) ||
                                 clean(card.querySelector('.VpMB0')?.textContent) ||
                                 '';
                    const ctaText = clean(card.querySelector('.ABZ6xb, .dsrqad a, a[data-tel], a[href]')?.textContent);
                    const postImage = normalizeImage(
                        card.querySelector('.tTCrvf')?.src ||
                        backgroundImageUrl(card.querySelector('.EvLOsc')) ||
                        card.querySelector('img[src*="geougc"], img[src*="googleusercontent"]')?.src ||
                        ''
                    );
                    const authorImage = normalizeImage(card.querySelector('.jE1Ghf')?.src || '');
                    const shareUrl = card.querySelector('[data-sharing-url]')?.getAttribute('data-sharing-url') || '';
                    const reportUrl = card.querySelector('[data-report-post-url]')?.getAttribute('data-report-post-url') || '';
                    const actionUrl = linkFromCard(card);

                    if (!body && !postImage && !shareUrl) continue;

                    cards.push({
                        title,
                        date,
                        type: '',
                        body,
                        image_url: postImage,
                        image_urls: postImage,
                        author_image_url: authorImage,
                        cta_text: ctaText,
                        action_url: actionUrl,
                        learn_more_url: ctaText.toLowerCase().includes('learn') ? actionUrl : '',
                        share_url: shareUrl,
                        report_url: reportUrl,
                        source: expandedCards.length ? 'expanded' : 'overview',
                    });
                }

                const seen = new Set();
                return cards.filter((post) => {
                    const key = `${post.date}|${post.body}|${post.image_url}`;
                    if (seen.has(key)) return false;
                    seen.add(key);
                    return true;
                });
            }
            """) or []

        def _find_owner_section() -> bool:
            try:
                return bool(page.evaluate("""
                () => {
                    const text = document.body ? document.body.innerText || '' : '';
                    const needles = [
                        'From the owner', 'Mises à jour', 'Mises a jour',
                        'Du propriétaire', 'Du proprietaire', 'Latest Posts'
                    ];
                    return needles.some((needle) => text.includes(needle));
                }
                """))
            except Exception:
                return False

        def _click_local_posts() -> bool:
            selectors = [
                'button[aria-label="See local posts"]',
                'button[aria-label*="local posts" i]',
                'button[jsaction*="local-post.expand"]',
                'button[jsaction*="localPost"][aria-label]',
            ]
            for selector in selectors:
                try:
                    loc = page.locator(selector)
                    if loc.count() > 0:
                        loc.first.click(force=True, timeout=5000)
                        page.wait_for_timeout(2500)
                        return True
                except Exception:
                    continue

            try:
                clicked = page.evaluate("""
                () => {
                    const candidates = Array.from(document.querySelectorAll('button'));
                    const scored = candidates
                        .map((el) => {
                            const text = `${el.getAttribute('aria-label') || ''} ${el.textContent || ''}`;
                            let score = 0;
                            if (/local posts/i.test(text)) score += 10;
                            if (/From the owner/i.test(el.closest('.S3NLN')?.textContent || '')) score += 6;
                            if (/Call now|Learn more|En savoir|Appeler/i.test(text)) score += 2;
                            if (el.querySelector('[style*="googleusercontent"]') ||
                                el.querySelector('img[src*="googleusercontent"]')) score += 4;
                            return { el, score };
                        })
                        .filter((item) => item.score > 0)
                        .sort((a, b) => b.score - a.score);
                    if (!scored.length) return false;
                    scored[0].el.click();
                    return true;
                }
                """)
                if clicked:
                    page.wait_for_timeout(2500)
                    return True
            except Exception:
                pass
            return False

        click_tab(page, "Overview")
        page.wait_for_timeout(1000)

        found_owner = _find_owner_section()
        for _ in range(12):
            if found_owner:
                break
            _scroll_place_panel(page, 900)
            page.wait_for_timeout(500)
            found_owner = _find_owner_section()

        def _collect_expanded_posts_with_scroll(max_rounds: int = 10) -> list:
            best = _extract_posts_from_dom()
            same_count_rounds = 0
            for _ in range(max_rounds):
                try:
                    # Scroll expanded side panel first; fall back to place panel scroll helper.
                    page.evaluate(
                        """
                        () => {
                            const selectors = [
                                '.m6QErb.DxyBCb.kA9KIf.dS8AEf',
                                '.m6QErb.DxyBCb',
                                '.m6QErb[role="main"]'
                            ];
                            for (const sel of selectors) {
                                const el = document.querySelector(sel);
                                if (el && el.scrollHeight > el.clientHeight) {
                                    el.scrollTop += 1200;
                                    return true;
                                }
                            }
                            return false;
                        }
                        """
                    )
                except Exception:
                    _scroll_place_panel(page, 1000)
                page.wait_for_timeout(650)

                current = _extract_posts_from_dom()
                if len(current) > len(best):
                    best = current
                    same_count_rounds = 0
                else:
                    same_count_rounds += 1
                    if same_count_rounds >= 3:
                        break
            return best

        preview_posts = _extract_posts_from_dom()

        if _click_local_posts():
            for _ in range(4):
                _scroll_place_panel(page, 900)
                page.wait_for_timeout(500)
            expanded_posts = _collect_expanded_posts_with_scroll(max_rounds=12)
            updates = expanded_posts or preview_posts
        else:
            updates = preview_posts

        # Fallback: if we only got one card, retry expanded-feed collection once more.
        if len(updates) <= 1 and _click_local_posts():
            retried_posts = _collect_expanded_posts_with_scroll(max_rounds=14)
            if len(retried_posts) > len(updates):
                updates = retried_posts
                logging.info(f"✅ Updates/posts fallback improved count to: {len(updates)}")

        if updates:
            logging.info(f"✅ Updates/posts: {len(updates)} found")
        else:
            logging.info("ℹ Updates/posts: none found")

    except Exception as e:
        logging.warning(f"⚠ Could not extract updates: {e}")
    return updates
