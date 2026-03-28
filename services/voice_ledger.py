import importlib
import json
import logging
import mimetypes
import os
import subprocess
import tempfile
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import requests
from pydantic import BaseModel, Field, ValidationError

from services.settings import get_settings
from supabase_config import get_supabase

logger = logging.getLogger(__name__)

FALLBACK_RESPONSE = "Samajh nahi aaya, dobara boliye 🙏"
MISSING_AUDIO_RESPONSE = "Voice note nahi mila. Kripya dobara bhejiye."
NON_AUDIO_RESPONSE = "Yeh audio message nahi hai. Kripya voice note bhejiye."

GROQ_CHAT_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_TRANSCRIPTIONS_URL = "https://api.groq.com/openai/v1/audio/transcriptions"

SUPPORTED_AUDIO_EXTENSIONS = (
    ".ogg",
    ".oga",
    ".opus",
    ".mp3",
    ".m4a",
    ".wav",
    ".amr",
    ".aac",
    ".webm",
)


class ExtractedEntry(BaseModel):
    intent: Literal["ADD_ENTRY"]
    amount: float = Field(gt=0)
    type: Literal["income", "expense"]
    category: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)


class ExtractedEntries(BaseModel):
    entries: List[ExtractedEntry]


def _normalize_whatsapp_number(value: str) -> str:
    number = value.strip()
    if number.startswith("whatsapp:"):
        return number
    return f"whatsapp:{number}"


def _format_inr(value: float) -> str:
    rounded = round(float(value), 2)
    if rounded.is_integer():
        return f"₹{int(rounded)}"
    return f"₹{rounded:.2f}"


def _safe_json_load(raw_content: str) -> Dict[str, Any]:
    cleaned = raw_content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    return json.loads(cleaned.strip())


def _guess_extension(content_type: str, media_url: str) -> str:
    parsed_content_type = (content_type or "").split(";", maxsplit=1)[0].strip().lower()
    if parsed_content_type:
        extension = mimetypes.guess_extension(parsed_content_type)
        if extension:
            return extension

    media_path = media_url.split("?", maxsplit=1)[0].lower()
    for extension in SUPPORTED_AUDIO_EXTENSIONS:
        if media_path.endswith(extension):
            return extension

    return ".bin"


def is_audio_message(media_content_type: str, media_url: str) -> bool:
    lowered = (media_content_type or "").lower()
    if "audio/" in lowered or "application/ogg" in lowered:
        return True

    media_path = (media_url or "").split("?", maxsplit=1)[0].lower()
    return media_path.endswith(SUPPORTED_AUDIO_EXTENSIONS)


def download_audio(media_url: str, destination_dir: Path) -> Path:
    settings = get_settings()
    destination_dir.mkdir(parents=True, exist_ok=True)

    response = requests.get(
        media_url,
        auth=(settings.twilio_account_sid, settings.twilio_auth_token),
        timeout=45,
    )

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise RuntimeError(f"Unable to download Twilio media: {exc}") from exc

    extension = _guess_extension(response.headers.get("Content-Type", ""), media_url)
    audio_path = destination_dir / f"incoming{extension}"
    audio_path.write_bytes(response.content)
    return audio_path


def convert_audio(input_audio: Path, destination_dir: Path) -> Path:
    settings = get_settings()
    destination_dir.mkdir(parents=True, exist_ok=True)

    output_audio = destination_dir / "normalized.mp3"
    command = [
        settings.ffmpeg_binary,
        "-y",
        "-i",
        str(input_audio),
        "-ac",
        "1",
        "-ar",
        "16000",
        str(output_audio),
    ]

    try:
        process = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("ffmpeg binary not found. Install ffmpeg before running webhook flow.") from exc

    if process.returncode != 0:
        stderr_tail = process.stderr.strip().splitlines()[-5:]
        raise RuntimeError("ffmpeg conversion failed: " + " | ".join(stderr_tail))

    if not output_audio.exists():
        raise RuntimeError("ffmpeg conversion failed: output file not generated")

    return output_audio


# ---------------------------------------------------------------------------
# Local Whisper model (lazy-loaded, cached)
# ---------------------------------------------------------------------------
_whisper_model = None
_whisper_model_name = None


def _get_whisper_model():
    """Load the local Whisper model once and cache it."""
    global _whisper_model, _whisper_model_name
    import whisper as openai_whisper

    # Use large-v3 for best Hindi/Marathi accuracy (you have it downloaded at ~/.cache/whisper/)
    model_name = os.environ.get("WHISPER_LOCAL_MODEL", "large-v3")
    if _whisper_model is None or _whisper_model_name != model_name:
        logger.info("Loading local Whisper model: %s (this may take a moment)...", model_name)
        _whisper_model = openai_whisper.load_model(model_name)
        _whisper_model_name = model_name
        logger.info("Whisper model '%s' loaded successfully.", model_name)
    return _whisper_model


