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
from pydantic import BaseModel
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
from services.stock_suggestions import aggregate_item_stats, call_groq_for_suggestions
from services.ai_insights import run_insights_pipeline
from services.conversation_engine import analyze_voice_input, process_follow_up_answer, has_pending, cancel_pending
from services.inventory import (
    get_inventory,
    upsert_inventory_item,
    delete_inventory_item,
    reset_daily_stock,
    get_item_stats_from_ledger,
)

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
        import traceback
        with open("/tmp/webhook_err.log", "w") as f:
            f.write(traceback.format_exc())
            f.write(f"\nMediaUrl: {media_url}\n")
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
    entry_date = created_at_str  # full ISO timestamp so UI parses local timezone correctly

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
def get_entries(vendor_id: str = "", limit: int = 100) -> Dict[str, Any]:
    """
    Compatibility endpoint for existing frontend screens.
    Reads data from the `ledger` table and shapes it like legacy daily entries.
    """
    safe_limit = max(1, min(limit, 1000))
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
        # When accessed from the web frontend (UUID vendor_id), show ALL entries
        # (web-client + whatsapp) so the ledger is a complete view of the business.

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

            # Map web frontend UUIDs to a consistent phone identifier.
            raw_id = vendor_id.strip()
            if not raw_id or _is_uuid(raw_id):
                phone_identifier = "web-client"
            else:
                phone_identifier = raw_id[:32]

            # ── Conversation Engine: analyze against inventory ────────────
            try:
                inv_items = get_inventory(phone_identifier)
            except Exception:
                inv_items = []

            analysis = analyze_voice_input(extracted, phone_identifier, inv_items)

            # Process entries that are already complete (STOCK_UPDATE, PRICE_UPDATE, complete sales)
            total_earned = 0.0
            total_spent = 0.0
            items_sold = []
            expenses_list = []
            inventory_updates = []
            last_saved = {}
            current_profit = 0.0

            for entry_data in analysis.get("entries_to_save", []):
                intent = str(entry_data.get("intent") or "ADD_ENTRY").upper()

                if intent in ("GET_REPORT", "GET_INVENTORY"):
                    continue

                if intent == "STOCK_UPDATE":
                    cat = str(entry_data.get("category") or "").strip().lower()
                    try:
                        qty = int(float(entry_data.get("quantity") or 0))
                    except (TypeError, ValueError):
                        qty = 0
                    if cat and qty > 0:
                        try:
                            row = upsert_inventory_item(
                                phone=phone_identifier,
                                item_name=cat,
                                daily_stock=qty,
                                unit=entry_data.get("unit", "piece"),
                                add_stock=True,
                            )
                            inventory_updates.append({"action": "stock_updated", "item": cat, "new_stock": qty})
                        except Exception as inv_exc:
                            logger.warning("STOCK_UPDATE failed for '%s': %s", cat, inv_exc)
                    continue

                if intent == "PRICE_UPDATE":
                    cat = str(entry_data.get("category") or "").strip().lower()
                    try:
                        new_price = float(entry_data.get("price_per_unit") or 0)
                    except (TypeError, ValueError):
                        new_price = 0.0
                    if cat and new_price > 0:
                        try:
                            supabase = get_supabase()
                            from datetime import date
                            today = date.today().isoformat()
                            supabase.table("inventory").update({
                                "price_per_unit": new_price,
                                "updated_at": datetime.now(timezone.utc).isoformat(),
                            }).eq("phone", phone_identifier).eq("item_name", cat).eq("stock_date", today).execute()
                            inventory_updates.append({"action": "price_updated", "item": cat, "new_price": new_price})
                        except Exception as inv_exc:
                            logger.warning("PRICE_UPDATE failed for '%s': %s", cat, inv_exc)
                    continue

                # ADD_ENTRY
                saved = save_to_db(phone=phone_identifier, extracted_data=entry_data, audio_url="")
                last_saved = saved.get("entry", {})
                current_profit = saved.get("current_profit", 0.0)
                amount = float(saved["entry"].get("amount", 0)) if saved.get("entry") else 0
                entry_type = entry_data.get("type", "")
                display_name = entry_data.get("description") or entry_data.get("category", "")

                if entry_type == "income":
                    total_earned += amount
                    items_sold.append({"item_name": display_name, "amount": amount})
                elif entry_type == "expense":
                    total_spent += amount
                    expenses_list.append({"item_name": display_name, "amount": amount})

            # Build response
            response: Dict[str, Any] = {
                "status": analysis["status"],
                "transcript": transcript,
                "extracted": extracted,
                "inventory_updates": inventory_updates,
                "data": {
                    **last_saved,
                    "transcription": transcript,
                    "total_earned": total_earned,
                    "total_spent": total_spent,
                    "items_sold": items_sold,
                    "expenses": expenses_list,
                    "entry_date": str(last_saved.get("created_at", "")),
                },
                "current_profit": current_profit,
            }

            # If pending, add counter question data
            if analysis["status"] == "pending":
                response["pending_reason"] = analysis.get("pending_reason", "")
                response["pending_category"] = analysis.get("pending_category", "")
                response["counter_question_hi"] = analysis.get("counter_question_hi", "")
                response["counter_question_en"] = analysis.get("counter_question_en", "")
                response["counter_audio_hi"] = analysis.get("counter_audio_hi")
                response["counter_audio_en"] = analysis.get("counter_audio_en")
                if analysis.get("inventory_created"):
                    response["inventory_created"] = analysis["inventory_created"]

            return response
    except HTTPException:
        raise
    except Exception as exc:
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


