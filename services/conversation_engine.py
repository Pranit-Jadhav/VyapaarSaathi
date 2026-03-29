"""
services/conversation_engine.py

Smart conversational voice recording engine for VyapaarSaathi.

Handles multi-turn voice interactions:
1. Analyzes extracted voice data against inventory
2. Determines if information is complete or needs follow-up
3. Generates counter-questions (text + TTS audio) for missing info
4. Merges follow-up answers with pending entries to complete the record

Statuses:
  COMPLETE       — All info present, entry saved immediately
  NEEDS_QUANTITY — Item exists in inventory, quantity missing
  NEEDS_AMOUNT   — Item exists, quantity given, but no price found
  NEEDS_BOTH     — Item exists, both quantity and amount missing
  NEW_ITEM       — Item not in inventory, need price + daily stock
  NEW_ITEM_SALE  — Inventory just created, now need sale quantity
"""

from __future__ import annotations

import base64
import io
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

from services.settings import get_settings

logger = logging.getLogger(__name__)

# In-memory store for pending conversations (keyed by phone/session_id)
# Format: { "phone_or_session": { "status": "...", "entry_data": {...}, "created_at": "..." } }
_pending_conversations: Dict[str, Dict[str, Any]] = {}

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"


# ─── Analyze voice input against inventory ────────────────────────────────────

