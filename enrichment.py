"""
enrichment.py — Data Enrichment Pipeline
=========================================
Reads all scraped data from ScrapeData/<BusinessName>/,
scrapes the business website for extra content,
calls OpenAI to generate missing copy (tagline, feature descriptions, etc.),
and saves everything to ScrapeData/<BusinessName>/enriched_data.json.

Usage:
    python enrichment.py --dir ScrapeData/Digimidi --api-key sk-...
    python enrichment.py --dir ScrapeData/Digimidi  # set OPENAI_API_KEY env var
"""

import os
import json
import re
import argparse
import logging
import zipfile
import xml.etree.ElementTree as ET
import requests
import pandas as pd
from bs4 import BeautifulSoup
from colorthief import ColorThief
from urllib.parse import urljoin
from utils.review_translator import ensure_reviews_translated

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_json(path: str) -> dict | list:
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.warning(f"Could not load {path}: {e}")
    return {} if path.endswith(".json") else []


def _load_csv(path: str) -> list[dict]:
    if os.path.isfile(path):
        try:
            return pd.read_csv(path, encoding="utf-8-sig").fillna("").to_dict("records")
        except Exception as e:
            logging.warning(f"Could not load {path}: {e}")
    return []


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int] | None:
    value = (hex_color or "").strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", value):
        return None
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(
        max(0, min(255, int(rgb[0]))),
        max(0, min(255, int(rgb[1]))),
        max(0, min(255, int(rgb[2]))),
    )


def _normalize_hex_color(value: str) -> str:
    rgb = _hex_to_rgb(value)
    return _rgb_to_hex(rgb) if rgb else ""


def _slugify(value: str, max_len: int = 32) -> str:
    text = str(value or "").strip().lower()
    for sep in [" - ", " | ", " – ", " — "]:
        if sep in text:
            text = text.split(sep)[0].strip()
            break
    text = re.sub(r"\s*\([^)]*\)\s*$", "", text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    if len(text) > max_len:
        words = text.split("-")
        shortened = []
        for word in words:
            candidate = "-".join(shortened + [word])
            if len(candidate) <= max_len:
                shortened.append(word)
            else:
                break
        text = "-".join(shortened) or text[:max_len].strip("-")
    return text or "business"


def _dedupe_colors(colors: list[str], limit: int = 12) -> list[str]:
    seen = set()
    result = []
    for color in colors:
        normalized = _normalize_hex_color(color)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
        if len(result) >= limit:
            break
    return result


def _extract_colors_from_text(text: str) -> list[str]:
    if not text:
        return []

    colors: list[str] = []
    colors.extend(re.findall(r"#[0-9a-fA-F]{3,6}\b", text))

    for match in re.finditer(r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})", text):
        rgb = tuple(int(match.group(i)) for i in range(1, 4))
        if all(0 <= channel <= 255 for channel in rgb):
            colors.append(_rgb_to_hex(rgb))

    named = {
        "black": "#000000", "white": "#FFFFFF", "red": "#DC2626",
        "blue": "#2563EB", "green": "#16A34A", "yellow": "#FACC15",
        "orange": "#F97316", "purple": "#7C3AED", "pink": "#DB2777",
        "teal": "#0D9488", "cyan": "#0891B2", "gray": "#64748B",
        "grey": "#64748B", "navy": "#1E3A8A", "gold": "#D97706",
    }
    low = text.lower()
    for name, hex_color in named.items():
        if re.search(rf"\b{name}\b", low):
            colors.append(hex_color)

    return _dedupe_colors(colors)


def _read_design_document(path: str) -> dict:
    result = {
        "filename": "",
        "text": "",
        "colors": [],
        "notes": "",
    }
    if not path or not os.path.isfile(path):
        return result

    result["filename"] = os.path.basename(path)
    ext = os.path.splitext(path)[1].lower()
    if ext in {".txt", ".md", ".markdown", ".html", ".htm", ".css", ".json", ".csv"}:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                result["text"] = f.read()[:12000]
        except Exception as e:
            result["notes"] = f"Could not read document text: {e}"
    elif ext == ".docx":
        try:
            result["text"] = _extract_docx_text(path)[:12000]
            if not result["text"]:
                result["notes"] = "DOCX was parsed, but no readable text was found."
        except Exception as e:
            result["notes"] = f"Could not extract DOCX text: {e}"
    elif ext == ".pdf":
        try:
            result["text"] = _extract_pdf_text(path)[:12000]
            if not result["text"]:
                result["notes"] = "PDF was parsed, but no readable text was found."
        except Exception as e:
            result["notes"] = f"Could not extract PDF text: {e}"
    else:
        result["notes"] = (
            "Document was uploaded and stored, but text extraction for this file type "
            "is not available without an additional parser."
        )

    result["colors"] = _extract_colors_from_text(result["text"])
    return result


def _extract_docx_text(path: str) -> str:
    """Extract text from a DOCX file using the zipped XML structure."""
    chunks: list[str] = []
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        document_parts = [
            "word/document.xml",
            *sorted(n for n in names if n.startswith("word/header") and n.endswith(".xml")),
            *sorted(n for n in names if n.startswith("word/footer") and n.endswith(".xml")),
        ]
        for part in document_parts:
            if part not in names:
                continue
            root = ET.fromstring(archive.read(part))
            for paragraph in root.findall(".//w:p", namespace):
                texts = [node.text or "" for node in paragraph.findall(".//w:t", namespace)]
                line = "".join(texts).strip()
                if line:
                    chunks.append(line)

    return "\n".join(chunks)


