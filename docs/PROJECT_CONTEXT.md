# Project Context

Last audited: 2026-05-23

This project is a Google Maps business scraper, AI enrichment pipeline, admin editor, and static website generator. The main runtime is `admin.py`, which serves the admin panel, starts scrape/enrichment jobs, saves editable draft data, previews sites dynamically, and publishes static website files.

## High-Level Flow

1. A business is added from the admin panel with a Google Maps URL.
2. `POST /api/scrape-and-enrich` starts a background thread in `admin.py`.
3. The thread calls `scraper.scraper.scrape_place_by_url()`.
4. The scraper writes raw business output under `ScrapeData/<BusinessName>/`.
5. `enrichment.enrich()` reads the raw files, scrapes the business website, calls OpenAI, translates reviews, and writes `enriched_data.json`.
6. The admin UI loads `enriched_data.json` or the newest `draft_data.json`.
7. Edits are saved only to `draft_data.json`.
8. Preview routes render HTML dynamically from draft/current form data.
9. Generate Website copies the newest draft to `enriched_data.json`, runs `generate_site.py`, and writes static files under `ScrapeData/<BusinessName>/website/`.

## Main Files

- `admin.py`: Flask app, auth, API routes, preview routes, static site serving, uploads, delete, re-scrape, contact form forwarding.
- `app.py`: CLI wrapper for standalone scraping.
- `scraper/`: Playwright-based Google Maps scraping package.
- `enrichment.py`: Website scraping, OpenAI copy generation, logo color extraction, review translation cache.
- `generate_site.py`: Jinja2 context builder and static site generator.
- `templates/admin/`: Admin shell, header/sidebar, and editing panels.
- `static/js/`: Admin frontend state, API calls, form serialization, live preview, section modules.
- `static/css/`: Admin styles and component styles.
- `templates/websites/`: Output website templates.
- `ScrapeData/`: Business data, media, draft data, enriched data, and generated static sites.

## Scraping System

### Entry Points

- Admin flow: `admin.py` -> `_background_scrape_worker()` -> `scrape_place_by_url()`.
- CLI single business: `python app.py --url "<maps-url>"`.
- CLI search/city mode: `scrape_places_until_end()` and `scrape_multiple_cities()`.
- Re-scrape flow: `POST /api/business/<name>/re-scrape` -> `scraper/re_scraper.py`.

### What Single-Business Scraping Collects

`scrape_place_by_url()` opens the Google Maps URL with Playwright and extracts:

- Place overview: name, address, phone, website, category, rating, review count, coordinates, plus code, price range, hours.
- Extra overview data: related places, web results, about tab attributes, social links.
- Popular times when available.
- Q&A and business updates.
- Review keywords and reviews.
- Images into `images/`.
- Videos into `videos/`.

### Raw Output Shape

Typical business folder:

```text
ScrapeData/<BusinessName>/
  place_data.json
  place_data.csv
  reviews.csv
  review_keywords.csv
  about.json
  about_attributes.csv
  social_links.csv
  popular_times.json
  qa.csv
  updates.csv
  images/
  videos/
  enriched_data.json
  draft_data.json
  website/
```

Not every file exists for every business. The enrichment and admin loaders generally tolerate missing optional files.

### Re-Scrape

Re-scrape updates only dynamic fields in `business`:

- phone
- email
- address
- latitude
- longitude
- plus code
- hours

It preserves AI content, reviews, images, and most editor data.

## Enrichment System

`enrichment.py` loads raw scrape files, scrapes the business website with `requests` and BeautifulSoup, calls OpenAI, extracts logo colors, and writes `enriched_data.json`.

Important outputs:

- `language`: selected content language.
- `business`: normalized business fields used by admin and templates.
- `website_data`: scraped title, meta description, headings, paragraphs, services, team, pricing hints, raw text.
- `ai`: generated copy fields, SEO fields, CTAs, navbar name, features.
- `images`: relative media paths such as `images/All/0001.webp`.
- `logo_colors`: dominant color and palette.
- `reviews`, `review_keywords`, `qa`, `updates`, `popular_times`, `about`, `about_attrs`, `social_links`, `web_results`, `related_places`.
- `reviews_translated`: added by `utils/review_translator.py` when translation succeeds.

The enrichment prompt currently asks for generic website copy plus services/contact SEO fields. Template-specific fields such as Bernard service cards are mostly derived later in admin JS or `generate_site.py` from `ai.features`.