def analyze_voice_input(
    extracted_entries: List[Dict[str, Any]],
    phone: str,
    inventory_items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Analyze extracted voice entries against inventory state.
    
    Returns a dict with:
      status: "complete" | "pending"
      entries_to_save: list of entries ready to save (for complete entries)
      pending_entry: the entry needing follow-up (for pending)
      counter_question_hi: Hindi counter question text
      counter_question_en: English counter question text
      pending_reason: why it's pending
    """
    if not extracted_entries:
        return {"status": "complete", "entries_to_save": [], "pending_entry": None}

    # Build inventory lookup (case-insensitive, space-normalized)
    inv_lookup: Dict[str, Dict[str, Any]] = {}
    for item in inventory_items:
        name = str(item.get("item_name", "")).strip().lower()
        inv_lookup[name] = item
        # Also add without spaces for fuzzy matching
        inv_lookup[name.replace(" ", "")] = item

    complete_entries = []
    pending_entry = None
    pending_reason = ""
    question_hi = ""
    question_en = ""

    for entry_data in extracted_entries:
        intent = str(entry_data.get("intent", "ADD_ENTRY")).upper()

        # Non-sale intents: pass through as complete
        if intent in ("STOCK_UPDATE", "PRICE_UPDATE", "GET_REPORT"):
            complete_entries.append(entry_data)
            continue

        # ADD_ENTRY: check completeness
        category = str(entry_data.get("category") or "").strip().lower()
        amount = entry_data.get("amount")
        quantity = entry_data.get("quantity")
        entry_type = str(entry_data.get("type") or "income").lower()

        # Try to parse numeric values
        try:
            amount_val = float(amount) if amount is not None else None
        except (TypeError, ValueError):
            amount_val = None

        try:
            qty_val = float(quantity) if quantity is not None else None
        except (TypeError, ValueError):
            qty_val = None

        # Only check for income (sales) entries
        if entry_type != "income":
            # Expense entries: just need amount
            if amount_val and amount_val > 0:
                complete_entries.append(entry_data)
            else:
                pending_entry = entry_data
                pending_reason = "NEEDS_AMOUNT"
                question_hi = f"'{category}' पर कितना खर्चा हुआ? रुपये में बताइए।"
                question_en = f"How much did you spend on '{category}'? Tell the amount in rupees."
            continue

        # ── Income/sale entry: check inventory + completeness ─────────────
        # Find item in inventory (exact or fuzzy)
        inv_item = _find_inventory_item(category, inv_lookup)

        has_qty = qty_val is not None and qty_val > 0
        has_amount = amount_val is not None and amount_val > 0

        logger.info(
            "ConversationEngine: category='%s', amount=%s, qty=%s, has_amount=%s, has_qty=%s, in_inventory=%s",
            category, amount_val, qty_val, has_amount, has_qty, inv_item is not None,
        )

        if has_qty and has_amount:
            # Everything provided — complete
            complete_entries.append(entry_data)
            continue

        if inv_item:
            # Item exists in inventory
            price = float(inv_item.get("price_per_unit") or 0)

            if has_qty and not has_amount and price > 0:
                # Has quantity, can compute amount from inventory price
                entry_data["amount"] = qty_val * price
                complete_entries.append(entry_data)
                continue

            if has_amount and not has_qty and price > 0:
                # Has amount, can compute quantity from price
                entry_data["quantity"] = amount_val / price
                complete_entries.append(entry_data)
                continue

            if has_qty and not has_amount and price <= 0:
                # Has qty but no price in inventory — need amount
                pending_entry = entry_data
                pending_reason = "NEEDS_AMOUNT"
                question_hi = f"आपने {int(qty_val)} {category} बेचे। कुल कितने रुपये मिले?"
                question_en = f"You sold {int(qty_val)} {category}. How much did you earn in total?"
                continue

            if not has_qty and not has_amount:
                # Both missing
                if price > 0:
                    pending_entry = entry_data
                    pending_reason = "NEEDS_QUANTITY"
                    question_hi = f"आपने {category} बेचे — कितने बेचे? (गिनती बताइए)"
                    question_en = f"You sold {category} — how many did you sell? (tell the count)"
                else:
                    pending_entry = entry_data
                    pending_reason = "NEEDS_BOTH"
                    question_hi = f"आपने {category} बेचे — कितने बेचे और कुल कितने रुपये मिले?"
                    question_en = f"You sold {category} — how many did you sell and how much did you earn?"
                continue

            if not has_qty and has_amount:
                # Has amount but no quantity — acceptable, save as is
                complete_entries.append(entry_data)
                continue

        else:
            # ── NEW ITEM: not in inventory ────────────────────────────────
            if has_qty and has_amount:
                # They gave everything, even though item isn't in inventory
                # Auto-create inventory entry from the data and save
                try:
                    from services.inventory import upsert_inventory_item
                    computed_price = amount_val / qty_val if qty_val > 0 else amount_val
                    upsert_inventory_item(
                        phone=phone,
                        item_name=category,
                        daily_stock=int(qty_val * 1.5),  # rough estimate of daily stock
                        unit="piece",
                        price_per_unit=computed_price,
                    )
                    logger.info("Auto-created inventory for '%s': ₹%.0f/unit, stock=%d",
                                category, computed_price, int(qty_val * 1.5))
                except Exception as exc:
                    logger.warning("Auto inventory creation failed: %s", exc)
                complete_entries.append(entry_data)
                continue

            # Item NOT in inventory and info is incomplete — MUST ask
            pending_entry = entry_data
            pending_reason = "NEW_ITEM"
            if has_amount:
                # Has amount but item is new — still need price to calculate qty
                question_hi = (
                    f"'{category}' आपकी inventory में नहीं है। "
                    f"बताइए — एक {category} कितने रुपये का है? "
                    f"और रोज़ कितने बनाते/रखते हो?"
                )
                question_en = (
                    f"'{category}' is not in your inventory. "
                    f"Tell me — what is the price of one {category}? "
                    f"And how many do you prepare/stock daily?"
                )
            elif has_qty:
                # Has quantity but no price info — need price
                question_hi = (
                    f"'{category}' आपकी inventory में नहीं है। "
                    f"आपने {int(qty_val)} {category} बेचे। एक {category} कितने रुपये का है? "
                    f"और रोज़ कितने बनाते हो?"
                )
                question_en = (
                    f"'{category}' is not in your inventory. "
                    f"You sold {int(qty_val)} {category}. What is the price of one {category}? "
                    f"And how many do you prepare daily?"
                )
            else:
                # Nothing given — ask everything
                question_hi = (
                    f"'{category}' आपकी inventory में नहीं है। "
                    f"पहले बताइए — एक {category} कितने रुपये का है? "
                    f"और रोज़ कितने बनाते/रखते हो?"
                )
                question_en = (
                    f"'{category}' is not in your inventory. "
                    f"First tell me — what is the price of one {category}? "
                    f"And how many do you prepare/stock daily?"
                )
            continue

    # If we have a pending entry, store it and return pending status
    if pending_entry:
        session_key = _session_key(phone)
        _pending_conversations[session_key] = {
            "status": pending_reason,
            "entry_data": pending_entry,
            "complete_entries": complete_entries,
            "phone": phone,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Generate TTS for counter question
        audio_hi = _generate_question_audio(question_hi, "hi")
        audio_en = _generate_question_audio(question_en, "en")

        return {
            "status": "pending",
            "pending_reason": pending_reason,
            "pending_category": str(pending_entry.get("category", "")),
            "counter_question_hi": question_hi,
            "counter_question_en": question_en,
            "counter_audio_hi": audio_hi,
            "counter_audio_en": audio_en,
            "entries_to_save": complete_entries,
            "pending_entry": pending_entry,
        }

    return {
        "status": "complete",
        "entries_to_save": complete_entries,
        "pending_entry": None,
    }


# ─── Process the follow-up answer ────────────────────────────────────────────

def process_follow_up_answer(
    phone: str,
    answer_transcript: str,
    answer_extracted: List[Dict[str, Any]],
    inventory_items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Process the user's answer to a counter question.
    Merges the answer with the pending entry and determines next step.
    
    Returns same shape as analyze_voice_input.
    """
    session_key = _session_key(phone)
    pending = _pending_conversations.get(session_key)

    if not pending:
        # No pending conversation — treat as a fresh recording
        return analyze_voice_input(answer_extracted, phone, inventory_items)

    pending_reason = pending["status"]
    original_entry = pending["entry_data"]
    already_saved = pending.get("complete_entries", [])
    category = str(original_entry.get("category", "")).strip().lower()

    # Extract numbers from the answer using LLM
    answer_data = _extract_answer_data(answer_transcript, pending_reason, category)

    if pending_reason == "NEEDS_QUANTITY":
        qty = answer_data.get("quantity")
        if qty and float(qty) > 0:
            original_entry["quantity"] = float(qty)
            # Try to compute amount from inventory price
            inv_item = _find_inventory_item(category, _build_inv_lookup(inventory_items))
            price = float(inv_item.get("price_per_unit", 0)) if inv_item else 0
            if price > 0:
                original_entry["amount"] = float(qty) * price
            # If answer also contains amount, use it
            if answer_data.get("amount") and float(answer_data.get("amount", 0)) > 0:
                original_entry["amount"] = float(answer_data["amount"])

            _clear_pending(phone)
            return {
                "status": "complete",
                "entries_to_save": already_saved + [original_entry],
                "pending_entry": None,
            }

    elif pending_reason == "NEEDS_AMOUNT":
        amt = answer_data.get("amount")
        if amt and float(amt) > 0:
            original_entry["amount"] = float(amt)
            if answer_data.get("quantity"):
                original_entry["quantity"] = float(answer_data["quantity"])
            _clear_pending(phone)
            return {
                "status": "complete",
                "entries_to_save": already_saved + [original_entry],
                "pending_entry": None,
            }

    elif pending_reason == "NEEDS_BOTH":
        qty = answer_data.get("quantity")
        amt = answer_data.get("amount")
        if qty and float(qty) > 0 and amt and float(amt) > 0:
            original_entry["quantity"] = float(qty)
            original_entry["amount"] = float(amt)
            _clear_pending(phone)
            return {
                "status": "complete",
                "entries_to_save": already_saved + [original_entry],
                "pending_entry": None,
            }
        elif qty and float(qty) > 0:
            # Got quantity but still no amount
            original_entry["quantity"] = float(qty)
            pending["status"] = "NEEDS_AMOUNT"
            pending["entry_data"] = original_entry
            question_hi = f"आपने {int(float(qty))} {category} बेचे। कुल कितने रुपये मिले?"
            question_en = f"You sold {int(float(qty))} {category}. How much did you earn?"
            audio_hi = _generate_question_audio(question_hi, "hi")
            audio_en = _generate_question_audio(question_en, "en")
            return {
                "status": "pending",
                "pending_reason": "NEEDS_AMOUNT",
                "pending_category": category,
                "counter_question_hi": question_hi,
                "counter_question_en": question_en,
                "counter_audio_hi": audio_hi,
                "counter_audio_en": audio_en,
                "entries_to_save": already_saved,
                "pending_entry": original_entry,
            }

    elif pending_reason == "NEW_ITEM":
        price = answer_data.get("price_per_unit") or answer_data.get("amount")
        daily_stock = answer_data.get("daily_stock") or answer_data.get("quantity")

        if price and float(price) > 0:
            price_val = float(price)
            stock_val = int(float(daily_stock)) if daily_stock and float(daily_stock) > 0 else 50

            # Create the inventory entry under 'web-client' so it appears in the
            # shared catalog that the web UI and all WhatsApp users share.
            inv_phone = phone if phone == "web-client" else "web-client"
            try:
                from services.inventory import upsert_inventory_item
                upsert_inventory_item(
                    phone=inv_phone,
                    item_name=category,
                    daily_stock=stock_val,
                    unit="piece",
                    price_per_unit=price_val,
                )
                logger.info("Created inventory for '%s' under '%s': ₹%.0f, stock=%d", category, inv_phone, price_val, stock_val)
            except Exception as exc:
                logger.warning("Failed to create inventory for '%s': %s", category, exc)

            # Now ask for sale quantity
            question_hi = f"✅ {category} inventory में जोड़ दिया (₹{int(price_val)}/piece, daily {stock_val})। अब बताइए — आज कितने {category} बेचे?"
            question_en = f"✅ Added {category} to inventory (₹{int(price_val)}/piece, daily {stock_val}). Now tell me — how many {category} did you sell today?"
            audio_hi = _generate_question_audio(question_hi, "hi")
            audio_en = _generate_question_audio(question_en, "en")

            # Update pending to NEW_ITEM_SALE
            pending["status"] = "NEW_ITEM_SALE"
            pending["entry_data"]["price_per_unit"] = price_val
            _pending_conversations[session_key] = pending

            return {
                "status": "pending",
                "pending_reason": "NEW_ITEM_SALE",
                "pending_category": category,
                "counter_question_hi": question_hi,
                "counter_question_en": question_en,
                "counter_audio_hi": audio_hi,
                "counter_audio_en": audio_en,
                "entries_to_save": already_saved,
                "pending_entry": original_entry,
                "inventory_created": {
                    "item": category,
                    "price": price_val,
                    "daily_stock": stock_val,
                },
            }

    elif pending_reason == "NEW_ITEM_SALE":
        qty = answer_data.get("quantity")
        amt = answer_data.get("amount")
        price_stored = original_entry.get("price_per_unit", 0)

        if qty and float(qty) > 0:
            original_entry["quantity"] = float(qty)
            if amt and float(amt) > 0:
                original_entry["amount"] = float(amt)
            elif price_stored and float(price_stored) > 0:
                original_entry["amount"] = float(qty) * float(price_stored)
            _clear_pending(phone)
            return {
                "status": "complete",
                "entries_to_save": already_saved + [original_entry],
                "pending_entry": None,
            }
        elif amt and float(amt) > 0:
            original_entry["amount"] = float(amt)
            if price_stored and float(price_stored) > 0:
                original_entry["quantity"] = float(amt) / float(price_stored)
            _clear_pending(phone)
            return {
                "status": "complete",
                "entries_to_save": already_saved + [original_entry],
                "pending_entry": None,
            }

    # If we get here, the answer wasn't useful — ask again
    question_hi = "समझ नहीं आया। कृपया संख्या और रुपये दोनों बताइए।"
    question_en = "I didn't understand. Please tell both the quantity and the amount in rupees."
    audio_hi = _generate_question_audio(question_hi, "hi")
    audio_en = _generate_question_audio(question_en, "en")

    return {
        "status": "pending",
        "pending_reason": pending_reason,
        "pending_category": category,
        "counter_question_hi": question_hi,
        "counter_question_en": question_en,
        "counter_audio_hi": audio_hi,
        "counter_audio_en": audio_en,
        "entries_to_save": already_saved,
        "pending_entry": original_entry,
    }


# ─── Helper: Extract answer data using LLM ───────────────────────────────────

def _extract_answer_data(transcript: str, pending_reason: str, category: str) -> Dict[str, Any]:
    """Use Groq LLM to extract numbers from the follow-up answer."""
    settings = get_settings()

    context_map = {
        "NEEDS_QUANTITY": f"The vendor previously said they sold '{category}'. Now they are telling how many.",
        "NEEDS_AMOUNT": f"The vendor previously said they sold some '{category}'. Now they are telling the total rupees earned.",
        "NEEDS_BOTH": f"The vendor previously said they sold '{category}'. Now they are telling both quantity and amount.",
        "NEW_ITEM": f"New item '{category}' is being added to inventory. Vendor is telling the price per unit and daily stock count.",
        "NEW_ITEM_SALE": f"Inventory for '{category}' was just created. Vendor is telling how many they sold today.",
    }

    system_prompt = (
        "You are extracting numbers from a vendor's follow-up answer. "
        f"Context: {context_map.get(pending_reason, 'Vendor is providing sales information.')}\n\n"
        "Extract these fields if mentioned (use null if not said):\n"
        "- quantity: count/number of items\n"
        "- amount: total rupees (₹)\n"
        "- price_per_unit: price of one item\n"
        "- daily_stock: how many items vendor prepares daily\n\n"
        "Return ONLY valid JSON: {\"quantity\": ..., \"amount\": ..., \"price_per_unit\": ..., \"daily_stock\": ...}\n"
        "No explanation."
    )

    payload = {
        "model": settings.groq_llm_model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Transcript: {transcript}"},
        ],
    }
    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(GROQ_CHAT_URL, headers=headers, json=payload, timeout=20)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception as exc:
        logger.warning("Answer extraction failed: %s", exc)
        # Fallback: try to parse numbers directly from transcript
        return _fallback_number_extraction(transcript)


