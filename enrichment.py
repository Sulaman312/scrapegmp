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
import requests
import pandas as pd
from bs4 import BeautifulSoup
from colorthief import ColorThief

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
    data["pricing_hints"] = data["pricing_hints"][:3]

    return data


# ── OpenAI Enrichment ─────────────────────────────────────────────────────────

def enrich_with_ai(place: dict, website: dict, api_key: str, language: str = "fr") -> dict:
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
        "features": [],
        "seo_title": "",
        "seo_description": "",
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
  "cta_primary": "Primary call-to-action button text (e.g. 'Get Started', 'Book Now', 'Contact Us')",
  "cta_secondary": "Secondary CTA text (e.g. 'Learn More', 'Our Services', 'View Menu')",
  "seo_title": "SEO page title (50-60 chars)",
  "seo_description": "SEO meta description (120-155 chars)",
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
Make features diverse and specific to the business type."""

    try:
        logging.info("🤖 Calling OpenAI to generate website copy...")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1500,
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

    return ai


# ── Main Enrichment Function ──────────────────────────────────────────────────

def enrich(business_dir: str, api_key: str = "", language: str = "fr") -> dict:
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

    # Scrape business website
    website_data = scrape_website(place_data.get("website", ""))

    # AI enrichment
    ai_data = enrich_with_ai(place_data, website_data, api_key, language)

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
        "ai":             ai_data,
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

    # Save
    out_path = os.path.join(business_dir, "enriched_data.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(enriched, f, ensure_ascii=False, indent=2)
    logging.info(f"💾 Saved enriched data → {out_path}")

    return enriched


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Enrich scraped Google Maps data with website + AI content")
    parser.add_argument("--dir", required=True, help="Path to business ScrapeData folder (e.g. ScrapeData/Digimidi)")
    parser.add_argument("--api-key", default="", help="OpenAI API key (or set OPENAI_API_KEY env var)")
    parser.add_argument("--language", default="fr", choices=["en", "fr", "de", "es"], help="Language for AI-generated content (default: fr)")
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("OPENAI_API_KEY", "")
    enrich(args.dir, api_key, args.language)


if __name__ == "__main__":
    main()
