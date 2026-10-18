# IKU


Imperial Kings UCL Women in STEM Hackathon

Team: Anjika, Farah, Freya

Local demo that extracts event details from a public Instagram reel with Gemini
and stores confirmed events in Tiger Cloud PostgreSQL.

## Run locally

1. Create a virtual environment and install dependencies:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and set `GEMINI_API_KEY`, `DATABASE_URL`, and
   `FLASK_SECRET_KEY`. Do not commit `.env`.

3. Start the server:

   ```powershell
   python -m flask --app real_app run
   ```

4. Open http://127.0.0.1:5000.

The demo login accepts any valid email and non-empty password. It is not a
production authentication system. The database table is created on first login.
Public, downloadable Instagram posts or reels and a working `yt-dlp`
installation are required for extraction. Gemini must find a clear event name,
date, and start time; incomplete results are not saved.