# ---------------------------------------------------------------------------
# Follow-up answer endpoint (conversation continuation)
# ---------------------------------------------------------------------------
@app.post("/record/answer")
async def record_follow_up_answer(
    audio: UploadFile = File(...),
    vendor_id: str = Form(""),
) -> Dict[str, Any]:
    """
    Handle the user's follow-up voice answer to a counter question.
    Merges the answer with the pending entry and saves if complete.
    """
    settings = get_settings()

    try:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory(prefix="vyapaarsaathi-answer-") as tmp_dir:
            working_dir = Path(tmp_dir)
            extension = Path(audio.filename or "uploaded.webm").suffix or ".webm"
            raw_path = working_dir / f"incoming{extension}"
            raw_path.write_bytes(await audio.read())

            mp3_audio = convert_audio(raw_path, working_dir)
            transcript_payload = transcribe_audio(mp3_audio)
            transcript = (transcript_payload.get("text") or "").strip()

            if not transcript:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Transcript was empty")

            # Map vendor_id to phone
            raw_id = vendor_id.strip()
            if not raw_id or _is_uuid(raw_id):
                phone_identifier = "web-client"
            else:
                phone_identifier = raw_id[:32]

            # Extract data from the answer
            answer_extracted = extract_json(transcript) or []

            # Get inventory
            try:
                inv_items = get_inventory(phone_identifier)
            except Exception:
                inv_items = []

            # Process the follow-up
            result = process_follow_up_answer(
                phone=phone_identifier,
                answer_transcript=transcript,
                answer_extracted=answer_extracted,
                inventory_items=inv_items,
            )

            # Save any complete entries
            total_earned = 0.0
            total_spent = 0.0
            items_sold = []
            expenses_list = []
            last_saved = {}
            current_profit = 0.0

            if result["status"] == "complete":
                for entry_data in result.get("entries_to_save", []):
                    intent = str(entry_data.get("intent") or "ADD_ENTRY").upper()
                    if intent in ("STOCK_UPDATE", "PRICE_UPDATE", "GET_REPORT", "GET_INVENTORY"):
                        continue

                    saved = save_to_db(phone=phone_identifier, extracted_data=entry_data, audio_url="")
                    last_saved = saved.get("entry", {})
                    current_profit = saved.get("current_profit", 0.0)
                    amount = float(saved["entry"].get("amount", 0)) if saved.get("entry") else 0
                    entry_type = entry_data.get("type", "")
                    display_name = entry_data.get("description") or entry_data.get("category", "")

                    if entry_type == "income":
                        total_earned += amount
                        items_sold.append({"item_name": display_name, "amount": amount})
                    elif entry_type == "expense":
                        total_spent += amount
                        expenses_list.append({"item_name": display_name, "amount": amount})

            response: Dict[str, Any] = {
                "status": result["status"],
                "transcript": transcript,
                "data": {
                    **last_saved,
                    "transcription": transcript,
                    "total_earned": total_earned,
                    "total_spent": total_spent,
                    "items_sold": items_sold,
                    "expenses": expenses_list,
                    "entry_date": str(last_saved.get("created_at", "")),
                },
                "current_profit": current_profit,
            }

            if result["status"] == "pending":
                response["pending_reason"] = result.get("pending_reason", "")
                response["pending_category"] = result.get("pending_category", "")
                response["counter_question_hi"] = result.get("counter_question_hi", "")
                response["counter_question_en"] = result.get("counter_question_en", "")
                response["counter_audio_hi"] = result.get("counter_audio_hi")
                response["counter_audio_en"] = result.get("counter_audio_en")
                if result.get("inventory_created"):
                    response["inventory_created"] = result["inventory_created"]

            return response
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("/record/answer failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Answer processing failed: {exc}")


