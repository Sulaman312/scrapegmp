import logging

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
                if elem.count() > 0:
                    elem.first.click(force=True)
                    page.wait_for_timeout(2000)
                    logging.info(f"Clicked '{name}' tab (requested: '{tab_name}')")
                    return True
            except Exception:
                continue

    logging.warning(f"Could not find '{tab_name}' tab (tried: {candidates})")
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
    Returns list of dicts: {date, body, image_urls}.
    """
    updates = []
    try:
        found_tab = click_tab(page, "Updates")
        if not found_tab:
            click_tab(page, "Overview")
            page.wait_for_timeout(1000)
            for _ in range(6):
                _scroll_place_panel(page, 1200)
                page.wait_for_timeout(400)
        else:
            page.wait_for_timeout(2000)
            for _ in range(5):
                _scroll_place_panel(page, 1500)
                page.wait_for_timeout(500)

        data = page.evaluate(r"""
        () => {
            const results = [];
            const seen = new Set();

            const postSelectors = [
                'div[jsrenderer*="Post"]',
                'div[data-post-id]',
                'div[class*="post"]',
                'div[class*="update"]',
            ];

            for (const sel of postSelectors) {
                for (const post of document.querySelectorAll(sel)) {
                    const texts = [];
                    const imgUrls = [];
                    for (const img of post.querySelectorAll('img[src*="googleusercontent"]')) {
                        const src = img.src || '';
                        const base = src.replace(/=.*$/, '');
                        if (base) imgUrls.push(base + '=s800');
                    }
                    const walker = document.createTreeWalker(post, NodeFilter.SHOW_TEXT, null);
                    while (walker.nextNode()) {
                        const t = walker.currentNode.textContent.trim();
                        if (t.length > 3) texts.push(t);
                    }
                    if (texts.length === 0) continue;
                    const key = texts[0];
                    if (seen.has(key)) continue;
                    seen.add(key);
                    const datePattern = /(\d+\s+\w+\s+\d{4}|\w+\s+\d+,?\s+\d{4}|\d+\s+(?:day|week|month|year)s?\s+ago)/i;
                    const dateStr = texts.find(t => datePattern.test(t)) || '';
                    const body = texts.filter(t => t !== dateStr).join(' ').slice(0, 2000);
                    results.push({
                        date: dateStr,
                        body: body,
                        image_urls: imgUrls.join('; '),
                    });
                }
                if (results.length > 0) break;
            }

            if (results.length === 0) {
                let updSection = null;
                for (const el of document.querySelectorAll('*')) {
                    if (el.children.length === 0 &&
                        (el.textContent.trim() === 'Updates' ||
                         el.textContent.trim() === 'Mises à jour')) {
                        updSection = el.closest('[jsrenderer]') || el.parentElement?.parentElement;
                        break;
                    }
                }
                if (updSection) {
                    const texts = (updSection.innerText || updSection.textContent || '')
                        .split('\n').map(s => s.trim()).filter(s => s.length > 5);
                    if (texts.length > 0) {
                        results.push({ date: '', body: texts.join(' | ').slice(0,2000), image_urls: '' });
                    }
                }
            }

            return results;
        }
        """) or []

        updates = data
        if updates:
            logging.info(f"✅ Updates/posts: {len(updates)} found")
        else:
            logging.info("ℹ Updates/posts: none found")

    except Exception as e:
        logging.warning(f"⚠ Could not extract updates: {e}")
    return updates
