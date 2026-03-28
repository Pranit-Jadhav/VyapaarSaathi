# VyapaarSaathi

Production-ready FastAPI backend for a WhatsApp-based voice ledger using Twilio WhatsApp API, Groq Whisper, Groq Llama 3 extraction, and Supabase.

## What This Backend Does

- Receives WhatsApp webhook events from Twilio at `POST /webhook`.
- Validates Twilio signatures for security.
- Downloads incoming audio from Twilio media URL using Twilio auth.
- Converts audio to MP3 using `ffmpeg`.
- Transcribes Hindi, Marathi, and Hinglish using Whisper via Groq API.
- Extracts structured ledger JSON with Llama 3.
- Saves entries to Supabase `ledger` table.
- Sends WhatsApp reply back to user using Twilio API.
- Optionally runs weekly summary cron with APScheduler.

## Environment Variables

Copy `.env.example` to `.env` and fill values:

```bash
cp .env.example .env
```

Required:

- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_WHATSAPP_NUMBER`
- `GROQ_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_KEY`

Optional:

- `GROQ_LLM_MODEL` (default: `llama-3.3-70b-versatile`)
- `GROQ_WHISPER_MODEL` (default: `whisper-large-v3-turbo`)
- `FFMPEG_BINARY` (default: `ffmpeg`)
- `TWILIO_VALIDATE_SIGNATURE` (default: `true`)
- `ENABLE_WEEKLY_SUMMARY` (default: `false`)
- `ENABLE_WEEKLY_SUMMARY_TTS` (default: `false`)

## Local Setup

1. Create virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Install ffmpeg (required for audio conversion):

```bash
brew install ffmpeg
```

3. Run database schema updates in Supabase SQL editor using `db/schema.sql`.

4. Start API server:

```bash
uvicorn main:app --reload --port 8000
```

## Twilio + ngrok Testing (Local Only)

1. Expose local API:

```bash
ngrok http 8000
```

2. Copy HTTPS URL from ngrok, for example:

`https://abc123.ngrok-free.app`

3. In Twilio WhatsApp sandbox, set webhook URL to:

`https://abc123.ngrok-free.app/webhook`

4. Send a WhatsApp voice note to sandbox number.

## Webhook Input Format

Twilio sends `application/x-www-form-urlencoded` fields. Backend reads:

- `From`
- `NumMedia`
- `MediaUrl0`
- `MediaContentType0`

## API Endpoints

- `GET /` basic service metadata
- `GET /health` runtime health + missing env list
- `POST /webhook` Twilio WhatsApp webhook receiver

## Response Behavior

- Extraction failure fallback: `Samajh nahi aaya, dobara boliye 🙏`
- Missing audio: asks user to resend voice note
- Non-audio media: asks user to send audio message
- Success: confirms saved entry and current profit

## Realtime Updates for Frontend Dashboard

`db/schema.sql` includes:

- `ledger` table
- index for `phone, created_at`
- `ALTER PUBLICATION supabase_realtime ADD TABLE ledger`

This enables live updates in Supabase realtime subscribers.