def _extract_pdf_text(path: str) -> str:
    """Extract text from PDF when pypdf/PyPDF2 is available."""
    reader_cls = None
    import_error = None
    try:
        from pypdf import PdfReader
        reader_cls = PdfReader
    except Exception as e:
        import_error = e
        try:
            from PyPDF2 import PdfReader
            reader_cls = PdfReader
        except Exception as e2:
            import_error = e2

    if reader_cls is None:
        raise RuntimeError(
            "PDF parser is not installed. Install pypdf or PyPDF2 to parse PDF design documents."
        ) from import_error

    reader = reader_cls(path)
    pages = []
    for page in reader.pages[:20]:
        pages.append(page.extract_text() or "")
    return "\n".join(pages)


def _shift_color(hex_color: str, amount: int) -> str:
    rgb = _hex_to_rgb(hex_color) or (37, 99, 235)
    return _rgb_to_hex(tuple(max(0, min(255, channel + amount)) for channel in rgb))


def _mix_color(color_a: str, color_b: str, ratio: float = 0.5) -> str:
    rgb_a = _hex_to_rgb(color_a) or (37, 99, 235)
    rgb_b = _hex_to_rgb(color_b) or (255, 255, 255)
    ratio = max(0, min(1, ratio))
    mixed = tuple(rgb_a[i] * (1 - ratio) + rgb_b[i] * ratio for i in range(3))
    return _rgb_to_hex(mixed)


def _palette_from_values(name: str, c1: str, c2: str, c3: str) -> dict:
    return {"name": name, "color1": c1, "color2": c2, "color3": c3}


def _build_color_presets(base_colors: list[str], template: str = "default") -> tuple[dict, list[dict]]:
    colors = _dedupe_colors(base_colors, limit=6)

    def pick(index: int, fallback: str) -> str:
        return colors[index] if len(colors) > index else fallback

    if template == "bernard":
        primary = pick(1, pick(0, "#1E3A8A"))
        if primary.upper() == "#F6D103" and len(colors) > 1:
            primary = colors[1]
        default = {
            "color1": primary,
            "color2": "#F8FAFC",
            "color3": pick(0, "#F59E0B"),
        }
    elif template == "facade":
        primary = pick(1, pick(0, "#0EA5E9"))
        default = {
            "color1": primary,
            "color2": pick(0, "#38BDF8"),
            "color3": pick(2, _shift_color(primary, 80)),
        }
    else:
        if len(colors) >= 3:
            default = {"color1": colors[0], "color2": colors[1], "color3": colors[2]}
        elif len(colors) == 2:
            default = {"color1": colors[0], "color2": colors[1], "color3": _shift_color(colors[0], 70)}
        elif len(colors) == 1:
            default = {"color1": colors[0], "color2": _shift_color(colors[0], -35), "color3": _shift_color(colors[0], 70)}
        else:
            default = {"color1": "#2563EB", "color2": "#0D9488", "color3": "#F59E0B"}

    c1, c2, c3 = default["color1"], default["color2"], default["color3"]
    if template == "bernard":
        presets = [
            _palette_from_values("Executive", _shift_color(c1, -18), "#F8FAFC", _shift_color(c3, -8)),
            _palette_from_values("Warm Accent", _shift_color(c1, -18), "#FFF7D1", _shift_color(c3, -8)),
            _palette_from_values("Clean Contrast", "#111827", "#EEF2F7", _mix_color(c3, "#FFFFFF", 0.18)),
        ]
    elif template == "facade":
        presets = [
            _palette_from_values("Urban Brand", _shift_color(c1, -20), c2, _shift_color(c3, 20)),
            _palette_from_values("Light Facade", _mix_color(c1, "#FFFFFF", 0.12), _mix_color(c2, "#FFFFFF", 0.32), _shift_color(c3, -12)),
            _palette_from_values("Strong Contrast", _shift_color(c1, -34), _shift_color(c2, 16), _mix_color(c3, "#111111", 0.22)),
        ]
    else:
        presets = [
            _palette_from_values("Brand Energy", c1, _shift_color(c2, 22), _shift_color(c3, -18)),
            _palette_from_values("Bright Gradient", _shift_color(c1, 22), _mix_color(c2, "#FFFFFF", 0.22), _shift_color(c3, 35)),
            _palette_from_values("Bold Contrast", c2, _shift_color(c1, -18), _mix_color(c3, "#111111", 0.25)),
        ]
    return default, presets


def _build_template_color_sets(base_colors: list[str]) -> dict:
    result = {}
    for template in ("default", "facade", "bernard"):
        main, presets = _build_color_presets(base_colors, template)
        result[template] = {
            "main": main,
            "presets": presets,
        }
    return result


def _palette_key(palette: dict) -> tuple[str, str, str]:
    return (
        _normalize_hex_color((palette or {}).get("color1", "")),
        _normalize_hex_color((palette or {}).get("color2", "")),
        _normalize_hex_color((palette or {}).get("color3", "")),
    )


def _clean_palette(palette: dict, fallback: dict) -> dict:
    cleaned = {}
    for key in ("color1", "color2", "color3"):
        cleaned[key] = _normalize_hex_color((palette or {}).get(key, "")) or fallback.get(key, "")
    return cleaned