def transcribe_audio(audio_path: Path) -> Dict[str, str]:
    """Transcribe audio using the LOCAL Whisper model (not Groq cloud)."""
    model = _get_whisper_model()
    logger.info("Transcribing with local Whisper (%s): %s", _whisper_model_name, audio_path.name)

    result = model.transcribe(
        str(audio_path),
        language="hi",       # Force Hindi — prevents misdetecting as English
        task="transcribe",
        fp16=False,          # CPU doesn't support FP16
        initial_prompt="Hindi, Marathi, Hinglish mein business transaction. Chai bechi 500 rupay, doodh pe 200 kharch.",
    )

    text = (result.get("text") or "").strip()
    language = (result.get("language") or "hi").strip().lower()
    logger.info("Local Whisper result — lang: %s, text: %s", language, text[:200])
    return {"text": text, "language": language}


def extract_json(transcript: str) -> Optional[List[Dict[str, Any]]]:
    settings = get_settings()

    system_prompt = (
        "You are a strict JSON extraction service for a small-business ledger. "
        "User audio transcripts can be Hindi, Marathi, Hinglish, or mixed language. "
        "Extract ALL transactions mentioned and return a JSON object with one key: 'entries' "
        "which is a list of transaction objects. "
        "Each object must have keys: intent, amount, type, category, description. "
        "intent must always be ADD_ENTRY. amount must be a positive number. "
        "type must be 'income' or 'expense'. category should be concise lowercase text (e.g. chai, milk, rice). "
        "IMPORTANT: If both income and expense are mentioned, create SEPARATE entries for each — do NOT merge them. "
        "Example: '500 ki chai bechi, doodh pe 200 kharch' → two entries: income 500 chai, expense 200 milk."
    )

    payload: Dict[str, Any] = {
        "model": settings.groq_llm_model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": "Transcript: " + transcript,
            },
        ],
    }

    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }

    response = requests.post(
        GROQ_CHAT_COMPLETIONS_URL,
        headers=headers,
        json=payload,
        timeout=60,
    )

    # Some models may reject strict response_format. Retry once without it.
    if response.status_code == 400 and "response_format" in response.text:
        payload.pop("response_format", None)
        response = requests.post(
            GROQ_CHAT_COMPLETIONS_URL,
            headers=headers,
            json=payload,
            timeout=60,
        )

    if response.status_code >= 400:
        logger.warning("Groq extraction call failed: %s", response.text)
        return None

    try:
        content = (
            response.json()
            .get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        parsed_payload = _safe_json_load(content)
        # Support both {"entries": [...]} and a bare single-object response
        if "entries" in parsed_payload and isinstance(parsed_payload["entries"], list):
            raw_list = parsed_payload["entries"]
        elif "intent" in parsed_payload:
            raw_list = [parsed_payload]
        else:
            logger.warning("Unexpected Groq extraction shape: %s", parsed_payload)
            return None

        results = []
        for item in raw_list:
            try:
                validated = ExtractedEntry.model_validate(item)
                results.append(validated.model_dump())
            except (ValidationError, ValueError) as exc:
                logger.warning("Skipping invalid entry from Groq: %s — %s", item, exc)
        return results if results else None
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        logger.warning("Groq extraction parse/validation failed: %s", exc)
        return None


def _calculate_current_profit(phone: str) -> float:
    supabase = get_supabase()
    result = (
        supabase.table("ledger")
        .select("amount,type")
        .eq("phone", phone)
        .execute()
    )

    profit = 0.0
    for row in result.data or []:
        try:
            amount = float(row.get("amount") or 0)
        except (TypeError, ValueError):
            amount = 0.0

        entry_type = (row.get("type") or "").lower()
        if entry_type == "income":
            profit += amount
        elif entry_type == "expense":
            profit -= amount

    return profit


def save_to_db(phone: str, extracted_data: Dict[str, Any], audio_url: str) -> Dict[str, Any]:
    """Save a single extracted entry. extracted_data is a single entry dict."""
    supabase = get_supabase()

    record = {
        "phone": phone,
        "amount": float(extracted_data["amount"]),
        "type": extracted_data["type"],
        "category": extracted_data["category"],
        "description": extracted_data["description"],
        "audio_url": audio_url,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    insert_result = supabase.table("ledger").insert(record).execute()
    inserted = (insert_result.data or [record])[0]
    current_profit = _calculate_current_profit(phone)
    return {"entry": inserted, "current_profit": current_profit}


def send_whatsapp_reply(to_phone: str, body: str, media_url: Optional[str] = None) -> str:
    settings = get_settings()

    try:
        client_class = getattr(importlib.import_module("twilio.rest"), "Client")
    except ModuleNotFoundError as exc:
        raise RuntimeError("twilio package is required for WhatsApp replies") from exc

    client = client_class(settings.twilio_account_sid, settings.twilio_auth_token)
    from_number = _normalize_whatsapp_number(settings.twilio_whatsapp_number)
    recipient = _normalize_whatsapp_number(to_phone)

    payload: Dict[str, Any] = {
        "from_": from_number,
        "to": recipient,
        "body": body,
    }
    if media_url:
        payload["media_url"] = [media_url]

    try:
        message = client.messages.create(**payload)
    except Exception as exc:
        raise RuntimeError(f"Twilio send failed: {exc}") from exc

    return message.sid


def process_voice_message(phone: str, media_url: str) -> str:
    with tempfile.TemporaryDirectory(prefix="vyapaarsaathi-wa-") as tmp_dir:
        working_dir = Path(tmp_dir)
        raw_audio = download_audio(media_url, working_dir)
        mp3_audio = convert_audio(raw_audio, working_dir)
        transcript_payload = transcribe_audio(mp3_audio)

    transcript = transcript_payload.get("text", "").strip()
    if not transcript:
        return FALLBACK_RESPONSE

    extracted = extract_json(transcript)
    if not extracted:
        return FALLBACK_RESPONSE

    total_income = 0.0
    total_expense = 0.0
    parts = []
    current_profit = 0.0

    for entry_data in extracted:
        saved = save_to_db(phone=phone, extracted_data=entry_data, audio_url=media_url)
        current_profit = float(saved["current_profit"])
        amount = float(entry_data["amount"])
        entry_type = entry_data["type"]
        category = entry_data.get("category", "")
        if entry_type == "income":
            total_income += amount
            parts.append(f"Income {_format_inr(amount)} ({category})")
        else:
            total_expense += amount
            parts.append(f"Expense {_format_inr(amount)} ({category})")

    summary = ", ".join(parts)
    return (
        f"✅ {summary} saved. "
        f"Current profit: {_format_inr(current_profit)}"
    )


def _build_weekly_summary_message(total_income: float, total_expense: float) -> str:
    net_profit = total_income - total_expense
    return (
        "Weekly summary:\n"
        f"Income: {_format_inr(total_income)}\n"
        f"Expense: {_format_inr(total_expense)}\n"
        f"Net: {_format_inr(net_profit)}"
    )


def _generate_tts_file(summary_text: str, destination_dir: Path) -> Optional[Path]:
    try:
        gtts_class = getattr(importlib.import_module("gtts"), "gTTS")
    except ImportError:
        logger.info("gTTS not installed. Sending text-only weekly summary.")
        return None

    destination_dir.mkdir(parents=True, exist_ok=True)
    output_path = destination_dir / "weekly_summary.mp3"
    try:
        tts = gtts_class(text=summary_text, lang="hi")
        tts.save(str(output_path))
    except Exception as exc:  # pragma: no cover - external dependency path
        logger.warning("TTS generation failed: %s", exc)
        return None

    return output_path


def _upload_weekly_audio(tts_path: Path, phone: str) -> Optional[str]:
    supabase = get_supabase()
    safe_phone = phone.replace("whatsapp:", "").replace("+", "")
    storage_path = f"{safe_phone}/{uuid.uuid4()}.mp3"

    try:
        with tts_path.open("rb") as source:
            supabase.storage.from_("weekly_summaries").upload(
                storage_path,
                source.read(),
                {"content-type": "audio/mpeg"},
            )
        return supabase.storage.from_("weekly_summaries").get_public_url(storage_path)
    except Exception as exc:  # pragma: no cover - network/storage path
        logger.warning("Weekly summary upload failed: %s", exc)
        return None


def run_weekly_summary_job() -> int:
    settings = get_settings()
    supabase = get_supabase()

    start_time = datetime.now(timezone.utc) - timedelta(days=7)
    result = (
        supabase.table("ledger")
        .select("phone,amount,type")
        .gte("created_at", start_time.isoformat())
        .execute()
    )

    aggregates: Dict[str, Dict[str, float]] = defaultdict(lambda: {"income": 0.0, "expense": 0.0})
    for row in result.data or []:
        phone = row.get("phone")
        if not phone:
            continue
        try:
            amount = float(row.get("amount") or 0)
        except (TypeError, ValueError):
            amount = 0.0
        row_type = (row.get("type") or "").lower()
        if row_type in {"income", "expense"}:
            aggregates[phone][row_type] += amount

    sent_count = 0
    for phone, values in aggregates.items():
        summary_text = _build_weekly_summary_message(values["income"], values["expense"])
        media_url: Optional[str] = None

        if settings.enable_weekly_summary_tts:
            with tempfile.TemporaryDirectory(prefix="vyapaarsaathi-weekly-") as tmp_dir:
                tts_file = _generate_tts_file(summary_text, Path(tmp_dir))
                if tts_file:
                    media_url = _upload_weekly_audio(tts_file, phone)

        try:
            send_whatsapp_reply(phone, summary_text, media_url=media_url)
            sent_count += 1
        except Exception as exc:  # pragma: no cover - external API path
            logger.warning("Weekly summary send failed for %s: %s", phone, exc)

    return sent_count


__all__ = [
    "FALLBACK_RESPONSE",
    "MISSING_AUDIO_RESPONSE",
    "NON_AUDIO_RESPONSE",
    "download_audio",
    "convert_audio",
    "transcribe_audio",
    "extract_json",
    "save_to_db",
    "send_whatsapp_reply",
    "is_audio_message",
    "process_voice_message",
    "run_weekly_summary_job",
]
