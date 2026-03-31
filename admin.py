import csv
import io
import json
import logging
import os
import shutil
import subprocess
import sys
import traceback
from werkzeug.utils import secure_filename
from PIL import Image
from dotenv import load_dotenv

from flask import Flask, jsonify, request, render_template, send_from_directory, make_response

import generate_site
from scraper.scraper import scrape_place_by_url
from enrichment import enrich

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi'}
ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS


def _save_as_webp(file_stream, dest_path: str):
    """Convert any uploaded image to WebP and save to dest_path."""
    img = Image.open(file_stream)
    if img.mode not in ('RGB', 'RGBA'):
        img = img.convert('RGB')
    img.save(dest_path, 'WEBP', quality=85, method=4)

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRAPE_DIR = os.path.join(BASE_DIR, "ScrapeData")


# ──────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_csv(path):
    """Load a CSV file as a list of dicts, returning [] on any error."""
    if not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            return [row for row in csv.DictReader(f)]
    except Exception:
        return []


def has_ai_data(enriched_path):
    try:
        d = load_json(enriched_path)
        ai = d.get("ai", {})
        return bool(ai.get("tagline") or ai.get("about_paragraph"))
    except Exception:
        return False


# ──────────────────────────────────────────────────────────────
#  Pages
# ──────────────────────────────────────────────────────────────

