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
from jinja2 import Environment, FileSystemLoader, select_autoescape

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


def load_template_config(template_id: str) -> dict:
    """Load a template's configuration from template.json with safe defaults."""
    config_path = os.path.join(
        os.path.dirname(__file__),
        "templates", "websites", template_id, "template.json"
    )
    if os.path.isfile(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    return loaded
        except Exception as exc:
            _log.warning(f"Failed to load template config for '{template_id}': {exc}")

    return {
        "id": template_id,
        "sections": {"enabled": [], "configs": {}},
        "theme": {"color_mode": "solid"},
    }


def _is_section_enabled(section_id: str, template_config: dict) -> bool:
    enabled = (template_config.get("sections") or {}).get("enabled") or []
    if not enabled:
        return True
    return section_id in enabled


def _has_section_data(section_type: str, data: dict) -> bool:
    """Validate whether a section has renderable data."""
    if section_type == "reviews":
        reviews = data.get("reviews", [])
        return bool(reviews and any((r.get("text") or "").strip() for r in reviews if isinstance(r, dict)))

    if section_type == "videos":
        videos = data.get("videos", [])
        return bool(videos and len(videos) > 0)

    if section_type in {"gallery", "gallery_alt", "portfolio"}:
        images = data.get("images", [])
        return bool(images and len(images) > 0)

    if section_type == "faq":
        qa = data.get("qa", [])
        return bool(qa and any((q.get("question") or "").strip() for q in qa if isinstance(q, dict)))

    if section_type in {"features", "services", "process"}:
        features = data.get("features") or data.get("ai", {}).get("features", [])
        return bool(features and len(features) > 0)

    if section_type == "about":
        ai = data.get("ai", {})
        return bool((ai.get("about_paragraph") or "").strip())

    if section_type == "contact":
        biz = data.get("business", {})
        return bool((biz.get("address") or "").strip() or (biz.get("phone") or "").strip() or (biz.get("email") or "").strip())

    if section_type in {"stats", "testimonials"}:
        biz = data.get("business", {})
        if section_type == "stats":
            return bool(biz.get("rating") or biz.get("reviews_count"))
        reviews = data.get("reviews", [])
        return bool(reviews and len(reviews) >= 1)

    if section_type in {"cta", "footer", "hero", "navbar", "top_header"}:
        return True

    return False


def _build_gallery_grid(images: list, media_prefix: str, max_images: int = 16, title: str = "Gallery") -> str:
    """Standard responsive gallery grid that shows all available images up to max_images."""
    if not images:
        return ""

    gallery_items = ""
    for img in images[:max_images]:
        gallery_items += f'''
            <div class="gallery-item">
                <img src="{media_prefix + _e(img)}" alt="Gallery" loading="lazy">
            </div>'''

    return f'''<section class="section-gallery" id="gallery">
        <div class="container">
            <h2 class="section-title">{_e(title)}</h2>
            <div class="gallery-grid">{gallery_items}
            </div>
        </div>
    </section>'''


def _build_gallery_alternating(images: list, paragraphs: list, media_prefix: str, images_to_show: int = 4) -> str:
    """Alternating text + image layout, with graceful fallback when content is insufficient."""
    if not images:
        return ""

    good_paras = [p for p in (paragraphs or []) if isinstance(p, str) and len(p.strip()) > 80]
    if len(good_paras) < 2 or len(images) < 3:
        return ""

    rows_to_render = min(max(images_to_show, 2), len(good_paras), len(images) - 1)
    if rows_to_render < 2:
        return ""

    html = ['<section class="section-gallery-alt" id="gallery">', '    <div class="container">']
    for i in range(rows_to_render):
        reverse = " reverse" if i % 2 == 1 else ""
        html.append(f'''
            <div class="gallery-alt-grid{reverse}">
                <div class="gallery-alt-content">
                    <p>{_e(good_paras[i])}</p>
                </div>
                <div class="gallery-alt-image">
                    <img src="{media_prefix + _e(images[i + 1])}" alt="Gallery Image {i + 1}" loading="lazy">
                </div>
            </div>''')

    remaining = images[rows_to_render + 1:]
    if remaining:
        grid_items = "".join(
            f'<div class="gallery-item"><img src="{media_prefix + _e(img)}" alt="Gallery" loading="lazy"></div>'
            for img in remaining[:12]
        )
        html.append(f'<div class="gallery-grid additional-images">{grid_items}</div>')

    html.append('    </div>')
    html.append('</section>')
    return "\n".join(html)


def build_html(business_dir: str, use_draft: bool = False, override_data: dict = None, template: str = "default") -> str:
    """
    Build the complete website HTML for a business and return it as a string.
    Does NOT write any files — callers decide what to do with the result.

    If use_draft is True and draft_data.json exists, that file is used.
    If override_data is provided, it is used as the source data (live preview).
    If template is not provided, uses "default" template.
    """
    return _render(business_dir, use_draft=use_draft, override_raw=override_data, template=template)


def generate(business_dir: str, open_browser: bool = False, template: str = "default") -> str:
    """Build the HTML, write it to website/index.html, and return the output path.

    This always uses the published enriched_data.json, not the draft JSON.
    Uses the specified template (default: "default").
    """
    html = build_html(business_dir, use_draft=False, template=template)
    out_dir = os.path.join(business_dir, "website")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    _log.info(f"✅ Website generated (template: {template}) → {out_path}")
    if open_browser:
        import webbrowser
        webbrowser.open(f"file://{os.path.abspath(out_path)}")
    return out_path


def _render_jinja2_template(business_dir: str, template: str, use_draft: bool = False, override_raw: dict = None) -> str:
    """
    Render a Jinja2-based template with prepared context data.
    Replaces _render_external_template for modular component-based templates.
    """
    # Load data
    enriched_path = os.path.join(business_dir, "enriched_data.json")
    draft_path = os.path.join(business_dir, "draft_data.json")

    if override_raw is not None:
        raw = override_raw
    elif use_draft:
        source_path = draft_path if os.path.isfile(draft_path) else enriched_path
        raw = _load_json(source_path) if os.path.isfile(source_path) else {}
    else:
        source_path = enriched_path
        raw = _load_json(source_path) if os.path.isfile(source_path) else {}

    place_raw = _load_json(os.path.join(business_dir, "place_data.json"))
    day_order = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    biz = raw.get("business") or {
        "name": place_raw.get("name", ""),
        "place_type": place_raw.get("place_type", ""),
        "address": place_raw.get("address", ""),
        "phone": place_raw.get("phone_number", ""),
        "website": place_raw.get("website", ""),
        "email": place_raw.get("email", ""),
        "rating": place_raw.get("reviews_average"),
        "reviews_count": place_raw.get("reviews_count"),
        "latitude": place_raw.get("latitude", ""),
        "longitude": place_raw.get("longitude", ""),
        "hours": {d: place_raw.get(d, "") for d in day_order},
    }
    ai = raw.get("ai", {})

    biz_slug = os.path.basename(business_dir.rstrip("/\\"))
    media_prefix = f"/media/{biz_slug}/"

    _json_images = raw.get("images")
    images = _json_images if _json_images else _find_images(os.path.join(business_dir, "images"))
    videos_raw = _find_videos(os.path.join(business_dir, "videos"))
    reviews = raw.get("reviews") or _load_csv(os.path.join(business_dir, "reviews.csv"))
    qa = raw.get("qa") or _load_csv(os.path.join(business_dir, "qa.csv"))
    website = raw.get("website_data") or {}
    features_raw = ai.get("features") or []
    reviews = [r for r in reviews if isinstance(r, dict) and (r.get("text", "").strip())]
    qa = [q for q in qa if isinstance(q, dict) and (q.get("question", "").strip())]

    _theme = raw.get("theme", {})

    # Prepare hero image
    hero_image_choice = _theme.get("hero_image", "").strip()
    if hero_image_choice and hero_image_choice in images:
        hero_image = media_prefix + hero_image_choice
    else:
        hero_image = media_prefix + images[0] if images else ""

    # Prepare keywords - match old renderer behavior
    keywords_raw = ai.get("keywords") or []
    keywords = []
    # Add business info to keywords list like old renderer
    if biz.get("place_type"):
        keywords.append(biz.get("place_type"))
    if biz.get("address"):
        keywords.append(biz.get("address"))
    if biz.get("phone"):
        keywords.append(biz.get("phone"))
    # Add location code if available
    plus_code = place_raw.get("plus_code", "")
    if plus_code:
        keywords.append(plus_code)
    # Add AI keywords
    for kw in keywords_raw[:20]:
        keyword_text = kw.get("keyword", kw) if isinstance(kw, dict) else str(kw)
        if keyword_text and keyword_text not in keywords:
            keywords.append(keyword_text)

    # Prepare features for default template
    emoji_to_material_icon = {
        "🍽️": "restaurant", "🍪": "cookie", "☀️": "wb_sunny",
        "🌅": "wb_twilight", "🍷": "wine_bar", "🔥": "local_fire_department",
        "🎉": "celebration", "👨‍🍳": "restaurant", "🤖": "smart_toy",
        "💬": "chat", "✍️": "edit_note", "📊": "bar_chart", "🏛️": "account_balance"
    }

    features = []
    for idx, feat in enumerate(features_raw[:12]):
        icon = feat.get("icon", "✦")
        icon_str = str(icon).strip()

        # Determine icon type and convert for default template
        if re.match(r'^[a-z][a-z0-9_]{1,49}$', icon_str):
            icon_type = "material"
            material_icon = icon_str
        elif icon_str in emoji_to_material_icon:
            icon_type = "material"
            material_icon = emoji_to_material_icon[icon_str]
        else:
            icon_type = "emoji"
            material_icon = "star"

        # Gradient colors for default template
        gradients = [
            ("#10B981", "#07b943"), ("#059669", "#0D9488"), ("#0D9488", "#10B981"),
            ("#10B981", "#059669"), ("#07b943", "#059669"), ("#059669", "#10B981"),
        ]
        gradient_start, gradient_end = gradients[idx % len(gradients)]

        features.append({
            "icon": material_icon if icon_type == "material" else icon,
            "icon_type": icon_type,
            "title": feat.get("title", ""),
            "description": feat.get("description", ""),
            "gradient_start": gradient_start,
            "gradient_end": gradient_end,
            "show_title": False  # For facade template
        })

    # Prepare gallery images
    gallery_images = []
    for idx, img in enumerate(images[:12]):
        gallery_images.append({
            "src": media_prefix + img,
            "alt": f"{biz.get('name', 'Business')} photo {idx + 1}",
            "delay": (idx % 3) * 80
        })

    # Prepare videos
    videos = []
    for vid in videos_raw[:6]:
        mime = "video/webm" if str(vid).lower().endswith(".webm") else "video/mp4"
        videos.append({
            "src": media_prefix + vid,
            "mime": mime
        })

    # Prepare opening hours for default template
    opening_hours = []
    day_labels = {"monday": "Mon", "tuesday": "Tue", "wednesday": "Wed", "thursday": "Thr", "friday": "Fri", "saturday": "Sat", "sunday": "Sun"}
    for day in day_order:
        hours_str = biz.get("hours", {}).get(day, "")
        opening_hours.append({
            "day": day_labels.get(day, day.capitalize()),
            "hours": hours_str if hours_str and hours_str.lower() not in ["closed", "fermé"] else "",
            "is_closed": not hours_str or hours_str.lower() in ["closed", "fermé"]
        })

    # Prepare about section for facade
    about_text = (ai.get("about_paragraph", "") or "").strip()
    custom_story_left = (ai.get("about_story_left", "") or "").strip()
    custom_story_right = (ai.get("about_story_right", "") or "").strip()

    if custom_story_left or custom_story_right:
        first_half = custom_story_left or about_text
        second_half = custom_story_right or about_text
    else:
        split_idx = len(about_text) // 2
        split_at = about_text.find(" ", split_idx) if split_idx else -1
        if split_at == -1:
            split_at = split_idx
        first_half = about_text[:split_at].strip() if split_at > 0 else about_text
        second_half = about_text[split_at:].strip() if split_at > 0 else about_text

    # Story images for facade
    hero_image_choice = _theme.get("hero_image", "").strip()
    story_candidates = [img for img in images if img != hero_image_choice] if images else []
    fallback_1 = story_candidates[0] if len(story_candidates) > 0 else (images[0] if images else "")
    fallback_2 = story_candidates[1] if len(story_candidates) > 1 else (images[1] if len(images) > 1 else fallback_1)

    selected_story_img_1 = (_theme.get("company_image_1") or "").strip()
    selected_story_img_2 = (_theme.get("company_image_2") or "").strip()

    story_img_1 = selected_story_img_1 if selected_story_img_1 in images else fallback_1
    story_img_2 = selected_story_img_2 if selected_story_img_2 in images else fallback_2

    # Prepare values section for facade
    values_raw = ai.get("values") or []
    values = []
    for val in values_raw[:5]:
        if isinstance(val, str) and val.strip():
            values.append(val.strip())
        elif isinstance(val, dict):
            value_text = (val.get("text") or val.get("title") or val.get("description") or "").strip()
            if value_text:
                values.append(value_text)

    # If no values from AI, use feature descriptions as fallback
    if not values and features_raw:
        for feat in features_raw[:5]:
            if isinstance(feat, dict):
                value_text = (feat.get("description") or feat.get("title") or "").strip()
                if value_text:
                    values.append(value_text)

    # Ensure we have exactly 5 values (pad with defaults if needed)
    while len(values) < 5:
        values.append(f"Value {len(values) + 1}")

    # Values image - use saved value or default to first non-hero image
    values_image = ""
    saved_values_image = _theme.get("values_image", "")
    if saved_values_image:
        # Use saved values image (strip media prefix if present)
        values_image = saved_values_image if saved_values_image.startswith(media_prefix) else media_prefix + saved_values_image
    elif images:
        # Default to first non-hero image
        non_hero_images = [img for img in images if img != hero_image_choice]
        chosen = non_hero_images[0] if non_hero_images else images[0]
        values_image = media_prefix + chosen

    # Prepare CSS for facade
    facade_css = ""
    if template == "facade":
        css_file = os.path.join(os.path.dirname(__file__), "templates", "websites", template, "style.css")
        if os.path.isfile(css_file):
            with open(css_file, "r", encoding="utf-8") as f:
                facade_css = f.read()
                theme_color1 = _theme.get("color1", "#10B981")
                theme_color2 = _theme.get("color2", "#059669")
                theme_color3 = _theme.get("color3", "#0D9488")
                theme_cta_color = _theme.get("cta_color", theme_color1)
                theme_hero_dark = _theme.get("hero_dark", "#06060f")
                facade_css = facade_css.replace("{{ theme_color1 }}", theme_color1)
                facade_css = facade_css.replace("{{ theme_color2 }}", theme_color2)
                facade_css = facade_css.replace("{{ theme_color3 }}", theme_color3)
                facade_css = facade_css.replace("{{ theme_cta_color }}", theme_cta_color)
                facade_css = facade_css.replace("{{ theme_hero_dark }}", theme_hero_dark)

    # Smart tagline and subtitle logic (match old renderer)
    tagline = ai.get("tagline", "")
    if not tagline:
        for h in (website.get("headings") or []):
            if 6 < len(h) < 120:
                tagline = (h[:77] + "…") if len(h) > 80 else h
                break
        if not tagline:
            tagline = biz.get("name", "Business")

    subtitle = ai.get("hero_subtitle", "")
    if not subtitle:
        for p in (website.get("paragraphs") or []):
            if len(p) > 40:
                subtitle = p[:220] + ("…" if len(p) > 220 else "")
                break
        if not subtitle:
            subtitle = biz.get("description", "")

    # URL with https:// prefix if missing
    website_url = biz.get("website", "")
    cta_url_with_protocol = ("https://" + website_url) if website_url and not website_url.startswith("http") else website_url
    ai_cta_url = ai.get("cta_primary_url", "")
    if ai_cta_url and not ai_cta_url.startswith("http"):
        ai_cta_url = "https://" + ai_cta_url
    cta_url = ai_cta_url or cta_url_with_protocol or "#"

    # Location for hero label
    city = biz.get("address", "").split(",")[-2].strip() if biz.get("address") and "," in biz.get("address") else biz.get("address", "").split(",")[0].strip() if biz.get("address") else ""

    # Generate dynamic navigation links based on enabled sections
    nav_links = []

    # For default template - check using the same conditions as the template uses
    if template == "default":
        # Keywords section shown if keywords exist
        if keywords:
            nav_links.append({"href": "#keywords", "label": "Avis"})
        # Features section shown if features exist
        if features:
            nav_links.append({"href": "#features", "label": "Fonctionnalités"})
        # Gallery section shown if gallery_images exist
        if gallery_images:
            nav_links.append({"href": "#gallery", "label": "Galerie"})
        # Videos section shown if videos exist
        if videos:
            nav_links.append({"href": "#videos", "label": "Vidéos"})
        # Contact is always shown in default template
        nav_links.append({"href": "#contact", "label": "Contact"})

    # For facade template - check using same conditions as template conditionals
    else:
        # About section: {% if about_story_left or about_story_right %}
        if first_half or second_half:
            nav_links.append({"href": "#about", "label": "About"})
        # Features section: {% if features %}
        if features:
            nav_links.append({"href": "#features", "label": "Features"})
        # Values section: {% if values %}
        if values:
            nav_links.append({"href": "#values", "label": "Values"})
        # Videos section: {% if videos %}
        if videos:
            nav_links.append({"href": "#videos", "label": "Videos"})
        # Contact section: {% if address or phone or email %}
        if biz.get("address") or biz.get("phone") or biz.get("email"):
            nav_links.append({"href": "#contact", "label": "Contact"})

    # Build Jinja2 context
    context = {
        # Business info
        "business_name": biz.get("name", "Business"),
        "address": biz.get("address", ""),
        "phone": biz.get("phone", ""),
        "email": biz.get("email", ""),
        "website": biz.get("website", ""),
        "latitude": biz.get("latitude", ""),
        "longitude": biz.get("longitude", ""),
        "category": biz.get("place_type", "Business"),
        "location": city,
        "rating": biz.get("rating", ""),
        "reviews_count": biz.get("reviews_count", ""),

        # SEO
        "meta_title": ai.get("seo_title") or f"{biz.get('name', 'Business')} — {biz.get('place_type', '')}",
        "meta_description": ai.get("seo_description") or subtitle[:155],
        "seo_title": ai.get("seo_title") or f"{biz.get('name', 'Business')} — {biz.get('place_type', '')}",
        "seo_description": ai.get("seo_description") or subtitle[:155],

        # Branding for facade
        "brand_short_name": ai.get("brand_short_name", biz.get("name", "Business")),

        # Hero section - use tagline and subtitle like old renderer
        "hero_title": tagline,
        "hero_description": subtitle,
        "hero_subtitle": subtitle,
        "hero_image": hero_image,

        # CTAs
        "cta_text": ai.get("cta_btn_label") or ai.get("cta_primary") or "Get Started",
        "cta_url": cta_url,
        "cta_primary": ai.get("cta_btn_label") or ai.get("cta_primary") or "Get Started",
        "cta_primary_url": cta_url,
        "cta_secondary": ai.get("cta_secondary") or "Learn More",
        "cta_secondary_url": ai.get("cta_secondary_url", "#contact"),
        "cta_banner_title": ai.get("cta_heading", "Ready to Get Started?"),
        "cta_heading": ai.get("cta_heading", "Ready to Get Started?"),

        # Maps
        "maps_embed_url": f"https://maps.google.com/maps?q={biz.get('latitude', '')},{biz.get('longitude', '')}&z=15&output=embed" if biz.get("latitude") and biz.get("longitude") else "",

        # Sections data
        "keywords": keywords,
        "features": features,
        "features_title": "Tout ce dont vous avez besoin",
        "features_subtitle": "Conçu pour les professionnels exigeants.",
        "features_intro_text": "We offer a comprehensive range of professional features designed to meet your needs",
        "gallery_images": gallery_images,
        "videos": videos,
        "opening_hours": opening_hours,

        # Facade-specific
        "about_story_left": first_half,
        "about_story_right": second_half,
        "story_image_1": media_prefix + story_img_1 if story_img_1 else "",
        "story_image_2": media_prefix + story_img_2 if story_img_2 else "",
        "values": values,
        "values_image": values_image,
        "facade_css": facade_css,
        "nav_links": nav_links,
        "dynamic_nav_links": "",  # Generated below for facade

        # Footer
        "footer_description": ai.get("footer_tagline") or (about_text[:200] if about_text else subtitle[:200]),
        "footer_tagline": ai.get("footer_tagline") or (about_text[:200] if about_text else subtitle[:200]),
        "footer_copyright": ai.get("footer_copyright", f"© {__import__('datetime').date.today().year} {biz.get('name', 'Business')}. All rights reserved."),
        "social_links": [],  # Can be populated from business data if available
    }

    # Generate dynamic nav links HTML for facade template
    if template == "facade":
        from markupsafe import Markup
        nav_html_parts = []
        for link in nav_links:
            nav_html_parts.append(f'<a href="{link["href"]}">{link["label"]}</a>')
        context["dynamic_nav_links"] = Markup("\n            ".join(nav_html_parts))
        # Mark facade_css as safe to prevent HTML escaping
        context["facade_css"] = Markup(context["facade_css"])

    # Setup Jinja2 environment
    templates_dir = os.path.join(os.path.dirname(__file__), "templates")
    env = Environment(
        loader=FileSystemLoader(templates_dir),
        autoescape=select_autoescape(['html', 'xml'])
    )

    # Render template
    template_obj = env.get_template(f"websites/{template}/index.html")
    return template_obj.render(context)


def _render(business_dir: str, use_draft: bool = False, override_raw: dict = None, template: str = "default") -> str:
    template_dir = os.path.join(os.path.dirname(__file__), "templates", "websites", template)
    template_file = os.path.join(template_dir, "index.html")

    if not os.path.isfile(template_file):
        raise FileNotFoundError(f"Template '{template}' not found at {template_file}")

    return _render_jinja2_template(
        business_dir,
        template=template,
        use_draft=use_draft,
        override_raw=override_raw,
    )


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate a static one-page website from enriched Google Maps data")
    parser.add_argument("--dir",  required=True, help="Path to business ScrapeData folder (e.g. ScrapeData/Digimidi)")
    parser.add_argument("--open", action="store_true", help="Open the generated site in browser after creation")
    parser.add_argument("--template", type=str, default="default", help="Template to use for website generation (default: default)")
    args = parser.parse_args()
    generate(args.dir, open_browser=args.open, template=args.template)


if __name__ == "__main__":
    main()
