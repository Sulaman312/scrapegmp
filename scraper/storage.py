import logging
import os
import time
from dataclasses import asdict

import pandas as pd

from scraper.models import Place


def load_existing_places(output_path: str) -> set:
    """Load already scraped place identifiers from CSV to avoid duplicates"""
    extracted_identifiers = set()
    if os.path.isfile(output_path):
        try:
            df = pd.read_csv(output_path)
            for _, row in df.iterrows():
                name = str(row.get('name', '')).lower()
                address = str(row.get('address', '')).lower()
                identifier = f"{name}|{address}"
                extracted_identifiers.add(identifier)
            logging.info(f"📋 Loaded {len(extracted_identifiers)} existing places from {output_path}")
        except Exception as e:
            logging.warning(f"⚠ Could not load existing CSV: {e}")
    return extracted_identifiers


def save_place_to_csv(place: Place, output_path: str = "result_11.csv"):
    """Save a single place to CSV immediately (append mode)"""
    df = pd.DataFrame([asdict(place)])

    if not df.empty:
        file_exists = os.path.isfile(output_path)

        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                df.to_csv(output_path, index=False, mode='a', header=not file_exists)
                return True
            except PermissionError:
                if attempt < max_attempts - 1:
                    logging.warning(f"⚠ Permission denied on attempt {attempt + 1}. Retrying...")
                    time.sleep(1)
                else:
                    backup_path = f"result_backup_{time.strftime('%Y%m%d_%H%M%S')}.csv"
                    logging.error(f"❌ PERMISSION DENIED: Please close '{output_path}' in Excel!")
                    logging.info(f"💾 Saving to backup file: {backup_path}")
                    try:
                        df.to_csv(backup_path, index=False, mode='a', header=not os.path.isfile(backup_path))
                        return True
                    except Exception as e:
                        logging.error(f"❌ Could not save backup: {e}")
                        return False
            except Exception as e:
                logging.error(f"❌ Error saving CSV: {e}")
                return False
    return False


def read_cities_from_excel(excel_path: str = "city/city.xlsx") -> list:
    """Read city names from Excel file"""
    try:
        df = pd.read_excel(excel_path)
        if 'city' not in df.columns:
            logging.error(f"❌ Excel file must have a 'city' column!")
            return []

        cities = df['city'].dropna().tolist()
        logging.info(f"✅ Loaded {len(cities)} cities from {excel_path}")
        logging.info(f"📍 Cities: {', '.join(cities)}")
        return cities
    except Exception as e:
        logging.error(f"❌ Failed to read Excel file: {e}")
        return []
