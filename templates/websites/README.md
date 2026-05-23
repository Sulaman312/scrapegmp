# Website Template System

## Template Structure
Each template consists of:
- `index.html`: Main template file with `{{ variable }}` placeholders
- `style.css`: Template-specific styles
- `template.json`: Configuration for sections, variants, and theme behavior

## Available Templates
- `default`: Production-approved output, preserved through legacy-compatible rendering
- `facade`: Corporate-focused external template with config-driven sections

## Section Rendering Rules
- Sections render from the Jinja templates for the selected template/page.
- Admin visibility is saved in `section_visibility` and applied by `generate_site.py` before template rendering.
- Empty media-driven sections such as videos/gallery are skipped automatically when their context lists are empty.

## Gallery Variants
- `grid`: Shows all images in a responsive grid (up to configured max)
- `alternating`: Alternates paragraph + image rows, then falls back to extra image grid
- Automatic fallback to `grid` happens when alternating content is insufficient

## Creating a New Template
1. Add `templates/websites/<template_id>/index.html`
2. Add optional `style.css`
3. Add `template.json` with enabled sections and configs
4. Add template metadata entry in `templates/websites/config.json`

## Testing
```bash
python3 generate_site.py --dir ScrapeData/<BUSINESS> --template default
python3 generate_site.py --dir ScrapeData/<BUSINESS> --template facade
```

For default template regression checks, compare against a known baseline:
```bash
diff /tmp/default_reference.html ScrapeData/<BUSINESS>/website/index.html
```