## Admin Backend

### Auth

`admin.py` uses hardcoded users in the `USERS` dictionary:

- admin user with access to all businesses.
- restricted example user with access to `The Monal Islamabad`.

`SECRET_KEY` uses the environment variable when present, otherwise a development fallback.

### Business APIs

- `GET /api/businesses`: lists business folders that have `enriched_data.json`.
- `GET /api/business/<name>`: loads the newest of `draft_data.json` and `enriched_data.json`, injects reviews fallback from CSV, and scans videos from disk.
- `POST /api/business/<name>/save`: saves admin edits to `draft_data.json`.
- `POST /api/business/<name>/generate`: copies newer draft into enriched data and runs `generate_site.py`.
- `DELETE /api/business/<name>`: deletes the business folder.
- `POST /api/business/<name>/upload`: uploads images/videos into `images/Uploaded`.
- `POST /api/business/<name>/videos/upload`: uploads videos into `videos`.
- `GET /api/business/<name>/videos`: scans videos from disk.
- `DELETE /api/business/<name>/videos/<filename>`: deletes a video.
- `POST /api/business/<name>/re-scrape`: updates dynamic Google Maps fields.

### Preview and Published Site Routes

- `GET /preview/<name>/`: dynamic preview, prefers draft data.
- `POST /api/preview/<name>/render`: live preview from current unsaved form payload.
- `GET /site/<business>/...`: serves generated static files from `website/`.
- Wildcard subdomain mode: if `BASE_DOMAIN` is configured, non-admin subdomains are mapped to matching business folders.
- `/media/<path>` serves media from `ScrapeData`.

Preview and published sites are intentionally separate. Preview can show unsaved or draft state; published site shows the last generated static files.

## Admin Frontend

### Script Order

`templates/admin/base.html` loads JS in this order:

1. `globals.js`
2. `utils.js`
3. `ui.js`
4. section modules (`social`, `hours`, `highlights`, `reviews`, `features`, `media`, `videos`, `colors`, `footer`, `visibility`, `bernard`)
5. `form.js`
6. `api.js`
7. `preview.js`

Order matters because later modules expect globals and helpers already defined.

### State Model

Global state lives mostly in `static/js/globals.js`:

- `currentBusiness`
- `currentData`
- `allBusinesses`
- `reviewKeywords`
- `highlights`
- `currentPage`
- `isMultipageTemplate`
- `ACTIVE_ADMIN_SECTIONS`
- `TEMPLATE_DEFS`

`populateForm(data)` in `form.js` hydrates all panels from loaded business data. `collectFormData()` serializes panel state back into the draft JSON shape.

### Sidebar and Sections

Static sidebar items are defined in `templates/admin/partials/sidebar.html`. JS controls whether they are visible:

- `ADMIN_SECTIONS` defines all possible admin panel keys.
- `applyTemplateSections()` hides panels that do not apply to the selected template.
- `updateMultipageUI()` further restricts panels for Bernard/Facade page editing.
- `switchSection()` toggles the active panel and tells the preview drawer which website section to scroll to.

Important admin panel keys:

- Website panels: `hero`, `features`, `our-services`, `why-choose-us`, `values`, `gallery`, `videos`, `about`, `reviews`, `contact`, `cta`, `footer`, `services-page`.
- Settings panels: `media`, `design`, `seo`, `visibility`.

### Live Preview

`static/js/preview.js` owns the preview drawer.

- The drawer uses an iframe.
- Desktop preview renders at 1280px width and scales down.
- Mobile preview renders at 390px width.
- Saved preview loads `/preview/<business>/`.
- Unsaved live preview posts `collectFormData()` to `/api/preview/<business>/render` and sets `iframe.srcdoc`.
- For multipage templates, `currentPage` is sent as `home`, `services`, or `contact`.

The preview section scroll map is `PV_ANCHORS`. It maps admin panels to website element IDs such as `features`, `gallery`, `videos`, `contact`, `services`, and `why-choose-us`.

## Template System

### Template Registry

`templates/websites/config.json` lists template choices exposed by `/api/templates`.

Current templates:

- `default`: one-page modern gradient site.
- `facade`: corporate multipage-capable site.
- `bernard`: service-business multipage-capable site.

Each template has a `template.json` with `sections.enabled`. The admin uses this to hide irrelevant editor panels. The backend currently does not consistently enforce it during render.

