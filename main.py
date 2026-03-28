import logging
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from twilio.twiml.messaging_response import MessagingResponse

from scheduler import start_scheduler, stop_scheduler
from services.settings import get_settings
from services.twilio_security import validate_twilio_request
from services.voice_ledger import (
    FALLBACK_RESPONSE,
    MISSING_AUDIO_RESPONSE,
    NON_AUDIO_RESPONSE,
    is_audio_message,
    process_voice_message,
    send_whatsapp_reply,
    convert_audio,
    extract_json,
    save_to_db,
    transcribe_audio,
)
from supabase_config import get_supabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    missing = settings.missing_required()
    if missing:
        logger.warning(
            "Missing required environment variables. Webhook features will fail until configured: %s",
            ", ".join(sorted(missing)),
        )

    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="VyapaarSaathi WhatsApp Ledger API",
    description="FastAPI backend for Twilio WhatsApp voice ledger ingestion.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _empty_twiml_response() -> Response:
    return Response(content=str(MessagingResponse()), media_type="application/xml")


def _parse_num_media(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _send_safe_reply(to_phone: str, body: str) -> None:
    try:
        send_whatsapp_reply(to_phone, body)
    except Exception as exc:  # pragma: no cover - external API path
        logger.error("Failed to send WhatsApp reply: %s", exc)


def _process_and_reply(sender: str, media_url: str) -> None:
    try:
        reply_body = process_voice_message(sender, media_url)
    except Exception as exc:  # pragma: no cover - external API path
        logger.exception("Voice message pipeline failed: %s", exc)
        reply_body = FALLBACK_RESPONSE

    _send_safe_reply(sender, reply_body)


def _is_phone_identifier(value: str) -> bool:
    text = value.strip()
    if not text:
        return False
    if text.startswith("whatsapp:+"):
        return True
    if text.startswith("+") and text[1:].isdigit():
        return True
    return text.isdigit()


def _is_uuid(value: str) -> bool:
    import re
    return bool(re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', value.strip().lower()))


def _legacy_entry_from_ledger(row: Dict[str, Any]) -> Dict[str, Any]:
    amount_raw = row.get("amount", 0)
    try:
        amount = float(amount_raw)
    except (TypeError, ValueError):
        amount = 0.0

    entry_type = str(row.get("type", "")).lower()
    category = str(row.get("category") or "general")
    description = str(row.get("description") or "")
    display_name = description if description else category

    items_sold: List[Dict[str, Any]] = []
    expenses: List[Dict[str, Any]] = []
    total_earned = 0.0
    total_spent = 0.0

    if entry_type == "income":
        total_earned = amount
        items_sold = [{"item_name": display_name, "amount": amount}]
    elif entry_type == "expense":
        total_spent = amount
        expenses = [{"item_name": display_name, "amount": amount}]

    created_at = row.get("created_at")
    created_at_str = str(created_at) if created_at else ""
    entry_date = created_at_str[:10] if len(created_at_str) >= 10 else created_at_str

    return {
        "entry_date": entry_date,
        "transcription": description,
        "total_earned": total_earned,
        "total_spent": total_spent,
        "items_sold": items_sold,
        "expenses": expenses,
        "mood_indicator": "neutral",
        "raw": {
            "id": row.get("id"),
            "phone": row.get("phone"),
            "type": entry_type,
            "category": category,
            "amount": amount,
            "audio_url": row.get("audio_url"),
            "created_at": created_at,
        },
    }


@app.get("/")
def read_root() -> Dict[str, str]:
    return {
        "message": "VyapaarSaathi WhatsApp Ledger API",
        "webhook": "/webhook",
        "docs": "/docs",
    }


@app.get("/health")
def health_check() -> Dict[str, Any]:
    missing = get_settings().missing_required()
    return {
        "status": "ok" if not missing else "degraded",
        "service": "VyapaarSaathi WhatsApp Ledger API",
        "missing_env": missing,
    }


@app.get("/entries")
def get_entries(vendor_id: str = "", limit: int = 7) -> Dict[str, Any]:
    """
    Compatibility endpoint for existing frontend screens.
    Reads data from the `ledger` table and shapes it like legacy daily entries.
    """
    safe_limit = max(1, min(limit, 100))
    supabase = get_supabase()

    try:
        query = (
            supabase.table("ledger")
            .select("id,phone,amount,type,category,description,audio_url,created_at")
            .order("created_at", desc=True)
            .limit(safe_limit)
        )

        incoming_identifier = (vendor_id or "").strip()
        if _is_phone_identifier(incoming_identifier):
            normalized = incoming_identifier
            if not normalized.startswith("whatsapp:"):
                normalized = f"whatsapp:{normalized}"
            query = query.eq("phone", normalized)
        elif incoming_identifier and _is_uuid(incoming_identifier):
            # UUID vendor IDs from the web frontend → entries are stored with phone="web-client"
            query = query.eq("phone", "web-client")

        result = query.execute()
        entries = [_legacy_entry_from_ledger(row) for row in (result.data or [])]
        return {"entries": entries}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load entries: {exc}")


@app.post("/record")
async def record_voice_entry(
    audio: UploadFile = File(...),
    vendor_id: str = Form(""),
) -> Dict[str, Any]:
    settings = get_settings()
    missing = settings.missing_required()
    if missing:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"message": "Missing required environment variables", "missing_env": missing},
        )

    if not audio:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Audio file is required")

    try:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory(prefix="vyapaarsaathi-upload-") as tmp_dir:
            working_dir = Path(tmp_dir)
            extension = Path(audio.filename or "uploaded.webm").suffix or ".webm"
            raw_path = working_dir / f"incoming{extension}"
            raw_path.write_bytes(await audio.read())

            mp3_audio = convert_audio(raw_path, working_dir)
            transcript_payload = transcribe_audio(mp3_audio)
            transcript = (transcript_payload.get("text") or "").strip()

            if not transcript:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Transcript was empty")

            extracted = extract_json(transcript)
            if not extracted:
                return {"detail": FALLBACK_RESPONSE, "transcript": transcript}

            # Ensure phone/vendor identifier fits Supabase column limit (varchar(32)).
            phone_identifier = (vendor_id.strip() or "web-client")[:32]

            # Save ALL extracted entries (income + expense as separate rows)
            total_earned = 0.0
            total_spent = 0.0
            items_sold = []
            expenses_list = []
            last_saved = {}
            current_profit = 0.0

            for entry_data in extracted:
                saved = save_to_db(phone=phone_identifier, extracted_data=entry_data, audio_url="")
                last_saved = saved.get("entry", {})
                current_profit = saved.get("current_profit", 0.0)

                amount = float(entry_data.get("amount", 0))
                entry_type = entry_data.get("type", "")
                display_name = entry_data.get("description") or entry_data.get("category", "")

                if entry_type == "income":
                    total_earned += amount
                    items_sold.append({"item_name": display_name, "amount": amount})
                elif entry_type == "expense":
                    total_spent += amount
                    expenses_list.append({"item_name": display_name, "amount": amount})

            return {
                "transcript": transcript,
                "extracted": extracted,
                "data": {
                    **last_saved,
                    "transcription": transcript,
                    # Correct totals summed across ALL entries from this recording
                    "total_earned": total_earned,
                    "total_spent": total_spent,
                    "items_sold": items_sold,
                    "expenses": expenses_list,
                    "entry_date": last_saved.get("created_at", "")[:10] if last_saved.get("created_at") else "",
                },
                "current_profit": current_profit,
            }
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - external paths
        logger.exception("/record upload failed: %s", exc)
        message = str(exc).lower()
        if "row-level security policy" in message or "code': '42501" in message:
            raise HTTPException(
                status_code=500,
                detail=(
                    "Supabase insert blocked by RLS. Configure SUPABASE_SERVICE_ROLE_KEY in backend .env "
                    "or add an INSERT policy for table ledger."
                ),
            )
        raise HTTPException(status_code=500, detail=f"Record failed: {exc}")