@app.post("/record/cancel")
def cancel_pending_conversation(vendor_id: str = "") -> Dict[str, str]:
    """Cancel any pending counter-question conversation."""
    raw_id = (vendor_id or "").strip()
    if not raw_id or _is_uuid(raw_id):
        phone = "web-client"
    else:
        phone = raw_id[:32]
    cancel_pending(phone)
    return {"status": "cancelled"}


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
        # UUID / web frontend: no phone filter → show all entries

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
# Inventory management endpoints
# ---------------------------------------------------------------------------

@app.get("/inventory")
def get_inventory_items(vendor_id: str = "", phone: str = "") -> Dict[str, Any]:
    """
    Get today's inventory for a vendor.
    Accepts either phone (WhatsApp) or vendor_id (web UUID).
    """
    phone_key = phone.strip() or vendor_id.strip() or "web-client"
    if not phone_key.startswith("whatsapp:") and _is_phone_identifier(phone_key):
        phone_key = f"whatsapp:{phone_key}"
    elif _is_uuid(phone_key):
        phone_key = "web-client"
    try:
        items = get_inventory(phone_key)
        return {"inventory": items, "date": __import__('datetime').date.today().isoformat()}
    except Exception as exc:
        logger.exception("/inventory GET failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Inventory fetch failed: {exc}")



class InventoryItemIn(BaseModel):
    vendor_id: str = ""
    phone: str = ""
    item_name: str
    daily_stock: int
    unit: str = "piece"
    price_per_unit: float = 0.0
    item_name_hi: str = ""


@app.post("/inventory")
def add_inventory_item(body: InventoryItemIn) -> Dict[str, Any]:
    """Add or update an item in the vendor's daily inventory catalog."""
    phone_key = (body.phone or body.vendor_id or "").strip() or "web-client"
    if _is_uuid(phone_key):
        phone_key = "web-client"
    try:
        row = upsert_inventory_item(
            phone=phone_key,
            item_name=body.item_name,
            daily_stock=body.daily_stock,
            unit=body.unit,
            price_per_unit=body.price_per_unit,
            item_name_hi=body.item_name_hi or None,
            update_catalog=True,
        )
        return {"item": row}
    except Exception as exc:
        logger.exception("/inventory POST failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Inventory add failed: {exc}")



@app.delete("/inventory/{item_name}")
def remove_inventory_item(item_name: str, vendor_id: str = "", phone: str = "") -> Dict[str, Any]:
    """Soft-delete an inventory item from the vendor's catalog."""
    phone_key = phone.strip() or vendor_id.strip() or "web-client"
    if _is_uuid(phone_key):
        phone_key = "web-client"
    try:
        delete_inventory_item(phone=phone_key, item_name=item_name)
        return {"deleted": item_name}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Delete failed: {exc}")


# ---------------------------------------------------------------------------
# Reports Endpoint
# ---------------------------------------------------------------------------

@app.get("/api/report")
def get_pnl_report(vendor_id: str = "", phone: str = "") -> Dict[str, str]:
    """
    Generate and return the URL for the Trading & P&L IT Return format PDF.
    """
    phone_key = phone.strip() or vendor_id.strip() or "web-client"
    if not phone_key.startswith("whatsapp:") and _is_phone_identifier(phone_key):
        phone_key = f"whatsapp:{phone_key}"
    elif _is_uuid(phone_key):
        phone_key = "web-client"
        
    try:
        from services.report_generator import generate_pnl_pdf
        # Default name, web frontend doesn't pass the profile name yet easily
        pdf_url = generate_pnl_pdf(phone_key, vendor_name="PROPRIETOR")
        if not pdf_url:
            raise HTTPException(status_code=404, detail="No ledger data found to generate report.")
        return {"pdf_url": pdf_url}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("/api/report GET failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Report generation failed: {exc}")

class InventoryResetIn(BaseModel):
    vendor_id: str = ""
    phone: str = ""


