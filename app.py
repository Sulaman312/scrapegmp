import argparse
import logging
import traceback

from scraper.scraper import scrape_multiple_cities, scrape_place_by_url, scrape_places_until_end
from scraper.storage import read_cities_from_excel
from scraper.utils import setup_logging


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--search", type=str, help="Search query for Google Maps")
    parser.add_argument("-t", "--total", type=int, help="Total number of results to scrape (deprecated for city mode)")
    parser.add_argument("-o", "--output", type=str, default="result.csv", help="Output CSV file path")
    parser.add_argument("--cities", action="store_true", help="Use city mode: read cities from city/city.xlsx")
    parser.add_argument("--city-file", type=str, default="city/city.xlsx", help="Path to Excel file with cities")
    parser.add_argument("--output-folder", type=str, default="ScrapeData", help="Folder to save city CSV files")
    parser.add_argument("--no-email", action="store_true", help="Skip email extraction (faster scraping)")
    parser.add_argument(
        "--url", type=str,
        help=(
            "Scrape everything from one specific Google Maps place URL. "
            "Downloads all images, all reviews, and all place details. "
            "Example: python app.py --url \"https://www.google.com/maps/place/...\""
        )
    )
    parser.add_argument(
        "--output-dir", type=str, default="ScrapeData",
        help="Base output directory when using --url mode (default: ScrapeData)"
    )
    parser.add_argument(
        "--chrome-profile", type=str, default="",
        help=(
            "Path to your Chrome 'User Data' folder so the scraper runs as a "
            "logged-in user (needed for Web results / People also search for). "
            "Chrome must be CLOSED before running. "
            r"Windows default: C:\Users\YourName\AppData\Local\Google\Chrome\User Data"
        )
    )
    args = parser.parse_args()

    extract_emails = not args.no_email
    log_file = setup_logging()

    logging.info("=" * 80)
    logging.info("🚀 GOOGLE MAPS SCRAPER STARTED")
    logging.info("=" * 80)
    logging.info(f"📧 Email Extraction: {'Enabled' if extract_emails else 'Disabled (--no-email flag)'}")

    try:
        if args.url:
            logging.info(f"🗺  MODE: Single-Place Full Scrape")
            logging.info(f"🔗 URL          : {args.url}")
            logging.info(f"📁 Output Dir   : {args.output_dir}")
            logging.info(f"📧 Email Extract: {'Enabled' if extract_emails else 'Disabled (--no-email)'}")
            logging.info("=" * 80)

            result = scrape_place_by_url(
                args.url, args.output_dir,
                extract_emails=extract_emails,
                chrome_profile=args.chrome_profile,
            )

            logging.info("=" * 80)
            if result['place_data'].get('name'):
                logging.info(f"✅ SUCCESS — data saved to: {result['output_dir']}")
            else:
                logging.warning("⚠ Scrape may be incomplete — check output folder")
            logging.info(f"📝 Full log: {log_file}")
            logging.info("=" * 80)

        elif args.cities or (not args.search and not args.total):
            logging.info(f"🏙 MODE: Multi-City Scraping")
            logging.info(f"📂 City File: {args.city_file}")
            logging.info(f"📁 Output Folder: {args.output_folder}")
            logging.info(f"📝 Log File: {log_file}")
            logging.info("=" * 80)

            cities = read_cities_from_excel(args.city_file)

            if not cities:
                logging.error("❌ No cities found in Excel file!")
                return

            results = scrape_multiple_cities(cities, output_folder=args.output_folder, extract_emails=extract_emails)

            logging.info("=" * 80)
            if sum(results.values()) > 0:
                logging.info(f"✅ SUCCESS! Scraped {sum(results.values())} total places across {len(results)} cities")
            else:
                logging.warning("⚠ No places were scraped!")
            logging.info(f"📝 Full log saved to: {log_file}")
            logging.info("=" * 80)

        else:
            search_for = args.search or "Vet Clinic in Switzerland"
            total = args.total or 10
            output_path = args.output

            logging.info(f"🔍 MODE: Single Search")
            logging.info(f"🔍 Search Query: {search_for}")
            logging.info(f"🎯 Target Results: {total}")
            logging.info(f"📁 Output File: {output_path}")
            logging.info(f"📝 Log File: {log_file}")
            logging.info("=" * 80)

            places_scraped = scrape_places_until_end(search_for, output_path, max_results=total, extract_emails=extract_emails)

            logging.info("=" * 80)
            if places_scraped > 0:
                logging.info(f"✅ SUCCESS! Scraped {places_scraped} places to {output_path}")
            else:
                logging.warning("⚠ No places were scraped!")
            logging.info(f"📝 Full log saved to: {log_file}")
            logging.info("=" * 80)

    except KeyboardInterrupt:
        logging.warning("⚠ Scraper interrupted by user (Ctrl+C)")
        logging.info(f"📝 Partial log saved to: {log_file}")
    except Exception as e:
        logging.error(f"💥 Fatal error in main: {e}")
        logging.error(f"🔍 Full traceback:\n{traceback.format_exc()}")
        logging.info(f"📝 Error log saved to: {log_file}")
        raise


if __name__ == "__main__":
    main()
