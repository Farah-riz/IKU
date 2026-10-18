import json
import os
import re
import tempfile
from datetime import date, datetime
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template_string, request, send_from_directory, session
from google import genai

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")

app = Flask(__name__, static_folder=None)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "local-demo-secret-change-me")
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
DEFAULT_TIMEZONE = "Europe/London"
DEMO_USERS = {
    "alex": {"id": "alex", "name": "Alex", "avatar": "A"},
    "sam": {"id": "sam", "name": "Sam", "avatar": "S"},
}
ASSETS = {"index.css", "login.css", "calendar.css", "index.js", "login.js", "calendar.js"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    event_date DATE NOT NULL,
    event_time TIME NOT NULL,
    timezone TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (name, event_date, event_time)
)
"""

PAGE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Save a plan — Event extractor</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=DM+Serif+Display:ital@0;1&display=swap');

    :root {
      --ink: #403832;
      --paper: #fffdf7;
      --peach: #e3aa96;
      --sage: #aec9c4;
      --mint: #cfe0da;
      --beige: #e2c7aa;
      --muted: #82786f;
      --line: #e2d9cd;
    }

    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--ink);
      font-family: 'DM Sans', sans-serif;
      background: #e9e9df;
    }
    button, input { font: inherit; }
    button { cursor: pointer; }
    [hidden] { display: none !important; }

    .page {
      width: min(1100px, calc(100% - 40px));
      margin: 0 auto;
      padding: 30px 0 60px;
    }
    .back {
      color: #766c64;
      text-decoration: none;
      font-size: 13px;
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: end;
      gap: 24px;
      margin: 22px 0 28px;
    }
    h1, h2, h3 {
      font-family: 'DM Serif Display', serif;
      font-weight: 400;
    }
    h1 { font-size: clamp(38px, 6vw, 62px); line-height: 1; margin: 8px 0 12px; }
    h1 em { color: #ae7d6c; }
    h2 { font-size: 28px; margin: 0 0 8px; }
    .small-label {
      color: #a07965;
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 2px;
      text-transform: uppercase;
    }
    .subtitle {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.6;
      margin: 0;
    }
    .header-note {
      background: white;
      border-radius: 30px;
      color: #82786f;
      font-size: 12px;
      padding: 11px 16px;
      white-space: nowrap;
    }
    .layout {
      display: grid;
      grid-template-columns: minmax(250px, .8fr) minmax(0, 1.2fr);
      gap: 22px;
      align-items: start;
    }
    .paper {
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 5px;
      box-shadow: 5px 6px 0 #dfd3c3, 9px 12px 25px #665d5015;
    }
    section { padding: 26px; }
    .upload-panel { background: #f7f3eb; }
    .panel-copy { color: var(--muted); font-size: 12px; line-height: 1.6; margin: 0 0 22px; }
    .drop-zone {
      background: white;
      border: 1px dashed #cdbfaf;
      border-radius: 8px;
      padding: 20px;
    }
    label {
      color: #6f645b;
      display: block;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: .5px;
      margin: 14px 0 7px;
    }
    .drop-zone > label:first-child { margin-top: 0; }
    input[type=file], input[type=text], input[type=date], input[type=time] {
      background: #fffdf9;
      border: 1px solid #d7cdc0;
      border-radius: 6px;
      color: var(--ink);
      padding: 11px;
      width: 100%;
    }
    input:focus {
      border-color: #91b3af;
      outline: 2px solid #cfe0da;
      outline-offset: 1px;
    }
    input[type=file] { padding: 8px; }
    button {
      background: var(--sage);
      border: 0;
      border-radius: 6px;
      color: #304b45;
      font-weight: 700;
      margin-top: 17px;
      padding: 12px 17px;
      transition: filter .2s, transform .2s;
    }
    button:hover { filter: brightness(.96); transform: translateY(-1px); }
    button:disabled { cursor: wait; opacity: .55; transform: none; }
    .preview {
      background: #f7f3eb;
      border-radius: 6px;
      display: block;
      margin-top: 15px;
      max-height: 270px;
      max-width: 100%;
      object-fit: contain;
      padding: 5px;
    }
    .tip {
      color: #94887c;
      font-size: 11px;
      line-height: 1.5;
      margin: 17px 0 0;
    }
    .review-panel { min-width: 0; }
    .review-heading {
      align-items: start;
      display: flex;
      gap: 12px;
      justify-content: space-between;
    }
    .review-heading h2 { margin-bottom: 0; }
    .badge {
      background: #d6eadb;
      border-radius: 20px;
      color: #487461;
      font-size: 10px;
      font-weight: 700;
      padding: 7px 10px;
      white-space: nowrap;
    }
    .candidate {
      border-top: 1px dashed #e1d7ca;
      margin-top: 20px;
      padding-top: 18px;
    }
    .candidate:first-child { border-top: 0; margin-top: 16px; padding-top: 0; }
    .candidate-title {
      align-items: center;
      display: flex;
      gap: 9px;
      margin-bottom: 12px;
    }
    .candidate-title label { margin: 0; }
    .candidate-title input { accent-color: #88aaa0; }
    .field-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 12px; }
    .field-wide { grid-column: 1 / -1; }
    .message {
      background: #f3efe7;
      border-radius: 8px;
      color: #81776c;
      font-size: 12px;
      line-height: 1.5;
      margin: 16px 0 0;
      padding: 12px 13px;
    }
    .error { background: #f9e4de; color: #7c2d1d; }
    .warning { background: #fff3c4; color: #715b26; }
    .save-row {
      align-items: center;
      border-top: 1px solid #e8e0d5;
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      justify-content: space-between;
      margin-top: 22px;
      padding-top: 4px;
    }
    .save-row button { margin-top: 16px; }

    @media (max-width: 760px) {
      .page { padding-top: 20px; width: min(100% - 28px, 600px); }
      .header { align-items: start; flex-direction: column; gap: 13px; }
      .header-note { align-self: stretch; text-align: center; }
      .layout { grid-template-columns: 1fr; }
      section { padding: 20px; }
    }
    @media (max-width: 430px) {
      .field-grid { grid-template-columns: 1fr; }
      .field-wide { grid-column: auto; }
      .save-row { align-items: stretch; flex-direction: column; }
      .save-row button { width: 100%; }
    }
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after { transition: none !important; }
    }
  </style>
</head>
<body>
  <main class="page">
    <a href="/calendar" class="back">← back to the planning corner</a>

    <header class="header">
      <div>
        <div class="small-label">✳ THE EVENT SCRAPBOOK</div>
        <h1>save a plan <em>for later.</em></h1>
        <p class="subtitle">Turn a screenshot from the group chat into a calendar-ready event. ♡</p>
      </div>
      <div class="header-note">✦ review before it goes in the diary</div>
    </header>

    <div class="layout">
      <section class="paper upload-panel">
        <div class="small-label">STEP ONE</div>
        <h2>bring the invite</h2>
        <p class="panel-copy">Upload a clear PNG screenshot of the event post. We'll find the date, time, and name for you.</p>
        <div class="drop-zone">
          <form id="upload-form">
            <label for="screenshot">PNG screenshot</label>
            <input id="screenshot" name="screenshot" type="file" accept="image/png" required>
            <img id="preview" class="preview" alt="Screenshot preview" hidden>
            <button id="extract-button" type="submit">✦ extract details</button>
          </form>
        </div>
        <p class="tip">Your screenshot is used only to read the event details. Nothing is saved until you confirm it.</p>
        <p id="upload-message" class="message" hidden></p>
      </section>

      <section id="results" class="paper review-panel" hidden>
        <div class="review-heading">
          <div>
            <div class="small-label">STEP TWO</div>
            <h2>check the details</h2>
          </div>
          <span class="badge">ready to save</span>
        </div>
        <p class="subtitle">Choose an option if we found more than one, then make any little edits before saving.</p>
        <p id="timezone-warning" class="message warning" hidden></p>
        <div id="candidates"></div>
        <div class="save-row">
          <button id="save-button" type="button">♡ save this event</button>
          <p id="save-message" class="message" hidden></p>
        </div>
      </section>
    </div>
  </main>
  <script>
    const form = document.querySelector("#upload-form");
    const fileInput = document.querySelector("#screenshot");
    const preview = document.querySelector("#preview");
    const results = document.querySelector("#results");
    const candidates = document.querySelector("#candidates");
    const uploadMessage = document.querySelector("#upload-message");
    const saveMessage = document.querySelector("#save-message");
    const timezoneWarning = document.querySelector("#timezone-warning");
    const extractButton = document.querySelector("#extract-button");
    const saveButton = document.querySelector("#save-button");
    let extractedCandidates = [];

    function showMessage(element, text, isError = false) {
      element.textContent = text;
      element.classList.toggle("error", isError);
      element.hidden = !text;
    }

    function escapeHtml(value) {
      return String(value || "").replace(/[&<>"']/g, (character) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
      })[character]);
    }

    fileInput.addEventListener("change", () => {
      const file = fileInput.files[0];
      if (!file) {
        preview.hidden = true;
        return;
      }
      preview.src = URL.createObjectURL(file);
      preview.hidden = false;
    });

    function renderCandidates() {
      candidates.innerHTML = extractedCandidates.map((event, index) => `
        <div class="candidate">
          <div class="candidate-title">
            <input id="candidate-${index}" type="radio" name="candidate" value="${index}" ${index === 0 ? "checked" : ""}>
            <label for="candidate-${index}">Candidate ${index + 1}</label>
          </div>
          <div class="field-grid">
            <div class="field-wide">
              <label for="name-${index}">Event name</label>
              <input id="name-${index}" data-field="name" data-index="${index}" type="text" value="${escapeHtml(event.name)}" required>
            </div>
            <div>
              <label for="date-${index}">Date</label>
              <input id="date-${index}" data-field="date" data-index="${index}" type="date" value="${escapeHtml(event.date)}" required>
            </div>
            <div>
              <label for="time-${index}">Start time</label>
              <input id="time-${index}" data-field="time" data-index="${index}" type="time" value="${escapeHtml(event.time)}" required>
            </div>
            <div class="field-wide">
              <label for="timezone-${index}">Timezone</label>
              <input id="timezone-${index}" data-field="timezone" data-index="${index}" type="text" value="${escapeHtml(event.timezone || "Europe/London")}" required>
            </div>
          </div>
        </div>
      `).join("");
      results.hidden = false;
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      showMessage(uploadMessage, "");
      showMessage(saveMessage, "");
      results.hidden = true;
      extractButton.disabled = true;
      const formData = new FormData(form);
      try {
        const response = await fetch("/api/extract", { method: "POST", body: formData });
        const body = await response.json();
        if (!response.ok) throw new Error(body.error || "Extraction failed.");
        extractedCandidates = body.candidates;
        renderCandidates();
        const assumed = extractedCandidates.some((candidate) => candidate.timezone_assumed);
        timezoneWarning.textContent = assumed
          ? "The timezone was not shown in the screenshot, so Europe/London was assumed. Check it before saving."
          : "";
        timezoneWarning.hidden = !assumed;
      } catch (error) {
        showMessage(uploadMessage, error.message, true);
      } finally {
        extractButton.disabled = false;
      }
    });

    candidates.addEventListener("input", (event) => {
      const field = event.target.dataset.field;
      const index = Number(event.target.dataset.index);
      if (field && extractedCandidates[index]) extractedCandidates[index][field] = event.target.value;
    });

    saveButton.addEventListener("click", async () => {
      const selected = document.querySelector("input[name=candidate]:checked");
      if (!selected) return;
      const event = extractedCandidates[Number(selected.value)];
      saveButton.disabled = true;
      showMessage(saveMessage, "");
      try {
        const response = await fetch("/api/events", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(event)
        });
        const body = await response.json();
        if (!response.ok) throw new Error(body.error || "Could not save event.");
        showMessage(saveMessage, "Event saved. Opening your calendar…");
        window.setTimeout(() => {
          window.location.href = "/calendar";
        }, 500);
      } catch (error) {
        showMessage(saveMessage, error.message, true);
      } finally {
        saveButton.disabled = false;
      }
    });
  </script>
</body>
</html>
"""


