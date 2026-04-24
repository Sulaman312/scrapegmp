import csv
import io
import json
import logging
import os
import smtplib
import shutil
import subprocess
import sys
import traceback
import threading
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage
from html import escape
from werkzeug.utils import secure_filename
from PIL import Image
from dotenv import load_dotenv

from flask import Flask, jsonify, request, render_template, send_from_directory, make_response, redirect, url_for, session
from functools import wraps

import generate_site
from scraper.scraper import scrape_place_by_url
from scraper.re_scraper import re_scrape_business_data
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

# Background job tracking for long-running scrapes
scrape_jobs = {}
scrape_jobs_lock = threading.Lock()


def _save_as_webp(file_stream, dest_path: str):
    """Convert any uploaded image to WebP and save to dest_path."""
    img = Image.open(file_stream)
    if img.mode not in ('RGB', 'RGBA'):
        img = img.convert('RGB')
    img.save(dest_path, 'WEBP', quality=85, method=4)

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SERVER_NAME'] = os.getenv('SERVER_NAME', None)  # Set to your domain for subdomain routing
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRAPE_DIR = os.path.join(BASE_DIR, "ScrapeData")

# ──────────────────────────────────────────────────────────────
#  Authentication Configuration
# ──────────────────────────────────────────────────────────────

USERS = {
    'admin@gmp.com': {
        'password': 'Admin@12345',
        'role': 'admin',
        'businesses': []  # Empty list means access to all
    },
    'monal@dev.com': {
        'password': 'Monal@12345',
        'role': 'user',
        'businesses': ['The Monal Islamabad']  # Restricted access
    }
}


# ──────────────────────────────────────────────────────────────
#  Authentication Helpers
# ──────────────────────────────────────────────────────────────

def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_user_businesses():
    """Get list of businesses the current user can access"""
    if 'user_email' not in session:
        return []

    user_email = session['user_email']
    user = USERS.get(user_email)

    if not user:
        return []

    # Admin has access to all businesses
    if user['role'] == 'admin' or not user['businesses']:
        return None  # None means all businesses

    # Regular user has restricted access
    return user['businesses']

def has_business_access(business_name):
    """Check if current user has access to the specified business"""
    allowed = get_user_businesses()
    # None means admin - has access to all
    if allowed is None:
        return True
    # Check if business is in allowed list
    return business_name in allowed

# ──────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _contact_mail_settings():
    recipient = os.getenv("CONTACT_TO_EMAIL", "tech@sulamanahmed.com").strip()
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_username = os.getenv("SMTP_USERNAME", recipient).strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    from_email = os.getenv("CONTACT_FROM_EMAIL", smtp_username or recipient).strip()
    use_tls = os.getenv("SMTP_USE_TLS", "true").strip().lower() not in {"0", "false", "no"}
    use_ssl = os.getenv("SMTP_USE_SSL", "false").strip().lower() in {"1", "true", "yes"}

    return {
        "recipient": recipient,
        "smtp_host": smtp_host,
        "smtp_port": smtp_port,
        "smtp_username": smtp_username,
        "smtp_password": smtp_password,
        "from_email": from_email,
        "use_tls": use_tls,
        "use_ssl": use_ssl,
    }


