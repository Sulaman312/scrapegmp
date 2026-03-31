# Default Template Variables Reference

## Global Variables (Used Throughout)
- `business_name` - Business/company name
- `cta_text` - Call-to-action button text (e.g., "Demandez une démo")
- `cta_url` - Call-to-action URL

## Meta & SEO (index.html head)
- `meta_title` - Page title suffix
- `meta_description` - Page meta description

## Navbar (navbar.html)
- `business_name` - Logo/brand name
- `cta_text` - Button text
- `cta_url` - Button URL

## Hero Section (hero.html)
- `category` - Business category/type
- `location` - City/location
- `hero_title` - Main headline
- `hero_description` - Hero paragraph
- `hero_image` - Main hero image URL
- `cta_text` - Primary CTA button text
- `cta_url` - Primary CTA URL

## Keywords Marquee (keywords.html)
- `keywords` - List of keywords to scroll (array)

## Features Section (features.html)
- `features_title` - Section title (e.g., "Tout ce dont vous avez besoin")
- `features_subtitle` - Section subtitle
- `features` - Array of feature objects:
  - `icon` - Icon (Material Icons name or emoji)
  - `icon_type` - "material" or "emoji"
  - `gradient_start` - CSS color for gradient start
  - `gradient_end` - CSS color for gradient end
  - `title` - Feature title
  - `description` - Feature description

## Gallery Section (gallery.html)
- `gallery_images` - Array of image objects:
  - `url` - Image URL
- `business_name` - For image alt tags
- `cta_text` - Button text
- `cta_url` - Button URL

## Videos Section (videos.html)
- `videos` - Array of video objects:
  - `url` - Video file URL

## About Section (index.html inline)
- `about_title` - Company name for heading
- `about_description` - Main description paragraph
- `about_sections` - Array of bullet point texts
- `about_image` - Optional image URL
- `cta_text` - Button text
- `cta_url` - Button URL

## Contact Section (contact.html)
- `address` - Full street address
- `phone` - Phone number
- `email` - Email address (optional)
- `website` - Full website URL
- `website_display` - Website display text (e.g., "digimidi.ch")
- `maps_embed_url` - Google Maps embed URL
- `maps_url` - Google Maps full URL
- `opening_hours` - Array of day objects (optional):
  - `day` - Day abbreviation (Mon, Tue, etc.)
  - `hours` - Hours text or "Closed"
  - `is_closed` - Boolean for styling

## CTA Banner (index.html inline)
- `cta_banner_title` - Banner headline
- `cta_banner_description` - Banner description
- `cta_text` - Button text
- `cta_url` - Button URL

## Footer (footer.html)
- `business_name` - Company name
- `footer_description` - Company description
- `social_links` - Array of social link objects:
  - `platform` - "facebook", "instagram", or "maps"
  - `url` - Social profile URL
- `address` - Full address
- `phone` - Phone number
- `email` - Email (optional)
- `website` - Website URL
- `website_display` - Website display text
- `footer_copyright` - Copyright text
- `maps_url` - Google Maps URL
