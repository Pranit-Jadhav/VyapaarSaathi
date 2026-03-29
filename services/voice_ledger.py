import importlib
import json
import logging
import mimetypes
import os
import subprocess
import tempfile
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import requests
from pydantic import BaseModel, Field, ValidationError, model_validator

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
    intent: Literal["ADD_ENTRY", "STOCK_UPDATE", "PRICE_UPDATE", "GET_REPORT"] = "ADD_ENTRY"
    # ADD_ENTRY fields (required for ADD_ENTRY, ignored for others)
    amount: Optional[float] = Field(default=None)
    type: Optional[Literal["income", "expense"]] = Field(default=None)
    category: Optional[str] = Field(default="report", max_length=100)
    description: Optional[str] = Field(default="", max_length=500)
    # Quantity — extracted from voice for ADD_ENTRY, required for STOCK_UPDATE
    quantity: Optional[float] = Field(default=None)
    # Price — used by PRICE_UPDATE
    price_per_unit: Optional[float] = Field(default=None)

    @model_validator(mode="after")
    def check_intent_fields(self):
        if self.intent == "ADD_ENTRY":
            # If vendor says "10 samosa bech diya" → quantity present, amount missing.
            # We allow this — amount will be computed from inventory price later.
            if self.quantity is not None and self.quantity > 0 and (self.amount is None or self.amount <= 0):
                self.amount = 0  # Placeholder — will be filled from price_per_unit × qty
            # Fix type: sell/bech = income, not expense. LLM sometimes gets this wrong.
            desc = (self.description or "").lower() + " " + (self.category or "").lower()
            sell_words = ["bech", "sell", "sold", "bechi", "बेच", "बेची", "bej", "बेज"]
            if any(w in desc for w in sell_words):
                self.type = "income"
            if self.type is None:
                self.type = "income"  # Default to income for sales

        elif self.intent == "STOCK_UPDATE":
            if self.quantity is None or self.quantity <= 0:
                raise ValueError("STOCK_UPDATE requires quantity > 0")
        elif self.intent == "PRICE_UPDATE":
            if self.price_per_unit is None or self.price_per_unit <= 0:
                raise ValueError("PRICE_UPDATE requires price_per_unit > 0")
        elif self.intent == "GET_REPORT":
            # No extra validation needed — just a request
            pass
        return self



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
        "Extract ALL commands and return JSON: {'entries': [...]}\n\n"

        "=== intent: ADD_ENTRY (vendor sold or spent money) ===\n"
        "Keys: intent, amount, type, category, description, quantity.\n"
        "RULES:\n"
        "- 'bech', 'bechi', 'bej', 'sell', 'sold', 'diya' = type:'income' (NEVER expense).\n"
        "- 'kharcha', 'kharch', 'liya', 'buy', 'bought', 'spent' = type:'expense'.\n"
        "- amount: the RUPEE number. If only quantity is said (no rupees), set amount to null.\n"
        "- quantity: the COUNT of units sold/bought. Extract if mentioned, else null.\n"
        "- category: concise lowercase item name (chai, samosa, milk, pav bhaji).\n"
        "EXAMPLES:\n"
        "  '100 rupay ke pav bhaji bech diya' → amount:100, type:'income', category:'pav bhaji', quantity:null\n"
        "  '10 samosa bej diya' → amount:null, type:'income', category:'samosa', quantity:10\n"
        "  '40 chai bechi 400 mein' → amount:400, type:'income', category:'chai', quantity:40\n"
        "  'doodh pe 200 kharch' → amount:200, type:'expense', category:'milk', quantity:null\n"
        "  '20 vadapav aur 30 samosa bech diya' → TWO entries, both income\n\n"

        "=== intent: STOCK_UPDATE (vendor sets/restocks inventory) ===\n"
        "Use ONLY when vendor says they are PREPARING/RESTOCKING, NOT selling.\n"
        "Keys: intent, category, quantity. (No amount, no type.)\n"
        "Examples: 'chai ka stock 100', 'maine 80 samosa banaya', 'aaj 60 vada pav rakha'\n\n"

        "=== intent: PRICE_UPDATE (vendor changes price of an item) ===\n"
        "Use ONLY when vendor mentions a NEW rate/price, NOT a sale.\n"
        "Keys: intent, category, price_per_unit. (No amount, no type.)\n"
        "Examples: 'chai ka rate 12 rupay', 'samosa ab 20 ka'\n\n"

        "=== intent: GET_REPORT (vendor asks for their record/report) ===\n"
        "Use when vendor asks for their report, record, hisaab, statement.\n"
        "Keys: intent (only). Set category to 'report'.\n"
        "Examples: 'mera record do', 'mujhe mera hisaab do', 'give me my report', "
        "'mera record bhejo', 'weekly report do', 'mera hisaab kitab bhejo'\n\n"

        "Return ONLY valid JSON. No explanation.\n"
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