def database_url():
    value = os.environ.get("DATABASE_URL")
    if not value:
        raise RuntimeError("DATABASE_URL is not configured.")
    return value


def ensure_schema():
    with psycopg.connect(database_url()) as connection:
        connection.execute(SCHEMA)


def parse_gemini_response(text):
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise RuntimeError("Gemini returned invalid event data.") from error
    if not isinstance(result, dict) or not isinstance(result.get("candidates"), list):
        raise RuntimeError("Gemini returned an invalid candidate list.")
    return result["candidates"]


def normalise_candidates(candidates):
    if not candidates:
        raise RuntimeError("No event could be found in the screenshot.")
    normalised = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        timezone = candidate.get("timezone")
        timezone_is_present = isinstance(timezone, str) and bool(timezone.strip())
        item = {
            "name": candidate.get("name") if isinstance(candidate.get("name"), str) else "",
            "date": candidate.get("date") if isinstance(candidate.get("date"), str) else "",
            "time": candidate.get("time") if isinstance(candidate.get("time"), str) else "",
            "timezone": timezone.strip() if timezone_is_present else DEFAULT_TIMEZONE,
            "timezone_assumed": not timezone_is_present,
        }
        if item["date"]:
            try:
                date.fromisoformat(item["date"])
            except ValueError:
                item["date"] = ""
        if item["time"]:
            try:
                datetime.strptime(item["time"], "%H:%M")
            except ValueError:
                item["time"] = ""
        normalised.append(item)
    if not normalised:
        raise RuntimeError("No usable event details were found in the screenshot.")
    return normalised