### Single Page vs Multipage

`generate_site.generate()` treats templates differently:

- `default`: writes one `website/index.html`.
- `bernard`: writes `index.html`, `services.html`, `contact.html`.
- `facade`: writes `index.html`, `services.html`, `contact.html`.

Preview follows the same page concept through `build_html_page()`.

### Rendering Pipeline

`generate_site.py`:

1. Loads `enriched_data.json`, `draft_data.json`, or override data.
2. Loads `place_data.json` as fallback for business fields.
3. Scans images and videos from disk.
4. Loads reviews and Q&A from JSON or CSV fallback.
5. Builds normalized template context.
6. Loads translations from `templates/websites/<template>/lang/`.
7. Builds navigation links based on available data/template mode.
8. Injects template CSS with theme color replacements for Bernard and Facade.
9. Renders Jinja2 template files.

### Template Data Sources

Common context fields:

- Business: `business_name`, `navbar_name`, `address`, `phone`, `email`, `website`, `website_display`, `latitude`, `longitude`, `category`, `location`, `rating`, `reviews_count`.
- SEO: `meta_title`, `meta_description`, `seo_title`, `seo_description`.
- Hero: `hero_title`, `hero_description`, `hero_subtitle`, `hero_image`.
- CTAs: `cta_text`, `cta_url`, `cta_primary`, `cta_primary_url`, `cta_secondary`, `cta_secondary_url`, `cta_banner_title`, `cta_heading`.
- Media/sections: `keywords`, `features`, `gallery_images`, `videos`, `opening_hours`.
- Facade/story: `about_story_left`, `about_story_right`, `story_image_1`, `story_image_2`, `values`, `values_image`.
- Footer: `footer_description`, `footer_tagline`, `footer_copyright`, `social_links`.
- Language: `html_lang`, `language`, `lang_file_code`, `tr`.

Bernard/Facade extra fields:

- `hours_summary`
- `advantages`
- `why_choose_us_heading`
- `why_choose_us_image`
- `about_image`
- `about_heading`
- `about_description`
- `about_bullets`
- `services`
- `values_heading`
- `values_list`
- `testimonials`
- services page SEO/content fields
- contact page SEO/content fields

## Color System

### Stored Color Data

Admin saves colors into `theme`:

- `color1`
- `color2`
- `color3`
- `cta_color`
- `hero_dark`

It also saves image choices:

- `hero_image`
- `values_image`
- `company_image_1`
- `company_image_2`
- `why_choose_us_image`

### Admin Color Controls

`static/js/sections/colors.js` controls color inputs, hex inputs, preview swatches, CTA mirrors, and logo color palette application.

`globals.js` defines template presets:

- `PRESETS_DEFAULT`
- `PRESETS_BERNARD`
- `PRESETS_FACADE`

`updatePresetsForTemplate()` swaps the preset list when the selected template changes.

### Website Color Rendering

- Default template receives `theme_color1`, `theme_color2`, `theme_color3` and uses inline CSS variables/styles in `templates/websites/default/index.html`.
- Facade loads `templates/websites/facade/style.css` and replaces placeholders like `{{ theme_color1 }}`, RGB variants, `{{ theme_cta_color }}`, and `{{ theme_hero_dark }}`.
- Bernard loads `templates/websites/bernard/style.css` and replaces `{{ theme_color1 }}`, `{{ theme_color2 }}`, `{{ theme_color3 }}`, and `{{ theme_cta_color }}`.

Logo colors are extracted in enrichment with `ColorThief` and displayed as optional admin palette suggestions. They are not applied automatically unless the user clicks them.

## Section Visibility

### Intended Model

The intended model appears to be:

1. Template config determines whether a template supports a section.
2. Data availability determines whether the section has content.
3. User visibility toggles determine whether the section should be shown.
4. Sidebar, live preview, and generated website should all follow the same decision.

### Current Implementation

Current implementation is split:

- Template support in admin: `templates/websites/*/template.json` -> `/api/templates` -> `TEMPLATE_DEFS` -> `applyTemplateSections()`.
- Data availability in admin visibility panel: `_hasContent()` in `static/js/sections/visibility.js`.
- User toggles: `currentData.section_visibility`.
- Sidebar hiding: `_syncSidebarWithVisibility()` hides nav items where possible.
- Generated site rendering: mostly Jinja `{% if ... %}` checks and manual conditions in `generate_site.py`.