@app.after_request
def no_cache(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.before_request
def log_request():
    if request.path.startswith("/site/"):
        print(f" [REQUEST] {request.method} {request.path!r}", flush=True)


@app.route("/")
def index():
    resp = make_response(render_template("admin/base.html"))
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp


# ──────────────────────────────────────────────────────────────
#  API – business list
# ──────────────────────────────────────────────────────────────

@app.route("/api/businesses")
def list_businesses():
    if not os.path.exists(SCRAPE_DIR):
        return jsonify([])
    businesses = []
    for name in sorted(os.listdir(SCRAPE_DIR)):
        folder = os.path.join(SCRAPE_DIR, name)
        enriched = os.path.join(folder, "enriched_data.json")
        if os.path.isdir(folder) and os.path.exists(enriched):
            businesses.append({
                "name": name,
                "has_website": os.path.exists(os.path.join(folder, "website", "index.html")),
                "has_ai": has_ai_data(enriched),
            })
    return jsonify(businesses)


@app.route("/api/templates")
def list_templates():
    """Return available website templates from config.json"""
    config_path = os.path.join(BASE_DIR, "templates", "websites", "config.json")
    try:
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                templates = config.get("templates", [])
                enriched_templates = []
                for template in templates:
                    template_id = template.get("id", "default")
                    template_json_path = os.path.join(
                        BASE_DIR,
                        "templates",
                        "websites",
                        template_id,
                        "template.json"
                    )
                    template_copy = dict(template)
                    if os.path.exists(template_json_path):
                        try:
                            with open(template_json_path, "r", encoding="utf-8") as tf:
                                template_config = json.load(tf)
                                template_copy["sections"] = template_config.get("sections", {})
                        except Exception:
                            template_copy["sections"] = {"enabled": [], "configs": {}}
                    else:
                        template_copy["sections"] = {"enabled": [], "configs": {}}
                    enriched_templates.append(template_copy)
                return jsonify(enriched_templates)
    except Exception as e:
        logging.error(f"Error reading templates config: {e}")
    return jsonify([{
        "id": "default",
        "name": "Default",
        "description": "Default template",
        "sections": {"enabled": [], "configs": {}}
    }])


@app.route("/api/scrape-and-enrich", methods=["POST"])
def scrape_and_enrich():
    """
    Scrape a business from Google Maps URL and enrich with AI.
    This combines the functionality of app.py --url and enrichment.py
    """
    data = request.get_json()
    if not data or not data.get("url"):
        return jsonify({"success": False, "error": "No URL provided"}), 400

    url = data["url"]

    # OpenAI API key - must be set via environment variable
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return jsonify({
            "success": False,
            "error": "OPENAI_API_KEY environment variable is not set"
        }), 500

    try:
        logging.info(f"Starting scrape for URL: {url}")

        # Step 1: Scrape the business data
        result = scrape_place_by_url(
            url,
            SCRAPE_DIR,
            extract_emails=True,
            chrome_profile=""
        )

        if not result or not result.get('place_data'):
            return jsonify({
                "success": False,
                "error": "Failed to scrape business data"
            }), 500

        business_name = result['place_data'].get('name', 'Unknown')
        output_dir = result['output_dir']

        logging.info(f"Scrape complete for: {business_name}")
        logging.info(f"Starting AI enrichment...")

        # Step 2: Enrich with AI
        enriched_data = enrich(output_dir, api_key)

        logging.info(f"AI enrichment complete for: {business_name}")

        return jsonify({
            "success": True,
            "business_name": business_name,
            "output_dir": output_dir,
            "message": f"Successfully scraped and enriched {business_name}"
        })

    except Exception as e:
        logging.error(f"Error in scrape_and_enrich: {e}")
        logging.error(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ──────────────────────────────────────────────────────────────
#  API – get / save business data
# ──────────────────────────────────────────────────────────────

@app.route("/api/business/<name>", methods=["GET"])
def get_business(name):
    biz_dir = os.path.join(SCRAPE_DIR, name)
    # Prefer the draft JSON if it exists; otherwise fall back to the
    # last published enriched_data.json so first-time edits start from
    # the current live content.
    draft_path = os.path.join(biz_dir, "draft_data.json")
    enriched_path = os.path.join(biz_dir, "enriched_data.json")
    src_path = draft_path if os.path.exists(draft_path) else enriched_path
    if not os.path.exists(src_path):
        return jsonify({"error": "Not found"}), 404
    data = load_json(src_path)
    # Fall back to reviews.csv when the JSON reviews array is empty
    if not data.get("reviews"):
        data["reviews"] = load_csv(os.path.join(biz_dir, "reviews.csv"))
    # List video files — not stored in enriched_data.json, always scanned from disk
    videos_dir = os.path.join(biz_dir, "videos")
    video_files = []
    if os.path.isdir(videos_dir):
        video_files = sorted(
            f for f in os.listdir(videos_dir)
            if f.lower().endswith((".mp4", ".webm", ".mov"))
        )
    # Expose both "videos" and underscored helper keys so older JSON
    # structures or future clients can all consume the same list.
    data["videos"] = video_files          # canonical list
    data["_has_videos"] = bool(video_files)
    data["_video_list"] = video_files     # filenames only, e.g. ["0001.mp4"]
    return jsonify(data)


@app.route("/api/business/<name>/save", methods=["POST"])
def save_business(name):
    biz_dir = os.path.join(SCRAPE_DIR, name)
    # Saving from the admin only updates the draft JSON so the user
    # can experiment safely. The published enriched_data.json is only
    # touched when "Generate Website" is run.
    enriched_path = os.path.join(biz_dir, "enriched_data.json")
    draft_path = os.path.join(biz_dir, "draft_data.json")
    if not os.path.exists(enriched_path):
        return jsonify({"error": "Not found"}), 404
    data = request.get_json()
    if data is None:
        return jsonify({"error": "Invalid JSON body"}), 400
    save_json(draft_path, data)
    return jsonify({"success": True})


# ──────────────────────────────────────────────────────────────
#  API – generate website
# ──────────────────────────────────────────────────────────────

@app.route("/api/business/<name>/generate", methods=["POST"])
def generate_website(name):
    biz_dir = os.path.join(SCRAPE_DIR, name)
    # On publish, copy the current draft into enriched_data.json so the
    # generated static site reflects exactly the last saved draft.
    draft_path = os.path.join(biz_dir, "draft_data.json")
    enriched_path = os.path.join(biz_dir, "enriched_data.json")
    if os.path.exists(draft_path):
        try:
            shutil.copyfile(draft_path, enriched_path)
        except Exception as exc:
            logging.warning(f"Failed to copy draft to enriched for '{name}': {exc}")

    # Get template from enriched data
    template = "default"
    try:
        enriched_data = load_json(enriched_path)
        template = enriched_data.get("template", "default")
    except Exception:
        pass

    dir_arg = os.path.join("ScrapeData", name)
    try:
        result = subprocess.run(
            [sys.executable, "generate_site.py", "--dir", dir_arg, "--template", template],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=BASE_DIR,
        )
        if result.returncode == 0:
            return jsonify({"success": True, "output": result.stdout[-2000:]})
        return jsonify({"success": False, "error": result.stderr[-2000:]})
    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "error": "Generation timed out after 120s."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ──────────────────────────────────────────────────────────────
#  API – upload images / videos
# ──────────────────────────────────────────────────────────────

@app.route("/api/business/<name>/upload", methods=["POST"])
def upload_media(name):
    biz_dir = os.path.join(SCRAPE_DIR, name)
    if not os.path.exists(biz_dir):
        return jsonify({"error": "Business not found"}), 404

    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files uploaded"}), 400

    upload_dir = os.path.join(biz_dir, "images", "Uploaded")
    os.makedirs(upload_dir, exist_ok=True)

    saved = []
    errors = []
    for f in files:
        if not f.filename:
            continue
        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            errors.append(f"{f.filename}: unsupported type")
            continue

        is_image = ext in IMAGE_EXTENSIONS
        base_name = os.path.splitext(secure_filename(f.filename))[0]
        # Images always get .webp extension; videos keep their original extension
        final_ext = '.webp' if is_image else ext
        safe_name = base_name + final_ext

        # Avoid overwriting existing files
        dest = os.path.join(upload_dir, safe_name)
        counter = 1
        while os.path.exists(dest):
            safe_name = f"{base_name}_{counter}{final_ext}"
            dest = os.path.join(upload_dir, safe_name)
            counter += 1

        try:
            if is_image:
                _save_as_webp(f.stream, dest)
            else:
                f.save(dest)
        except Exception as e:
            errors.append(f"{f.filename}: conversion failed — {e}")
            continue

        rel_path = os.path.join("images", "Uploaded", safe_name).replace("\\", "/")
        saved.append(rel_path)

    return jsonify({"success": True, "saved": saved, "errors": errors})


# ──────────────────────────────────────────────────────────────
#  API – video management  (upload / delete)
# ──────────────────────────────────────────────────────────────

@app.route("/api/business/<name>/videos/upload", methods=["POST"])
def upload_videos(name):
    biz_dir = os.path.join(SCRAPE_DIR, name)
    if not os.path.exists(biz_dir):
        return jsonify({"error": "Business not found"}), 404

    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files uploaded"}), 400

    videos_dir = os.path.join(biz_dir, "videos")
    os.makedirs(videos_dir, exist_ok=True)

    saved, errors = [], []
    for f in files:
        if not f.filename:
            continue
        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in VIDEO_EXTENSIONS:
            errors.append(f"{f.filename}: only video files are allowed (mp4, mov, webm, avi)")
            continue

        safe_name = secure_filename(f.filename)
        base_name = os.path.splitext(safe_name)[0]
        dest = os.path.join(videos_dir, safe_name)
        counter = 1
        while os.path.exists(dest):
            safe_name = f"{base_name}_{counter}{ext}"
            dest = os.path.join(videos_dir, safe_name)
            counter += 1

        try:
            f.save(dest)
            saved.append(safe_name)
        except Exception as e:
            errors.append(f"{f.filename}: save failed — {e}")

    return jsonify({"success": True, "saved": saved, "errors": errors})


@app.route("/api/business/<name>/videos", methods=["GET"])
def list_videos(name):
    """Return the list of video files for a business by scanning disk.

    This is used by the admin panel's Video Library so that any files that
    already exist under ScrapeData/<name>/videos show up even if the JSON
    structure in enriched_data.json does not yet contain video metadata.
    """
    biz_dir = os.path.join(SCRAPE_DIR, name)
    if not os.path.exists(biz_dir):
        return jsonify({"files": []})
    videos_dir = os.path.join(biz_dir, "videos")
    files = []
    if os.path.isdir(videos_dir):
        files = sorted(
            f for f in os.listdir(videos_dir)
            if f.lower().endswith((".mp4", ".webm", ".mov"))
        )
    return jsonify({"files": files})

@app.route("/api/business/<name>/videos/<filename>", methods=["DELETE"])
def delete_video(name, filename):
    safe_name = secure_filename(filename)
    video_path = os.path.join(SCRAPE_DIR, name, "videos", safe_name)
    if not os.path.isfile(video_path):
        return jsonify({"error": "Video not found"}), 404
    try:
        os.remove(video_path)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ──────────────────────────────────────────────────────────────
#  Preview – dynamic rendering (Approach 1)
#
#  Instead of serving a pre-generated static file we call
#  generate_site.build_html() at request time so the preview
#  always reflects the latest enriched_data.json without
#  needing a separate "Generate" step.
#
#  Image/video paths in the HTML use "../images/…" which are
#  rewritten to "/media/<name>/" so Flask can serve them.
# ──────────────────────────────────────────────────────────────

def _prep_preview_html(html: str, name: str) -> str:
    """Rewrite asset paths and inject preview CSS. Used by GET preview and POST render."""
    html = html.replace('"../', f'"/media/{name}/')
    html = html.replace("'../", f"'/media/{name}/")
    # Handle relative paths like href="style.css" → href="/media/BusinessName/website/style.css"
    html = html.replace('href="style.css"', f'href="/media/{name}/website/style.css"')
    html = html.replace("href='style.css'", f"href='/media/{name}/website/style.css'")
    html = html.replace('src="style.css"', f'src="/media/{name}/website/style.css"')
    html = html.replace("src='style.css'", f"src='/media/{name}/website/style.css'")
    preview_css = (
        '<style id="__preview_overrides__">'
        '[data-aos],[data-aos].aos-init,[data-aos].aos-animate{'
        'opacity:1!important;transform:none!important;transition:none!important;}'
        'html{scroll-behavior:auto!important;}'
        '</style>'
    )
    html = html.replace('</head>', preview_css + '\n</head>', 1)
    return html


@app.route("/api/preview/<name>/render", methods=["POST"])
def preview_render_live(name):
    """Render HTML from current form data (live preview without saving)."""
    biz_dir = os.path.join(SCRAPE_DIR, name)
    if not os.path.isdir(biz_dir):
        return jsonify({"error": "Business not found"}), 404
    data = request.get_json()
    if data is None:
        return jsonify({"error": "JSON body required"}), 400
    try:
        template = data.get("template", "default")
        html = generate_site.build_html(biz_dir, use_draft=False, override_data=data, template=template)
        html = _prep_preview_html(html, name)
        return make_response(html, 200, {"Content-Type": "text/html; charset=utf-8"})
    except Exception as exc:
        logging.warning(f"Live preview render failed for '{name}': {exc}")
        return jsonify({"error": str(exc)}), 500


@app.route("/preview/<name>/")
@app.route("/preview/<name>/website/")
@app.route("/preview/<name>/website/index.html")
def preview_website(name):
    biz_dir = os.path.join(SCRAPE_DIR, name)
    # Preview should always reflect the latest draft edits if present.
    draft_path = os.path.join(biz_dir, "draft_data.json")
    enriched = os.path.join(biz_dir, "enriched_data.json")

    if os.path.exists(draft_path) or os.path.exists(enriched):
        try:
            # Get template from draft or enriched data
            template = "default"
            for path in [draft_path, enriched]:
                if os.path.exists(path):
                    try:
                        data = load_json(path)
                        template = data.get("template", "default")
                        break
                    except Exception:
                        pass

            html = generate_site.build_html(biz_dir, use_draft=True, template=template)
            html = _prep_preview_html(html, name)
            resp = make_response(html)
            resp.headers["Content-Type"] = "text/html; charset=utf-8"
            return resp
        except Exception as exc:
            logging.warning(f"Dynamic preview failed for '{name}': {exc}")

    # Preview never serves the static file — that would mix draft and published.
    # If we get here, show a clear message.
    return (
        "<h2 style='font-family:sans-serif;padding:2rem'>"
        "No draft or enriched data for this business. Save data first.</h2>",
        404,
    )


@app.route("/preview/<name>/<path:subpath>")
def preview_static(name, subpath):
    biz_dir = os.path.join(SCRAPE_DIR, name)
    return send_from_directory(biz_dir, subpath)


# ──────────────────────────────────────────────────────────────
#  Published site – ONLY the last generated website (no draft)
#
#  Serves ScrapeData/<name>/website/index.html. This file is
#  written ONLY when the user clicks "Generate Website". So
#  Preview (draft) and Open Site (published) are fully separate.
#
#  Use a single <path:subpath> rule so /site/Digimidi, /site/Digimidi/,
#  and /site/Digimidi/index.html all hit this view (avoids Flask slash 404s).
# ──────────────────────────────────────────────────────────────

@app.route("/site/<path:subpath>")
def serve_published_site(subpath):
    # subpath is e.g. "Digimidi", "Digimidi/", or "Digimidi/index.html"
    name = (subpath.split("/")[0] or "").strip().rstrip("/") or subpath.replace("/index.html", "").rstrip("/")
    if not name:
        return ("<h2>Invalid site path.</h2>", 404)
    print(f" [serve_published_site] name={name!r}", flush=True)
    biz_dir = os.path.join(SCRAPE_DIR, name)
    website_dir = os.path.join(biz_dir, "website")
    index_path = os.path.join(website_dir, "index.html")
    if not os.path.isfile(index_path):
        return (
            "<h2 style='font-family:sans-serif;padding:2rem'>"
            "No website generated yet. Click <b>Generate Website</b> in the admin.</h2>",
            404,
        )
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        # Rewrite relative asset paths so images/videos load via Flask
        html = html.replace('"../', f'"/media/{name}/')
        html = html.replace("'../", f"'/media/{name}/")
        resp = make_response(html)
        resp.headers["Content-Type"] = "text/html; charset=utf-8"
        return resp
    except Exception as exc:
        logging.warning(f"Failed to serve published site for '{name}': {exc}")
        return ("<h2>Error loading published site.</h2>", 500)


# ──────────────────────────────────────────────────────────────
#  Media – serve images/videos inside the admin panel itself
# ──────────────────────────────────────────────────────────────

@app.route("/media/<path:filepath>")
def serve_media(filepath):
    return send_from_directory(SCRAPE_DIR, filepath)


# ──────────────────────────────────────────────────────────────
#  Run
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print("\n" + "=" * 55)
    print("  GMP Admin Panel")
    print(f"  Open in your browser:  http://localhost:{port}")
    print(f"  Published site:       http://localhost:{port}/site/<BusinessName>/")
    site_routes = [r.rule for r in app.url_map.iter_rules() if "site" in r.rule]
    print("  Registered /site/ routes:", site_routes if site_routes else "NONE (bug)")
    print("=" * 55 + "\n")
    app.run(debug=False, host="0.0.0.0", port=port, use_reloader=False)