def _normalize_template_color_palettes(ai_palettes: dict, fallback_palettes: dict) -> dict:
    """Validate AI palettes and ensure each template has a distinct main palette."""
    normalized: dict = {}
    used_main_keys: set[tuple[str, str, str]] = set()

    for template in ("default", "facade", "bernard"):
        fallback = fallback_palettes.get(template, {})
        fallback_main = fallback.get("main", {})
        fallback_presets = fallback.get("presets", [])

        raw = ai_palettes.get(template, {}) if isinstance(ai_palettes, dict) else {}
        main = _clean_palette(raw.get("main", {}), fallback_main)

        # If OpenAI copied the same palette between templates, fall back to our
        # template-specific transform so the UI visibly changes on template switch.
        if _palette_key(main) in used_main_keys:
            main = fallback_main
        used_main_keys.add(_palette_key(main))

        presets = []
        used_preset_keys = {_palette_key(main)}
        raw_presets = raw.get("presets", []) if isinstance(raw.get("presets", []), list) else []
        for index in range(3):
            fallback_preset = fallback_presets[index] if index < len(fallback_presets) else fallback_main
            raw_preset = raw_presets[index] if index < len(raw_presets) else {}
            preset = {
                "name": (raw_preset or {}).get("name") or fallback_preset.get("name") or f"Preset {index + 1}",
                **_clean_palette(raw_preset, fallback_preset),
            }
            if _palette_key(preset) in used_preset_keys:
                preset = {
                    "name": fallback_preset.get("name") or f"Preset {index + 1}",
                    **_clean_palette(fallback_preset, fallback_preset),
                }
            used_preset_keys.add(_palette_key(preset))
            presets.append(preset)

        normalized[template] = {"main": main, "presets": presets}

    return normalized


def _find_images(images_dir: str) -> list[str]:
    """Return relative paths to all downloaded images."""
    results = []
    if not os.path.isdir(images_dir):
        return results
    for root, _, files in os.walk(images_dir):
        for f in sorted(files):
            if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                rel = os.path.relpath(os.path.join(root, f), os.path.dirname(images_dir))
                results.append(rel.replace("\\", "/"))
    return results


def extract_logo_colors(business_dir: str) -> dict:
    """
    Extract dominant colors from the first image (typically the logo).
    Returns dict: { dominant_color, palette }
    """
    colors_data = {
        "dominant_color": None,
        "palette": []
    }

    images_dir = os.path.join(business_dir, "images")
    if not os.path.isdir(images_dir):
        logging.info("No images directory found for color extraction")
        return colors_data

    # Get the first image (often the logo)
    image_files = []
    for f in sorted(os.listdir(images_dir)):
        if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            image_files.append(f)

    if not image_files:
        logging.info("No images found for color extraction")
        return colors_data

    first_image_path = os.path.join(images_dir, image_files[0])

    try:
        color_thief = ColorThief(first_image_path)

        # Get dominant color
        dominant_color = color_thief.get_color(quality=1)
        colors_data["dominant_color"] = "#{:02x}{:02x}{:02x}".format(*dominant_color)

        # Get color palette (5 colors)
        palette = color_thief.get_palette(color_count=5, quality=1)
        colors_data["palette"] = [
            "#{:02x}{:02x}{:02x}".format(*color) for color in palette
        ]

        logging.info(f"✅ Extracted colors from {image_files[0]}")
        logging.info(f"   Dominant: {colors_data['dominant_color']}")
        logging.info(f"   Palette: {', '.join(colors_data['palette'])}")

    except Exception as e:
        logging.warning(f"Could not extract colors from {first_image_path}: {e}")

    return colors_data


# ── Website Scraper ───────────────────────────────────────────────────────────

