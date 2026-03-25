"""
generate_site.py — One-Page Website Generator
===============================================
Reads ScrapeData/<BusinessName>/enriched_data.json (produced by enrichment.py)
and generates a beautiful static one-page website at:
  ScrapeData/<BusinessName>/website/index.html

Design: modern SaaS style (inspired by Picmal / Quid AI)
  • Sticky navigation
  • Hero with tagline + CTA
  • Stats bar (rating, reviews, location)
  • Features bento grid
  • Photo gallery
  • Testimonials / reviews
  • Popular times bar chart
  • FAQ accordion
  • Contact section with embedded map
  • Footer with social links

Usage:
    python generate_site.py --dir ScrapeData/Digimidi
    python generate_site.py --dir ScrapeData/Digimidi --open   # opens in browser after
"""

import os
import json
import argparse
import logging
import shutil
import re
import html as html_lib

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
_log = logging.getLogger(__name__)


def _e(text) -> str:
    """HTML-escape a value."""
    return html_lib.escape(str(text or ""), quote=True)


def _stars(rating) -> str:
    """Return filled/empty star HTML for a numeric rating."""
    if not rating:
        return ""
    r = float(rating)
    stars = ""
    for i in range(1, 6):
        if r >= i:
            stars += '<span class="text-yellow-400">★</span>'
        elif r >= i - 0.5:
            stars += '<span class="text-yellow-300">★</span>'
        else:
            stars += '<span class="text-gray-300">★</span>'
    return stars


def _load_json(path):
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _load_csv(path):
    if not os.path.isfile(path):
        return []
    try:
        import pandas as pd
        return pd.read_csv(path, encoding="utf-8-sig").fillna("").to_dict("records")
    except Exception:
        return []


def _extract_brand_colors(image_rel_paths: list, business_dir: str):
    """
    Analyse scraped images and return a list of up to 3 vivid hex brand colors.
    Falls back to None if Pillow is unavailable or no usable colors found.
    """
    try:
        import colorsys
        from PIL import Image

        collected = []  # (saturation*value score, r, g, b)
        for rel in image_rel_paths[:6]:
            full = os.path.join(business_dir, rel)
            if not os.path.isfile(full):
                continue
            try:
                img = Image.open(full).convert("RGB").resize((120, 120))
                # quantize → reliable dominant palette
                q = img.quantize(colors=8, method=0, kmeans=0)
                pal = q.getpalette()  # flat [R,G,B, R,G,B, ...]
                counts = q.getcolors(maxcolors=256) or []
                freq = {idx: cnt for cnt, idx in counts}
                for idx in range(8):
                    r, g, b = pal[idx*3], pal[idx*3+1], pal[idx*3+2]
                    h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
                    # skip near-white, near-black, near-grey
                    if s < 0.25 or v < 0.20 or v > 0.95:
                        continue
                    weight = freq.get(idx, 1)
                    collected.append((s * v * weight, h, r, g, b))
            except Exception:
                continue

        if not collected:
            return None

        collected.sort(reverse=True)

        # Deduplicate by hue (keep colors at least 30° apart)
        unique_hex = []
        used_hues = []
        for score, h, r, g, b in collected:
            if all(min(abs(h - uh), 1 - abs(h - uh)) > 0.08 for uh in used_hues):
                unique_hex.append((h, r, g, b))
                used_hues.append(h)
            if len(unique_hex) == 3:
                break

        return [f"#{r:02x}{g:02x}{b:02x}" for _, r, g, b in unique_hex] if unique_hex else None
    except Exception:
        return None