def _send_contact_submission_email(payload: dict) -> None:
    settings = _contact_mail_settings()

    if not settings["smtp_username"] or not settings["smtp_password"]:
        raise RuntimeError(
            "SMTP credentials are not configured. Set SMTP_USERNAME and SMTP_PASSWORD in the environment."
        )

    business_name = (payload.get("business_name") or "Business").strip() or "Business"
    form_type = (payload.get("form_type") or "contact").strip() or "contact"
    submitted_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    page_url = (payload.get("page_url") or payload.get("referrer") or "").strip()
    page_title = (payload.get("page_title") or "").strip()
    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip()
    phone = (payload.get("phone") or "").strip()
    subject = (payload.get("subject") or "").strip()
    message = (payload.get("message") or "").strip()

    if not message and form_type == "hero":
        message = f"Hero form submission from {name or 'a visitor'}"
        if phone:
            message += f". Phone: {phone}"

    email_subject = f"[Website Contact] {business_name} — {subject or 'New submission'}"

    body_lines = [
        "New contact form submission received.",
        "",
        f"Business: {business_name}",
        f"Form type: {form_type}",
        f"Submitted at: {submitted_at}",
    ]
    if page_title:
        body_lines.append(f"Page title: {page_title}")
    if page_url:
        body_lines.append(f"Page URL: {page_url}")
    body_lines.extend([
        "",
        f"Name: {name or '-'}",
        f"Email: {email or '-'}",
        f"Phone: {phone or '-'}",
        f"Subject: {subject or '-'}",
        "",
        "Message:",
        message or "-",
    ])

    html_parts = [
        "<h2>New contact form submission received</h2>",
        "<ul>",
        f"<li><strong>Business:</strong> {escape(business_name)}</li>",
        f"<li><strong>Form type:</strong> {escape(form_type)}</li>",
        f"<li><strong>Submitted at:</strong> {escape(submitted_at)}</li>",
    ]
    if page_title:
        html_parts.append(f"<li><strong>Page title:</strong> {escape(page_title)}</li>")
    if page_url:
        html_parts.append(f"<li><strong>Page URL:</strong> {escape(page_url)}</li>")
    html_parts.extend([
        f"<li><strong>Name:</strong> {escape(name or '-')}</li>",
        f"<li><strong>Email:</strong> {escape(email or '-')}</li>",
        f"<li><strong>Phone:</strong> {escape(phone or '-')}</li>",
        f"<li><strong>Subject:</strong> {escape(subject or '-')}</li>",
        "</ul>",
        "<h3>Message</h3>",
        f"<pre style=\"white-space:pre-wrap;font-family:inherit\">{escape(message or '-')}</pre>",
    ])

    email_message = EmailMessage()
    email_message["Subject"] = email_subject
    email_message["From"] = settings["from_email"]
    email_message["To"] = settings["recipient"]
    if email:
        email_message["Reply-To"] = email
    email_message.set_content("\n".join(body_lines))
    email_message.add_alternative("".join(html_parts), subtype="html")

    if settings["use_ssl"]:
        with smtplib.SMTP_SSL(settings["smtp_host"], settings["smtp_port"], timeout=30) as smtp:
            smtp.login(settings["smtp_username"], settings["smtp_password"])
            smtp.send_message(email_message)
    else:
        with smtplib.SMTP(settings["smtp_host"], settings["smtp_port"], timeout=30) as smtp:
            if settings["use_tls"]:
                smtp.starttls()
            smtp.login(settings["smtp_username"], settings["smtp_password"])
            smtp.send_message(email_message)


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


def get_subdomain_and_business():
    """
    Extract subdomain from the request and determine if it's admin or a business site.
    Returns: (subdomain, business_name, is_admin)

    Examples:
    - admin.example.com → ('admin', None, True)
    - businessname.example.com → ('businessname', 'businessname', False)
    - localhost:8000 → (None, None, True)  # Treat as admin for local dev
    """
    host = request.host.lower()

    # For local development (localhost or IP addresses), treat as admin
    if 'localhost' in host or host.startswith('127.0.0.1') or host.startswith('192.168.'):
        return (None, None, True)

    # Split host to get subdomain
    parts = host.split(':')[0].split('.')  # Remove port, then split by dots

    # If it's just domain.com (2 parts), treat as admin
    if len(parts) <= 2:
        return (None, None, True)

    # If it's subdomain.domain.com (3+ parts), extract subdomain
    subdomain = parts[0]

    # Check if it's the admin subdomain
    if subdomain == 'admin':
        return (subdomain, None, True)

    # Otherwise, treat subdomain as business name
    # Normalize the subdomain to match folder names (replace hyphens with spaces, capitalize)
    business_name = subdomain.replace('-', ' ').title()

    # Check if this business exists in ScrapeData
    if os.path.exists(os.path.join(SCRAPE_DIR, business_name)):
        return (subdomain, business_name, False)

    # Also try the subdomain as-is (in case it's already properly formatted)
    if os.path.exists(os.path.join(SCRAPE_DIR, subdomain)):
        return (subdomain, subdomain, False)

    # If business doesn't exist, treat as admin (will 404 later)
    return (subdomain, None, True)