def scrape_website(url: str) -> dict:
    """
    Crawl the business website and extract useful content.
    Returns dict: { title, meta_description, headings, paragraphs, services, team, pricing_hints }
    """
    data = {
        "title": "",
        "meta_description": "",
        "headings": [],
        "paragraphs": [],
        "services": [],
        "team": [],
        "pricing_hints": [],
        "nav_labels": [],
        "cta_texts": [],
        "detected_colors": [],
        "font_families": [],
        "logo_url": "",
        "raw_text": "",
    }
    if not url:
        return data

    # Ensure protocol
    if not url.startswith("http"):
        url = "https://" + url

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

    pages_to_try = [url, url.rstrip("/") + "/en", url.rstrip("/") + "/fr"]
    contact_paths = ["/contact", "/kontakt", "/about", "/services", "/pricing", "/tarifs"]

    def _scrape_page(page_url):
        try:
            r = requests.get(page_url, headers=headers, timeout=15)
            if r.status_code != 200:
                return None
            return BeautifulSoup(r.text, "html.parser")
        except Exception:
            return None

    def _collect_design_signals(soup_obj, page_url):
        css_text_parts = []

        for el in soup_obj.find_all(style=True):
            css_text_parts.append(el.get("style", ""))

        for style_tag in soup_obj.find_all("style"):
            css_text_parts.append(style_tag.get_text(" ", strip=True))

        for link in soup_obj.find_all("link", href=True):
            rel = " ".join(link.get("rel", [])).lower() if isinstance(link.get("rel"), list) else str(link.get("rel", "")).lower()
            href = link.get("href", "")
            if "stylesheet" not in rel or not href:
                continue
            css_url = urljoin(page_url, href)
            try:
                css_resp = requests.get(css_url, headers=headers, timeout=8)
                if css_resp.status_code == 200 and len(css_resp.text) < 300000:
                    css_text_parts.append(css_resp.text[:300000])
            except Exception:
                continue

        css_text = "\n".join(css_text_parts)
        data["detected_colors"] = _dedupe_colors(data["detected_colors"] + _extract_colors_from_text(css_text), limit=18)

        fonts = []
        for match in re.finditer(r"font-family\s*:\s*([^;}{]+)", css_text, flags=re.I):
            value = re.sub(r"['\"]", "", match.group(1)).strip()
            if value and value not in fonts:
                fonts.append(value)
        data["font_families"] = fonts[:8]

        logo = soup_obj.find("meta", attrs={"property": "og:image"})
        if logo and logo.get("content") and not data["logo_url"]:
            data["logo_url"] = urljoin(page_url, logo["content"])
        if not data["logo_url"]:
            for img in soup_obj.find_all("img", src=True):
                class_value = img.get("class", "")
                if isinstance(class_value, list):
                    class_value = " ".join(class_value)
                marker = " ".join([str(img.get("alt", "")), str(class_value), str(img.get("id", ""))]).lower()
                if "logo" in marker:
                    data["logo_url"] = urljoin(page_url, img["src"])
                    break

    # Main page
    soup = None
    for attempt in pages_to_try:
        soup = _scrape_page(attempt)
        if soup:
            logging.info(f"✅ Website scraped: {attempt}")
            break

    if not soup:
        logging.warning("⚠ Could not reach business website")
        return data

    scraped_url = attempt
    _collect_design_signals(soup, scraped_url)

    # Title
    data["title"] = (soup.find("title") or soup.new_tag("t")).get_text().strip()

    # Meta description
    meta = soup.find("meta", attrs={"name": "description"}) or \
           soup.find("meta", attrs={"property": "og:description"})
    if meta:
        data["meta_description"] = meta.get("content", "").strip()

    # Headings
    for tag in ["h1", "h2", "h3"]:
        for el in soup.find_all(tag):
            t = el.get_text(" ", strip=True)
            if t and len(t) > 3:
                data["headings"].append(t)

    for nav in soup.find_all(["nav", "header"]):
        for a in nav.find_all("a"):
            t = a.get_text(" ", strip=True)
            if 2 < len(t) < 60:
                data["nav_labels"].append(t)

    for el in soup.find_all(["a", "button"]):
        t = el.get_text(" ", strip=True)
        if 2 < len(t) < 80:
            low = t.lower()
            if any(word in low for word in ["contact", "book", "call", "quote", "devis", "réserver", "demander", "appel", "acheter", "learn more", "en savoir"]):
                data["cta_texts"].append(t)

    # Paragraphs (meaningful ones, > 40 chars)
    for p in soup.find_all("p"):
        t = p.get_text(" ", strip=True)
        if len(t) > 40:
            data["paragraphs"].append(t)

    # Services — look for lists under service/feature sections
    service_keywords = ["service", "feature", "solution", "produit", "fonctionnalité", "leistung"]
    for section in soup.find_all(["section", "div", "article"]):
        text_lower = (section.get_text(" ") or "").lower()
        if any(kw in text_lower for kw in service_keywords):
            for li in section.find_all("li"):
                t = li.get_text(" ", strip=True)
                if 5 < len(t) < 100:
                    data["services"].append(t)

    # Team — look for names near "team", "équipe", "team" patterns
    team_keywords = ["team", "équipe", "staff", "founder", "ceo", "cto", "directeur"]
    for section in soup.find_all(["section", "div", "article"]):
        text_lower = (section.get_text(" ") or "").lower()
        if any(kw in text_lower for kw in team_keywords):
            for name_el in section.find_all(["h3", "h4", "strong", "b", "p"]):
                t = name_el.get_text(" ", strip=True)
                if 3 < len(t) < 50 and re.search(r"[A-Z][a-z]+ [A-Z][a-z]+", t):
                    data["team"].append(t)

    # Pricing hints
    pricing_keywords = ["prix", "price", "preis", "tarif", "plan", "€", "CHF", "Fr."]
    for section in soup.find_all(["section", "div", "article"]):
        text_lower = (section.get_text(" ") or "").lower()
        if any(kw in text_lower for kw in pricing_keywords):
            t = section.get_text(" ", strip=True)[:500]
            if t:
                data["pricing_hints"].append(t)
            break

    # Raw text (for AI context, max 3000 chars)
    body_text = soup.get_text(" ", strip=True)
    data["raw_text"] = re.sub(r"\s+", " ", body_text)[:3000]

    # Also check /contact and /about for extra content
    for path in contact_paths[:3]:
        sub_soup = _scrape_page(url.rstrip("/") + path)
        if sub_soup:
            _collect_design_signals(sub_soup, url.rstrip("/") + path)
            extra = sub_soup.get_text(" ", strip=True)
            for p in sub_soup.find_all("p"):
                t = p.get_text(" ", strip=True)
                if len(t) > 40 and t not in data["paragraphs"]:
                    data["paragraphs"].append(t)
            # Look for extra team members
            for name_el in sub_soup.find_all(["h3", "h4", "strong"]):
                t = name_el.get_text(" ", strip=True)
                if 3 < len(t) < 50 and re.search(r"[A-Z][a-z]+ [A-Z][a-z]+", t):
                    if t not in data["team"]:
                        data["team"].append(t)

    # Deduplicate
    data["headings"]      = list(dict.fromkeys(data["headings"]))[:20]
    data["paragraphs"]    = list(dict.fromkeys(data["paragraphs"]))[:20]
    data["services"]      = list(dict.fromkeys(data["services"]))[:20]
    data["team"]          = list(dict.fromkeys(data["team"]))[:10]
    data["nav_labels"]    = list(dict.fromkeys(data["nav_labels"]))[:20]
    data["cta_texts"]     = list(dict.fromkeys(data["cta_texts"]))[:12]
    data["pricing_hints"] = data["pricing_hints"][:3]

    return data


# ── OpenAI Enrichment ─────────────────────────────────────────────────────────