def save_to_db(phone: str, extracted_data: Dict[str, Any], audio_url: str, catalog_phone: str = "") -> Dict[str, Any]:
    """Save a single extracted entry. extracted_data is a single entry dict.
    catalog_phone: the phone key used for inventory lookups (defaults to phone if not given).
    Pass 'web-client' to make WhatsApp entries use the shared web-client catalog."""
    supabase = get_supabase()
    # Use catalog_phone for inventory if provided, else fall back to phone
    inv_phone = catalog_phone if catalog_phone else phone

    # Extract quantity if provided (may be None / missing)
    raw_qty = extracted_data.get("quantity")
    quantity: Optional[float] = None
    if raw_qty is not None:
        try:
            quantity = float(raw_qty)
            if quantity <= 0:
                quantity = None
        except (TypeError, ValueError):
            quantity = None

    # Compute amount from inventory price if vendor only said quantity, no ₹ amount
    raw_amount = extracted_data.get("amount") or 0
    try:
        amount = float(raw_amount)
    except (TypeError, ValueError):
        amount = 0.0

    if amount <= 0 and quantity is not None and quantity > 0:
        # Look up price from inventory
        try:
            from services.inventory import get_inventory
            inv_items = get_inventory(inv_phone)
            cat_lower = str(extracted_data.get("category") or "").strip().lower()
            for inv_item in inv_items:
                if inv_item.get("item_name") == cat_lower:
                    price = float(inv_item.get("price_per_unit") or 0)
                    if price > 0:
                        amount = quantity * price
                        logger.info("Computed amount ₹%.2f from qty=%g × price=₹%.2f for '%s'",
                                    amount, quantity, price, cat_lower)
                    break
        except Exception as price_exc:
            logger.warning("Price lookup failed: %s", price_exc)

        # If still 0, set amount = quantity (placeholder to prevent DB constraint violation)
        if amount <= 0:
            amount = quantity
            logger.info("No price found for '%s', using amount=quantity=%g", extracted_data.get("category"), quantity)

    record = {
        "phone": phone,
        "amount": amount,
        "type": extracted_data.get("type") or "income",
        "category": extracted_data.get("category") or "general",
        "description": extracted_data.get("description") or extracted_data.get("category") or "",
        "audio_url": audio_url,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if quantity is not None:
        record["quantity"] = quantity


    insert_result = supabase.table("ledger").insert(record).execute()
    inserted = (insert_result.data or [record])[0]
    current_profit = _calculate_current_profit(phone)

    # Auto-deduct from inventory for ALL income entries
    # If quantity is known, use it directly. If only amount, compute qty from price.
    stockout_info = None
    if record.get("type") == "income":
        deduct_qty = quantity  # may be None
        category = (extracted_data.get("category") or "").lower().strip()

        # If no quantity but we have amount, compute from inventory price
        if deduct_qty is None and amount > 0 and category:
            try:
                from services.inventory import get_inventory
                inv_items = get_inventory(inv_phone)
                # Also check web-client if inv_phone is different
                if inv_phone != "web-client" and not inv_items:
                    inv_items = get_inventory("web-client")
                for inv_item in inv_items:
                    if inv_item.get("item_name") == category or \
                       category.replace(" ", "") in inv_item.get("item_name", "").replace(" ", "") or \
                       inv_item.get("item_name", "").replace(" ", "") in category.replace(" ", ""):
                        price = float(inv_item.get("price_per_unit") or 0)
                        if price > 0:
                            deduct_qty = amount / price
                            logger.info("Computed qty=%.1f from amount=₹%.0f / price=₹%.0f for '%s'",
                                        deduct_qty, amount, price, category)
                        break
            except Exception as price_exc:
                logger.warning("Price lookup for qty computation failed: %s", price_exc)

        if deduct_qty is not None and deduct_qty > 0:
            try:
                from services.inventory import deduct_stock
                stockout_info = deduct_stock(
                    phone=inv_phone,
                    item_name=category,
                    quantity=deduct_qty,
                )
            except Exception as inv_exc:
                logger.warning("Inventory deduction failed for '%s': %s", category, inv_exc)

    return {
        "entry": inserted,
        "current_profit": current_profit,
        "quantity": quantity,
        "stockout": stockout_info.get("stockout") if stockout_info else False,
        "inventory_updated": stockout_info is not None,
    }



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
    from services.conversation_engine import (
        analyze_voice_input, process_follow_up_answer, has_pending, get_pending,
    )
    from services.inventory import get_inventory

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

    # Get inventory for conversation engine.
    # Always use the shared 'web-client' catalog so WhatsApp and web UI
    # share the same items, prices and stock levels.
    catalog_phone = "web-client"
    try:
        inv_items = get_inventory(catalog_phone)
        if not inv_items:
            inv_items = get_inventory(phone)
    except Exception:
        inv_items = []

    # ── Check if this is a follow-up answer to a pending question ─────────
    if has_pending(phone):
        result = process_follow_up_answer(
            phone=phone,
            answer_transcript=transcript,
            answer_extracted=extracted,
            inventory_items=inv_items,
        )

        if result["status"] == "pending":
            # Still pending — send another counter question
            question = result.get("counter_question_hi", "")
            if result.get("inventory_created"):
                inv_info = result["inventory_created"]
                question = f"✅ {inv_info['item']} inventory mein add ho gaya (₹{int(inv_info['price'])}/piece).\n{question}"
            return f"🤖 {question}"

        if result["status"] == "complete":
            # Save all entries — use web-client as canonical phone so web UI sees them
            return _save_and_reply(phone, result.get("entries_to_save", []), media_url, catalog_phone=catalog_phone)

    # ── Fresh message — analyze against inventory ────────────────────────
    # First handle GET_REPORT separately (not inventory-dependent)
    for entry_data in extracted:
        intent = str(entry_data.get("intent") or "ADD_ENTRY").upper()
        if intent == "GET_REPORT":
            try:
                from services.report_generator import generate_pnl_pdf
                pdf_url = generate_pnl_pdf(phone, vendor_name=phone)
                if pdf_url:
                    send_whatsapp_reply(
                        to_phone=phone,
                        body="📊 Here is your weekly P&L report:",
                        media_url=pdf_url,
                    )
                    return "📊 Your weekly report has been sent! Check the PDF attached above."
                else:
                    return "⚠️ No transactions found this week. Record some sales first!"
            except Exception as report_exc:
                logger.error("GET_REPORT failed: %s", report_exc)
                return "⚠️ Report generation failed. Please try again."

    # Analyze all entries against inventory
    analysis = analyze_voice_input(extracted, phone, inv_items)

    if analysis["status"] == "pending":
        # Send counter question — save any complete entries first
        if analysis.get("entries_to_save"):
            _save_and_reply_silent(phone, analysis["entries_to_save"], media_url, catalog_phone=catalog_phone)
        question = analysis.get("counter_question_hi", "")
        return f"🤖 {question}"

    # All complete — save everything
    return _save_and_reply(phone, analysis.get("entries_to_save", []), media_url, catalog_phone=catalog_phone)


def _save_and_reply(phone: str, entries: List[Dict[str, Any]], media_url: str, catalog_phone: str = "web-client") -> str:
    """Save entries and build WhatsApp reply text."""
    total_income = 0.0
    total_expense = 0.0
    parts = []
    inventory_confirmations = []
    current_profit = 0.0

    for entry_data in entries:
        intent = str(entry_data.get("intent") or "ADD_ENTRY").upper()

        if intent == "STOCK_UPDATE":
            cat = str(entry_data.get("category") or "").strip().lower()
            try:
                qty = int(float(entry_data.get("quantity") or 0))
            except (TypeError, ValueError):
                qty = 0
            if cat and qty > 0:
                try:
                    from services.inventory import upsert_inventory_item
                    upsert_inventory_item(phone=catalog_phone, item_name=cat, daily_stock=qty, unit=entry_data.get("unit", "piece"), add_stock=True)
                    inventory_confirmations.append(f"📦 {cat} stock → {qty}")
                except Exception as inv_exc:
                    logger.warning("STOCK_UPDATE failed '%s': %s", cat, inv_exc)
            continue

        if intent == "PRICE_UPDATE":
            cat = str(entry_data.get("category") or "").strip().lower()
            try:
                new_price = float(entry_data.get("price_per_unit") or 0)
            except (TypeError, ValueError):
                new_price = 0.0
            if cat and new_price > 0:
                try:
                    _sb = get_supabase()
                    _sb.table("inventory").update({
                        "price_per_unit": new_price,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }).eq("phone", catalog_phone).eq("item_name", cat).eq("stock_date", date.today().isoformat()).execute()
                    inventory_confirmations.append(f"💰 {cat} rate → ₹{new_price:.0f}")
                except Exception as inv_exc:
                    logger.warning("PRICE_UPDATE failed '%s': %s", cat, inv_exc)
            continue

        if intent == "GET_REPORT":
            continue

        # ADD_ENTRY — save under real phone but use shared catalog for inventory ops
        try:
            saved = save_to_db(phone=phone, extracted_data=entry_data, audio_url=media_url, catalog_phone=catalog_phone)
            current_profit = float(saved["current_profit"])
            amount = float(saved["entry"].get("amount", 0))
            qty = saved.get("quantity")
            entry_type = entry_data.get("type") or "income"
            category = entry_data.get("category", "")
            inv_updated = saved.get("inventory_updated", False)

            if entry_type == "income":
                total_income += amount
                qty_str = f" ({int(qty)} {category})" if qty else f" ({category})"
                amt_str = f" {_format_inr(amount)}" if amount > 0 else ""
                stock_str = " 📦 Stock updated" if inv_updated else ""
                parts.append(f"Income{amt_str}{qty_str}{stock_str}")
            else:
                total_expense += amount
                parts.append(f"Expense {_format_inr(amount)} ({category})")
        except Exception as save_exc:
            logger.warning("save_to_db failed for entry %s: %s", entry_data, save_exc)
            continue

    reply_parts = []
    if parts:
        reply_parts.append("✅ " + ", ".join(parts))
        reply_parts.append(f"Current profit: {_format_inr(current_profit)}")
    if inventory_confirmations:
        reply_parts.append("🔄 Updated: " + " | ".join(inventory_confirmations))

    if not reply_parts:
        return FALLBACK_RESPONSE

    return "\n".join(reply_parts)


def _save_and_reply_silent(phone: str, entries: List[Dict[str, Any]], media_url: str, catalog_phone: str = "web-client") -> None:
    """Save entries silently (no reply generation needed — used for partial saves)."""
    for entry_data in entries:
        intent = str(entry_data.get("intent") or "ADD_ENTRY").upper()
        if intent in ("STOCK_UPDATE", "PRICE_UPDATE", "GET_REPORT"):
            continue
        try:
            save_to_db(phone=phone, extracted_data=entry_data, audio_url=media_url, catalog_phone=catalog_phone)
        except Exception as exc:
            logger.warning("Silent save failed: %s", exc)


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
