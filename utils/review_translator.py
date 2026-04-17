"""
Review translation utilities using OpenAI API.
Detects review language automatically and caches translations in enriched_data.json.
"""

import json
import logging
import os
from typing import List, Dict, Optional

import openai


def detect_review_language(review_text: str) -> str:
    """
    Detect the language of a review text using OpenAI.
    Returns ISO 639-1 language code (en, de, fr, es, etc.)
    """
    try:
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a language detector. Respond ONLY with the ISO 639-1 language code (2 letters: en, de, fr, es, it, pt, etc.). Nothing else."
                },
                {
                    "role": "user",
                    "content": f"What language is this text in?\n\n{review_text[:500]}"
                }
            ],
            max_tokens=5,
            temperature=0
        )

        lang_code = response.choices[0].message.content.strip().lower()
        return lang_code if len(lang_code) == 2 else "en"

    except Exception as e:
        logging.warning(f"Language detection failed: {e}")
        return "en"  # Default to English


def translate_reviews_batch(reviews: List[Dict], source_lang: str, target_lang: str) -> List[Dict]:
    """
    Translate a batch of reviews from source_lang to target_lang using OpenAI.

    Args:
        reviews: List of review dicts with 'text', 'author_name', 'rating', 'date'
        source_lang: Source language code (e.g., 'de')
        target_lang: Target language code (e.g., 'en')

    Returns:
        List of translated review dicts (same structure, with 'text' translated)
    """
    if source_lang == target_lang:
        return reviews  # No translation needed

    try:
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Prepare batch translation request
        review_texts = [r.get("text", "") for r in reviews]
        review_texts_json = json.dumps(review_texts, ensure_ascii=False)

        lang_names = {
            "en": "English",
            "de": "German",
            "fr": "French",
            "es": "Spanish",
            "it": "Italian",
            "pt": "Portuguese",
            "nl": "Dutch",
            "pl": "Polish",
            "ru": "Russian",
            "zh": "Chinese",
            "ja": "Japanese",
            "ko": "Korean",
            "ar": "Arabic"
        }

        source_name = lang_names.get(source_lang, source_lang.upper())
        target_name = lang_names.get(target_lang, target_lang.upper())

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"""You are a professional translator. Translate the following customer reviews from {source_name} to {target_name}.

CRITICAL RULES:
1. Maintain the tone and sentiment of the original review
2. Keep the same level of formality/informality
3. Preserve any specific business/product names
4. Return ONLY a JSON array of translated strings, nothing else
5. The output must be valid JSON that can be parsed

Example input: ["Great food!", "Service was slow"]
Example output: ["Excellent nourriture!", "Le service était lent"]"""
                },
                {
                    "role": "user",
                    "content": review_texts_json
                }
            ],
            temperature=0.3,
            max_tokens=4000
        )

        # Parse translated texts
        translated_json = response.choices[0].message.content.strip()

        # Remove markdown code blocks if present
        if translated_json.startswith("```"):
            translated_json = translated_json.split("```")[1]
            if translated_json.startswith("json"):
                translated_json = translated_json[4:]
            translated_json = translated_json.strip()

        translated_texts = json.loads(translated_json)

        # Create translated reviews (copy structure, replace text)
        translated_reviews = []
        for i, review in enumerate(reviews):
            translated_review = review.copy()
            if i < len(translated_texts):
                translated_review["text"] = translated_texts[i]
            translated_reviews.append(translated_review)

        logging.info(f"✅ Translated {len(translated_reviews)} reviews from {source_lang} to {target_lang}")
        return translated_reviews

    except Exception as e:
        logging.error(f"Translation failed: {e}")
        return reviews  # Return original reviews on error


def ensure_reviews_translated(enriched_data_path: str, target_languages: List[str] = None) -> None:
    """
    Ensure reviews are translated to target languages and cached in enriched_data.json.

    Args:
        enriched_data_path: Path to enriched_data.json
        target_languages: List of language codes to translate to (default: ['en', 'fr', 'de', 'es'])
    """
    if target_languages is None:
        target_languages = ['en', 'fr', 'de', 'es']

    if not os.path.exists(enriched_data_path):
        logging.warning(f"enriched_data.json not found: {enriched_data_path}")
        return

    # Load enriched data
    with open(enriched_data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    reviews = data.get('reviews', [])
    if not reviews:
        logging.info("No reviews to translate")
        return

    # Check if translations already exist
    if 'reviews_translated' not in data:
        data['reviews_translated'] = {}

    # Detect source language from first review
    first_review_text = reviews[0].get('text', '')
    if not first_review_text:
        logging.warning("First review has no text, skipping translation")
        return

    source_lang = detect_review_language(first_review_text)
    logging.info(f"🔍 Detected review language: {source_lang}")

    # Store original reviews under source language
    if source_lang not in data['reviews_translated']:
        data['reviews_translated'][source_lang] = reviews
        logging.info(f"📝 Stored original reviews under '{source_lang}'")

    # Translate to each target language if not already cached
    translation_needed = False
    for target_lang in target_languages:
        if target_lang not in data['reviews_translated']:
            logging.info(f"🌐 Translating reviews to '{target_lang}'...")
            translated = translate_reviews_batch(reviews, source_lang, target_lang)
            data['reviews_translated'][target_lang] = translated
            translation_needed = True
        else:
            logging.info(f"✅ Reviews already translated to '{target_lang}' (cached)")

    # Save updated enriched data if translations were added
    if translation_needed or source_lang not in data.get('reviews_translated', {}):
        try:
            with open(enriched_data_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()  # Explicitly flush to disk
            logging.info(f"💾 Saved translated reviews to {enriched_data_path}")
            # Verify the save was successful
            with open(enriched_data_path, 'r', encoding='utf-8') as f:
                verify_data = json.load(f)
                if 'reviews_translated' in verify_data:
                    logging.info(f"✅ Verified: reviews_translated key exists with {len(verify_data.get('reviews_translated', {}))} languages")
                else:
                    logging.error(f"❌ ERROR: reviews_translated key NOT found in saved file!")
        except Exception as e:
            logging.error(f"❌ Failed to save translations: {e}")


def get_reviews_for_language(enriched_data: Dict, language: str) -> List[Dict]:
    """
    Get reviews in the specified language from enriched_data.
    Falls back to original reviews if translation not available.

    Args:
        enriched_data: The loaded enriched_data dict
        language: ISO 639-1 language code (e.g., 'en', 'fr', 'de', 'es')

    Returns:
        List of review dicts in the requested language
    """
    reviews_translated = enriched_data.get('reviews_translated', {})

    # Try to get reviews in requested language
    if language in reviews_translated:
        return reviews_translated[language]

    # Fallback to original reviews
    return enriched_data.get('reviews', [])
