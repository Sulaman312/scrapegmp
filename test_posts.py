#!/usr/bin/env python3
"""Standalone Google Maps local-post scraper test harness.

This is intentionally isolated from the production scraper. It captures HTML,
main-panel HTML, screenshots, and parsed post JSON at each meaningful step so
the Maps DOM can be debugged without changing the app pipeline.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Page, sync_playwright


DEFAULT_URL = (
    "https://www.google.com/maps/place/AVIS+CONSO+-+Mieux+r%C3%A9f%C3%A9renc%C3%A9+avec+vos+avis/"
    "@46.6689118,6.803273,17z/data=!4m14!1m7!3m6!1s0x478dd59451ba97fb:0x2fa4cfdbb0f1d6b6!"
    "2sAVIS+CONSO+-+Mieux+r%C3%A9f%C3%A9renc%C3%A9+avec+vos+avis!8m2!3d46.675839!4d6.8111239!"
    "16s%2Fg%2F11p6wn_y9x!3m5!1s0x478dd59451ba97fb:0x2fa4cfdbb0f1d6b6!8m2!3d46.675839!"
    "4d6.8111239!16s%2Fg%2F11p6wn_y9x?entry=ttu"
)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def _safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", value).strip("_")


def _configured_browser_executable() -> str | None:
    configured = os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE", "").strip()
    if configured and Path(configured).exists():
        return configured
    return None


def _find_browser_executable() -> str | None:
    for command in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        path = shutil.which(command)
        if path and path.startswith("/snap/"):
            continue
        if path:
            return path
    return None


def _apply_stealth(page: Page) -> None:
    page.add_init_script(
        """
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """
    )


def dump_step(page: Page, output_dir: Path, step: str) -> None:
    """Capture page screenshot, full HTML, main panel HTML, and metadata."""
    safe = _safe_name(step)
    (output_dir / f"{safe}.html").write_text(page.content(), encoding="utf-8")

    try:
        main_html = page.evaluate(
            """
            () => {
                const main = document.querySelector('[role="main"]');
                return main ? main.outerHTML : '';
            }
            """
        )
        (output_dir / f"{safe}.main.html").write_text(main_html or "", encoding="utf-8")
    except Exception as exc:
        (output_dir / f"{safe}.main_error.txt").write_text(str(exc), encoding="utf-8")

    try:
        body_text = page.locator("body").inner_text(timeout=3000)
        (output_dir / f"{safe}.text.txt").write_text(body_text, encoding="utf-8")
    except Exception as exc:
        (output_dir / f"{safe}.text_error.txt").write_text(str(exc), encoding="utf-8")

    try:
        page.screenshot(path=str(output_dir / f"{safe}.png"), full_page=True)
    except Exception as exc:
        (output_dir / f"{safe}.screenshot_error.txt").write_text(str(exc), encoding="utf-8")

    meta = {
        "step": step,
        "url": page.url,
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
    }
    (output_dir / f"{safe}.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def dismiss_google_consent(page: Page) -> None:
    for selector in (
        'button:has-text("Accept all")',
        'button:has-text("I agree")',
        'button:has-text("Reject all")',
        '//button[contains(., "Accept")]',
        'form[action*="consent"] button',
    ):
        try:
            loc = page.locator(selector)
            if loc.count() > 0:
                loc.first.click(timeout=4000)
                page.wait_for_timeout(1500)
                return
        except Exception:
            continue


def scroll_place_panel(page: Page, amount: int = 1200) -> None:
    page.evaluate(
        """
        (amount) => {
            const candidates = [
                document.querySelector('div.m6QErb.DxyBCb.kA9KIf.dS8AEf'),
                document.querySelector('div.m6QErb.DxyBCb'),
                document.querySelector('div.m6QErb'),
                document.querySelector('[role="main"] [tabindex="-1"]'),
                document.querySelector('[role="main"]')
            ];
            for (const el of candidates) {
                if (el && el.scrollHeight > el.clientHeight) {
                    el.scrollTop += amount;
                    return true;
                }
            }
            window.scrollBy(0, amount);
            return false;
        }
        """,
        amount,
    )


def find_from_owner(page: Page) -> bool:
    return bool(
        page.evaluate(
            """
            () => {
                const needles = ['From the owner', 'Mises a jour', 'Mises à jour', 'Du proprietaire', 'Du propriétaire'];
                const text = document.body ? document.body.innerText || '' : '';
                return needles.some((n) => text.includes(n));
            }
            """
        )
    )


def click_local_posts(page: Page) -> bool:
    selectors = (
        'button[aria-label="See local posts"]',
        'button[aria-label*="local posts" i]',
        'button[jsaction*="local-post.expand"]',
        'button[jsaction*="localPost"][aria-label]',
    )
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
        clicked = page.evaluate(
            """
            () => {
                const candidates = Array.from(document.querySelectorAll('button'));
                const scored = candidates
                    .map((el) => {
                        const text = `${el.getAttribute('aria-label') || ''} ${el.textContent || ''}`;
                        let score = 0;
                        if (/local posts/i.test(text)) score += 10;
                        if (/From the owner/i.test(el.closest('.S3NLN')?.textContent || '')) score += 6;
                        if (/Call now|Learn more|En savoir|Appeler/i.test(text)) score += 2;
                        if ((el.querySelector('[style*="googleusercontent"]') || el.querySelector('img[src*="googleusercontent"]'))) score += 4;
                        return { el, score };
                    })
                    .filter((item) => item.score > 0)
                    .sort((a, b) => b.score - a.score);
                if (!scored.length) return false;
                scored[0].el.click();
                return true;
            }
            """
        )
        if clicked:
            page.wait_for_timeout(2500)
            return True
    except Exception:
        pass
    return False


def extract_posts_from_dom(page: Page) -> list[dict]:
    return page.evaluate(
        r"""
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
                    return firstLink.getAttribute('data-link') || firstLink.href || firstLink.getAttribute('data-tel') || '';
                }
                return '';
            }

            const cards = [];
            const expandedCards = Array.from(document.querySelectorAll('.cKbrCd'));
            const overviewCards = Array.from(document.querySelectorAll('.S3NLN button, button[jsaction*="local-post.expand"]'));
            const candidates = expandedCards.length ? expandedCards : overviewCards;

            for (const card of candidates) {
                const title = clean(card.querySelector('.kf0LHf')?.textContent)
                    || clean(card.querySelector('.fontTitleSmall')?.textContent)
                    || '';
                const date = clean(card.querySelector('.mgX1W')?.textContent)
                    || clean(card.querySelector('.lqMB')?.textContent)
                    || '';
                const body = clean(card.querySelector('.hfJtQe')?.textContent)
                    || clean(card.querySelector('.VpMB0')?.textContent)
                    || '';
                const ctaText = clean(card.querySelector('.ABZ6xb, .dsrqad a, a[data-tel], a[href]')?.textContent);
                const postImage = normalizeImage(
                    card.querySelector('.tTCrvf')?.src
                    || backgroundImageUrl(card.querySelector('.EvLOsc'))
                    || card.querySelector('img[src*="geougc"], img[src*="googleusercontent"]')?.src
                    || ''
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
                    author_image_url: authorImage,
                    cta_text: ctaText,
                    action_url: actionUrl,
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
        """
    ) or []


def run(url: str, output_root: Path, headful: bool, max_scrolls: int) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = output_root / stamp
    output_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        launch_kwargs = {
            "headless": not headful,
            "args": ["--no-sandbox", "--disable-setuid-sandbox"],
        }
        executable = _configured_browser_executable()
        if executable:
            launch_kwargs["executable_path"] = executable

        try:
            browser = p.chromium.launch(**launch_kwargs)
        except Exception:
            fallback = _find_browser_executable()
            if not fallback or executable:
                raise
            launch_kwargs["executable_path"] = fallback
            browser = p.chromium.launch(**launch_kwargs)
        page = browser.new_page(
            viewport={"width": 1366, "height": 900},
            user_agent=DEFAULT_USER_AGENT,
            locale="en-US",
            timezone_id="Asia/Karachi",
        )
        _apply_stealth(page)

        try:
            page.goto(url, timeout=90000, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            dismiss_google_consent(page)
            dump_step(page, output_dir, "01_loaded")

            try:
                page.wait_for_selector("h1", timeout=20000)
            except Exception:
                pass
            dump_step(page, output_dir, "02_after_header_wait")

            found_owner = find_from_owner(page)
            for index in range(max_scrolls):
                if found_owner:
                    break
                scroll_place_panel(page, 900)
                page.wait_for_timeout(750)
                dump_step(page, output_dir, f"03_scroll_{index + 1:02d}")
                found_owner = find_from_owner(page)

            posts_before_click = extract_posts_from_dom(page)
            (output_dir / "posts_before_click.json").write_text(
                json.dumps(posts_before_click, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            dump_step(page, output_dir, "04_before_local_posts_click")

            clicked = click_local_posts(page)
            (output_dir / "click_result.json").write_text(
                json.dumps({"clicked": clicked}, indent=2),
                encoding="utf-8",
            )
            dump_step(page, output_dir, "05_after_local_posts_click")

            for index in range(3):
                scroll_place_panel(page, 800)
                page.wait_for_timeout(600)
                dump_step(page, output_dir, f"06_expanded_scroll_{index + 1:02d}")

            posts_after_click = extract_posts_from_dom(page)
            final_posts = posts_after_click or posts_before_click
            (output_dir / "posts_after_click.json").write_text(
                json.dumps(posts_after_click, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (output_dir / "posts.json").write_text(
                json.dumps(final_posts, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        finally:
            browser.close()

    return output_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Debug Google Maps local-post extraction.")
    parser.add_argument("url", nargs="?", default=DEFAULT_URL)
    parser.add_argument("--output-root", default="test_posts_output")
    parser.add_argument("--headful", action="store_true")
    parser.add_argument("--max-scrolls", type=int, default=12)
    args = parser.parse_args()

    output_dir = run(
        url=args.url,
        output_root=Path(args.output_root),
        headful=args.headful,
        max_scrolls=args.max_scrolls,
    )
    print(f"Output: {output_dir}")
    print(f"Posts JSON: {output_dir / 'posts.json'}")


if __name__ == "__main__":
    main()