def extract_events(image_path):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")
    client = genai.Client(api_key=api_key)
    uploaded = client.files.upload(file=str(image_path))
    prompt = f"""
Extract event details from this social media screenshot. The current date is {date.today().isoformat()}.
Return ONLY valid JSON in this exact shape:
{{"candidates":[{{"name":"string or null","date":"YYYY-MM-DD or null","time":"HH:MM in 24-hour time or null","timezone":"IANA timezone or null"}}]}}
Return one candidate for each distinct event visible, with the most likely event first.
Use the event start time, not doors-open or end time. Do not guess missing values.
Interpret relative dates only when the screenshot provides enough context. A date without a year may use the next upcoming occurrence.
The timezone must be null unless explicitly shown or unambiguously indicated.
"""
    response = client.models.generate_content(
        model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
        contents=[uploaded, prompt],
    )
    return normalise_candidates(parse_gemini_response(response.text))


def validate_event(body):
    if not isinstance(body, dict):
        raise ValueError("Event data is required.")
    name = body.get("name", "").strip()
    timezone = body.get("timezone", "").strip()
    if not name or not timezone:
        raise ValueError("Event name and timezone are required.")
    try:
        event_date = date.fromisoformat(body.get("date", ""))
        event_time = datetime.strptime(body.get("time", ""), "%H:%M").time()
    except (TypeError, ValueError) as error:
        raise ValueError("Enter a valid date and start time.") from error
    return name, event_date, event_time, timezone


def logged_in_user():
    user_id = session.get("user_id")
    return DEMO_USERS.get(user_id)


def require_login():
    if not logged_in_user():
        return jsonify(error="Please log in first."), 401
    return None


@app.get("/assets/<path:filename>")
def asset(filename):
    if filename not in ASSETS:
        return jsonify(error="Asset not found."), 404
    return send_from_directory(ROOT, filename)


@app.get("/")
def index():
    return send_from_directory(ROOT, "index.html")


@app.get("/login")
def login_page():
    return send_from_directory(ROOT, "login.html")


@app.get("/add-event")
def add_event_page():
    if not logged_in_user():
        return redirect("/login")
    return render_template_string(PAGE)


@app.get("/calendar")
def calendar_page():
    if not logged_in_user():
        return redirect("/login")
    return send_from_directory(ROOT, "calendar.html")


@app.get("/api/session")
def current_session():
    return jsonify(user=logged_in_user())


@app.post("/api/login")
def login():
    body = request.get_json(silent=True) or {}
    user = DEMO_USERS.get(body.get("user_id"))
    if not user:
        return jsonify(error="Choose Alex or Sam to continue."), 400
    session["user_id"] = user["id"]
    return jsonify(user=user)


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@app.post("/api/extract")
def extract():
    error = require_login()
    if error:
        return error
    upload = request.files.get("screenshot")
    if not upload or not upload.filename:
        return jsonify(error="Choose a PNG screenshot."), 400
    if upload.mimetype != "image/png":
        return jsonify(error="Only PNG screenshots are supported."), 400
    try:
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "screenshot.png"
            upload.save(image_path)
            candidates = extract_events(image_path)
        return jsonify(candidates=candidates)
    except Exception as error:
        app.logger.exception("Screenshot extraction failed")
        return jsonify(error=f"Could not extract event details: {error}"), 422


@app.get("/api/events")
def events():
    error = require_login()
    if error:
        return error
    try:
        ensure_schema()
        with psycopg.connect(database_url()) as connection:
            rows = connection.execute(
                "SELECT name, event_date, event_time, timezone "
                "FROM events ORDER BY event_date, event_time"
            ).fetchall()
        return jsonify(events=[
            {
                "name": row[0],
                "date": row[1].isoformat(),
                "time": row[2].strftime("%H:%M"),
                "timezone": row[3],
            }
            for row in rows
        ])
    except Exception:
        app.logger.exception("Event listing failed")
        return jsonify(error="The database is unavailable."), 503


@app.post("/api/events")
def save_event():
    error = require_login()
    if error:
        return error
    try:
        name, event_date, event_time, timezone = validate_event(request.get_json(silent=True))
        ensure_schema()
        with psycopg.connect(database_url()) as connection:
            connection.execute(
                "INSERT INTO events (name, event_date, event_time, timezone) VALUES (%s, %s, %s, %s)",
                (name, event_date, event_time, timezone),
            )
    except ValueError as error:
        return jsonify(error=str(error)), 400
    except psycopg.errors.UniqueViolation:
        return jsonify(error="This event is already saved."), 409
    except Exception:
        app.logger.exception("Event save failed")
        return jsonify(error="The database is unavailable."), 503
    return jsonify(ok=True), 201


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")