def get_business_url(business_name):
    """
    Generate the public URL for a business.
    Returns subdomain-based URL if BASE_DOMAIN is set, otherwise falls back to /site/ path.

    Examples:
    - With BASE_DOMAIN='example.com': 'https://businessname.example.com'
    - Without BASE_DOMAIN: '/site/BusinessName/'
    """
    base_domain = os.getenv('BASE_DOMAIN', None)

    if base_domain:
        # Convert business name to subdomain format (lowercase, spaces to hyphens)
        subdomain = business_name.lower().replace(' ', '-')
        protocol = 'https' if os.getenv('USE_HTTPS', 'true').lower() == 'true' else 'http'
        return f"{protocol}://{subdomain}.{base_domain}"
    else:
        # Fallback to old /site/ format for local development
        return f"/site/{business_name}/"


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


@app.before_request
def handle_subdomain_routing():
    """
    Handle wildcard subdomain routing:
    - admin.domain.com → serve admin panel
    - businessname.domain.com → serve business website
    - domain.com → serve admin panel (for backward compatibility)
    """
    subdomain, business_name, is_admin = get_subdomain_and_business()

    # Log subdomain routing for debugging
    print(f" [SUBDOMAIN] host={request.host} subdomain={subdomain} business={business_name} is_admin={is_admin}", flush=True)

    # If it's admin or root domain, let normal routes handle it
    if is_admin:
        return None

    # If it's a business subdomain, serve the business website
    if business_name:
        # Skip this handler for API, media, and static routes
        if request.path.startswith('/api/') or request.path.startswith('/media/') or request.path.startswith('/static/'):
            return None

        # Serve the business website
        return serve_business_subdomain(business_name)