@app.post("/webhook", response_class=Response)
async def twilio_webhook(request: Request, background_tasks: BackgroundTasks) -> Response:
    settings = get_settings()
    missing = settings.missing_required()
    if missing:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "Missing required environment variables",
                "missing_env": missing,
            },
        )

    form_data = await request.form()
    validate_twilio_request(request, form_data)

    sender = (form_data.get("From") or "").strip()
    media_url = (form_data.get("MediaUrl0") or "").strip()
    media_content_type = (form_data.get("MediaContentType0") or "").strip().lower()
    num_media = _parse_num_media(form_data.get("NumMedia"))

    if not sender:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing sender phone number in Twilio payload",
        )

    if num_media < 1 or not media_url:
        background_tasks.add_task(_send_safe_reply, sender, MISSING_AUDIO_RESPONSE)
        return _empty_twiml_response()

    if not is_audio_message(media_content_type, media_url):
        background_tasks.add_task(_send_safe_reply, sender, NON_AUDIO_RESPONSE)
        return _empty_twiml_response()

    background_tasks.add_task(_process_and_reply, sender, media_url)
    return _empty_twiml_response()


# ---------------------------------------------------------------------------
# AI Insights endpoint
# ---------------------------------------------------------------------------
@app.get("/insights")
def get_insights(vendor_id: str = "", refresh: bool = False) -> Dict[str, Any]:
    """
    Analyse ledger entries for the given vendor and return patterns, alerts, and metrics.
    """
    supabase = get_supabase()

    try:
        query = (
            supabase.table("ledger")
            .select("id,phone,amount,type,category,description,created_at")
            .order("created_at", desc=True)
            .limit(100)
        )

        incoming = (vendor_id or "").strip()
        if _is_phone_identifier(incoming):
            normalized = incoming if incoming.startswith("whatsapp:") else f"whatsapp:{incoming}"
            query = query.eq("phone", normalized)
        elif incoming and _is_uuid(incoming):
            query = query.eq("phone", "web-client")

        result = query.execute()
        rows = result.data or []

        # ---------- compute patterns, metrics, alerts ----------
        total_income = 0.0
        total_expense = 0.0
        category_totals: Dict[str, float] = defaultdict(float)
        daily_net: Dict[str, float] = {}
        alerts: List[str] = []
        patterns: List[str] = []

        for row in rows:
            try:
                amount = float(row.get("amount") or 0)
            except (TypeError, ValueError):
                amount = 0.0
            entry_type = (row.get("type") or "").lower()
            category = str(row.get("category") or "general")
            created_at = str(row.get("created_at") or "")[:10]

            if entry_type == "income":
                total_income += amount
                category_totals[category] += amount
            elif entry_type == "expense":
                total_expense += amount

            daily_net.setdefault(created_at, 0.0)
            daily_net[created_at] += amount if entry_type == "income" else -amount

        net_profit = total_income - total_expense
        num_days = max(len(daily_net), 1)
        avg_daily = net_profit / num_days

        # Best seller
        if category_totals:
            best_cat = max(category_totals, key=lambda k: category_totals[k])
            patterns.append(f"Your best seller is '{best_cat}' with total income ₹{category_totals[best_cat]:.0f}.")
        else:
            patterns.append("Record more entries to see your best selling pattern.")

        patterns.append(f"Your average daily net profit is ₹{avg_daily:.0f} over {num_days} days.")

        # Loss-day alerts
        loss_days = [d for d, v in daily_net.items() if v < 0]
        if loss_days:
            alerts.append(f"{len(loss_days)} loss day(s) detected in recent history.")

        if total_expense > total_income * 0.8 and total_income > 0:
            alerts.append("Expense-to-income ratio is high (>80%). Review your costs.")

        # Best day of week
        dow_totals: Dict[str, float] = defaultdict(float)
        dow_counts: Dict[str, int] = defaultdict(int)
        for d, v in daily_net.items():
            try:
                dt = datetime.fromisoformat(d)
                day_name = dt.strftime("%A")
                dow_totals[day_name] += v
                dow_counts[day_name] += 1
            except Exception:
                pass
        best_day = max(dow_totals, key=lambda k: dow_totals[k]) if dow_totals else "N/A"

        metrics = {
            "total_income": total_income,
            "total_expense": total_expense,
            "net_profit": net_profit,
            "avg_daily_net_profit_inr": round(avg_daily, 2),
            "num_days": num_days,
            "best_day_of_week": best_day,
        }

        return {
            "patterns": patterns,
            "alerts": alerts,
            "metrics": metrics,
        }
    except Exception as exc:
        logger.exception("/insights failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Insights failed: {exc}")