@app.post("/inventory/reset")
def reset_inventory(body: InventoryResetIn) -> Dict[str, Any]:
    """Reset today's current_stock = daily_stock for all items. Call each morning."""
    phone_key = (body.phone or body.vendor_id or "").strip() or "web-client"
    if _is_uuid(phone_key):
        phone_key = "web-client"
    try:
        count = reset_daily_stock(phone=phone_key)
        return {"reset_count": count}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Reset failed: {exc}")


# ---------------------------------------------------------------------------
# Stock suggestion endpoint  (AI-powered, using VoiceTrace PS prompt logic)
# ---------------------------------------------------------------------------
@app.get("/suggestions")
def get_suggestions(
    vendor_id: str = "",
    vendor_name: str = "Vendor",
    vendor_type: str = "street vendor",
    language: str = "hi",
    days: int = 14,
) -> Dict[str, Any]:
    """
    Suggest next-day stock quantities using AI (Groq LLM).
    Falls back to a simple 15% heuristic if the AI call fails.
    """
    settings = get_settings()
    supabase = get_supabase()

    try:
        # Fetch recent income ledger rows
        safe_days = max(7, min(days, 30))
        cutoff = (datetime.now(timezone.utc) - timedelta(days=safe_days)).isoformat()
        query = (
            supabase.table("ledger")
            .select("id,phone,amount,type,category,description,created_at")
            .eq("type", "income")
            .gte("created_at", cutoff)
            .order("created_at", desc=True)
            .limit(500)
        )

        incoming = (vendor_id or "").strip()
        if _is_phone_identifier(incoming):
            normalized = incoming if incoming.startswith("whatsapp:") else f"whatsapp:{incoming}"
            query = query.eq("phone", normalized)

        result = query.execute()
        rows = result.data or []

        # --- Try real quantity data first ---
        item_stats = get_item_stats_from_ledger(phone_key, days=safe_days)

        if not item_stats:
            # Fallback: use ₹ amount-based aggregation from ledger
            item_stats = aggregate_item_stats(rows, days=safe_days)

        # Call the AI model with the structured prompt
        ai_result = call_groq_for_suggestions(
            groq_api_key=settings.groq_api_key,
            groq_model=settings.groq_llm_model,
            vendor_name=vendor_name,
            vendor_type=vendor_type,
            item_stats=item_stats,
            language=language,
        )

        return ai_result

    except Exception as exc:
        logger.exception("/suggestions failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Suggestions failed: {exc}")



# ---------------------------------------------------------------------------
# Deep AI Insights endpoint (with voice narration)
# ---------------------------------------------------------------------------
@app.get("/ai-insights")
def get_ai_insights(
    vendor_id: str = "",
    vendor_name: str = "Vendor",
    vendor_type: str = "street vendor",
    language: str = "hi",
) -> Dict[str, Any]:
    """
    Deep AI analysis of the vendor's business with voice narration.
    Returns metrics, AI-generated narrative, key findings, recommendations,
    and a base64-encoded MP3 audio of the summary.
    """
    settings = get_settings()
    supabase = get_supabase()

    try:
        # Fetch ledger entries (last 30 days)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        query = (
            supabase.table("ledger")
            .select("id,phone,amount,type,category,description,created_at")
            .gte("created_at", cutoff)
            .order("created_at", desc=True)
            .limit(500)
        )

        incoming = (vendor_id or "").strip()
        if _is_phone_identifier(incoming):
            normalized = incoming if incoming.startswith("whatsapp:") else f"whatsapp:{incoming}"
            query = query.eq("phone", normalized)

        result = query.execute()
        ledger_rows = result.data or []

        # Fetch inventory items
        phone_key = "web-client"
        if _is_phone_identifier(incoming):
            phone_key = incoming if incoming.startswith("whatsapp:") else f"whatsapp:{incoming}"
        try:
            inv_items = get_inventory(phone_key)
        except Exception:
            inv_items = []

        # Run the full pipeline
        response = run_insights_pipeline(
            groq_api_key=settings.groq_api_key,
            groq_model=settings.groq_llm_model,
            ledger_rows=ledger_rows,
            inventory_items=inv_items,
            vendor_name=vendor_name,
            vendor_type=vendor_type,
            language=language,
        )

        return response

    except Exception as exc:
        logger.exception("/ai-insights failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"AI Insights failed: {exc}")


@app.exception_handler(Exception)
async def global_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )
