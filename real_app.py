import json
import os
import re
import tempfile
from datetime import date, datetime
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template_string, request
from google import genai

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
DEFAULT_TIMEZONE = "Europe/London"

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
  <title>Event screenshot extractor</title>
  <style>
    :root { font-family: system-ui, sans-serif; color: #242428; background: #f2efe7; }
    body { margin: 0; }
    main { width: min(680px, calc(100% - 32px)); margin: 48px auto; }
    h1 { margin-bottom: 8px; }
    p { line-height: 1.5; }
    section { background: white; border: 1px solid #d7d1c5; border-radius: 12px; padding: 24px; margin-top: 20px; }
    label { display: block; font-weight: 650; margin: 14px 0 6px; }
    input, button { font: inherit; }
    input[type=file], input[type=text], input[type=date], input[type=time] { width: 100%; padding: 10px; border: 1px solid #bdb7ad; border-radius: 6px; box-sizing: border-box; }
    button { margin-top: 16px; padding: 10px 16px; border: 0; border-radius: 6px; background: #aec9c4; cursor: pointer; }
    button:disabled { opacity: .55; cursor: wait; }
    .preview { max-width: 100%; max-height: 320px; margin-top: 16px; border-radius: 6px; }
    .candidate { border-top: 1px solid #e2ded7; padding-top: 16px; margin-top: 16px; }
    .candidate:first-child { border-top: 0; padding-top: 0; margin-top: 0; }
    .message { padding: 12px; border-radius: 6px; background: #f7f3e9; }
    .error { background: #f9e4de; color: #7c2d1d; }
    .warning { background: #fff3c4; }
    [hidden] { display: none; }
  </style>
</head>
<body>
  <main>
    <h1>Extract an event</h1>
    <p>Upload a PNG screenshot of an event post. Review the extracted details before saving.</p>

    <section>
      <form id="upload-form">
        <label for="screenshot">PNG screenshot</label>
        <input id="screenshot" name="screenshot" type="file" accept="image/png" required>
        <img id="preview" class="preview" alt="Screenshot preview" hidden>
        <button id="extract-button" type="submit">Extract details</button>
      </form>
      <p id="upload-message" class="message" hidden></p>
    </section>

    <section id="results" hidden>
      <h2>Review details</h2>
      <p id="timezone-warning" class="message warning" hidden></p>
      <div id="candidates"></div>
      <button id="save-button" type="button">Save selected event</button>
      <p id="save-message" class="message" hidden></p>
    </section>
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
          <label><input type="radio" name="candidate" value="${index}" ${index === 0 ? "checked" : ""}> Candidate ${index + 1}</label>
          <label for="name-${index}">Event name</label>
          <input id="name-${index}" data-field="name" data-index="${index}" type="text" value="${escapeHtml(event.name)}" required>
          <label for="date-${index}">Date</label>
          <input id="date-${index}" data-field="date" data-index="${index}" type="date" value="${escapeHtml(event.date)}" required>
          <label for="time-${index}">Start time</label>
          <input id="time-${index}" data-field="time" data-index="${index}" type="time" value="${escapeHtml(event.time)}" required>
          <label for="timezone-${index}">Timezone</label>
          <input id="timezone-${index}" data-field="timezone" data-index="${index}" type="text" value="${escapeHtml(event.timezone || "Europe/London")}" required>
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
        showMessage(saveMessage, "Event saved.");
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


@app.get("/")
def index():
    return render_template_string(PAGE)


@app.post("/api/extract")
def extract():
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


@app.post("/api/events")
def save_event():
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