The generated site does not currently use `section_visibility`, and it does not consistently use the template config helpers in `generate_site.py`.

## Website Template Sections

### Default

Source: `templates/websites/default/index.html` and `components/`.

Rendered sections:

- Navbar
- Hero
- Keywords marquee when `keywords` exists
- Features when `features` exists
- Gallery when `gallery_images` exists
- Videos when `videos` exists
- About block when `about_sections` exists
- Contact
- CTA banner
- Footer

Main admin panels that affect it:

- Hero: hero copy, CTAs, hero image.
- Features: `ai.features`.
- Gallery/Media: `images`, `theme.hero_image`.
- Videos: disk-scanned videos.
- Reviews: review keywords affect the keyword ribbon; reviews are not currently rendered as a visible default testimonial section.
- Contact: business contact fields and hours.
- CTA: `ai.cta_heading`, `ai.cta_subtitle`, `ai.cta_btn_label`, `ai.cta_link`.
- Footer: footer copy and social links, though social render has a backend gap noted below.
- Design: theme colors.

### Bernard

Source: `templates/websites/bernard/pages/` and `components/`.

Generated pages:

- `index.html`: hero, advantages, about, services, why choose us, testimonials.
- `services.html`: service detail/cards page.
- `contact.html`: contact form/details page.

Admin panels:

- `our-services`: home services cards.
- `why-choose-us`: why choose cards and image.
- `services-page`: services page SEO and cards/content.
- `contact`: business fields and hours.
- `reviews`: testimonials source.
- `about`: about paragraph, bullets, years of experience, image derivation.

### Facade

Source: `templates/websites/facade/pages/` and `components/`.

Generated pages:

- `index.html`: hero, about/company story, colored features, values, videos, CTA.
- `services.html`: service detail/cards page.
- `contact.html`: contact form/details page.

Admin panels:

- Hero, features, values, videos, about, contact, CTA, footer, services page, design, SEO.
- Facade hides Bernard-specific `our-services` and `why-choose-us` panels in multipage home mode.

## Draft, Preview, Publish

### Draft Save

`saveChanges()` in `static/js/api.js` sends `collectFormData()` to `POST /api/business/<name>/save`.

`admin.py` writes that payload to `draft_data.json` and preserves `reviews_translated` from enriched data if present.

### Preview

Dynamic preview prefers draft data and never serves static `website/index.html`. Live unsaved preview posts the current form payload.

Preview HTML is post-processed by `_prep_preview_html()` to:

- rewrite relative media paths to `/media/<business>/`.
- rewrite multipage links to `/preview/<business>/?page=...`.
- disable AOS animation opacity/transform for stable iframe display.

### Publish

Generate Website:

1. Saves current form data.
2. `POST /api/business/<name>/generate`.
3. Backend copies newer draft into enriched data.
4. Backend runs `python generate_site.py --dir ScrapeData/<name> --template <template>`.
5. Static files are written under `website/`.

Published routes serve only these generated files.

## Known Issues and Risks

### Section Visibility Does Not Drive Generated Output

`section_visibility` is saved by `collectFormData()`, and the visibility panel updates admin UI state. `generate_site.py` does not read it when building context or deciding sections. Result: hiding a section can fail to hide it from live preview/published HTML.

Recommended fix: create one backend function that resolves `should_render_section(section_key, raw_data, template_config)`, using template enabled sections, data availability, and `section_visibility`. Use that function before adding nav links and before exposing section data to Jinja.

### Backend Template Config Helpers Are Unused

`generate_site.py` defines `load_template_config()`, `_is_section_enabled()`, and `_has_section_data()`, and `templates/websites/README.md` documents those rules. The renderer currently does not call them in the actual render path.

Recommended fix: wire these helpers into `_render_jinja2_template()` and remove duplicated frontend-only assumptions.

### Default Template About/CTA Variables Are Incomplete

`templates/websites/default/index.html` checks `about_sections` and prints `about_title`, `about_description`, `about_image`, and `cta_banner_description`. The context builder does not populate `about_sections`, `about_title`, or `cta_banner_description` for the default template.

Result: the default About section likely never renders, and the CTA description can be blank.

Recommended fix: either populate those fields from `ai.about_paragraph`, `about.highlights`, and CTA subtitle data, or remove the dead default About block.

### Visibility Panel Contains Sections That Are Not Real Rendered Sections

`VIS_SECTIONS` includes `popular_times` and `keywords`.

- `popular_times` is collected and saved, but no current template renders a popular-times chart.
- `keywords` is rendered in the default template, but it is not in `default/template.json`, so template filtering hides it from the visibility list.

Recommended fix: align `VIS_SECTIONS`, template configs, sidebar items, and actual website components.

### Social Links Are Dropped During Rendering

`enriched_data.json` and `draft_data.json` can contain `social_links`, and the admin has social link controls. `generate_site.py` currently sets context `social_links` to an empty list.

Result: generated footer social icons may not reflect saved social data.

Recommended fix: pass normalized `raw.get("social_links", [])` into context and keep Google Maps as a synthetic link if desired.

### Auth and Secrets Are Hardcoded

`admin.py` contains plaintext users/passwords and a development fallback secret key.

Recommended fix before production: move users to environment/database, hash passwords, require `SECRET_KEY`, and add CSRF protection for state-changing admin routes.

### Template Switching Can Overwrite Colors

`updateTemplateAndPreview()` applies the first preset for the new template immediately. This can overwrite a business's selected colors when someone experiments with templates.

Recommended fix: ask before resetting colors, or only apply defaults when no theme exists.

### Multiple Section Truth Sources Are Drifting

Section existence is currently defined in:

- `templates/websites/*/template.json`
- `static/js/globals.js`
- `static/js/sections/visibility.js`
- Jinja `{% if ... %}` checks in templates
- unused helper functions in `generate_site.py`

Recommended fix: make backend section metadata authoritative and expose it to admin JS.

### Generated Navigation Does Not Always Match Rendered Sections

Navigation links are manually built in `generate_site.py`. Some templates/pages render sections differently from the nav conditions, especially in multipage mode and where visibility is toggled.

Recommended fix: build nav links from the same resolved section list used for rendering.

### Contact Forms Depend on SMTP Environment

Public contact form forwarding requires SMTP credentials. If SMTP is not configured, `/api/public/contact` returns an error. This is expected, but should be visible in deployment setup and admin status.

## Recommended Fix Order

1. Unify section resolution in `generate_site.py`.
2. Make `section_visibility` affect preview and published output.
3. Align visibility panel sections with real template sections.
4. Fix default template missing variables or remove dead blocks.
5. Pass social links into generated templates.
6. Prevent template switching from overwriting colors unexpectedly.
7. Move hardcoded auth/secrets to deploy-safe configuration.
8. Add lightweight render regression checks for each template with a known business.

## Adding New Fixes Safely

When changing section behavior:

- Update `template.json` for supported website sections.
- Update admin panel mapping in `globals.js` only if the editor panel changes.
- Update `VIS_SECTIONS` only for sections the generated website can actually render.
- Update backend render decisions in `generate_site.py`.
- Verify both dynamic preview and generated static site.
- Test at least one single-page template and one multipage template.

When adding a new template:

1. Add `templates/websites/<template_id>/`.
2. Add `index.html` or `pages/` templates.
3. Add `style.css` if needed.
4. Add `template.json`.
5. Add metadata to `templates/websites/config.json`.
6. Add admin section mapping if the template uses existing panels differently.
7. Add language files under `lang/` if the template uses `tr`.
8. Run `generate_site.py --dir ScrapeData/<BusinessName> --template <template_id>`.

When adding a new admin field:

1. Add the input in a panel under `templates/admin/panels/`.
2. Hydrate it in `populateForm()`.
3. Serialize it in `collectFormData()`.
4. Consume it in `generate_site.py`.
5. Add it to the relevant website component.
6. Check live preview and generated output.

## Useful Commands

```bash
python admin.py
python app.py --url "https://www.google.com/maps/place/..."
python enrichment.py --dir "ScrapeData/<BusinessName>" --language fr
python generate_site.py --dir "ScrapeData/<BusinessName>" --template default
python generate_site.py --dir "ScrapeData/<BusinessName>" --template bernard
python generate_site.py --dir "ScrapeData/<BusinessName>" --template facade
```

## Current Mental Model

Treat `ScrapeData/<BusinessName>/enriched_data.json` as the published source of truth, `draft_data.json` as the admin working copy, and `generate_site.py` as the renderer boundary. The admin frontend is an editor over that JSON shape, not the final authority for what renders. Any future feature should be wired through all three layers: admin form state, persisted JSON, and backend render context.