def _fallback_number_extraction(text: str) -> Dict[str, Any]:
    """Simple regex-based number extraction as fallback."""
    import re
    numbers = re.findall(r'\d+\.?\d*', text)
    result: Dict[str, Any] = {"quantity": None, "amount": None, "price_per_unit": None, "daily_stock": None}
    
    if len(numbers) >= 2:
        # Smaller number is likely quantity, larger is amount
        nums = [float(n) for n in numbers[:2]]
        nums.sort()
        result["quantity"] = nums[0]
        result["amount"] = nums[1]
    elif len(numbers) == 1:
        result["quantity"] = float(numbers[0])
    
    return result


# ─── Helper: Find item in inventory (fuzzy) ──────────────────────────────────

def _find_inventory_item(
    category: str, inv_lookup: Dict[str, Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """Find an inventory item by name, with fuzzy matching."""
    cat = category.strip().lower()
    
    # Exact match
    if cat in inv_lookup:
        return inv_lookup[cat]
    
    # Without spaces
    cat_nospace = cat.replace(" ", "")
    if cat_nospace in inv_lookup:
        return inv_lookup[cat_nospace]
    
    # Substring match
    for key, item in inv_lookup.items():
        key_nospace = key.replace(" ", "")
        if cat_nospace in key_nospace or key_nospace in cat_nospace:
            return item
    
    return None


def _build_inv_lookup(inventory_items: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Build an inventory lookup dict."""
    lookup: Dict[str, Dict[str, Any]] = {}
    for item in inventory_items:
        name = str(item.get("item_name", "")).strip().lower()
        lookup[name] = item
        lookup[name.replace(" ", "")] = item
    return lookup


# ─── Helper: Generate TTS audio for counter question ─────────────────────────

def _generate_question_audio(text: str, lang: str = "hi") -> Optional[str]:
    """Generate base64-encoded MP3 audio of the counter question."""
    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang=lang, slow=False)
        buffer = io.BytesIO()
        tts.write_to_fp(buffer)
        buffer.seek(0)
        return base64.b64encode(buffer.read()).decode("utf-8")
    except Exception as exc:
        logger.warning("Counter question TTS failed: %s", exc)
        return None


# ─── Session management ──────────────────────────────────────────────────────

def _session_key(phone: str) -> str:
    """Normalize phone to a consistent session key."""
    return phone.strip().lower()


def _clear_pending(phone: str) -> None:
    """Remove pending conversation for a phone."""
    key = _session_key(phone)
    _pending_conversations.pop(key, None)


def has_pending(phone: str) -> bool:
    """Check if there's a pending conversation for this phone."""
    return _session_key(phone) in _pending_conversations


def get_pending(phone: str) -> Optional[Dict[str, Any]]:
    """Get the pending conversation data."""
    return _pending_conversations.get(_session_key(phone))


def cancel_pending(phone: str) -> None:
    """Cancel/clear any pending conversation."""
    _clear_pending(phone)