# ---------------------------------------------------------------------------
# Stock suggestion endpoint
# ---------------------------------------------------------------------------
@app.get("/suggestions")
def get_suggestions(vendor_id: str = "", refresh: bool = False) -> Dict[str, Any]:
    """
    Suggest next-day stock quantities based on past sales patterns.
    """
    supabase = get_supabase()

    try:
        # Look at last 14 days of income entries to compute averages
        cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
        query = (
            supabase.table("ledger")
            .select("amount,type,category,description,created_at")
            .eq("type", "income")
            .gte("created_at", cutoff)
            .order("created_at", desc=True)
            .limit(200)
        )

        incoming = (vendor_id or "").strip()
        if _is_phone_identifier(incoming):
            normalized = incoming if incoming.startswith("whatsapp:") else f"whatsapp:{incoming}"
            query = query.eq("phone", normalized)
        elif incoming and _is_uuid(incoming):
            query = query.eq("phone", "web-client")

        result = query.execute()
        rows = result.data or []

        # Aggregate sales by category
        cat_daily: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for row in rows:
            try:
                amount = float(row.get("amount") or 0)
            except (TypeError, ValueError):
                amount = 0.0
            category = str(row.get("category") or "general")
            day = str(row.get("created_at") or "")[:10]
            cat_daily[category][day] += amount

        suggestions: List[Dict[str, Any]] = []
        for cat, day_map in cat_daily.items():
            total = sum(day_map.values())
            num_days = max(len(day_map), 1)
            avg = total / num_days
            suggestions.append({
                "item_name": cat,
                "avg_daily_sold": round(avg, 0),
                "suggested_qty": max(1, round(avg * 1.15)),  # 15% buffer
                "total_14d": round(total, 0),
            })

        suggestions.sort(key=lambda s: s["avg_daily_sold"], reverse=True)

        return {"suggestions": suggestions}
    except Exception as exc:
        logger.exception("/suggestions failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Suggestions failed: {exc}")


@app.exception_handler(Exception)
async def global_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )
