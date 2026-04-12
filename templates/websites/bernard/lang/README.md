# Bernard Translation Guide

This folder controls **hardcoded UI text** for the Bernard template.

## Files

- `en.json` → English
- `fr.json` → French
- `gn.json` → German (requested filename)
- `esp.json` → Spanish (requested filename)

## How language is selected

Priority order in code:

1. `LANGUAGE_OVERRIDE` in `generate_site.py` (for quick testing on existing sites)
2. Persisted business language from data JSON (`language` field)
3. Fallback to French (`fr`)

## Language code mapping

Scraper/admin language values map to translation files as:

- `en` -> `en.json`
- `fr` -> `fr.json`
- `de` (or `gn`) -> `gn.json`
- `es` (or `esp`) -> `esp.json`

## Persisted behavior

When scraping a new business, selected language is saved into `enriched_data.json` as:

```json
{
  "language": "fr"
}
```

This language is preserved on admin draft saves and reused for preview + generated website.

## What is translated (Bernard for now)

- Navbar labels (`Home/Services/Contact`)
- Hero form labels/placeholders/button
- About labels/fallback heading
- Services section headings + card "learn more"
- Why choose us heading
- Testimonials heading/subheading
- Footer section headings + rights-reserved fallback
- About years-of-experience unit

## Adding/updating keys

1. Add/edit key in `fr.json` first (base fallback)
2. Add same key in `en.json`, `gn.json`, `esp.json`
3. Keep key names identical across all files

## Quick testing without re-scraping

### Option A (per business, recommended)
Edit `ScrapeData/<BusinessName>/draft_data.json` (or `enriched_data.json`) and set:

```json
"language": "en"
```

Then open preview or generate site.

### Option B (global code override)
In `generate_site.py`, set:

```python
LANGUAGE_OVERRIDE = "en"
```

Use values: `en`, `fr`, `de`/`gn`, `es`/`esp`.

Set back to `""` to disable override.