def build_personalization(
    business_dir: str,
    place: dict,
    website: dict,
    updates: list[dict],
    logo_colors: dict,
    design_document_path: str = "",
    preferred_website_url: str = "",
) -> dict:
    design_doc = _read_design_document(design_document_path)
    color_sources = []

    if design_doc.get("colors"):
        color_sources.append("design_document")
    elif website.get("detected_colors"):
        color_sources.append("website")
    elif logo_colors.get("palette") or logo_colors.get("dominant_color"):
        color_sources.append("google_maps_images")
    else:
        color_sources.append("generic_fallback")

    base_colors = (
        design_doc.get("colors") or
        website.get("detected_colors") or
        logo_colors.get("palette") or
        ([logo_colors.get("dominant_color")] if logo_colors.get("dominant_color") else [])
    )
    template_color_sets = _build_template_color_sets(base_colors)
    default_theme = template_color_sets["default"]["main"]
    suggested_presets = template_color_sets["default"]["presets"]

    posts_count = len(updates or [])
    personalization = {
        "version": 1,
        "sources": {
            "google_maps": True,
            "google_posts_count": posts_count,
            "business_website": preferred_website_url or place.get("website", ""),
            "design_document": design_doc.get("filename", ""),
            "color_source": color_sources[0],
            "used_posts_in_ai_context": posts_count > 0,
        },
        "brand": {
            "business_name": place.get("name", ""),
            "business_type": place.get("place_type", ""),
            "website_title": website.get("title", ""),
            "meta_description": website.get("meta_description", ""),
        },
        "style_notes": {
            "document_excerpt": design_doc.get("text", "")[:2500],
            "website_headings": website.get("headings", [])[:10],
            "website_ctas": website.get("cta_texts", [])[:8],
            "website_nav_labels": website.get("nav_labels", [])[:12],
            "website_services": website.get("services", [])[:12],
            "writing_direction": (
                "Use the uploaded design document first, then the provided website, "
                "then Google Maps business facts and posts. Keep the business's existing tone."
            ),
            "font_note": "Do not change template font families; personalization only controls content and colors.",
        },
        "colors": {
            "document_colors": design_doc.get("colors", []),
            "website_colors": website.get("detected_colors", []),
            "logo_colors": logo_colors.get("palette", []),
            "selected_theme": default_theme,
            "suggested_color_presets": suggested_presets,
            "template_palettes": template_color_sets,
        },
        "google_posts": {
            "count": posts_count,
            "latest": [
                {
                    "date": post.get("date", ""),
                    "body": (post.get("body", "") or "")[:500],
                    "cta_text": post.get("cta_text", ""),
                    "action_url": post.get("action_url", ""),
                    "image_url": post.get("image_url", "") or post.get("image_urls", ""),
                }
                for post in (updates or [])[:5]
            ],
        },
    }

    out_path = os.path.join(business_dir, "personalization.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(personalization, f, ensure_ascii=False, indent=2)
    logging.info(f"💾 Saved personalization data → {out_path} ({posts_count} posts)")

    return personalization


def enrich_with_ai(
    place: dict,
    website: dict,
    api_key: str,
    language: str = "fr",
    personalization: dict | None = None,
    updates: list[dict] | None = None,
) -> dict:
    """
    Call OpenAI to generate: tagline, subtitle, feature descriptions,
    about paragraph, CTA texts.
    """
    ai = {
        "tagline": "",
        "hero_subtitle": "",
        "about_paragraph": "",
        "cta_primary": "Get Started",
        "cta_secondary": "Learn More",
        "navbar_name": "",
        "url_slug": "",
        "features": [],
        "seo_title": "",
        "seo_description": "",
        "services_page_seo_title": "",
        "services_page_seo_description": "",
        "contact_page_seo_title": "",
        "contact_page_seo_description": "",
    }

    if not api_key:
        logging.warning("⚠ No OpenAI API key provided — skipping AI enrichment")
        return ai

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
    except ImportError:
        logging.error("❌ openai package not installed. Run: pip install openai")
        return ai

    # Build context for the AI
    context_parts = [
        f"Business name: {place.get('name', '')}",
        f"Type: {place.get('place_type', '')}",
        f"Address: {place.get('address', '')}",
        f"Website: {place.get('website', '')}",
    ]
    if place.get("description"):
        context_parts.append(f"Description: {place['description']}")
    if website.get("meta_description"):
        context_parts.append(f"Website meta description: {website['meta_description']}")
    if website.get("headings"):
        context_parts.append(f"Website headings: {' | '.join(website['headings'][:8])}")
    if website.get("paragraphs"):
        context_parts.append(f"Website intro text: {website['paragraphs'][0][:400]}")
    if website.get("services"):
        context_parts.append(f"Services listed: {', '.join(website['services'][:10])}")
    if website.get("raw_text"):
        context_parts.append(f"Website content excerpt: {website['raw_text'][:800]}")
    if updates:
        post_lines = []
        for post in updates[:5]:
            body = (post.get("body", "") or "")[:450]
            date = post.get("date", "")
            cta = post.get("cta_text", "")
            post_lines.append(f"- {date} {cta}: {body}")
        context_parts.append("Recent Google Business Profile posts:\n" + "\n".join(post_lines))
    if personalization:
        context_parts.append(
            "Personalization context JSON:\n" +
            json.dumps(personalization, ensure_ascii=False)[:5000]
        )

    context = "\n".join(context_parts)

    # Language mapping
    language_names = {
        "en": "English",
        "fr": "French",
        "de": "German",
        "es": "Spanish"
    }
    output_language = language_names.get(language.lower(), "French")

    prompt = f"""You are a professional copywriter creating a modern website for a business.

Here is everything we know about this business:
{context}

IMPORTANT: Generate ALL content in {output_language} language.

Generate the following in JSON format (respond ONLY with valid JSON, no markdown, no explanation):
{{
  "tagline": "A punchy 6-10 word headline capturing what this business does",
  "hero_subtitle": "1-2 sentence value proposition, compelling and specific",
  "about_paragraph": "2-3 sentence paragraph about the company, professional tone",
  "navbar_name": "Shortened business name for navbar (max 20 chars, keep core brand name only, remove legal suffixes, location details, and overly descriptive parts. Examples: 'PISCIFLOR VAUD - Réparation et rénovation piscines, fontaines, jacuzzis' → 'PISCIFLOR', 'John Smith Law Firm LLC - Estate Planning Services' → 'John Smith Law')",
  "url_slug": "Short lowercase URL slug for this website, 2-4 words max, ASCII letters/numbers/hyphens only. Use the core brand name, not the full Google title. Example: 'AVIS CONSO - Mieux référencé avec vos avis' → 'avis-conso'",
  "cta_primary": "Primary call-to-action button text (e.g. 'Get Started', 'Book Now', 'Contact Us')",
  "cta_secondary": "Secondary CTA text (e.g. 'Learn More', 'Our Services', 'View Menu')",
  "seo_title": "SEO page title (50-60 chars)",
  "seo_description": "SEO meta description (120-155 chars)",
  "services_page_seo_title": "SEO page title for the services page (50-60 chars, service-focused)",
  "services_page_seo_description": "SEO meta description for the services page (120-155 chars, mention services/offers)",
  "contact_page_seo_title": "SEO page title for the contact page (50-60 chars, contact/location-focused)",
  "contact_page_seo_description": "SEO meta description for the contact page (120-155 chars, invite users to call, visit, or request information)",
  "theme": {{
    "color1": "Default-template primary brand hex color from personalization.colors.template_palettes.default.main",
    "color2": "Default-template secondary brand hex color from personalization.colors.template_palettes.default.main",
    "color3": "Default-template accent brand hex color from personalization.colors.template_palettes.default.main"
  }},
  "template_color_palettes": {{
    "default": {{
      "main": {{"color1": "#HEX", "color2": "#HEX", "color3": "#HEX"}},
      "presets": [
        {{"name": "Preset name", "color1": "#HEX", "color2": "#HEX", "color3": "#HEX"}},
        {{"name": "Preset name", "color1": "#HEX", "color2": "#HEX", "color3": "#HEX"}},
        {{"name": "Preset name", "color1": "#HEX", "color2": "#HEX", "color3": "#HEX"}}
      ]
    }},
    "facade": {{
      "main": {{"color1": "#HEX", "color2": "#HEX", "color3": "#HEX"}},
      "presets": [
        {{"name": "Preset name", "color1": "#HEX", "color2": "#HEX", "color3": "#HEX"}},
        {{"name": "Preset name", "color1": "#HEX", "color2": "#HEX", "color3": "#HEX"}},
        {{"name": "Preset name", "color1": "#HEX", "color2": "#HEX", "color3": "#HEX"}}
      ]
    }},
    "bernard": {{
      "main": {{"color1": "#HEX", "color2": "#HEX", "color3": "#HEX"}},
      "presets": [
        {{"name": "Preset name", "color1": "#HEX", "color2": "#HEX", "color3": "#HEX"}},
        {{"name": "Preset name", "color1": "#HEX", "color2": "#HEX", "color3": "#HEX"}},
        {{"name": "Preset name", "color1": "#HEX", "color2": "#HEX", "color3": "#HEX"}}
      ]
    }}
  }},
  "features": [
    {{
      "icon": "material_symbol_name",
      "title": "Feature name",
      "description": "1-2 sentence feature description"
    }},
    ... (generate 8-10 features/services based on the business context)
  ]
}}

CRITICAL ICON RULES:
- Use ONLY valid Material Symbols icon names from Google's official icon library
- Icons must be actual icon names with underscores, NOT plain text words
- INVALID examples: "paint", "clean", "quality", "service" (these are plain text, not icon names)
- VALID examples: "workspace_premium", "speed", "security", "verified", "support_agent", "dining", "local_shipping", "schedule", "payments", "star", "thumb_up", "checklist", "lock", "bolt", "celebration", "restaurant", "coffee", "fitness_center", "spa", "directions_car", "home", "storefront", "shopping_cart", "medical_services", "school", "business_center", "home_repair_service", "plumbing", "electric_bolt", "construction", "cleaning_services"
- Choose icons that match each feature's purpose
- NEVER use emojis, emoji descriptions like "🎯" or "trophy emoji", or plain text words
- If unsure about an icon name, use a generic icon like "check_circle", "star", or "verified"

Generate 8-10 features to ensure sufficient content for different page templates (some templates show 3 features, others show 6+ services).
Make features diverse and specific to the business type.

COLOR RULES:
- Use colors found in the personalization context first.
- Return exactly 3 colors for each template main palette and exactly 3 presets per template.
- The three template main palettes must NOT be identical. Even if the source colors are limited, adapt the role of each color per template so switching templates changes the visual design.
- Do not simply copy the same color1/color2/color3 triplet into default, facade, and bernard.
- Inside each template, the 3 presets must also be visibly different from the main palette and from each other. Do not return simple near-duplicates.
- Presets should vary color roles, contrast level, and emphasis while staying compatible with that template.
- Default template can use stronger gradients and more vivid combinations.
- Facade template works best with a confident primary, a related secondary, and a clean accent.
- Bernard template works best with a dark/professional primary, a very light secondary/background-compatible color, and a warm/accent color.
- If the source brand has yellow + dark gray, default should be yellow-forward, facade should be dark-forward with yellow support, and bernard should be dark primary + very light secondary + yellow accent.
- Do not suggest font changes."""

    try:
        logging.info("🤖 Calling OpenAI to generate website copy...")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1800,
            response_format={"type": "json_object"}
        )
        raw = response.choices[0].message.content.strip()
        # Remove markdown code fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        try:
            ai.update(json.loads(raw))
            logging.info("✅ AI enrichment complete")
        except json.JSONDecodeError as json_err:
            logging.error(f"❌ JSON parsing failed: {json_err}")
            logging.error(f"Raw OpenAI response:\n{raw[:500]}...")
            # Try to salvage what we can with a more lenient parser
            try:
                # Sometimes there are trailing commas or other issues - try to fix common problems
                fixed_raw = raw.replace(",]", "]").replace(",}", "}")
                ai.update(json.loads(fixed_raw))
                logging.info("✅ AI enrichment complete (with JSON fixes)")
            except:
                logging.error("❌ Could not parse OpenAI response even after fixes")
    except Exception as e:
        logging.error(f"❌ OpenAI call failed: {e}")

    # Fallback: If navbar_name is still empty, create a cleaned version from business name
    if not ai.get("navbar_name"):
        business_name = place.get("name", "")
        if business_name:
            # Remove common patterns: location details, legal suffixes, descriptive parts
            cleaned = business_name
            # Remove everything after common separators like " - ", " | ", " – "
            for sep in [" - ", " | ", " – ", " — "]:
                if sep in cleaned:
                    cleaned = cleaned.split(sep)[0].strip()
            # Remove location indicators in parentheses or at the end
            cleaned = re.sub(r'\s*\([^)]*\)\s*$', '', cleaned)
            # Remove common legal suffixes
            for suffix in [" LLC", " Ltd", " Inc", " Corp", " GmbH", " SA", " SARL", " Sàrl"]:
                if cleaned.endswith(suffix):
                    cleaned = cleaned[:-len(suffix)].strip()
            # Limit to 25 characters max
            if len(cleaned) > 25:
                # Try to break at a word boundary
                words = cleaned.split()
                cleaned = words[0]
                for word in words[1:]:
                    if len(cleaned + " " + word) <= 25:
                        cleaned += " " + word
                    else:
                        break
            ai["navbar_name"] = cleaned[:25].strip()
            logging.info(f"📝 Generated fallback navbar_name: {ai['navbar_name']}")

    ai["url_slug"] = _slugify(ai.get("url_slug") or ai.get("navbar_name") or place.get("name", ""))

    business_name = place.get("name", "") or ai.get("navbar_name") or "Business"
    place_type = place.get("place_type", "") or "services"
    address = place.get("address", "")
    location = address.split(",")[-1].strip() if address and "," in address else address
    location_suffix = f" in {location}" if location else ""

    seo_fallbacks = {
        "services_page_seo_title": f"{business_name} Services{location_suffix}"[:60],
        "services_page_seo_description": (
            f"Discover the services and solutions offered by {business_name}. "
            f"Contact the team for details, availability, and support."
        )[:155],
        "contact_page_seo_title": f"Contact {business_name}{location_suffix}"[:60],
        "contact_page_seo_description": (
            f"Contact {business_name} for information about {place_type}. "
            f"Call, visit, or send a message to get assistance."
        )[:155],
    }
    for key, fallback in seo_fallbacks.items():
        if not ai.get(key):
            ai[key] = fallback

    return ai


# ── Main Enrichment Function ──────────────────────────────────────────────────

def enrich(
    business_dir: str,
    api_key: str = "",
    language: str = "fr",
    website_url: str = "",
    design_document_path: str = "",
) -> dict:
    """
    Load all scraped data, scrape website, call AI, return enriched dict.
    """
    logging.info(f"📂 Loading scraped data from: {business_dir}")

    place_data   = _load_json(os.path.join(business_dir, "place_data.json"))
    about_data   = _load_json(os.path.join(business_dir, "about.json"))
    popular_times= _load_json(os.path.join(business_dir, "popular_times.json"))
    web_results  = _load_csv(os.path.join(business_dir, "web_results.csv"))
    related      = _load_csv(os.path.join(business_dir, "related_places.csv"))
    reviews      = _load_csv(os.path.join(business_dir, "reviews.csv"))
    qa           = _load_csv(os.path.join(business_dir, "qa.csv"))
    updates      = _load_csv(os.path.join(business_dir, "updates.csv"))
    social_links = _load_csv(os.path.join(business_dir, "social_links.csv"))
    keywords_raw = _load_csv(os.path.join(business_dir, "review_keywords.csv"))
    about_attrs  = _load_csv(os.path.join(business_dir, "about_attributes.csv"))

    # Filter review keywords — remove Google Maps navigation noise
    nav_noise = {
        "restaurants", "hotels", "things to do", "transit", "parking", "pharmacies",
        "atms", "see photos", "overview", "about", "directions", "save", "nearby",
        "send to phone", "share", "suggest an edit", "add photos & videos",
        "write a review", "sign in", "suggest new hours",
    }
    review_keywords = [
        row["keyword"] for row in keywords_raw
        if row.get("keyword", "").lower().strip() not in nav_noise
        and len(row.get("keyword", "")) > 2
        and not re.match(r"^\+?\d[\d\s\-]+$", row.get("keyword", ""))
    ]

    # Collect images
    images = _find_images(os.path.join(business_dir, "images"))

    # Extract logo colors
    logo_colors = extract_logo_colors(business_dir)

    # Scrape business website. A user-provided website takes priority over
    # the Google Maps website field for personalization signals.
    website_for_personalization = website_url or place_data.get("website", "")
    website_data = scrape_website(website_for_personalization)

    personalization = build_personalization(
        business_dir=business_dir,
        place=place_data,
        website=website_data,
        updates=updates,
        logo_colors=logo_colors,
        design_document_path=design_document_path,
        preferred_website_url=website_for_personalization,
    )

    # AI enrichment
    ai_data = enrich_with_ai(place_data, website_data, api_key, language, personalization, updates)

    theme_from_ai = ai_data.get("theme") if isinstance(ai_data.get("theme"), dict) else {}
    ai_palettes = ai_data.get("template_color_palettes") if isinstance(ai_data.get("template_color_palettes"), dict) else {}
    fallback_palettes = personalization.get("colors", {}).get("template_palettes", {})
    if ai_palettes:
        personalization.setdefault("colors", {})["template_palettes"] = _normalize_template_color_palettes(
            ai_palettes,
            fallback_palettes,
        )
        with open(os.path.join(business_dir, "personalization.json"), "w", encoding="utf-8") as f:
            json.dump(personalization, f, ensure_ascii=False, indent=2)
    selected_theme = (
        personalization.get("colors", {})
        .get("template_palettes", {})
        .get("default", {})
        .get("main", {})
    ) or personalization.get("colors", {}).get("selected_theme", {})
    theme = {
        "color1": _normalize_hex_color(theme_from_ai.get("color1", "")) or selected_theme.get("color1", "#2563EB"),
        "color2": _normalize_hex_color(theme_from_ai.get("color2", "")) or selected_theme.get("color2", "#0D9488"),
        "color3": _normalize_hex_color(theme_from_ai.get("color3", "")) or selected_theme.get("color3", "#F59E0B"),
    }

    # Build hours list
    day_order = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    hours = {day: place_data.get(day, "") for day in day_order}

    # Assemble enriched structure
    enriched = {
        "language": language,
        "business": {
            "name":           place_data.get("name", ""),
            "place_type":     place_data.get("place_type", ""),
            "address":        place_data.get("address", ""),
            "phone":          place_data.get("phone_number", ""),
            "website":        place_data.get("website", ""),
            "email":          place_data.get("email", ""),
            "rating":         place_data.get("reviews_average"),
            "reviews_count":  place_data.get("reviews_count"),
            "price_range":    place_data.get("price_range", ""),
            "plus_code":      place_data.get("plus_code", ""),
            "latitude":       place_data.get("latitude", ""),
            "longitude":      place_data.get("longitude", ""),
            "google_maps_url":place_data.get("google_maps_url", ""),
            "description":    place_data.get("description", "") or website_data.get("meta_description", ""),
            "hours":          hours,
        },
        "website_data":   website_data,
        "personalization": personalization,
        "ai":             ai_data,
        "theme":          theme,
        "images":         images,
        "logo_colors":    logo_colors,
        "reviews":        reviews[:20],       # top 20 for testimonials
        "review_keywords":review_keywords,
        "qa":             qa[:15],
        "updates":        updates[:10],
        "popular_times":  popular_times,
        "about":          about_data,
        "about_attrs":    about_attrs,
        "social_links":   social_links,
        "web_results":    web_results,
        "related_places": related,
    }

    # Save enriched data first
    out_path = os.path.join(business_dir, "enriched_data.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(enriched, f, ensure_ascii=False, indent=2)
    logging.info(f"💾 Saved enriched data → {out_path}")

    # Translate reviews to the selected language only and cache them in enriched_data.json
    if reviews:
        try:
            # Map language parameter to ISO 639-1 code
            lang_code_map = {
                "en": "en",
                "fr": "fr",
                "de": "de",
                "es": "es"
            }
            target_lang_code = lang_code_map.get(language.lower(), "fr")

            logging.info(f"🌐 Translating reviews to {target_lang_code}...")
            ensure_reviews_translated(out_path, target_languages=[target_lang_code])

            # Reload enriched data with translations
            with open(out_path, "r", encoding="utf-8") as f:
                enriched = json.load(f)

            # Save translated reviews back to reviews.csv to override original
            reviews_translated = enriched.get('reviews_translated', {})
            if reviews_translated.get(target_lang_code):
                translated_reviews = reviews_translated[target_lang_code]
                reviews_csv_path = os.path.join(business_dir, 'reviews.csv')
                pd.DataFrame(translated_reviews).to_csv(reviews_csv_path, index=False, encoding='utf-8-sig')
                logging.info(f"💾 Saved translated reviews → {reviews_csv_path}")

        except Exception as e:
            logging.warning(f"⚠ Review translation failed: {e}")

    return enriched


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Enrich scraped Google Maps data with website + AI content")
    parser.add_argument("--dir", required=True, help="Path to business ScrapeData folder (e.g. ScrapeData/Digimidi)")
    parser.add_argument("--api-key", default="", help="OpenAI API key (or set OPENAI_API_KEY env var)")
    parser.add_argument("--language", default="fr", choices=["en", "fr", "de", "es"], help="Language for AI-generated content (default: fr)")
    parser.add_argument("--website-url", default="", help="Optional website URL supplied by the user for personalization")
    parser.add_argument("--design-document", default="", help="Optional uploaded design document path for personalization")
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("OPENAI_API_KEY", "")
    enrich(args.dir, api_key, args.language, args.website_url, args.design_document)


if __name__ == "__main__":
    main()
