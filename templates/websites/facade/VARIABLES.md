# Facade Template Variables

This document lists all Jinja2 variables used in the Facade template.

## Global Variables

### SEO & Meta
- `seo_title` - Page title (used in `<title>` and hero h1)
- `seo_description` - Meta description for SEO

### Branding
- `brand_short_name` - Business name (used in navbar logo)

### Contact Information
- `email` - Email address (top header, footer)
- `phone` - Phone number (top header, footer)
- `address` - Physical address (contact section)
- `latitude` - Location latitude for map embed
- `longitude` - Location longitude for map embed

### Hero Section
- `hero_image` - Hero background image URL
- `hero_subtitle` - Subtitle text below main title
- `cta_primary` - Primary CTA button text
- `cta_primary_url` - Primary CTA button URL
- `cta_secondary` - Secondary CTA button text
- `cta_secondary_url` - Secondary CTA button URL (default: #contact)

### Footer
- `footer_tagline` - Short description in footer
- `footer_copyright` - Copyright text

### Navigation
- `dynamic_nav_links` - HTML string of navigation links (generated based on enabled sections)

### Styling
- `facade_css` - Complete CSS stylesheet with color variables replaced

## Section Variables

### About Section (`components/about.html`)
Conditional: Only shown if `about_story_left` or `about_story_right` exist

- `about_story_left` - First half of about text (left column)
- `about_story_right` - Second half of about text (right column)
- `story_image_1` - First story image URL
- `story_image_2` - Second story image URL

### Features Colored Section (`components/features_colored.html`)
Conditional: Only shown if `features` array exists

- `features_intro_text` - Intro paragraph above features grid
- `features[]` - Array of feature objects with:
  - `icon` - Material icon name or emoji
  - `icon_type` - 'material' or other (determines rendering)
  - `title` - Feature title (optional, shown if show_title is true)
  - `description` - Feature description
  - `show_title` - Boolean, whether to display title

### Videos Section (`components/videos.html`)
Conditional: Only shown if `videos` array exists

- `videos[]` - Array of video objects with:
  - `src` - Video file URL with media prefix
  - `mime` - Video MIME type (video/mp4 or video/webm)

### Contact Section (`components/contact.html`)
Conditional: Only shown if `address`, `phone`, or `email` exist

- `address` - Physical address
- `phone` - Phone number
- `email` - Email address
- `latitude` - Map latitude (optional)
- `longitude` - Map longitude (optional)

### Values Section (`components/values.html`)
Conditional: Only shown if `values` array exists

- `values[]` - Array of 5 value/benefit text strings
- `values_image` - Center image URL for the values stage

Note: Values are populated from AI data or feature descriptions as fallback. Always contains exactly 5 items.

### CTA Banner (`components/cta_banner.html`)
Conditional: Only shown if `cta_heading` exists

- `cta_heading` - Main heading text
- `cta_primary` - Button text
- `cta_primary_url` - Button URL

## Component Structure

```
templates/websites/facade/
├── index.html              # Main template
├── style.css               # Template CSS with {{ theme_colorN }} placeholders
├── components/
│   ├── top_header.html     # Top contact bar (always shown)
│   ├── navbar.html         # Navigation (always shown)
│   ├── hero.html           # Hero section (always shown)
│   ├── about.html          # About/story section (conditional)
│   ├── features_colored.html  # Features grid (conditional)
│   ├── values.html         # Values/benefits with center image (conditional)
│   ├── videos.html         # Video showcase (conditional)
│   ├── contact.html        # Contact info & map (conditional)
│   ├── cta_banner.html     # Call-to-action (conditional)
│   └── footer.html         # Footer (always shown)
└── VARIABLES.md            # This file
```

## Notes

- All component files use Jinja2 syntax: `{{ variable }}`, `{% if %}`, `{% for %}`
- The main `index.html` uses `{% include %}` to compose components
- Conditional sections only render when their data exists
- The `facade_css` variable contains the complete stylesheet with theme colors injected
- Material icons use the `material-symbols-outlined` class
