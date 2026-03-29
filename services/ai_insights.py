"""
services/ai_insights.py

Deep AI-powered business analytics for VyapaarSaathi.

Pipeline:
1. Fetch ledger entries (last 30 days) from Supabase
2. Compute comprehensive business metrics
3. Send metrics to Groq LLM for conversational narrative + structured findings
4. Generate TTS audio (gTTS) from the narrative
5. Return everything as a single JSON response
"""

from __future__ import annotations

import base64
import io
import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"

# ─── Metric Computation ──────────────────────────────────────────────────────

def compute_metrics(rows: List[Dict[str, Any]], inventory_items: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
    """
    Process raw ledger rows into comprehensive business metrics.
    """
    total_income = 0.0
    total_expense = 0.0
    category_income: Dict[str, float] = defaultdict(float)
    category_expense: Dict[str, float] = defaultdict(float)
    daily_income: Dict[str, float] = defaultdict(float)
    daily_expense: Dict[str, float] = defaultdict(float)
    dow_income: Dict[str, float] = defaultdict(float)
    dow_counts: Dict[str, int] = defaultdict(int)
    entry_count = 0

    for row in rows:
        try:
            amount = float(row.get("amount") or 0)
        except (TypeError, ValueError):
            amount = 0.0

        entry_type = (row.get("type") or "").lower()
        category = str(row.get("category") or "general").strip().lower()
        created_at = str(row.get("created_at") or "")[:10]

        entry_count += 1

        if entry_type == "income":
            total_income += amount
            category_income[category] += amount
            daily_income[created_at] += amount
        elif entry_type == "expense":
            total_expense += amount
            category_expense[category] += amount
            daily_expense[created_at] += amount

        # Day-of-week analysis
        try:
            dt = datetime.fromisoformat(created_at)
            day_name = dt.strftime("%A")
            if entry_type == "income":
                dow_income[day_name] += amount
                dow_counts[day_name] += 1
        except Exception:
            pass

    net_profit = total_income - total_expense
    all_dates = sorted(set(list(daily_income.keys()) + list(daily_expense.keys())))
    num_days = max(len(all_dates), 1)
    avg_daily_profit = net_profit / num_days

    # Daily net profits
    daily_net: Dict[str, float] = {}
    for d in all_dates:
        daily_net[d] = daily_income.get(d, 0) - daily_expense.get(d, 0)

    # Loss days
    loss_days = [d for d, v in daily_net.items() if v < 0]
    profit_days = [d for d, v in daily_net.items() if v > 0]

    # Consecutive loss streak
    max_loss_streak = 0
    current_streak = 0
    for d in sorted(daily_net.keys()):
        if daily_net[d] < 0:
            current_streak += 1
            max_loss_streak = max(max_loss_streak, current_streak)
        else:
            current_streak = 0

    # Best and worst days
    best_day = max(daily_net, key=lambda k: daily_net[k]) if daily_net else "N/A"
    worst_day = min(daily_net, key=lambda k: daily_net[k]) if daily_net else "N/A"
    best_day_amount = daily_net.get(best_day, 0)
    worst_day_amount = daily_net.get(worst_day, 0)

    # Best day of week
    dow_avg = {}
    for day_name, total in dow_income.items():
        count = dow_counts.get(day_name, 1)
        dow_avg[day_name] = total / count
    best_dow = max(dow_avg, key=lambda k: dow_avg[k]) if dow_avg else "N/A"
    worst_dow = min(dow_avg, key=lambda k: dow_avg[k]) if dow_avg else "N/A"

    # Top categories
    sorted_categories = sorted(category_income.items(), key=lambda x: x[1], reverse=True)
    top_3_categories = sorted_categories[:3]
    bottom_categories = sorted_categories[-2:] if len(sorted_categories) > 2 else []

    # Category breakdown for visualization
    total_cat_income = sum(v for _, v in sorted_categories) or 1
    category_breakdown = [
        {
            "name": cat,
            "amount": round(amt, 0),
            "percentage": round((amt / total_cat_income) * 100, 1),
        }
        for cat, amt in sorted_categories[:8]  # top 8 for UI
    ]

    # Expense ratio
    expense_ratio = (total_expense / total_income * 100) if total_income > 0 else 0

    # Trend detection (comparing first half vs second half of period)
    if len(all_dates) >= 4:
        mid = len(all_dates) // 2
        first_half_profit = sum(daily_net.get(d, 0) for d in all_dates[:mid])
        second_half_profit = sum(daily_net.get(d, 0) for d in all_dates[mid:])
        if second_half_profit > first_half_profit * 1.15:
            trend = "growing"
        elif second_half_profit < first_half_profit * 0.85:
            trend = "declining"
        else:
            trend = "stable"
    else:
        trend = "insufficient_data"

    # Health score (0-100)
    health = 50  # base
    if net_profit > 0:
        health += 15
    if expense_ratio < 50:
        health += 10
    elif expense_ratio > 80:
        health -= 15
    if trend == "growing":
        health += 10
    elif trend == "declining":
        health -= 10
    if len(loss_days) == 0:
        health += 10
    elif len(loss_days) > num_days * 0.5:
        health -= 15
    if max_loss_streak > 3:
        health -= 5
    if entry_count > 20:
        health += 5
    health = max(0, min(100, health))

    # Top expense categories
    sorted_expenses = sorted(category_expense.items(), key=lambda x: x[1], reverse=True)
    top_expenses = sorted_expenses[:3]

    # Weekly comparison
    today = datetime.now(timezone.utc).date()
    this_week_start = today - timedelta(days=today.weekday())
    last_week_start = this_week_start - timedelta(days=7)
    this_week_income = sum(
        daily_income.get(d, 0) for d in all_dates
        if d >= this_week_start.isoformat() and d < (this_week_start + timedelta(days=7)).isoformat()
    )
    last_week_income = sum(
        daily_income.get(d, 0) for d in all_dates
        if d >= last_week_start.isoformat() and d < this_week_start.isoformat()
    )
    week_over_week_change = (
        round(((this_week_income - last_week_income) / last_week_income) * 100, 1)
        if last_week_income > 0 else 0
    )

    # Inventory warnings
    inventory_warnings = []
    if inventory_items:
        for item in inventory_items:
            if not item.get("is_active", True):
                continue
            current = item.get("current_stock", 0)
            daily = item.get("daily_stock", 1) or 1
            pct = (current / daily) * 100
            if pct <= 20:
                inventory_warnings.append({
                    "item": item.get("item_name", "unknown"),
                    "current": current,
                    "daily": daily,
                    "percentage": round(pct, 0),
                })

    return {
        "total_income": round(total_income, 0),
        "total_expense": round(total_expense, 0),
        "net_profit": round(net_profit, 0),
        "avg_daily_profit": round(avg_daily_profit, 0),
        "num_days": num_days,
        "entry_count": entry_count,
        "expense_ratio": round(expense_ratio, 1),
        "trend": trend,
        "health_score": health,
        "loss_days_count": len(loss_days),
        "profit_days_count": len(profit_days),
        "max_loss_streak": max_loss_streak,
        "best_day": {"date": best_day, "amount": round(best_day_amount, 0)},
        "worst_day": {"date": worst_day, "amount": round(worst_day_amount, 0)},
        "best_day_of_week": best_dow,
        "worst_day_of_week": worst_dow,
        "top_categories": [{"name": c, "amount": round(a, 0)} for c, a in top_3_categories],
        "bottom_categories": [{"name": c, "amount": round(a, 0)} for c, a in bottom_categories],
        "top_expenses": [{"name": c, "amount": round(a, 0)} for c, a in top_expenses],
        "category_breakdown": category_breakdown,
        "week_over_week_change": week_over_week_change,
        "inventory_warnings": inventory_warnings,
    }


# ─── AI Summary Generation ───────────────────────────────────────────────────

AI_INSIGHTS_SYSTEM_PROMPT = """
You are a friendly, practical Indian business advisor for small vendors and shopkeepers.
You analyze their sales data and give them a clear, conversational summary of their business health.

You will receive computed business metrics. Your job is to INTERPRET them and give actionable advice.

OUTPUT RULES — follow these exactly:
1. Return ONLY valid JSON. No explanation, no markdown, no preamble.
2. Write the narrative as if you are SPEAKING directly to the vendor — warm, encouraging, practical.
3. Keep the narrative between 5–8 sentences. Be specific with numbers.
4. Each key_finding must have a clear, specific title and 1-2 sentence description.
5. Each recommendation must be specific and actionable — not generic advice.
6. Use the vendor's actual data in your response — don't make up numbers.

Return this exact JSON structure:
{
  "narrative_en": "Your full business summary in English, 5-8 sentences, conversational tone...",
  "narrative_hi": "आपके बिज़नेस की पूरी समरी हिंदी में, 5-8 वाक्य...",
  "key_findings": [
    {
      "title_en": "Strong Revenue Growth",
      "title_hi": "अच्छी कमाई बढ़ रही है",
      "description_en": "Your income grew 18% this week compared to last week.",
      "description_hi": "इस हफ्ते पिछले हफ्ते से 18% ज़्यादा कमाई हुई।",
      "type": "positive",
      "icon": "📈"
    }
  ],
  "recommendations": [
    {
      "text_en": "Focus more on chai sales on Mondays — it's your best performing day.",
      "text_hi": "सोमवार को चाय पर ध्यान दें — यह आपका सबसे अच्छा दिन है।",
      "priority": "high"
    }
  ]
}

FINDING TYPES: "positive", "warning", "critical", "neutral"
RECOMMENDATION PRIORITIES: "high", "medium", "low"
ICONS: Use relevant emoji only from: 📈 📉 💰 ⚠️ 🔥 ❄️ 📦 🎯 💡 ✅ ❌ 🏆 📊 🛡️
Generate 4-6 key findings and 3-5 recommendations.
"""


def _build_insights_prompt(metrics: Dict[str, Any], vendor_name: str, vendor_type: str) -> str:
    """Build the user prompt with all computed metrics for the LLM."""
    top_cats = ", ".join(
        f"{c['name']} (₹{c['amount']})" for c in metrics.get("top_categories", [])
    ) or "No data"

    top_exps = ", ".join(
        f"{c['name']} (₹{c['amount']})" for c in metrics.get("top_expenses", [])
    ) or "No expenses"

    inv_warnings = ""
    if metrics.get("inventory_warnings"):
        inv_warnings = "\nINVENTORY WARNINGS:\n" + "\n".join(
            f"- {w['item']}: only {w['current']}/{w['daily']} remaining ({w['percentage']}%)"
            for w in metrics["inventory_warnings"]
        )

    return f"""
VENDOR: {vendor_name}
VENDOR TYPE: {vendor_type}

BUSINESS METRICS (last {metrics['num_days']} days, {metrics['entry_count']} transactions):

REVENUE:
- Total Income: ₹{metrics['total_income']}
- Total Expenses: ₹{metrics['total_expense']}
- Net Profit: ₹{metrics['net_profit']}
- Average Daily Profit: ₹{metrics['avg_daily_profit']}
- Expense-to-Income Ratio: {metrics['expense_ratio']}%

TREND: {metrics['trend']}
- Week-over-week revenue change: {metrics['week_over_week_change']}%
- Profit days: {metrics['profit_days_count']}, Loss days: {metrics['loss_days_count']}
- Max consecutive loss streak: {metrics['max_loss_streak']} days

BEST & WORST:
- Best earning day: {metrics['best_day']['date']} (₹{metrics['best_day']['amount']})
- Worst day: {metrics['worst_day']['date']} (₹{metrics['worst_day']['amount']})
- Best day of week: {metrics['best_day_of_week']}
- Worst day of week: {metrics['worst_day_of_week']}

TOP SELLING CATEGORIES: {top_cats}
TOP EXPENSES: {top_exps}

HEALTH SCORE: {metrics['health_score']}/100
{inv_warnings}

Generate a comprehensive business analysis with narrative, key findings, and recommendations.
"""


def generate_ai_summary(
    groq_api_key: str,
    groq_model: str,
    metrics: Dict[str, Any],
    vendor_name: str = "Vendor",
    vendor_type: str = "street vendor",
) -> Dict[str, Any]:
    """Call Groq LLM to generate the AI narrative and structured findings."""
    user_prompt = _build_insights_prompt(metrics, vendor_name, vendor_type)

    headers = {
        "Authorization": f"Bearer {groq_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": groq_model,
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": AI_INSIGHTS_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    }

    try:
        resp = requests.post(GROQ_CHAT_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return parsed
    except Exception as exc:
        logger.warning("Groq AI insights call failed: %s — using fallback", exc)
        return _fallback_summary(metrics)


def _fallback_summary(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a basic summary without AI if the LLM call fails."""
    profit = metrics["net_profit"]
    trend = metrics["trend"]
    health = metrics["health_score"]

    en = (
        f"Over the last {metrics['num_days']} days, you earned ₹{metrics['total_income']} "
        f"and spent ₹{metrics['total_expense']}, leaving a net profit of ₹{profit}. "
        f"Your average daily profit is ₹{metrics['avg_daily_profit']}. "
        f"Your business trend is {trend}. "
        f"Your best performing day of the week is {metrics['best_day_of_week']}. "
        f"Business health score: {health}/100."
    )
    hi = (
        f"पिछले {metrics['num_days']} दिनों में, आपने ₹{metrics['total_income']} कमाए "
        f"और ₹{metrics['total_expense']} खर्च किए, शुद्ध लाभ ₹{profit}। "
        f"आपका दैनिक औसत लाभ ₹{metrics['avg_daily_profit']} है। "
        f"आपके बिज़नेस का ट्रेंड {trend} है। "
        f"सबसे अच्छा दिन {metrics['best_day_of_week']} है। "
        f"बिज़नेस स्वास्थ्य स्कोर: {health}/100।"
    )

    findings = []
    if profit > 0:
        findings.append({
            "title_en": "Profitable Business",
            "title_hi": "लाभदायक व्यापार",
            "description_en": f"Net profit of ₹{profit} over {metrics['num_days']} days.",
            "description_hi": f"{metrics['num_days']} दिनों में ₹{profit} का शुद्ध लाभ।",
            "type": "positive",
            "icon": "💰",
        })
    else:
        findings.append({
            "title_en": "Business Running at a Loss",
            "title_hi": "व्यापार में नुकसान",
            "description_en": f"Net loss of ₹{abs(profit)} over {metrics['num_days']} days.",
            "description_hi": f"{metrics['num_days']} दिनों में ₹{abs(profit)} का नुकसान।",
            "type": "critical",
            "icon": "📉",
        })

    if metrics["expense_ratio"] > 80:
        findings.append({
            "title_en": "High Expense Ratio",
            "title_hi": "खर्चा ज़्यादा है",
            "description_en": f"Expenses are {metrics['expense_ratio']}% of income. Try to reduce costs.",
            "description_hi": f"खर्चा आय का {metrics['expense_ratio']}% है। कम करने की कोशिश करें।",
            "type": "warning",
            "icon": "⚠️",
        })

    return {
        "narrative_en": en,
        "narrative_hi": hi,
        "key_findings": findings,
        "recommendations": [
            {
                "text_en": "Record all transactions daily for better insights.",
                "text_hi": "बेहतर जानकारी के लिए रोज़ाना सभी लेन-देन रिकॉर्ड करें।",
                "priority": "high",
            }
        ],
    }


# ─── TTS Audio Generation ────────────────────────────────────────────────────

def generate_audio_base64(text: str, lang: str = "hi") -> Optional[str]:
    """
    Convert text to speech using gTTS and return base64-encoded MP3.
    Returns None if gTTS is not available or fails.
    """
    try:
        from gtts import gTTS

        tts = gTTS(text=text, lang=lang, slow=False)
        buffer = io.BytesIO()
        tts.write_to_fp(buffer)
        buffer.seek(0)
        audio_bytes = buffer.read()
        return base64.b64encode(audio_bytes).decode("utf-8")
    except ImportError:
        logger.warning("gTTS not installed. Skipping audio generation.")
        return None
    except Exception as exc:
        logger.warning("TTS generation failed: %s", exc)
        return None


# ─── Main Pipeline ────────────────────────────────────────────────────────────

def run_insights_pipeline(
    groq_api_key: str,
    groq_model: str,
    ledger_rows: List[Dict[str, Any]],
    inventory_items: List[Dict[str, Any]] | None = None,
    vendor_name: str = "Vendor",
    vendor_type: str = "street vendor",
    language: str = "hi",
) -> Dict[str, Any]:
    """
    Full pipeline: metrics → AI summary → TTS audio (both languages) → combined response.
    """
    # Step 1: Compute metrics
    metrics = compute_metrics(ledger_rows, inventory_items)

    # Step 2: Generate AI summary
    ai_summary = generate_ai_summary(
        groq_api_key=groq_api_key,
        groq_model=groq_model,
        metrics=metrics,
        vendor_name=vendor_name,
        vendor_type=vendor_type,
    )

    # Step 3: Generate TTS audio in BOTH languages
    narrative_hi = ai_summary.get("narrative_hi", "")
    narrative_en = ai_summary.get("narrative_en", "")

    audio_hi_base64 = None
    audio_en_base64 = None

    if narrative_hi:
        audio_hi_base64 = generate_audio_base64(narrative_hi, lang="hi")
    if narrative_en:
        audio_en_base64 = generate_audio_base64(narrative_en, lang="en")

    # Step 4: Combine response
    return {
        "metrics": metrics,
        "narrative_en": narrative_en,
        "narrative_hi": narrative_hi,
        "key_findings": ai_summary.get("key_findings", []),
        "recommendations": ai_summary.get("recommendations", []),
        "health_score": metrics["health_score"],
        "category_breakdown": metrics["category_breakdown"],
        "audio_hi_base64": audio_hi_base64,
        "audio_en_base64": audio_en_base64,
    }

