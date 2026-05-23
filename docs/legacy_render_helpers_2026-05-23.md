# Legacy Render Helpers Backup

This file keeps a copy of the old section helper block removed from `generate_site.py` on 2026-05-23 while consolidating section visibility around the Jinja-rendered sections.

```python
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
```