# ──────────────────────────────────────────────────────────────
#  Authentication Routes
# ──────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        user = USERS.get(email)

        if user and user['password'] == password:
            session['user_email'] = email
            session['user_role'] = user['role']
            session['user_businesses'] = user['businesses']
            return redirect(url_for('index'))
        else:
            return redirect(url_for('login', error='invalid'))

    # If already logged in, redirect to dashboard
    if 'user_email' in session:
        return redirect(url_for('index'))

    return render_template("admin/login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('login'))

# ──────────────────────────────────────────────────────────────
#  Dashboard Routes
# ──────────────────────────────────────────────────────────────

@app.route("/")
@login_required
def index():
    resp = make_response(render_template("admin/base.html"))
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp


# ──────────────────────────────────────────────────────────────
#  API – business list
# ──────────────────────────────────────────────────────────────

@app.route("/api/businesses")
@login_required
def list_businesses():
    if not os.path.exists(SCRAPE_DIR):
        return jsonify([])

    allowed_businesses = get_user_businesses()
    businesses = []
    for name in sorted(os.listdir(SCRAPE_DIR)):
        # Filter businesses based on user permissions
        if allowed_businesses is not None and name not in allowed_businesses:
            continue

        folder = os.path.join(SCRAPE_DIR, name)
        enriched = os.path.join(folder, "enriched_data.json")
        if os.path.isdir(folder) and os.path.exists(enriched):
            businesses.append({
                "name": name,
                "has_website": os.path.exists(os.path.join(folder, "website", "index.html")),
                "has_ai": has_ai_data(enriched),
                "url": get_business_url(name),  # Add public URL
            })
    return jsonify(businesses)


@app.route("/api/templates")
@login_required
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


def _background_scrape_worker(job_id: str, url: str, language: str, api_key: str):
    """
    Background worker function that performs the actual scraping and enrichment.
    Updates the scrape_jobs dictionary with progress.
    """
    def update_job(status, progress=None, **kwargs):
        with scrape_jobs_lock:
            scrape_jobs[job_id].update({
                'status': status,
                'updated_at': datetime.now().isoformat(),
                **kwargs
            })
            if progress is not None:
                scrape_jobs[job_id]['progress'] = progress

    try:
        update_job('scraping', progress=10)
        logging.info(f"[Job {job_id}] Starting scrape for URL: {url}")

        # Step 1: Scrape the business data
        logging.info(f"[Job {job_id}] Step 1/3: Scraping business data...")
        result = scrape_place_by_url(
            url,
            SCRAPE_DIR,
            extract_emails=True,
            chrome_profile=""
        )
        logging.info(f"[Job {job_id}] Step 1/3: Scraping completed")

        if not result or not result.get('place_data'):
            logging.error(f"[Job {job_id}] Scraping failed - no place_data returned")
            update_job('failed', error="Failed to scrape business data")
            return

        business_name = result['place_data'].get('name', 'Unknown')
        output_dir = result['output_dir']
        images_count = result.get('images_count', 0)

        logging.info(f"[Job {job_id}] Scrape complete for: {business_name} ({images_count} images)")
        update_job('enriching', progress=60, business_name=business_name)

        # Step 2: Enrich with AI
        logging.info(f"[Job {job_id}] Step 2/3: Starting AI enrichment...")
        enriched_data = enrich(output_dir, api_key, language)

        logging.info(f"[Job {job_id}] Step 2/3: AI enrichment complete for: {business_name}")
        update_job('completed', progress=100, business_name=business_name, output_dir=output_dir)

    except Exception as e:
        logging.error(f"[Job {job_id}] ERROR: {type(e).__name__}: {e}")
        logging.error(f"[Job {job_id}] Traceback:\n{traceback.format_exc()}")
        update_job('failed', error=f"{type(e).__name__}: {str(e)}")


@app.route("/api/scrape-and-enrich", methods=["POST"])
@login_required
def scrape_and_enrich():
    """
    Start a background scrape job and return immediately with a job ID.
    Client should poll /api/scrape-status/<job_id> for progress.
    """
    data = request.get_json()
    if not data or not data.get("url"):
        return jsonify({"success": False, "error": "No URL provided"}), 400

    url = data["url"]
    language = data.get("language", "fr")

    # OpenAI API key - must be set via environment variable
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return jsonify({
            "success": False,
            "error": "OPENAI_API_KEY environment variable is not set"
        }), 500

    # Create a unique job ID
    job_id = str(uuid.uuid4())

    # Initialize job status
    with scrape_jobs_lock:
        scrape_jobs[job_id] = {
            'job_id': job_id,
            'status': 'queued',
            'progress': 0,
            'url': url,
            'language': language,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }

    # Start background thread
    thread = threading.Thread(
        target=_background_scrape_worker,
        args=(job_id, url, language, api_key),
        daemon=True
    )
    thread.start()

    logging.info(f"Started background scrape job {job_id} for URL: {url}")

    return jsonify({
        "success": True,
        "job_id": job_id,
        "message": "Scrape job started. Poll /api/scrape-status/{job_id} for progress."
    })


@app.route("/api/scrape-status/<job_id>", methods=["GET"])
@login_required
def scrape_status(job_id):
    """
    Check the status of a background scrape job.
    Returns: { status: 'queued'|'scraping'|'enriching'|'completed'|'failed', progress: 0-100, ... }
    """
    with scrape_jobs_lock:
        job = scrape_jobs.get(job_id)

    if not job:
        return jsonify({"success": False, "error": "Job not found"}), 404

    return jsonify({
        "success": True,
        **job
    })


@app.route("/api/download-place-data/<path:business_name>", methods=["GET"])
@login_required
def download_place_data(business_name):
    """Download place_data.json for debugging."""
    import os
    from flask import send_file

    file_path = os.path.join("ScrapeData", business_name, "place_data.json")

    if not os.path.exists(file_path):
        return jsonify({"success": False, "error": "File not found"}), 404

    return send_file(file_path, as_attachment=True, download_name="place_data.json")


@app.route("/api/public/contact", methods=["POST"])
def public_contact_submit():
    """Receive public Bernard contact form submissions and forward them by email."""
    payload = request.get_json(silent=True) or request.form.to_dict(flat=True)

    if not payload:
        return jsonify({"success": False, "error": "No form data provided"}), 400

    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip()
    phone = (payload.get("phone") or "").strip()
    subject = (payload.get("subject") or "").strip()
    message = (payload.get("message") or "").strip()
    business_name = (payload.get("business_name") or "Business").strip() or "Business"
    form_type = (payload.get("form_type") or "contact").strip() or "contact"

    if not name:
        return jsonify({"success": False, "error": "Name is required"}), 400

    if form_type == "contact" and (not email or not message):
        return jsonify({"success": False, "error": "Email is required"}), 400

    try:
        _send_contact_submission_email({
            "name": name,
            "email": email,
            "phone": phone,
            "subject": subject,
            "message": message,
            "business_name": business_name,
            "form_type": form_type,
            "page_url": (payload.get("page_url") or "").strip(),
            "page_title": (payload.get("page_title") or "").strip(),
            "referrer": request.referrer or "",
        })
    except Exception as exc:
        logging.error("Failed to forward contact submission: %s", exc)
        logging.error(traceback.format_exc())
        return jsonify({"success": False, "error": "Unable to send message right now"}), 500

    return jsonify({"success": True, "message": "Your message has been sent successfully."})


# ──────────────────────────────────────────────────────────────
#  API – get / save business data
# ──────────────────────────────────────────────────────────────

@app.route("/api/business/<name>", methods=["GET"])
@login_required
def get_business(name):
    # Check business access
    if not has_business_access(name):
        return jsonify({"error": "Access denied"}), 403

    biz_dir = os.path.join(SCRAPE_DIR, name)
    # Prefer the most recently updated JSON between draft and enriched.
    # This avoids stale draft files overriding manually fixed enriched data.
    draft_path = os.path.join(biz_dir, "draft_data.json")
    enriched_path = os.path.join(biz_dir, "enriched_data.json")
    draft_exists = os.path.exists(draft_path)
    enriched_exists = os.path.exists(enriched_path)

    if draft_exists and enriched_exists:
        src_path = draft_path if os.path.getmtime(draft_path) >= os.path.getmtime(enriched_path) else enriched_path
    elif draft_exists:
        src_path = draft_path
    else:
        src_path = enriched_path

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
@login_required
def save_business(name):
    # Check business access
    if not has_business_access(name):
        return jsonify({"error": "Access denied"}), 403

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

    # Preserve reviews_translated from enriched_data.json so translations aren't lost
    enriched_data = load_json(enriched_path)
    if enriched_data.get('reviews_translated'):
        data['reviews_translated'] = enriched_data['reviews_translated']

    save_json(draft_path, data)
    return jsonify({"success": True})


@app.route("/api/business/<name>/re-scrape", methods=["POST"])
@login_required
def re_scrape_business(name):
    """Re-scrape dynamic data (hours, contact, location) from Google Maps"""
    if not has_business_access(name):
        return jsonify({"error": "Access denied"}), 403

    biz_dir = os.path.join(SCRAPE_DIR, name)
    enriched_path = os.path.join(biz_dir, "enriched_data.json")
    draft_path = os.path.join(biz_dir, "draft_data.json")

    if not os.path.exists(enriched_path):
        return jsonify({"error": "Business not found"}), 404

    try:
        # Load existing data
        enriched_data = load_json(enriched_path)
        google_maps_url = enriched_data.get('business', {}).get('google_maps_url')

        if not google_maps_url:
            return jsonify({"error": "No Google Maps URL found for this business"}), 400

        # Re-scrape dynamic data
        logging.info(f"Re-scraping business: {name}")
        new_data = re_scrape_business_data(google_maps_url, extract_emails=True)

        # Update business fields in enriched data
        if 'business' not in enriched_data:
            enriched_data['business'] = {}

        enriched_data['business']['phone'] = new_data['phone']
        enriched_data['business']['email'] = new_data['email']
        enriched_data['business']['address'] = new_data['address']
        enriched_data['business']['latitude'] = new_data['latitude']
        enriched_data['business']['longitude'] = new_data['longitude']
        enriched_data['business']['plus_code'] = new_data['plus_code']
        enriched_data['business']['hours'] = new_data['hours']

        # Save to both enriched and draft
        save_json(enriched_path, enriched_data)
        save_json(draft_path, enriched_data)

        logging.info(f"Re-scrape completed for: {name}")
        return jsonify({
            "success": True,
            "message": "Business data re-scraped successfully",
            "updated": new_data
        })

    except Exception as e:
        logging.error(f"Re-scrape failed for {name}: {e}")
        return jsonify({"error": str(e)}), 500


# ──────────────────────────────────────────────────────────────
#  API – generate website
# ──────────────────────────────────────────────────────────────

@app.route("/api/business/<name>/generate", methods=["POST"])
@login_required
def generate_website(name):
    # Check business access
    if not has_business_access(name):
        return jsonify({"error": "Access denied"}), 403

    biz_dir = os.path.join(SCRAPE_DIR, name)
    # On publish, copy draft into enriched only when draft is newer (or
    # enriched is missing), so stale drafts cannot re-corrupt published data.
    draft_path = os.path.join(biz_dir, "draft_data.json")
    enriched_path = os.path.join(biz_dir, "enriched_data.json")
    if os.path.exists(draft_path):
        draft_is_newer = (
            (not os.path.exists(enriched_path))
            or (os.path.getmtime(draft_path) >= os.path.getmtime(enriched_path))
        )
        if draft_is_newer:
            try:
                # Load draft and current enriched
                draft_data = load_json(draft_path)
                enriched_data = load_json(enriched_path) if os.path.exists(enriched_path) else {}

                # Preserve reviews_translated from enriched if draft doesn't have it
                if enriched_data.get('reviews_translated') and not draft_data.get('reviews_translated'):
                    draft_data['reviews_translated'] = enriched_data['reviews_translated']

                # Save draft as enriched
                save_json(enriched_path, draft_data)
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
@login_required
def upload_media(name):
    # Check business access
    if not has_business_access(name):
        return jsonify({"error": "Access denied"}), 403

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
@login_required
def upload_videos(name):
    # Check business access
    if not has_business_access(name):
        return jsonify({"error": "Access denied"}), 403

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
@login_required
def list_videos(name):
    # Check business access
    if not has_business_access(name):
        return jsonify({"error": "Access denied"}), 403

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
@login_required
def delete_video(name, filename):
    # Check business access
    if not has_business_access(name):
        return jsonify({"error": "Access denied"}), 403

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

    # Bernard multipage preview links must stay on dynamic preview routes
    # (index/services/contact), not static html files.
    html = html.replace('href="index.html"', f'href="/preview/{name}/?page=home"')
    html = html.replace("href='index.html'", f"href='/preview/{name}/?page=home'")
    html = html.replace('href="services.html"', f'href="/preview/{name}/?page=services"')
    html = html.replace("href='services.html'", f"href='/preview/{name}/?page=services'")
    html = html.replace('href="contact.html"', f'href="/preview/{name}/?page=contact"')
    html = html.replace("href='contact.html'", f"href='/preview/{name}/?page=contact'")

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
@login_required
def preview_render_live(name):
    # Check business access
    if not has_business_access(name):
        return jsonify({"error": "Access denied"}), 403

    """Render HTML from current form data (live preview without saving)."""
    biz_dir = os.path.join(SCRAPE_DIR, name)
    if not os.path.isdir(biz_dir):
        return jsonify({"error": "Business not found"}), 404
    data = request.get_json()
    if data is None:
        return jsonify({"error": "JSON body required"}), 400
    try:
        template = data.get("template", "default")
        current_page = data.get("current_page", "home")

        # Check if this is a multipage template
        if template in ["bernard", "facade"] and current_page in ["home", "services", "contact"]:
            html = generate_site.build_html_page(biz_dir, template, current_page, current_page, use_draft=False, override_data=data)
        else:
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
    name = (name or "").strip()
    biz_dir = os.path.join(SCRAPE_DIR, name)
    # Preview should always reflect the latest draft edits if present.
    draft_path = os.path.join(biz_dir, "draft_data.json")
    enriched = os.path.join(biz_dir, "enriched_data.json")

    has_draft = os.path.exists(draft_path)
    has_enriched = os.path.exists(enriched)
    if has_draft or has_enriched:
        # Get template and page from query params or draft/enriched data
        template = "default"
        current_page = request.args.get("page", "home")

        for path in [draft_path, enriched]:
            if os.path.exists(path):
                try:
                    data = load_json(path)
                    template = data.get("template", "default")
                    break
                except Exception:
                    pass

        try:
            # First try: render from draft (preferred for admin preview)
            if template in ["bernard", "facade"] and current_page in ["home", "services", "contact"]:
                html = generate_site.build_html_page(biz_dir, template, current_page, current_page, use_draft=True)
            else:
                html = generate_site.build_html(biz_dir, use_draft=True, template=template)

            html = _prep_preview_html(html, name)
            resp = make_response(html)
            resp.headers["Content-Type"] = "text/html; charset=utf-8"
            return resp
        except Exception as draft_exc:
            logging.warning(f"Draft preview failed for '{name}' (page={current_page}): {draft_exc}")
            # Fallback: render from enriched so preview still works if draft is malformed
            try:
                if template in ["bernard", "facade"] and current_page in ["home", "services", "contact"]:
                    html = generate_site.build_html_page(biz_dir, template, current_page, current_page, use_draft=False)
                else:
                    html = generate_site.build_html(biz_dir, use_draft=False, template=template)

                html = _prep_preview_html(html, name)
                resp = make_response(html)
                resp.headers["Content-Type"] = "text/html; charset=utf-8"
                return resp
            except Exception as enriched_exc:
                logging.warning(
                    f"Dynamic preview failed for '{name}' (page={current_page}). "
                    f"draft_error={draft_exc}; enriched_error={enriched_exc}"
                )
                return (
                    "<h2 style='font-family:sans-serif;padding:2rem'>"
                    "Preview render failed. Please check data format and server logs.</h2>",
                    500,
                )

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
#  Subdomain business site handler
# ──────────────────────────────────────────────────────────────

def serve_business_subdomain(business_name):
    """
    Serve business website from subdomain (businessname.domain.com)
    This function is called by the before_request handler for business subdomains.
    """
    biz_dir = os.path.join(SCRAPE_DIR, business_name)
    website_dir = os.path.join(biz_dir, "website")

    # Determine which file to serve based on path
    path = request.path.lstrip('/')

    # Default to index.html if no path specified
    if not path or path == '':
        path = 'index.html'
    # Append index.html if path is a directory
    elif path.endswith('/'):
        path = path + 'index.html'

    # Normalize path to prevent traversal attacks
    path = os.path.normpath(path).replace("\\", "/")
    if path.startswith("../") or path == "..":
        return ("<h2>Invalid path.</h2>", 404)

    index_path = os.path.join(website_dir, "index.html")
    if not os.path.isfile(index_path):
        return (
            "<h2 style='font-family:sans-serif;padding:2rem'>"
            f"No website generated yet for {business_name}. "
            "Please contact the administrator.</h2>",
            404,
        )

    target_path = os.path.join(website_dir, path)
    if not os.path.isfile(target_path):
        # Try with .html extension
        if not path.endswith('.html'):
            target_path_html = os.path.join(website_dir, path + '.html')
            if os.path.isfile(target_path_html):
                target_path = target_path_html
            else:
                return ("<h2>Page not found.</h2>", 404)
        else:
            return ("<h2>Page not found.</h2>", 404)

    try:
        # For HTML files, rewrite relative media paths
        if path.lower().endswith(".html"):
            with open(target_path, "r", encoding="utf-8") as f:
                html = f.read()
            # Rewrite media paths to use absolute /media/ paths
            html = html.replace('"../', f'"/media/{business_name}/')
            html = html.replace("'../", f"'/media/{business_name}/")
            resp = make_response(html)
            resp.headers["Content-Type"] = "text/html; charset=utf-8"
            return resp

        # Non-HTML assets
        return send_from_directory(website_dir, path)
    except Exception as exc:
        logging.warning(f"Failed to serve subdomain site for '{business_name}/{path}': {exc}")
        return ("<h2>Error loading website.</h2>", 500)


# ──────────────────────────────────────────────────────────────
#  Published site – ONLY the last generated website (no draft)
#
#  Serves ScrapeData/<name>/website/index.html. This file is
#  written ONLY when the user clicks "Generate Website". So
#  Preview (draft) and Open Site (published) are fully separate.
#
#  Use a single <path:subpath> rule so /site/Digimidi, /site/Digimidi/,
#  and /site/Digimidi/index.html all hit this view (avoids Flask slash 404s).
#
#  NOTE: This route is kept for backward compatibility. With wildcard domains,
#  businesses should be accessed via businessname.domain.com instead.
# ──────────────────────────────────────────────────────────────

@app.route("/site/<path:subpath>")
def serve_published_site(subpath):
    # subpath is e.g. "Digimidi", "Digimidi/", "Digimidi/index.html", "Digimidi/services.html"
    parts = [p for p in subpath.split("/") if p]
    name = (parts[0] if parts else "").strip()
    if not name:
        return ("<h2>Invalid site path.</h2>", 404)

    # Canonicalize root URL to include trailing slash so relative links resolve correctly.
    if len(parts) == 1 and not request.path.endswith("/"):
        return redirect(f"/site/{name}/", code=301)

    requested_rel = "/".join(parts[1:]) if len(parts) > 1 else "index.html"
    if requested_rel.endswith("/") or requested_rel == "":
        requested_rel = requested_rel + "index.html" if requested_rel else "index.html"

    # Prevent path traversal
    requested_rel = os.path.normpath(requested_rel).replace("\\", "/")
    if requested_rel.startswith("../") or requested_rel == "..":
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

    target_path = os.path.join(website_dir, requested_rel)
    if not os.path.isfile(target_path):
        return ("<h2>Page not found.</h2>", 404)

    try:
        # For HTML files, rewrite relative media paths and return inline response.
        if requested_rel.lower().endswith(".html"):
            with open(target_path, "r", encoding="utf-8") as f:
                html = f.read()
            html = html.replace('"../', f'"/media/{name}/')
            html = html.replace("'../", f"'/media/{name}/")
            resp = make_response(html)
            resp.headers["Content-Type"] = "text/html; charset=utf-8"
            return resp

        # Non-HTML assets under /website
        return send_from_directory(website_dir, requested_rel)
    except Exception as exc:
        logging.warning(f"Failed to serve published site for '{name}/{requested_rel}': {exc}")
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