def _darken_hex(hex_color: str, factor: float = 0.45) -> str:
    """Return a darkened version of a hex color (factor 0=black, 1=original)."""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    r, g, b = int(r * factor), int(g * factor), int(b * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


def _mix_hex(c1: str, c2: str, t: float = 0.5) -> str:
    """Linear interpolation between two hex colors (t=0→c1, t=1→c2)."""
    c1 = c1.lstrip("#"); c2 = c2.lstrip("#")
    r = int(int(c1[0:2],16)*(1-t) + int(c2[0:2],16)*t)
    g = int(int(c1[2:4],16)*(1-t) + int(c2[2:4],16)*t)
    b = int(int(c1[4:6],16)*(1-t) + int(c2[4:6],16)*t)
    return f"#{r:02x}{g:02x}{b:02x}"


def _shift_hue(hex_color: str, degrees: float) -> str:
    """Rotate hue by `degrees` while keeping saturation and value."""
    import colorsys
    h_str = hex_color.lstrip("#")
    r, g, b = int(h_str[0:2],16)/255, int(h_str[2:4],16)/255, int(h_str[4:6],16)/255
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    h = (h + degrees / 360) % 1.0
    # Boost saturation slightly so shifted colors stay vivid
    s = min(1.0, s * 1.05)
    nr, ng, nb = colorsys.hsv_to_rgb(h, s, v)
    return f"#{int(nr*255):02x}{int(ng*255):02x}{int(nb*255):02x}"


def _find_images(images_dir):
    results = []
    if not os.path.isdir(images_dir):
        return results
    for root, _, files in os.walk(images_dir):
        for f in sorted(files):
            if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                rel = os.path.relpath(os.path.join(root, f), os.path.dirname(images_dir))
                results.append(rel.replace("\\", "/"))
    return results


def _find_videos(videos_dir):
    """Return list of relative paths (from the business_dir) for mp4/webm files."""
    results = []
    if not os.path.isdir(videos_dir):
        return results
    for f in sorted(os.listdir(videos_dir)):
        if f.lower().endswith((".mp4", ".webm", ".mov")):
            results.append(os.path.join("videos", f).replace("\\", "/"))
    return results


def build_html(business_dir: str, use_draft: bool = False, override_data: dict = None) -> str:
    """
    Build the complete website HTML for a business and return it as a string.
    Does NOT write any files — callers decide what to do with the result.

    If use_draft is True and draft_data.json exists, that file is used.
    If override_data is provided, it is used as the source data (live preview).
    """
    return _render(business_dir, use_draft=use_draft, override_raw=override_data)


def generate(business_dir: str, open_browser: bool = False) -> str:
    """Build the HTML, write it to website/index.html, and return the output path.

    This always uses the published enriched_data.json, not the draft JSON.
    """
    html = build_html(business_dir, use_draft=False)
    out_dir = os.path.join(business_dir, "website")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    _log.info(f"✅ Website generated → {out_path}")
    if open_browser:
        import webbrowser
        webbrowser.open(f"file://{os.path.abspath(out_path)}")
    return out_path


def _render(business_dir: str, use_draft: bool = False, override_raw: dict = None) -> str:
    enriched_path = os.path.join(business_dir, "enriched_data.json")
    draft_path    = os.path.join(business_dir, "draft_data.json")

    # ── Load source data (strict draft vs published separation) ──────────────
    if override_raw is not None:
        raw = override_raw
    elif use_draft:
        source_path = draft_path if os.path.isfile(draft_path) else enriched_path
        raw = _load_json(source_path) if os.path.isfile(source_path) else {}
    else:
        source_path = enriched_path
        raw = _load_json(source_path) if os.path.isfile(source_path) else {}

    # Business slug used for media URLs (folder name under ScrapeData)
    import os as _osmod  # local alias to avoid confusion with outer scope
    biz_slug = _osmod.path.basename(business_dir.rstrip("/\\"))
    media_prefix = f"/media/{biz_slug}/"

    # Detect flat structure (just AI fields at top level, no "business" key)
    if raw and "business" not in raw and "tagline" in raw:
        logging.info("ℹ enriched_data.json has flat AI structure — merging with scraped files")
        ai_flat = raw
        raw = {}  # rebuild below
    else:
        ai_flat = {}

    # ── business dict: prefer enriched, fall back to place_data.json ─────────
    place_raw = _load_json(os.path.join(business_dir, "place_data.json"))
    day_order = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]

    if raw.get("business"):
        biz = raw["business"]
    else:
        biz = {
            "name":            place_raw.get("name", ""),
            "place_type":      place_raw.get("place_type", ""),
            "address":         place_raw.get("address", ""),
            "phone":           place_raw.get("phone_number", ""),
            "website":         place_raw.get("website", ""),
            "email":           place_raw.get("email", ""),
            "rating":          place_raw.get("reviews_average"),
            "reviews_count":   place_raw.get("reviews_count"),
            "price_range":     place_raw.get("price_range", ""),
            "plus_code":       place_raw.get("plus_code", ""),
            "latitude":        place_raw.get("latitude", ""),
            "longitude":       place_raw.get("longitude", ""),
            "google_maps_url": place_raw.get("google_maps_url", ""),
            "description":     place_raw.get("description", ""),
            "hours":           {d: place_raw.get(d, "") for d in day_order},
        }

    # ── ai dict: prefer enriched, fall back to flat keys ─────────────────────
    ai = raw.get("ai") or ai_flat or {}

    # ── all other data: prefer enriched, fall back to individual CSV/JSON files
    def _get(key, fallback_loader):
        return raw.get(key) if raw.get(key) else fallback_loader()

    # Always scan the filesystem — enriched_data.json paths can go stale
    # if images are re-scraped into different sub-folders after enrichment.
    _json_images = raw.get("images")
    images = _json_images if _json_images else _find_images(os.path.join(business_dir, "images"))
    videos   = _find_videos(os.path.join(business_dir, "videos"))
    reviews  = _get("reviews",  lambda: _load_csv(os.path.join(business_dir, "reviews.csv")))
    qa       = _get("qa",       lambda: _load_csv(os.path.join(business_dir, "qa.csv")))
    popular  = _get("popular_times", lambda: _load_json(os.path.join(business_dir, "popular_times.json")))
    social   = _get("social_links",  lambda: _load_csv(os.path.join(business_dir, "social_links.csv")))
    attrs    = _get("about_attrs",   lambda: _load_csv(os.path.join(business_dir, "about_attributes.csv")))
    website  = _get("website_data",  lambda: {})

    nav_noise = {
        "restaurants","hotels","things to do","transit","parking","pharmacies","atms",
        "see photos","overview","about","directions","save","nearby","send to phone",
        "share","suggest an edit","add photos & videos","write a review","sign in",
        "suggest new hours",
    }
    raw_keywords = _get("review_keywords", lambda: _load_csv(os.path.join(business_dir, "review_keywords.csv")))
    if raw_keywords and isinstance(raw_keywords[0], dict):
        keywords = [r.get("keyword","") for r in raw_keywords
                    if r.get("keyword","").lower().strip() not in nav_noise
                    and len(r.get("keyword","")) > 2]
    else:
        keywords = [k for k in raw_keywords if isinstance(k, str)]

    reviews  = [r for r in reviews if r.get("text", "").strip()]
    qa       = [q for q in qa if q.get("question", "").strip()]
    features = ai.get("features") or []

    # ── Section visibility (admin panel toggle) ────────────────────────────
    _vis = raw.get("section_visibility", {})
    def _show(key):
        """Return True if the section should be rendered (default: visible)."""
        return _vis.get(key, True)

    name         = biz.get("name") or "Business"
    # Short brand label used in the sticky navbar (can be edited in the admin);
    # falls back to the full business name when not set.
    brand_name   = ai.get("brand_short_name") or name

    # Tagline: AI first, else first website heading (max 80 chars), else name
    def _smart_tagline():
        if ai.get("tagline"): return ai["tagline"]
        for h in (website.get("headings") or []):
            if 6 < len(h) < 120:
                return (h[:77] + "…") if len(h) > 80 else h
        return name
    tagline = _smart_tagline()

    # Subtitle: AI first, else first paragraph from website
    def _smart_subtitle():
        if ai.get("hero_subtitle"): return ai["hero_subtitle"]
        for p in (website.get("paragraphs") or []):
            if len(p) > 40:
                return p[:220] + ("…" if len(p) > 220 else "")
        return biz.get("description", "")
    subtitle     = _smart_subtitle()

    about_para    = ai.get("about_paragraph") or subtitle or ""
    seo_title     = ai.get("seo_title") or f"{name} — {biz.get('place_type','')}"
    seo_desc      = ai.get("seo_description") or subtitle[:155]

    # ── Language detection ────────────────────────────────────────────────────
    _fr_words = {"les","des","une","pour","avec","dans","votre","notre","vous","nous",
                 "sur","par","qui","est","sont","mais","aussi","cette","leur","tout",
                 "logiciel","gestion","clinique","vétérinaire","suisse","solutions",
                 "entreprise","société","développement","numérique","services"}
    _sample   = " ".join(
        (website.get("headings") or [])[:6] +
        (website.get("paragraphs") or [])[:3] +
        [place_raw.get("name",""), place_raw.get("address",""),
         place_raw.get("description",""), place_raw.get("place_type",""),
         place_raw.get("introduction","")]
    ).lower()
    _fr_hits  = sum(1 for w in _sample.split() if w.strip(".,!?;:()") in _fr_words)
    lang      = "fr" if _fr_hits >= 3 else "en"

    # ── UI string table (EN / FR) ─────────────────────────────────────────────
    _T = {
        "en": {
            "features_label":  "Features",
            "features_h":      "Everything you need",
            "features_sub":    "Built for professionals who demand the best.",
            "gallery_label":   "Gallery",
            "gallery_h_pre":   "See it",
            "gallery_h_post":  "in action",
            "reviews_label":   "Client reviews",
            "reviews_h":       "What clients are saying",
            "about_label":     "About",
            "about_suffix":    "at your service",
            "hours_label":     "Availability",
            "hours_h":         "Popular times",
            "faq_label":       "FAQ",
            "faq_h":           "Common questions",
            "contact_label":   "Contact",
            "contact_h_pre":   "Let's work",
            "contact_h_post":  "together",
            "addr_lbl":        "Address",
            "phone_lbl":       "Phone",
            "email_lbl":       "Email",
            "web_lbl":         "Website",
            "hours_lbl":       "Opening Hours",
            "industry_lbl":    "Industry",
            "rating_lbl":      "Rating",
            "reviews_lbl":     "Reviews",
            "scroll_lbl":      "Scroll",
            "copyright":       "All rights reserved.",
            "gmaps_lbl":       "View on Google Maps",
            "cta_def":         "Get Started",
            "sec_def":         "Learn More",
            "cta_cta_h":       "Ready to get started?",
            "days": {"monday":"Mon","tuesday":"Tue","wednesday":"Wed","thursday":"Thu","friday":"Fri","saturday":"Sat","sunday":"Sun"},
            "videos_label":    "Videos",
            "videos_h":        "Watch us in action",
        },
        "fr": {
            "features_label":  "Fonctionnalités",
            "features_h":      "Tout ce dont vous avez besoin",
            "features_sub":    "Conçu pour les professionnels exigeants.",
            "gallery_label":   "Galerie",
            "gallery_h_pre":   "Découvrez-le",
            "gallery_h_post":  "en action",
            "reviews_label":   "Avis clients",
            "reviews_h":       "Ce que disent nos clients",
            "about_label":     "À propos",
            "about_suffix":    "à votre service",
            "hours_label":     "Disponibilité",
            "hours_h":         "Heures d'affluence",
            "faq_label":       "FAQ",
            "faq_h":           "Questions fréquentes",
            "contact_label":   "Contact",
            "contact_h_pre":   "Travaillons",
            "contact_h_post":  "ensemble",
            "addr_lbl":        "Adresse",
            "phone_lbl":       "Téléphone",
            "email_lbl":       "E-mail",
            "web_lbl":         "Site web",
            "hours_lbl":       "Heures d'ouverture",
            "industry_lbl":    "Secteur",
            "rating_lbl":      "Note",
            "reviews_lbl":     "Avis",
            "scroll_lbl":      "Défiler",
            "copyright":       "Tous droits réservés.",
            "gmaps_lbl":       "Voir sur Google Maps",
            "cta_def":         "Demander une démo",
            "sec_def":         "En savoir plus",
            "cta_cta_h":       "Prêt à transformer votre clinique ?",
            "days": {"monday":"Mon","tuesday":"Tue","wednesday":"Wed","thursday":"Thr","friday":"Fri","saturday":"Sat","sunday":"Sun"},
            "videos_label":    "Vidéos",
            "videos_h":        "Découvrez-nous en vidéo",
        },
    }
    t = _T[lang]
    logging.info(f"🌐 Detected language: {lang.upper()}")

    cta_primary   = ai.get("cta_btn_label") or ai.get("cta_primary")  or t["cta_def"]
    cta_secondary = ai.get("cta_secondary") or t["sec_def"]
    rating       = biz.get("rating")
    reviews_count= biz.get("reviews_count")
    address      = biz.get("address", "")
    phone        = biz.get("phone", "")
    email        = biz.get("email", "")
    website_url  = biz.get("website", "")
    lat          = biz.get("latitude", "")
    lng          = biz.get("longitude", "")
    hours        = biz.get("hours", {})

    # ── Auto-extract feature pairs from website headings if ai.features empty ──
    if not features and website.get("headings"):
        headings = website["headings"]
        skip_words = {"obtenez","ils nous","vos précieux","prêt à","copyright","gérez",
                      "avantages","équipe","nouveauté","solutions","discover","get started"}
        auto_feats = []
        i = 0
        while i < len(headings) - 1 and len(auto_feats) < 6:
            title = headings[i].strip()
            nxt   = headings[i+1].strip()
            if (8 < len(title) < 90 and len(nxt) > 55
                    and not any(sw in title.lower() for sw in skip_words)
                    and not nxt.lower().startswith(("obtenez","©","pour une démo"))):
                auto_feats.append({"title": title, "description": nxt})
                i += 2
            else:
                i += 1
        if auto_feats:
            features = auto_feats

    # ── Professional SVG icon sets ────────────────────────────────────────────
    def _svg(paths, size=22):
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
                f'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{paths}</svg>')

    FEAT_ICONS = [
        _svg('<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>'),  # Zap
        _svg('<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>'
             '<polyline points="9 12 11 14 15 10"/>'),                         # ShieldCheck
        _svg('<line x1="18" y1="20" x2="18" y2="10"/>'
             '<line x1="12" y1="20" x2="12" y2="4"/>'
             '<line x1="6" y1="20" x2="6" y2="14"/>'),                        # BarChart2
        _svg('<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>'
             '<circle cx="9" cy="7" r="4"/>'
             '<path d="M23 21v-2a4 4 0 0 0-3-3.87"/>'
             '<path d="M16 3.13a4 4 0 0 1 0 7.75"/>'),                        # Users
        _svg('<rect x="4" y="4" width="16" height="16" rx="2"/>'
             '<rect x="9" y="9" width="6" height="6"/>'
             '<line x1="9" y1="1" x2="9" y2="4"/>'
             '<line x1="15" y1="1" x2="15" y2="4"/>'
             '<line x1="9" y1="20" x2="9" y2="23"/>'
             '<line x1="15" y1="20" x2="15" y2="23"/>'
             '<line x1="20" y1="9" x2="23" y2="9"/>'
             '<line x1="20" y1="14" x2="23" y2="14"/>'
             '<line x1="1" y1="9" x2="4" y2="9"/>'
             '<line x1="1" y1="14" x2="4" y2="14"/>'),                        # Cpu
        _svg('<circle cx="12" cy="12" r="10"/>'
             '<path d="M8 14s1.5 2 4 2 4-2 4-2"/>'
             '<line x1="9" y1="9" x2="9.01" y2="9"/>'
             '<line x1="15" y1="9" x2="15.01" y2="9"/>'),                     # Smile
        _svg('<path d="M12 2L2 7l10 5 10-5-10-5z"/>'
             '<path d="M2 17l10 5 10-5"/>'
             '<path d="M2 12l10 5 10-5"/>'),                                   # Layers
        _svg('<circle cx="12" cy="12" r="3"/>'
             '<path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 4.93a10 10 0 0 0 0 14.14"'
             '/><path d="M15.54 8.46a5 5 0 0 1 0 7.07M8.46 8.46a5 5 0 0 0 0 7.07"/>'),  # Wifi/Signal
    ]
    ICO_MAP_PIN  = _svg('<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>'
                        '<circle cx="12" cy="10" r="3"/>', size=20)
    ICO_PHONE    = _svg('<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07'
                        'A19.5 19.5 0 0 1 4.69 13a19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 3.6 2.18h3'
                        'a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.91 9.91'
                        'a16 16 0 0 0 6.08 6.08l1.79-1.79a2 2 0 0 1 2.11-.45c.907.339 1.85.573'
                        ' 2.81.7A2 2 0 0 1 22 16.92z"/>', size=20)
    ICO_MAIL     = _svg('<path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2'
                        'V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/>', size=20)
    ICO_GLOBE    = _svg('<circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/>'
                        '<path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10'
                        ' 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>', size=20)
    ICO_CLOCK    = _svg('<circle cx="12" cy="12" r="10"/>'
                        '<polyline points="12 6 12 12 16 14"/>', size=16)

    # ── Images (paths relative to website/index.html) ─────────────────────────
    hero_img = ""
    gallery_imgs = []
    for img in images:
        rel = "../" + img
        if not hero_img:
            hero_img = rel
        gallery_imgs.append(rel)

    # ── Nav links (first pass — before image paths are recomputed below) ────
    nav_items = []
    if (features or attrs) and _show("features"): nav_items.append(("features",     t.get("features_label", "Features")))
    if gallery_imgs and _show("gallery"):          nav_items.append(("gallery",      t.get("gallery_label", "Gallery")))
    if videos and _show("videos"):                 nav_items.append(("videos",       t.get("videos_label", "Videos")))
    if reviews and _show("reviews"):               nav_items.append(("testimonials", t.get("reviews_label", "Reviews")))
    if popular and _show("popular_times"):         nav_items.append(("hours",        t.get("hours_label", "Availability")))
    if qa and _show("faq"):                        nav_items.append(("faq",          t.get("faq_label", "FAQ")))
    if _show("contact"):                           nav_items.append(("contact",      t.get("contact_label", "Contact")))

    nav_html = "\n".join(
        f'<a href="#{aid}" class="nav-link text-white/70 hover:text-white transition-colors text-sm font-medium">{_e(label)}</a>'
        for aid, label in nav_items
    )

    # ── Brand color extraction from images ───────────────────────────────────
    extracted = _extract_brand_colors(images, business_dir)
    if extracted:
        logging.info(f"🎨 Brand colors extracted from images: {extracted}")
        c1 = extracted[0]
        # Use neighboring hues when only 1 base color was found
        c2 = extracted[1] if len(extracted) > 1 else _shift_hue(c1, -35)
        c3 = extracted[2] if len(extracted) > 2 else _shift_hue(c1, +35)
    else:
        logging.info("🎨 Using default brand colors (no vivid colors found in images)")
        c1, c2, c3 = "#4f7df5", "#7c3aed", "#06c9d4"

    # ── Admin-panel theme overrides (from enriched_data.json "theme" key) ───────
    _theme = raw.get("theme", {})
    if _theme.get("color1"): c1 = _theme["color1"]
    if _theme.get("color2"): c2 = _theme["color2"]
    if _theme.get("color3"): c3 = _theme["color3"]

    # Hero background — admin can brighten or change, default keeps near-black
    hero_dark = _theme.get("hero_dark") or "#06060f"

    # CTA button uses its own color if set (must be valid hex), otherwise falls back to c1
    _cta_raw = (_theme.get("cta_color") or "").strip()
    _cta = _cta_raw if (_cta_raw and _cta_raw.startswith("#") and len(_cta_raw) >= 7) else c1

    # Very subtle brand-tinted spot for depth (≤12 % opacity)
    hero_spot  = f"radial-gradient(ellipse 70% 55% at 15% 45%, color-mix(in srgb,{c1} 14%,{hero_dark}), {hero_dark} 65%)"
    text_grad  = f"linear-gradient(135deg, {c1} 0%, {c2} 50%, {c3} 100%)"
    btn_grad   = f"linear-gradient(135deg, {_cta}, {_shift_hue(_cta,-20)})"
    feat_grads = [
        f"linear-gradient(135deg,{c1},{c2})",
        f"linear-gradient(135deg,{c2},{c3})",
        f"linear-gradient(135deg,{c3},{_shift_hue(c3,20)})",
        f"linear-gradient(135deg,{_shift_hue(c1,15)},{c1})",
        f"linear-gradient(135deg,{c1},{_shift_hue(c1,-50)})",
        f"linear-gradient(135deg,{c2},{_shift_hue(c2,25)})",
    ]
    contact_grads = [
        f"linear-gradient(135deg,{c1},{c2})",
        f"linear-gradient(135deg,{c2},{c3})",
        f"linear-gradient(135deg,{c3},{_shift_hue(c3,-25)})",
        f"linear-gradient(135deg,{_shift_hue(c1,-25)},{c1})",
    ]
    c1_faint = f"color-mix(in srgb,{c1} 12%,white)"   # light tint for bg pills

    # ── Shared helpers ────────────────────────────────────────────────────────
    wurl = ("https://" + website_url) if website_url and not website_url.startswith("http") else website_url
    # Use admin-specified CTA link if set, otherwise fall back to website URL
    cta_link = ai.get("cta_link","").strip() or wurl
    google_maps_link = biz.get("google_maps_url", "")
    lat = biz.get("latitude",""); lng = biz.get("longitude","")
    hours = biz.get("hours", {})
    city  = address.split(",")[-2].strip() if address.count(",") >= 2 else address.split(",")[0]

    # ── Images (paths relative to website/index.html) ────────────────────────
    hero_img = ""
    gallery_imgs = []
    for img in images:
        # Images are always served via the /media/<business>/ route
        rel = media_prefix + img
        gallery_imgs.append(rel)

    # Prefer a photo-like image for the hero device frame — skip pure SVG / tiny logos
    # Heuristic: pick the largest file among the first 5 images
    def _pick_hero(image_rels: list, biz_dir: str) -> str:
        best, best_size = "", 0
        for rel in image_rels[:8]:
            full = os.path.join(biz_dir, rel.replace("../", ""))
            try:
                sz = os.path.getsize(full)
                if sz > best_size:
                    best_size = sz
                    best = rel
            except OSError:
                pass
        return best or (image_rels[0] if image_rels else "")

    _hero_override = _theme.get("hero_image")
    if _hero_override:
        hero_img = media_prefix + _hero_override
    else:
        hero_img = _pick_hero(gallery_imgs, business_dir)

    # ── Nav links ─────────────────────────────────────────────────────────────
    nav_items = []
    if (features or attrs) and _show("features"): nav_items.append(("features",     t["features_label"]))
    if gallery_imgs and _show("gallery"):          nav_items.append(("gallery",      t["gallery_label"]))
    if videos and _show("videos"):                 nav_items.append(("videos",       t["videos_label"]))
    if reviews and _show("reviews"):               nav_items.append(("testimonials", t["reviews_label"]))
    if popular and _show("popular_times"):         nav_items.append(("hours",        t["hours_label"]))
    if qa and _show("faq"):                        nav_items.append(("faq",          t["faq_label"]))
    if _show("contact"):                           nav_items.append(("contact",      t["contact_label"]))
    nav_html = "\n".join(
        f'<a href="#{aid}" class="text-white/60 hover:text-white transition-colors text-sm font-medium">{_e(lbl)}</a>'
        for aid, lbl in nav_items)

    # ── Hero device frame ─────────────────────────────────────────────────────
    hero_img_html = ""
    if hero_img:
        hero_img_html = f"""
        <div class="relative w-full">
          <!-- Soft glow behind -->
          <div class="absolute -inset-6 rounded-3xl opacity-20 blur-3xl pointer-events-none" style="background:{btn_grad}"></div>
          <!-- macOS-style browser frame -->
          <div class="relative rounded-2xl overflow-hidden shadow-[0_40px_100px_rgba(0,0,0,0.75)] ring-1 ring-white/10" style="background:#0e0e0e">
            <!-- Titlebar -->
            <div class="flex items-center gap-2 px-4 h-10 shrink-0 border-b border-white/[0.06]" style="background:#161616">
              <span class="w-3 h-3 rounded-full shrink-0" style="background:#ff5f57"></span>
              <span class="w-3 h-3 rounded-full shrink-0" style="background:#febc2e"></span>
              <span class="w-3 h-3 rounded-full shrink-0" style="background:#28c840"></span>
              <div class="flex-1 h-6 rounded-md mx-3" style="background:rgba(255,255,255,0.06)">
                <div class="w-2/3 h-full mx-auto rounded-md" style="background:rgba(255,255,255,0.03)"></div>
              </div>
            </div>
            <!-- Image: responsive height so it never clips on short viewports -->
            <div class="relative overflow-hidden" style="height:clamp(220px,36vh,400px)">
              <img src="{_e(hero_img)}" alt="{_e(name)}"
                   class="absolute inset-0 w-full h-full object-cover"/>
              <div class="absolute inset-0" style="background:linear-gradient(to bottom,transparent 70%,rgba(0,0,0,0.35) 100%)"></div>
            </div>
          </div>
        </div>"""

    # ── Build all sections ────────────────────────────────────────────────────

    # Features
    def _render_icon(icon_val, grad):
        """Render a feature icon — Material Icons name or emoji/SVG fallback."""
        import re as _re
        if icon_val and _re.match(r'^[a-z][a-z0-9_]{1,49}$', str(icon_val).strip()):
            # Material icon name (e.g. "restaurant", "star")
            return (f'<div class="f-ico w-14 h-14 rounded-2xl flex items-center justify-center '
                    f'text-white mb-6 shadow-xl" style="background:{grad}">'
                    f'<span class="material-icons text-2xl">{_e(icon_val)}</span></div>')
        elif icon_val:
            # Emoji or legacy text
            return (f'<div class="f-ico w-14 h-14 rounded-2xl flex items-center justify-center '
                    f'text-white mb-6 shadow-xl text-2xl" style="background:{grad}">{_e(str(icon_val))}</div>')
        else:
            return (f'<div class="f-ico w-14 h-14 rounded-2xl flex items-center justify-center '
                    f'text-white mb-6 shadow-xl" style="background:{grad}">•</div>')

    feat_html = ""
    if features:
        for i, f in enumerate(features[:6]):
            num  = f"0{i+1}"
            fg   = feat_grads[i % len(feat_grads)]
            ico  = _render_icon(f.get("icon",""), fg)
            feat_html += f"""
            <div class="group relative bg-white border border-gray-100 rounded-3xl p-8 hover:shadow-2xl hover:-translate-y-2 transition-all duration-500 overflow-hidden" data-aos="fade-up" data-aos-delay="{i*70}">
              <div class="absolute top-6 right-6 text-7xl font-black leading-none select-none pointer-events-none" style="color:rgba(0,0,0,0.04)">{num}</div>
              {ico}
              <h3 class="text-xl font-bold text-gray-900 mb-3 leading-snug">{_e(f.get("title",""))}</h3>
              <p class="text-gray-500 text-sm leading-relaxed">{_e(f.get("description",""))}</p>
            </div>"""
    elif attrs:
        for i, row in enumerate(attrs[:6]):
            fg = feat_grads[i % len(feat_grads)]; ico = FEAT_ICONS[i % len(FEAT_ICONS)]
            feat_html += f'<div class="group bg-white border border-gray-100 rounded-3xl p-7 hover:shadow-xl hover:-translate-y-1 transition-all duration-400" data-aos="fade-up" data-aos-delay="{i*70}"><div class="w-12 h-12 rounded-2xl flex items-center justify-center text-white mb-4 shadow-lg" style="background:{fg}">{ico}</div><div class="text-xs font-black uppercase tracking-[0.15em] mb-2" style="color:{c1}">{_e(row.get("category",""))}</div><p class="text-gray-800 font-semibold">{_e(row.get("feature",""))}</p></div>'

    features_sec = ""
    if feat_html and _show("features"):
        features_sec = f"""
<section id="features" class="py-32 px-6 bg-[#f8f9ff]">
  <div class="max-w-6xl mx-auto">
    <div class="max-w-2xl mb-20" data-aos="fade-up">
      <div class="sec-pill mb-5">
        {ICO_MAP_PIN} {t["features_label"]}
      </div>
      <h2 class="text-5xl md:text-6xl font-black text-gray-950 leading-[1.08] mb-5">{t["features_h"]}</h2>
      <p class="text-gray-500 text-lg leading-relaxed">{t["features_sub"]}</p>
    </div>
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">{feat_html}</div>
  </div>
</section>"""

    # Gallery — uniform 3-col grid, all cells same height
    gal_html = ""
    for i, img in enumerate(gallery_imgs[:9]):
        delay = (i % 3) * 80
        gal_html += f"""
        <div class="group relative overflow-hidden rounded-2xl bg-gray-900 shadow-lg" style="aspect-ratio:4/3" data-aos="fade-up" data-aos-delay="{delay}">
          <img src="{_e(img)}" alt="{_e(name)} photo {i+1}"
               class="absolute inset-0 w-full h-full object-cover transition-transform duration-700"
               style="transform-origin:center;transition:transform .7s ease"/>
          <div class="absolute inset-0 bg-gradient-to-t from-black/70 via-black/10 to-transparent
                      opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
          <div class="absolute bottom-4 left-4 opacity-0 group-hover:opacity-100 transition-all duration-300 translate-y-2 group-hover:translate-y-0">
            <span class="text-white text-xs font-semibold bg-white/20 backdrop-blur px-3 py-1.5 rounded-full">{_e(name)}</span>
          </div>
        </div>"""

    gallery_sec = ""
    if gallery_imgs and _show("gallery"):
        gallery_sec = f"""
<section id="gallery" class="py-32 px-6" style="background:#0a0a18">
  <div class="max-w-6xl mx-auto">
    <div class="flex flex-col md:flex-row md:items-end md:justify-between gap-6 mb-14" data-aos="fade-up">
      <div>
        <div class="sec-pill sec-pill-dark">{t["gallery_label"]}</div>
        <h2 class="text-5xl md:text-6xl font-black text-white leading-[1.08] tracking-[-0.02em]">{t["gallery_h_pre"]} <span style="background:{text_grad};-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text">{t["gallery_h_post"]}</span></h2>
      </div>
      {"<a href='" + _e(cta_link) + "' target='_blank' class='cta-btn text-white font-bold px-7 py-3.5 rounded-xl text-sm whitespace-nowrap shrink-0'>" + _e(cta_primary) + " →</a>" if cta_link else ""}
    </div>
    <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">{gal_html}</div>
  </div>
</section>"""

    # ── Video section ─────────────────────────────────────────────────────────
    video_sec = ""
    if videos and _show("videos"):
        vid_cards = ""
        for i, vpath in enumerate(videos[:6]):
            # Videos are also served from /media/<business>/videos/…
            rel = media_prefix + vpath
            vid_cards += f"""
        <div class="rounded-3xl overflow-hidden shadow-[0_20px_60px_rgba(0,0,0,0.5)] ring-1 ring-white/10 bg-black" data-aos="fade-up" data-aos-delay="{i*80}">
          <video controls preload="metadata" class="w-full block"
                 style="aspect-ratio:16/9;object-fit:contain;background:#000;max-height:420px">
            <source src="{_e(rel)}" type="{'video/webm' if vpath.lower().endswith('.webm') else 'video/mp4'}">
          </video>
        </div>"""
        video_sec = f"""
<section id="videos" class="py-32 px-6" style="background:#06060f">
  <div class="max-w-6xl mx-auto">
    <div class="max-w-2xl mb-14" data-aos="fade-up">
      <div class="sec-pill sec-pill-dark mb-5">{t["videos_label"]}</div>
      <h2 class="text-5xl md:text-6xl font-black text-white leading-[1.08] tracking-[-0.02em]">{t["videos_h"]}</h2>
    </div>
    <div class="grid grid-cols-1 {'md:grid-cols-2' if len(videos) > 1 else ''} gap-6">
      {vid_cards}
    </div>
  </div>
</section>"""

    # Testimonials
    rev_html = ""
    for i, rev in enumerate(reviews[:8]):
        author   = _e(rev.get("author_name","Anonymous"))
        text     = _e((rev.get("text") or "")[:260])
        r        = rev.get("rating",5)
        stars    = "★"*int(float(r or 5))
        date     = _e(rev.get("date",""))
        initials = author[:2].upper() if author else "??"
        fg       = feat_grads[i % len(feat_grads)]
        rev_html += f"""
        <div class="bg-white border border-gray-100 rounded-3xl p-8 flex flex-col gap-5 hover:shadow-xl hover:-translate-y-1 transition-all duration-400" data-aos="fade-up" data-aos-delay="{(i%3)*80}">
          <div class="flex gap-1 text-yellow-400 text-base">{stars}</div>
          <p class="text-gray-600 text-sm leading-[1.8] flex-1">&ldquo;{text}&rdquo;</p>
          <div class="flex items-center gap-3 pt-5 border-t border-gray-100">
            <div class="w-10 h-10 rounded-full flex items-center justify-center text-white text-xs font-black shrink-0" style="background:{fg}">{_e(initials)}</div>
            <div><div class="font-bold text-gray-900 text-sm">{author}</div><div class="text-gray-400 text-xs mt-0.5">{date}</div></div>
          </div>
        </div>"""
    rev_sec = ""
    if reviews and _show("reviews"):
        rev_sec = f"""
<section id="testimonials" class="py-32 px-6 bg-[#f8f9ff]">
  <div class="max-w-6xl mx-auto">
    <div class="text-center max-w-2xl mx-auto mb-20" data-aos="fade-up">
      <div class="sec-pill mb-5">{t["reviews_label"]}</div>
      <h2 class="text-5xl md:text-6xl font-black text-gray-950 leading-[1.08]">{t["reviews_h"]}</h2>
    </div>
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">{rev_html}</div>
  </div>
</section>"""

    # About / split highlight
    highlight_sec = ""
    if about_para and len(about_para) > 60 and _show("about"):
        bullet_items = ""
        # Use admin-defined highlights if set, otherwise fall back to website paragraphs
        _highlights = raw.get("about", {}).get("highlights") or []
        if _highlights:
            for hl in _highlights[:6]:
                if hl and len(str(hl).strip()) > 2:
                    bullet_items += f'<div class="flex gap-3 items-start"><div class="w-5 h-5 rounded-full flex-shrink-0 mt-0.5 flex items-center justify-center" style="background:{btn_grad}"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg></div><p class="text-white/70 text-sm leading-relaxed">{_e(str(hl)[:180])}</p></div>'
        else:
            for para in (website.get("paragraphs") or [about_para])[:4]:
                if len(para) > 40 and para != about_para:
                    bullet_items += f'<div class="flex gap-3 items-start"><div class="w-5 h-5 rounded-full flex-shrink-0 mt-0.5 flex items-center justify-center" style="background:{btn_grad}"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg></div><p class="text-white/70 text-sm leading-relaxed">{_e(para[:180])}</p></div>'
        highlight_sec = f"""
<section class="py-32 px-6" style="background:#0d0d1e">
  <div class="max-w-6xl mx-auto grid lg:grid-cols-2 gap-20 items-center">
    <div data-aos="fade-right">
      <div class="sec-pill sec-pill-dark mb-6">{t["about_label"]}</div>
      <h2 class="text-4xl md:text-5xl font-black text-white leading-[1.1] mb-8">{_e(name)},<br/><span style="background:{text_grad};-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text">{t["about_suffix"]}</span></h2>
      <p class="text-white/55 text-lg leading-relaxed mb-10">{_e(about_para[:300])}</p>
      {"<a href='" + _e(cta_link) + "' target='_blank' class='inline-flex items-center gap-2 cta-btn text-white font-bold px-7 py-3.5 rounded-xl text-sm transition-all'>" + _e(cta_primary) + " →</a>" if cta_link else ""}
    </div>
    <div class="flex flex-col gap-4" data-aos="fade-left" data-aos-delay="100">
      {bullet_items or ""}
      {("<div class='mt-8 rounded-2xl overflow-hidden shadow-2xl ring-1 ring-white/10'><img src=" + repr(gallery_imgs[1] if len(gallery_imgs)>1 else hero_img) + ' class="w-full object-cover" style="max-height:260px"/></div>') if gallery_imgs else ""}
    </div>
  </div>
</section>"""

    # Popular times
    pop_sec = ""
    if popular and _show("popular_times"):
        days_order  = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
        avail_days  = [d for d in days_order if d in popular]
        tabs_html, panels_html = "", ""
        for i, day in enumerate(avail_days):
            active = i == 0
            ts = f'style="background:{btn_grad}"' if active else ""
            tc = "text-white shadow-lg" if active else "bg-white/5 text-white/50 hover:text-white hover:bg-white/10"
            tabs_html += f'<button onclick="sDay(\'{day}\')" id="t-{day}" class="px-5 py-2.5 rounded-xl text-sm font-bold transition-all {tc}" {ts}>{day[:3]}</button>\n'
            bars = ""
            for h in popular[day]:
                hour = h.get("hour",""); busy = h.get("busyness","")
                pm   = re.search(r"(\d+)%", busy)
                pct  = int(pm.group(1)) if pm else (88 if "very" in busy.lower() else 60 if "busy" in busy.lower() else 35 if "normal" in busy.lower() else 15)
                bc   = btn_grad if pct>70 else f"linear-gradient(to top,{c2},{c3})" if pct>40 else "linear-gradient(to top,#374151,#4b5563)"
                bars += f'<div class="flex flex-col items-center gap-2 group cursor-default" title="{_e(hour)}: {_e(busy)}"><div class="w-8 rounded-t-lg relative bg-white/5" style="height:100px"><div class="absolute bottom-0 left-0 w-full rounded-t-lg transition-all duration-700" style="height:{pct}%;background:{bc}"></div></div><span class="text-[10px] text-white/30 group-hover:text-white/60 transition-colors whitespace-nowrap" style="writing-mode:vertical-rl;transform:rotate(180deg)">{_e(hour.replace(" ",""))}</span></div>'
            disp = "flex" if active else "hidden"
            panels_html += f'<div id="p-{day}" class="{disp} gap-2 items-end overflow-x-auto pb-2 pt-3 min-h-36">{bars}</div>\n'

        pop_sec = f"""
<section id="hours" class="py-32 px-6" style="background:#0a0a18">
  <div class="max-w-4xl mx-auto">
    <div class="text-center mb-16" data-aos="fade-up">
      <div class="sec-pill sec-pill-dark mb-5">{t["hours_label"]}</div>
      <h2 class="text-5xl font-black text-white">{t["hours_h"]}</h2>
    </div>
    <div class="bg-white/5 backdrop-blur-xl rounded-3xl border border-white/8 p-8 md:p-10" data-aos="fade-up">
      <div class="flex gap-2 mb-8 flex-wrap">{tabs_html}</div>
      {panels_html}
    </div>
  </div>
</section>
<script>
var _bg="{btn_grad}";
function sDay(d){{var ds={json.dumps(avail_days)};ds.forEach(function(x){{
  var p=document.getElementById('p-'+x),t=document.getElementById('t-'+x);
  p.className=x===d?'flex gap-2 items-end overflow-x-auto pb-2 pt-3 min-h-36':'hidden';
  if(x===d){{t.className='px-5 py-2.5 rounded-xl text-sm font-bold transition-all text-white shadow-lg';t.style.background=_bg;}}
  else{{t.className='px-5 py-2.5 rounded-xl text-sm font-bold transition-all bg-white/5 text-white/50 hover:text-white hover:bg-white/10';t.style.background='';}}
}});}}
</script>"""

    # FAQ
    faq_sec = ""
    if qa and _show("faq"):
        faq_items = ""
        for i, q in enumerate(qa[:10]):
            question = _e(q.get("question",""))
            answer   = _e(q.get("answer","") or q.get("additional",""))
            faq_items += f"""
            <div class="border border-gray-100 rounded-2xl bg-white overflow-hidden shadow-sm hover:shadow-md transition-shadow" data-aos="fade-up" data-aos-delay="{i*50}">
              <button onclick="tFq({i})" class="w-full flex justify-between items-center px-8 py-6 text-left group">
                <span class="font-semibold text-gray-900 text-base group-hover:text-[{c1}] transition-colors pr-4">{question}</span>
                <svg id="fqi-{i}" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="shrink-0 text-gray-400 transition-transform duration-300"><polyline points="6 9 12 15 18 9"/></svg>
              </button>
              <div id="fqa-{i}" class="hidden px-8 pb-7 text-gray-500 text-sm leading-[1.8] border-t border-gray-100 pt-4">{answer}</div>
            </div>"""
        faq_sec = f"""
<section id="faq" class="py-32 px-6 bg-white">
  <div class="max-w-3xl mx-auto">
    <div class="text-center mb-16" data-aos="fade-up">
      <div class="sec-pill mb-5">{t["faq_label"]}</div>
      <h2 class="text-5xl font-black text-gray-950">{t["faq_h"]}</h2>
    </div>
    <div class="flex flex-col gap-3">{faq_items}</div>
  </div>
</section>
<script>function tFq(i){{var a=document.getElementById('fqa-'+i),ic=document.getElementById('fqi-'+i),o=a.classList.contains('hidden');a.classList.toggle('hidden',!o);ic.style.transform=o?'rotate(180deg)':'';}}
</script>"""

    # Contact
    def _cc(cg, ico, lbl, body):
        return (f'<div class="flex gap-4 p-5 bg-gray-50 rounded-2xl hover:bg-gray-100 transition-colors items-start">'
                f'<div class="w-12 h-12 rounded-2xl flex items-center justify-center text-white shrink-0 shadow-md" style="background:{cg}">{ico}</div>'
                f'<div><div class="font-bold text-gray-800 text-sm mb-1">{lbl}</div>{body}</div></div>')

    ls = f'font-weight:600;font-size:.875rem;color:{c1};'
    ccs = ""
    if address: ccs += _cc(contact_grads[0], ICO_MAP_PIN, t["addr_lbl"],  f'<p class="text-gray-500 text-sm">{_e(address)}</p>')
    if phone:   ccs += _cc(contact_grads[1], ICO_PHONE,   t["phone_lbl"], f'<a href="tel:{_e(phone)}" style="{ls}">{_e(phone)}</a>')
    if email:   ccs += _cc(contact_grads[2], ICO_MAIL,    t["email_lbl"], f'<a href="mailto:{_e(email)}" style="{ls}">{_e(email)}</a>')
    if wurl:    ccs += _cc(contact_grads[3], ICO_GLOBE,   t["web_lbl"],   f'<a href="{_e(wurl)}" target="_blank" style="{ls}">{_e(website_url)}</a>')

    hrs_html = ""
    if any(hours.values()):
        for k, lbl in t["days"].items():
            val = hours.get(k,"") or "Closed"
            closed = "closed" in val.lower()
            hrs_html += f'<div class="flex justify-between py-2.5 border-b border-gray-100 last:border-0"><span class="text-sm font-medium text-gray-700">{lbl}</span><span class="text-sm {"font-medium" if not closed else "text-red-400"}" style="{f"color:{c1}" if not closed else ""}">{_e(val)}</span></div>'

    map_h = f'<div class="rounded-3xl overflow-hidden shadow-xl h-full" style="min-height:320px"><iframe src="https://maps.google.com/maps?q={_e(lat)},{_e(lng)}&z=15&output=embed" class="w-full border-0" style="height:100%;min-height:320px" allowfullscreen loading="lazy"></iframe></div>' if lat and lng else ""

    contact_sec = f"""
<section id="contact" class="py-32 px-6 bg-[#f8f9ff]">
  <div class="max-w-6xl mx-auto">
    <div class="max-w-2xl mb-20" data-aos="fade-up">
      <div class="sec-pill mb-5">{t["contact_label"]}</div>
      <h2 class="text-5xl md:text-6xl font-black text-gray-950 leading-[1.08]">{t["contact_h_pre"]}<br/>{t["contact_h_post"]}</h2>
    </div>
    <div class="grid lg:grid-cols-2 gap-10">
      <div class="flex flex-col gap-4" data-aos="fade-right">
        {ccs}
          {"<div class='bg-white border border-gray-100 rounded-3xl p-7 shadow-sm mt-2'><div class='flex items-center gap-2 font-bold text-gray-900 text-sm mb-4'>" + ICO_CLOCK + " " + t["hours_lbl"] + "</div>" + hrs_html + "</div>" if hrs_html else ""}
      </div>
      <div data-aos="fade-left">{map_h}</div>
    </div>
  </div>
</section>"""
    if not _show("contact"):
        contact_sec = ""

    # CTA Banner — section-specific button label/link when set, else main CTA; uses .cta-btn for theme color
    cta_banner = ""
    if wurl and _show("cta"):
        _ai = raw.get("ai", {})
        cta_text = (_ai.get("cta_heading") or
                    (website.get("headings",[""])[8] if len(website.get("headings",[]))>8 else t["cta_cta_h"]))
        cta_sub  = _ai.get("cta_subtitle") or subtitle
        _banner_lbl = (_ai.get("cta_banner_btn_label") or "").strip() or cta_primary
        _banner_url = (_ai.get("cta_banner_btn_link") or "").strip() or cta_link
        cta_banner = f"""
<section class="py-28 px-6 relative overflow-hidden" style="background:linear-gradient(135deg,{_darken_hex(c1,0.55)},{_darken_hex(c2,0.45)})">
  <div class="orb w-96 h-96 right-0 top-0 opacity-20" style="background:{c3}"></div>
  <div class="relative z-10 max-w-3xl mx-auto text-center" data-aos="fade-up">
    <h2 class="text-4xl md:text-5xl font-black text-white mb-6 leading-tight">{_e(cta_text[:80])}</h2>
    <p class="text-white/60 text-lg mb-10">{_e(cta_sub[:200])}</p>
    <a href="{_e(_banner_url)}" target="_blank" class="cta-btn inline-flex items-center gap-3 text-white font-black px-10 py-5 rounded-2xl text-base shadow-2xl hover:scale-105 transition-all">
      {_e(_banner_lbl)} <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
    </a>
  </div>
</section>"""

    # Keywords marquee
    kw_sec = ""
    clean_kw = [k for k in keywords if len(k)>2]
    if clean_kw and _show("keywords"):
        pills = " ".join(f'<span class="inline-flex items-center gap-2 px-5 py-2.5 rounded-full text-xs font-bold uppercase tracking-widest whitespace-nowrap border border-white/8 text-white/60" style="background:rgba(255,255,255,0.04)">· {_e(k)}</span>' for k in clean_kw[:16])
        kw_sec = f'<div class="overflow-hidden py-6 border-y border-white/5" style="background:#08081a"><div class="marquee">{pills}&nbsp;&nbsp;&nbsp;{pills}</div></div>'

    # Social footer — SVG icons per platform
    def _soc_svg(name):
        n = name.lower()
        if "facebook"  in n: return '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M18 2h-3a5 5 0 00-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 011-1h3z"/></svg>'
        if "instagram" in n: return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="20" rx="5"/><path d="M16 11.37A4 4 0 1112.63 8 4 4 0 0116 11.37z"/><line x1="17.5" y1="6.5" x2="17.51" y2="6.5"/></svg>'
        if "linkedin"  in n: return '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M16 8a6 6 0 016 6v7h-4v-7a2 2 0 00-2-2 2 2 0 00-2 2v7h-4v-7a6 6 0 016-6zM2 9h4v12H2z"/><circle cx="4" cy="4" r="2"/></svg>'
        if "youtube"   in n: return '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M22.54 6.42a2.78 2.78 0 00-1.95-1.96C18.88 4 12 4 12 4s-6.88 0-8.59.46a2.78 2.78 0 00-1.95 1.96A29 29 0 001 12a29 29 0 00.46 5.33A2.78 2.78 0 003.41 19.1C5.12 19.56 12 19.56 12 19.56s6.88 0 8.59-.46a2.78 2.78 0 001.95-1.95A29 29 0 0023 12a29 29 0 00-.46-5.58z"/><polygon points="9.75 15.02 15.5 12 9.75 8.98" fill="#fff"/></svg>'
        if "twitter"   in n or " x" in n: return '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.737l7.73-8.835L1.254 2.25H8.08l4.261 5.632zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>'
        if "tiktok"    in n: return '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M19.59 6.69a4.83 4.83 0 01-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 01-2.88 2.5 2.89 2.89 0 01-2.89-2.89 2.89 2.89 0 012.89-2.89c.28 0 .54.04.79.1V9.01a6.34 6.34 0 106.34 6.34V8.75a8.12 8.12 0 004.77 1.52V6.82a4.85 4.85 0 01-1-.13z"/></svg>'
        if "whatsapp"  in n: return '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51a6.34 6.34 0 00-.57-.01c-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654A11.882 11.882 0 0012.05 24h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>'
        if "pinterest" in n: return '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0a12 12 0 00-4.373 23.178c-.03-.528-.005-1.163.13-1.738l.97-4.11s-.248-.494-.248-1.228c0-1.15.668-2.01 1.5-2.01.707 0 1.05.53 1.05 1.167 0 .71-.453 1.775-.687 2.763-.195.824.413 1.495 1.224 1.495 1.467 0 2.597-1.547 2.597-3.78 0-1.975-1.42-3.354-3.448-3.354-2.348 0-3.725 1.76-3.725 3.579 0 .708.272 1.466.613 1.88a.246.246 0 01.057.233c-.062.26-.2.824-.228.939-.037.15-.122.182-.28.11-1.048-.488-1.703-2.023-1.703-3.257 0-2.647 1.923-5.082 5.547-5.082 2.912 0 5.177 2.073 5.177 4.844 0 2.89-1.822 5.213-4.348 5.213-.85 0-1.649-.442-1.923-.962l-.522 1.948c-.19.727-.698 1.636-1.04 2.19.785.243 1.615.374 2.476.374a12 12 0 000-24z"/></svg>'
        return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>'

    soc_html = ""
    for lnk in social:
        if isinstance(lnk, str):
            lnk = {"url": lnk, "platform": ""}
        url = lnk.get("url","").strip()
        if not url:
            continue
        ico = _soc_svg(lnk.get("platform",""))
        soc_html += f'<a href="{_e(url)}" target="_blank" class="w-10 h-10 rounded-xl flex items-center justify-center text-white/50 hover:text-white transition-all border border-white/10 hover:border-white/25">{ico}</a>'
    if google_maps_link:
        soc_html += f'<a href="{_e(google_maps_link)}" target="_blank" class="w-10 h-10 rounded-xl flex items-center justify-center text-white/50 hover:text-white transition-all border border-white/10 hover:border-white/25">{ICO_MAP_PIN}</a>'

    # ── Final HTML ────────────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en" class="scroll-smooth">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>{_e(seo_title)}</title>
  <meta name="description" content="{_e(seo_desc)}"/>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet"/>
  <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet"/>
  <link href="https://unpkg.com/aos@2.3.4/dist/aos.css" rel="stylesheet"/>
  <style>
    :root{{--c1:{c1};--c2:{c2};--c3:{c3};--hero:{hero_dark};}}
    *{{box-sizing:border-box;margin:0;padding:0;}}
    html{{scroll-behavior:smooth;}}
    body{{font-family:'Inter',sans-serif;-webkit-font-smoothing:antialiased;background:#fff;color:#111;}}
    /* Hero — always near-black, brand color as subtle spot only */
    .hero-bg{{background:{hero_spot};position:relative;}}
    /* Dot grid overlay */
    .dot-grid::before{{content:'';position:absolute;inset:0;background-image:radial-gradient(rgba(255,255,255,0.055) 1px,transparent 1px);background-size:28px 28px;pointer-events:none;}}
    /* Floating orbs */
    .orb{{position:absolute;border-radius:50%;filter:blur(110px);animation:floatOrb 12s ease-in-out infinite;pointer-events:none;}}
    @keyframes floatOrb{{0%,100%{{transform:translateY(0) scale(1)}}50%{{transform:translateY(-40px) scale(1.06)}}}}
    /* Gradient text */
    .gt{{background:{text_grad};-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}}
    /* CTA button — !important so Tailwind/utilities cannot override */
    a.cta-btn,.cta-btn{{background:{btn_grad}!important;transition:transform .2s,box-shadow .3s;border:none;}}
    a.cta-btn:hover,.cta-btn:hover{{transform:translateY(-2px);box-shadow:0 20px 60px color-mix(in srgb,{c1} 50%,transparent);}}
    /* Outline button */
    .btn-outline{{background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.14);transition:background .2s,border-color .2s;}}
    .btn-outline:hover{{background:rgba(255,255,255,0.12);border-color:rgba(255,255,255,0.25);}}
    /* Nav */
    #nav{{transition:background .4s,backdrop-filter .4s,border-color .4s;}}
    #nav.scrolled{{background:rgba(6,6,15,0.94);backdrop-filter:blur(24px);border-color:rgba(255,255,255,0.06)!important;}}
    /* Marquee */
    .marquee{{display:flex;gap:12px;animation:marquee 40s linear infinite;width:max-content;}}
    @keyframes marquee{{to{{transform:translateX(-50%)}}}}
    /* Section label pill */
    .sec-pill{{display:inline-flex;align-items:center;gap:8px;font-size:.68rem;font-weight:800;letter-spacing:.18em;text-transform:uppercase;padding:.4rem 1rem;border-radius:9999px;background:{c1_faint};color:{c1};margin-bottom:1.5rem;}}
    .sec-pill-dark{{background:rgba(255,255,255,0.07);color:rgba(255,255,255,0.55);}}
    /* Feature card hover */
    .feat-card:hover{{box-shadow:0 24px 64px rgba(0,0,0,0.10);}}
    .feat-card:hover .f-ico{{transform:scale(1.12);box-shadow:0 12px 30px color-mix(in srgb,{c1} 40%,transparent);}}
    /* Gallery image zoom */
    .gal-img:hover img{{transform:scale(1.08);}}
  </style>
</head>
<body>

<!-- NAV -->
<nav id="nav" class="fixed top-0 w-full z-50 border-b border-transparent px-6 lg:px-10">
  <div class="max-w-7xl mx-auto h-16 flex items-center justify-between">
    <a href="#" class="font-black text-xl text-white tracking-tight">{_e(brand_name)}</a>
    <div class="hidden md:flex items-center gap-8">
      {nav_html}
    </div>
    {"<a href='" + _e(cta_link) + "' target='_blank' class='cta-btn text-white text-sm font-bold px-5 py-2.5 rounded-xl'>" + _e(cta_primary) + " →</a>" if cta_link else ""}
  </div>
</nav>

<!-- HERO -->
<section class="hero-bg dot-grid relative min-h-screen flex items-center overflow-hidden px-6 lg:px-10">
  <!-- Orbs: brand color, very low opacity so dark bg stays dominant -->
  <div class="orb w-[600px] h-[600px] -top-40 -left-48" style="background:{c1};opacity:.18;animation-delay:0s"></div>
  <div class="orb w-72 h-72 bottom-20 right-16" style="background:{c2};opacity:.14;animation-delay:-6s"></div>
  <div class="orb w-52 h-52" style="background:{c3};opacity:.10;top:40%;left:55%;animation-delay:-12s"></div>

  <!-- Grid fills full viewport height so both columns are truly centered -->
  <div class="relative z-10 w-full min-h-screen flex flex-col justify-center">
    <div class="max-w-7xl mx-auto w-full px-6 lg:px-10 py-28
                grid lg:grid-cols-[1fr_1fr] gap-10 xl:gap-16 items-center">

      <!-- ── LEFT: text ── -->
      <div>
        <div class="inline-flex items-center gap-2 sec-pill sec-pill-dark mb-6" data-aos="fade-down">
          <span class="w-2 h-2 rounded-full animate-pulse" style="background:{c3}"></span>
          {_e(biz.get("place_type","Business"))} &nbsp;·&nbsp; {_e(city)}
        </div>
        <h1 class="font-black leading-[1.04] tracking-[-0.025em] text-white mb-6"
            style="font-size:clamp(2.2rem,4.8vw,4rem)" data-aos="fade-up" data-aos-delay="60">
          <span class="gt">{_e(tagline)}</span>
        </h1>
        <p class="text-white/50 text-[1.05rem] leading-[1.8] mb-10 max-w-md"
           data-aos="fade-up" data-aos-delay="130">
          {_e(subtitle)}
        </p>
        <div class="flex flex-wrap gap-4" data-aos="fade-up" data-aos-delay="200">
          {"<a href='" + _e(cta_link) + "' target='_blank' class='cta-btn inline-flex items-center gap-2.5 text-white font-bold px-8 py-[14px] rounded-2xl text-[15px]'>" + _e(cta_primary) + " <svg xmlns='http://www.w3.org/2000/svg' width='14' height='14' fill='none' stroke='currentColor' stroke-width='2.5' viewBox='0 0 24 24'><line x1='5' y1='12' x2='19' y2='12'/><polyline points='12 5 19 12 12 19'/></svg></a>" if cta_link else ""}
          <a href="#contact" class="btn-outline inline-flex items-center gap-2.5 text-white/75 font-semibold px-8 py-[14px] rounded-2xl text-[15px]">
            {_e(cta_secondary)}
          </a>
        </div>
        <!-- Stat chips -->
        <div class="flex flex-wrap gap-8 mt-12 pt-10 border-t border-white/[0.08]"
             data-aos="fade-up" data-aos-delay="280">
          {(f'<div><div class="flex items-baseline gap-1"><span class="text-[2rem] font-black text-white tracking-tight leading-none">{_e(rating)}</span><span class="text-yellow-400 text-lg ml-1">★</span></div><div class="text-white/35 text-[10px] uppercase tracking-widest mt-1">{t["rating_lbl"]}</div></div>' if rating else "") +
           (f'<div><div class="text-[2rem] font-black text-white tracking-tight leading-none">{_e(reviews_count)}</div><div class="text-white/35 text-[10px] uppercase tracking-widest mt-1">{t["reviews_lbl"]}</div></div>' if reviews_count else "") +
           (f'<div><div class="text-sm font-bold leading-none mt-0.5" style="color:{c2}">{_e(biz.get("place_type",""))}</div><div class="text-white/35 text-[10px] uppercase tracking-widest mt-1">{t["industry_lbl"]}</div></div>' if biz.get("place_type") else "") +
           (f'<div><div class="text-sm font-bold leading-none mt-0.5 text-white">{_e(biz.get("price_range",""))}</div><div class="text-white/35 text-[10px] uppercase tracking-widest mt-1">Price Range</div></div>' if biz.get("price_range") else "")}
        </div>
      </div>

      <!-- ── RIGHT: device frame — hidden on mobile ── -->
      {"<div class='hidden lg:block' data-aos='fade-left' data-aos-delay='150'>" + hero_img_html + "</div>" if hero_img_html else ""}

    </div>
  </div>

  <!-- Scroll hint -->
  <div class="absolute bottom-6 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 text-white/20 animate-bounce z-20">
    <span class="text-[9px] tracking-[0.3em] uppercase font-semibold">{t["scroll_lbl"]}</span>
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><polyline points="19 12 12 19 5 12"/></svg>
  </div>
</section>

{kw_sec}
{features_sec}
{gallery_sec}
{video_sec}
{highlight_sec}
{rev_sec}
{pop_sec}
{faq_sec}
{contact_sec}
{cta_banner}

<!-- FOOTER -->
<footer style="background:#06060f" class="pt-20 pb-10 px-6 lg:px-10">
  <div class="max-w-7xl mx-auto">
    <div class="grid md:grid-cols-3 gap-12 pb-12 border-b border-white/8">
      <div class="md:col-span-2">
        <div class="font-black text-2xl mb-3 gt">{_e(name)}</div>
        <p class="text-white/35 text-sm leading-relaxed max-w-md">{_e((ai.get("footer_tagline") or about_para or subtitle)[:200])}</p>
        <div class="flex gap-3 mt-6">{soc_html}</div>
      </div>
      <div>
        <div class="text-white/50 text-xs font-black uppercase tracking-widest mb-4">Contact</div>
        <div class="flex flex-col gap-2 text-sm text-white/40">
          {f'<span>{_e(address)}</span>' if address else ""}
          {f'<a href="tel:{_e(phone)}" class="hover:text-white transition-colors">{_e(phone)}</a>' if phone else ""}
          {f'<a href="mailto:{_e(email)}" class="hover:text-white transition-colors">{_e(email)}</a>' if email else ""}
          {f'<a href="{_e(wurl)}" target="_blank" class="hover:text-white transition-colors">{_e(website_url)}</a>' if wurl else ""}
        </div>
      </div>
    </div>
    <div class="flex flex-col md:flex-row justify-between items-center gap-4 pt-8 text-xs text-white/20">
      <span>{_e(ai.get("footer_copyright") or f"© {__import__('datetime').date.today().year} {name}. {t['copyright']}")}</span>
      {f'<a href="{_e(google_maps_link)}" target="_blank" class="hover:text-white/50 transition-colors">{t["gmaps_lbl"]}</a>' if google_maps_link else ""}
    </div>
  </div>
</footer>

<script src="https://unpkg.com/aos@2.3.4/dist/aos.js"></script>
<script>
  AOS.init({{duration:800,once:true,offset:80,easing:'ease-out-cubic'}});
  window.addEventListener('scroll',function(){{
    document.getElementById('nav').classList.toggle('scrolled',window.scrollY>40);
  }});
</script>
</body>
</html>"""

    return html


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate a static one-page website from enriched Google Maps data")
    parser.add_argument("--dir",  required=True, help="Path to business ScrapeData folder (e.g. ScrapeData/Digimidi)")
    parser.add_argument("--open", action="store_true", help="Open the generated site in browser after creation")
    args = parser.parse_args()
    generate(args.dir, open_browser=args.open)


if __name__ == "__main__":
    main()
