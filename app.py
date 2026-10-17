import json
import os
import re
import tempfile
from datetime import date, datetime
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory, session
from google import genai
from yt_dlp import YoutubeDL

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "local-demo-secret-change-me")
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id BIGSERIAL PRIMARY KEY,
    user_email TEXT NOT NULL,
    name TEXT NOT NULL,
    event_date DATE NOT NULL,
    event_time TIME NOT NULL,
    timezone TEXT NOT NULL,
    source_url TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_email, name, event_date, event_time)
)
"""


def database_url():
    value = os.environ.get("DATABASE_URL")
    if not value:
        raise RuntimeError("DATABASE_URL is not configured.")
    return value


def ensure_schema():
    with psycopg.connect(database_url()) as connection:
        connection.execute(SCHEMA)


def logged_in_email():
    email = session.get("email")
    return email if isinstance(email, str) and email else None


def require_login():
    email = logged_in_email()
    if not email:
        return None, (jsonify(error="Please log in first."), 401)
    return email, None


def valid_reel_url(url):
    return bool(re.match(r"^https?://(www\.)?instagram\.com/(reel|p|tv)/[^/?#]+", url or "", re.IGNORECASE))


def download_reel(url, directory):
    options = {
        "outtmpl": str(Path(directory) / "reel.%(ext)s"),
        "format": "best[ext=mp4]/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }
    with YoutubeDL(options) as downloader:
        downloader.download([url])
    files = list(Path(directory).glob("reel.*"))
    if not files:
        raise RuntimeError("Instagram did not provide downloadable reel media.")
    return files[0]


def extract_event(video_path):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")
    client = genai.Client(api_key=api_key)
    uploaded = client.files.upload(file=str(video_path))
    prompt = """Extract the event advertised in this Instagram reel. Return ONLY valid JSON with exactly:
{"name": string or null, "date": "YYYY-MM-DD" or null, "time": "HH:MM" 24-hour or null, "timezone": IANA timezone string or null}
Do not guess missing values. Resolve relative dates using the current date only if the reel provides enough context. The timezone must be null unless explicitly stated or unambiguously indicated."""
    response = client.models.generate_content(model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"), contents=[uploaded, prompt])
    text = response.text.strip().removeprefix("```json").removesuffix("```").strip()
    try:
        result = json.loads(text)
    except json.JSONDecodeError as error:
        raise RuntimeError("Gemini returned an invalid event response.") from error
    if not isinstance(result, dict):
        raise RuntimeError("Gemini returned an invalid event response.")
    required = ("name", "date", "time")
    if any(not isinstance(result.get(key), str) or not result[key].strip() for key in required):
        raise RuntimeError("The reel did not contain a clear event name, date, and start time.")
    try:
        date.fromisoformat(result["date"])
        datetime.strptime(result["time"], "%H:%M")
    except ValueError as error:
        raise RuntimeError("Gemini returned an invalid date or time.") from error
    timezone = result.get("timezone")
    return {
        "name": result["name"].strip(),
        "date": result["date"],
        "time": result["time"],
        "timezone": timezone.strip() if isinstance(timezone, str) and timezone.strip() else "Europe/London",
        "timezone_assumed": not timezone,
    }


@app.get("/")
def index():
    return send_from_directory(ROOT, "index.html")


@app.get("/api/session")
def current_session():
    return jsonify(email=logged_in_email())


@app.post("/api/login")
def login():
    body = request.get_json(silent=True) or {}
    email = body.get("email", "").strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) or not body.get("password"):
        return jsonify(error="Enter a valid email and password."), 400
    session["email"] = email
    try:
        ensure_schema()
    except Exception:
        app.logger.exception("Database initialization failed")
        return jsonify(error="The database is unavailable. Check DATABASE_URL."), 503
    return jsonify(email=email)


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@app.post("/api/extract")
def extract():
    _, error = require_login()
    if error:
        return error
    url = (request.get_json(silent=True) or {}).get("url", "").strip()
    if not valid_reel_url(url):
        return jsonify(error="Enter a valid public Instagram reel URL."), 400
    try:
        with tempfile.TemporaryDirectory() as directory:
            video = download_reel(url, directory)
            event = extract_event(video)
        event["source_url"] = url
        return jsonify(event=event)
    except Exception as exception:
        app.logger.exception("Event extraction failed")
        return jsonify(error=f"Could not extract event details: {exception}"), 422


@app.get("/api/events")
def events():
    email, error = require_login()
    if error:
        return error
    try:
        with psycopg.connect(database_url()) as connection:
            rows = connection.execute("SELECT name, event_date, event_time, timezone FROM events WHERE user_email = %s ORDER BY event_date, event_time", (email,)).fetchall()
        return jsonify(events=[{"name": row[0], "date": row[1].isoformat(), "time": row[2].strftime("%H:%M"), "timezone": row[3]} for row in rows])
    except Exception:
        app.logger.exception("Event listing failed")
        return jsonify(error="The database is unavailable."), 503


@app.post("/api/events")
def save_event():
    email, error = require_login()
    if error:
        return error
    body = request.get_json(silent=True) or {}
    try:
        event_date = date.fromisoformat(body.get("date", ""))
        event_time = datetime.strptime(body.get("time", ""), "%H:%M").time()
    except (TypeError, ValueError):
        return jsonify(error="Enter a valid date and time."), 400
    name = body.get("name", "").strip()
    timezone = body.get("timezone", "").strip()
    if not name or not timezone:
        return jsonify(error="Event name and timezone are required."), 400
    try:
        with psycopg.connect(database_url()) as connection:
            connection.execute("INSERT INTO events (user_email, name, event_date, event_time, timezone, source_url) VALUES (%s, %s, %s, %s, %s, %s)", (email, name, event_date, event_time, timezone, body.get("source_url", "instagram")))
    except psycopg.errors.UniqueViolation:
        return jsonify(error="This event is already saved."), 409
    except Exception:
        app.logger.exception("Event save failed")
        return jsonify(error="The database is unavailable."), 503
    return jsonify(ok=True), 201


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
