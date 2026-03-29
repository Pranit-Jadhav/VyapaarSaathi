"""
services/stock_suggestions.py

AI-powered next-day stock suggestion engine for VyapaarSaathi.

This module implements the prompt logic from the VoiceTrace PS exactly.
It aggregates raw ledger rows into per-item statistics and sends them to
the Groq LLM using the structured prompt so the model returns actionable,
bilingual suggestions without doing any math itself.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

GROQ_CHAT_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"

# ─── Prompt ──────────────────────────────────────────────────────────────────

STOCK_SUGGESTION_SYSTEM_PROMPT = """
You are a business advisor for Indian street vendors. Your job is to suggest
how much of each item a vendor should prepare or purchase for tomorrow.

You will receive structured data about the vendor's last 7–30 days of sales.
The data has already been computed — do not re-calculate anything. Use the
numbers as given.

OUTPUT RULES — follow these exactly:
1. Return ONLY valid JSON. No explanation, no markdown, no preamble.
2. One suggestion per item. Never combine items.
3. Keep reason_hi under 12 words (Hindi). Keep reason_en under 15 words (English).
4. The reason must explain WHY — not just restate the number.
5. If an item ran out frequently, say so. If weather affects it, say so.
6. Round suggested_qty to the nearest practical unit:
   - Chai/coffee cups: nearest 5
   - Fruits/vegetables by kg: nearest 0.5
   - Pieces (samosa, vada pav): nearest 10
   - Litres: nearest 0.5
7. suggested_qty must ALWAYS be > 0. Minimum is 1 unit.
8. confidence must be "high", "medium", or "low":
   - high: 5+ days of data for this item
   - medium: 3–4 days of data
   - low: 1–2 days of data
9. action must be one of: "increase", "maintain", "decrease", "new"
   - increase: suggest more than the average sold
   - maintain: suggest approximately the average sold
   - decrease: suggest less (due to waste or low sell-through)
   - new: item was mentioned as something vendor wants to try

REASON WRITING GUIDE:
- Stockout reason: mention how many days it ran out out of how many days tracked
- Weather boost: mention the specific weather condition tomorrow
- Growth reason: mention the upward trend simply
- Decrease reason: mention waste or leftover without being judgmental
- Always write from the vendor's perspective — practical, not technical

Return this exact JSON structure:
{
  "suggestions": [
    {
      "item_name": "chai",
      "item_name_hi": "चाय",
      "suggested_qty": 90,
      "unit": "cup",
      "reason_en": "Ran out 4 of last 7 days — prepare more.",
      "reason_hi": "7 में 4 दिन स्टॉक खत्म हुआ — ज़्यादा बनाएं।",
      "confidence": "high",
      "action": "increase",
      "weather_affected": false,
      "stockout_warning": true,
      "avg_sold": 78,
      "days_tracked": 7
    }
  ],
  "summary_hi": "कल के लिए 3 चीज़ों के सुझाव तैयार हैं।",
  "summary_en": "Stock suggestions ready for 3 items tomorrow.",
  "weather_note_hi": null,
  "weather_note_en": null
}
"""


def _build_user_prompt(
    vendor_name: str,
    vendor_type: str,
    item_stats: List[Dict[str, Any]],
    tomorrow_weather: Dict[str, Any],
    language: str = "hi",
) -> str:
    weather_context = (
        f"Tomorrow's weather: {tomorrow_weather.get('condition', 'normal')}, "
        f"{tomorrow_weather.get('temp_c', 28)}°C. "
        f"Raining: {tomorrow_weather.get('is_raining', False)}. "
        f"Hot (>33°C): {tomorrow_weather.get('is_hot', False)}. "
        f"Cold (<18°C): {tomorrow_weather.get('is_cold', False)}."
    )

    items_context = "\n".join([
        f"- {s['item_name']} ({s.get('item_name_hi', s['item_name'])}) [{s['unit']}]: "
        f"tracked {s['days_tracked']} days, "
        f"avg sold {s['avg_qty_sold']:.1f}/day, "
        f"max {s['max_qty_sold']}, min {s['min_qty_sold']}, "
        f"ran out {s['stockout_days']} days, "
        f"wasted/leftover {s['waste_days']} days, "
        f"trend: {s['trend']}, "
        f"last 3 days avg: {s.get('last_3_days_avg', s['avg_qty_sold']):.1f}, "
        f"sell-through rate: {s['sell_through_rate']:.0%}"
        for s in item_stats
    ])

    max_days = max((s["days_tracked"] for s in item_stats), default=0)

    return f"""
Vendor: {vendor_name}
Vendor type: {vendor_type}
Preferred language for suggestions: {language}

ITEM PERFORMANCE DATA (last {max_days} days):
{items_context}

TOMORROW'S WEATHER:
{weather_context}

Generate next-day stock suggestions for all items listed above.
Apply weather adjustments where appropriate (e.g. more chai/coffee if cold or rainy,
more cold drinks/juice if hot, less outdoor-sensitive items if heavy rain).
Do not suggest items not in the list above.
"""


# ─── Aggregation helper ───────────────────────────────────────────────────────

def _determine_trend(daily_amounts: List[float]) -> str:
    """Simple linear trend detection on sorted daily values."""
    if len(daily_amounts) < 3:
        return "stable"
    first_half = sum(daily_amounts[: len(daily_amounts) // 2])
    second_half = sum(daily_amounts[len(daily_amounts) // 2 :])
    if second_half > first_half * 1.15:
        return "increasing"
    if second_half < first_half * 0.85:
        return "decreasing"
    return "stable"


def aggregate_item_stats(
    ledger_rows: List[Dict[str, Any]],
    days: int = 14,
) -> List[Dict[str, Any]]:
    """
    Transform raw ledger income rows into per-item statistics suitable for
    the stock suggestion prompt.

    Expected ledger row fields (from /entries shape):
        created_at, category, amount, description
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # item -> date -> total amount earned
    item_daily: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for row in ledger_rows:
        # Use raw dict if available (direct ledger row)
        raw = row.get("raw") or row
        entry_type = str(raw.get("type", "")).lower()
        if entry_type != "income":
            continue

        # Parse date
        created_at_str = str(raw.get("created_at") or row.get("entry_date") or "")
        try:
            if "T" in created_at_str:
                dt = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            else:
                dt = datetime.strptime(created_at_str[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue

        if dt < cutoff:
            continue

        day_key = dt.strftime("%Y-%m-%d")
        category = str(raw.get("category") or "general").strip().lower()
        try:
            amount = float(raw.get("amount") or 0)
        except (TypeError, ValueError):
            amount = 0.0

        item_daily[category][day_key] += amount

    stats: List[Dict[str, Any]] = []
    for item_name, day_map in item_daily.items():
        sorted_vals = [day_map[d] for d in sorted(day_map.keys())]
        n = len(sorted_vals)
        avg = sum(sorted_vals) / max(n, 1)
        last3 = sum(sorted_vals[-3:]) / min(n, 3) if sorted_vals else avg

        stats.append({
            "item_name": item_name,
            "item_name_hi": item_name,   # AI will translate in its output
            "unit": "unit",              # generic; AI will adjust to common sense
            "days_tracked": n,
            "avg_qty_sold": round(avg, 1),
            "max_qty_sold": round(max(sorted_vals), 1),
            "min_qty_sold": round(min(sorted_vals), 1),
            "total_qty_sold": round(sum(sorted_vals), 1),
            "stockout_days": 0,          # we don't track stockouts yet — AI will infer from trend
            "waste_days": 0,
            "sell_through_rate": min(1.0, n / days),
            "trend": _determine_trend(sorted_vals),
            "last_3_days_avg": round(last3, 1),
            "price_per_unit": round(avg, 0),
        })

    # Sort by most data → most confidence first
    stats.sort(key=lambda s: s["days_tracked"], reverse=True)
    return stats


# ─── Default weather (used when no weather API is configured) ─────────────────

def _default_weather() -> Dict[str, Any]:
    return {
        "temp_c": 28,
        "condition": "sunny",
        "is_raining": False,
        "is_hot": False,
        "is_cold": False,
        "description_hi": "कल सामान्य मौसम रहेगा",
        "description_en": "Normal weather expected tomorrow",
    }


# ─── Main AI call ─────────────────────────────────────────────────────────────

def call_groq_for_suggestions(
    groq_api_key: str,
    groq_model: str,
    vendor_name: str,
    vendor_type: str,
    item_stats: List[Dict[str, Any]],
    language: str = "hi",
    tomorrow_weather: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Call the Groq LLM with the stock suggestion prompt and parse the response.

    Returns the parsed JSON dict from the model, or a fallback structure on error.
    """
    if not item_stats:
        return {
            "suggestions": [],
            "summary_hi": "अभी पर्याप्त डेटा नहीं है।",
            "summary_en": "Not enough data yet to generate suggestions.",
            "weather_note_hi": None,
            "weather_note_en": None,
        }

    weather = tomorrow_weather or _default_weather()
    user_prompt = _build_user_prompt(vendor_name, vendor_type, item_stats, weather, language)

    headers = {
        "Authorization": f"Bearer {groq_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": groq_model,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": STOCK_SUGGESTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    }

    try:
        resp = requests.post(GROQ_CHAT_COMPLETIONS_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception as exc:
        logger.warning("Groq suggestion call failed: %s — falling back to heuristic", exc)
        # Graceful heuristic fallback so the UI doesn't break
        return _heuristic_fallback(item_stats)


def _heuristic_fallback(item_stats: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Simple 15% buffer fallback if the AI call fails."""
    suggestions = []
    for s in item_stats:
        avg = s["avg_qty_sold"]
        suggestions.append({
            "item_name": s["item_name"],
            "item_name_hi": s["item_name"],
            "suggested_qty": max(1, round(avg * 1.15)),
            "unit": s["unit"],
            "reason_en": f"Based on {s['days_tracked']}-day average with 15% buffer.",
            "reason_hi": f"{s['days_tracked']} दिन के औसत पर आधारित।",
            "confidence": "high" if s["days_tracked"] >= 5 else ("medium" if s["days_tracked"] >= 3 else "low"),
            "action": "maintain",
            "weather_affected": False,
            "stockout_warning": False,
            "avg_sold": avg,
            "days_tracked": s["days_tracked"],
        })
    n = len(suggestions)
    return {
        "suggestions": suggestions,
        "summary_hi": f"कल के लिए {n} चीज़ों के सुझाव तैयार हैं।",
        "summary_en": f"Stock suggestions ready for {n} items tomorrow.",
        "weather_note_hi": None,
        "weather_note_en": None,
    }
