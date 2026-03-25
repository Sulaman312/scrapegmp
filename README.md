# Google Maps Business Scraper & Website Generator

A comprehensive tool to scrape business data from Google Maps, enrich it with AI-generated content using OpenAI, and generate beautiful one-page websites.

## Features

### 🔍 Automated Scraping
- Scrape complete business profiles from Google Maps
- Extract business info, reviews, images, videos, Q&A, and more
- Download all media files automatically
- Extract contact information including emails

### 🤖 AI-Powered Enrichment
- Automatically generate compelling website copy using OpenAI GPT-4o-mini
- Create SEO-optimized titles and descriptions
- Generate feature descriptions and marketing content
- Smart content extraction from business websites

### 🎨 Website Generation
- Create modern, responsive one-page websites
- Live preview with real-time editing
- Customizable design themes and colors
- Image gallery and video support
- Review showcase
- Contact forms and CTAs

### 🖥️ Admin Panel
- User-friendly web interface
- Real-time preview
- Drag-and-drop media management
- Section-based editing
- Auto-save functionality
- Dark/light theme

## Quick Start

### Local Development

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

2. **Set up environment variables** (optional)
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   ```

3. **Run the application**
   ```bash
   python admin.py
   ```

4. **Open in browser**
   ```
   http://localhost:5051
   ```

### Using the Application

1. **Add a business**
   - Click the dropdown in the header
   - Click "+ Add Business"
   - Paste a Google Maps URL
   - Wait for scraping and AI enrichment (1-3 minutes)

2. **Edit business details**
   - Select the business from dropdown
   - Edit content in the admin panels
   - Changes are auto-saved

3. **Generate website**
   - Click "Generate Website"
   - Click "Open Site" to view the published site

## Project Structure

```
scrapegmpshared/scrapegmp/
├── admin.py                 # Main Flask application
├── app.py                   # Standalone scraper CLI
├── enrichment.py            # AI enrichment module
├── generate_site.py         # Website generation module
├── scraper/                 # Scraping modules
│   ├── scraper.py          # Main scraper logic
│   ├── place_extractor.py  # Business data extraction
│   ├── review_extractor.py # Review scraping
│   ├── media_downloader.py # Image/video downloads
│   └── ...
├── templates/               # HTML templates
│   └── admin/              # Admin panel templates
├── static/                  # CSS, JS, assets
│   ├── css/
│   └── js/
├── ScrapeData/             # Scraped business data
│   └── <BusinessName>/
│       ├── place_data.json
│       ├── enriched_data.json
│       ├── images/
│       ├── videos/
│       └── website/
├── requirements.txt         # Python dependencies
├── Dockerfile              # Docker configuration
└── DEPLOYMENT.md           # Deployment guide
```

## API Endpoints

### Public Endpoints

- `GET /` - Admin panel
- `GET /site/<business_name>/` - Published website
- `GET /preview/<business_name>/` - Draft preview

### API Endpoints

- `GET /api/businesses` - List all businesses
- `GET /api/business/<name>` - Get business data
- `POST /api/business/<name>/save` - Save draft changes
- `POST /api/business/<name>/generate` - Generate website
- `POST /api/scrape-and-enrich` - Scrape and enrich new business
- `POST /api/business/<name>/upload` - Upload images
- `POST /api/business/<name>/videos/upload` - Upload videos

## Technologies Used

- **Backend**: Flask (Python)
- **Scraping**: Playwright (Chromium automation)
- **AI**: OpenAI GPT-4o-mini
- **Frontend**: Vanilla JavaScript, Tailwind CSS
- **Image Processing**: Pillow (WebP conversion)
- **Data Processing**: Pandas

## Manual Workflow (Old Method)

Previously, the workflow was:

1. Run `python app.py --url "<google-maps-url>"` to scrape
2. Manually paste data into ChatGPT with a prompt
3. Manually copy JSON response into `enriched_data.json`
4. Run `python admin.py` to view/edit

**Now everything is automated!** Just click "+ Add Business" and the system handles scraping, AI enrichment, and data organization automatically.

## Environment Variables

- `OPENAI_API_KEY` - Your OpenAI API key (optional, has fallback)
- `PORT` - Server port (default: 5051)
- `FLASK_ENV` - Flask environment (development/production)

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment instructions for Koyeb and other platforms.

### Quick Deploy to Koyeb

1. Push code to GitHub
2. Create new service on Koyeb
3. Select your repository
4. Set builder to Docker
5. Add `OPENAI_API_KEY` environment variable
6. Deploy!

## Development

### Running the Standalone Scraper

```bash
# Scrape a single business
python app.py --url "https://www.google.com/maps/place/YourBusiness/..."

# Scrape from search query
python app.py --search "Vet Clinic in Switzerland" --total 10

# Multi-city scraping
python app.py --cities --city-file city/city.xlsx
```

### Running Enrichment Manually

```bash
python enrichment.py --dir ScrapeData/BusinessName --api-key your-key
```

### Generating a Website Manually

```bash
python generate_site.py --dir ScrapeData/BusinessName
```

## Configuration

All configuration is done through environment variables or can be set in the code:

- Scraping timeout: 120s (configurable in `scraper.py`)
- OpenAI model: gpt-4o-mini (configurable in `enrichment.py`)
- Server port: 5051 (configurable via `PORT` env var)

## Troubleshooting

### Scraper doesn't work
- Ensure Playwright is installed: `playwright install chromium`
- Check that Google Maps is accessible
- Verify the URL is valid

### AI enrichment fails
- Check OpenAI API key is valid
- Ensure you have API credits
- Review error logs

### Website doesn't generate
- Ensure `enriched_data.json` exists
- Check file permissions
- Review Flask logs

## License

This project is proprietary software. All rights reserved.

## Support

For issues or questions, check the application logs or contact the development team.

## Credits

Built with:
- Flask
- Playwright
- OpenAI
- Tailwind CSS
- And many other open-source libraries
