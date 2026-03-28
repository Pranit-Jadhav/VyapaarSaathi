"""
analytics_service.py
Pattern Engine: Generates vendor insights from aggregated daily_entries data.
Runs SQL aggregations and then uses Groq LLM to generate plain Hindi/Hinglish summaries.
"""
import os
import json
from groq import Groq

_client = None

def get_groq_client():
    global _client
    if _client is None:
        _client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    return _client

INSIGHT_PROMPT = """
You are a helpful business advisor for Indian street vendors. 
Given the following business metrics for a vendor (in JSON), write 3 concise, friendly, and encouraging 
sentences in plain Hinglish (a natural mix of Hindi and English) that explain the key patterns.
Be specific and use the numbers. Do not use markdown formatting.

Metrics JSON:
{metrics}

Output format: Write exactly 3 sentences, one per line.
"""

def compute_metrics(vendor_id: str, supabase) -> dict:
    """
    Fetches the last 30 days of data and computes key business patterns.
    """
    try:
        # Fetch last 30 daily entries
        res = (
            supabase.table("daily_entries")
            .select("entry_date, total_earned, total_spent, items_sold, mood_indicator")
            .eq("vendor_id", vendor_id)
            .order("entry_date", desc=True)
            .limit(30)
            .execute()
        )
        entries = res.data
        if not entries or len(entries) < 2:
            return {}

        # 1. Net profits per day
        nets = [e["total_earned"] - e["total_spent"] for e in entries]
        avg_daily_net = round(sum(nets) / len(nets), 2)
        max_single_day = max(nets)

        # 2. Best day of the week
        import datetime
        day_profits = {}
        for e in entries:
            try:
                date = datetime.date.fromisoformat(e["entry_date"])
                day_name = date.strftime("%A")
                day_profits[day_name] = day_profits.get(day_name, 0) + (e["total_earned"] - e["total_spent"])
            except Exception:
                pass
        best_day = max(day_profits, key=day_profits.get) if day_profits else "N/A"

        # 3. Most consistent item sold
        item_counts = {}
        for e in entries:
            for item in (e.get("items_sold") or []):
                name = item.get("item_name", "Unknown")
                item_counts[name] = item_counts.get(name, 0) + 1
        most_consistent_item = max(item_counts, key=item_counts.get) if item_counts else "N/A"

        # 4. 7-day trend direction: compare first half vs second half of last 14 days
        recent_14 = nets[:14] if len(nets) >= 14 else nets
        mid = len(recent_14) // 2
        first_half_avg = sum(recent_14[mid:]) / max(len(recent_14[mid:]), 1)
        second_half_avg = sum(recent_14[:mid]) / max(len(recent_14[:mid]), 1)
        trend = "improving" if second_half_avg > first_half_avg else "declining"

        # 5. Mood summary
        mood_counts = {}
        for e in entries:
            mood = e.get("mood_indicator", "neutral")
            mood_counts[mood] = mood_counts.get(mood, 0) + 1
        dominant_mood = max(mood_counts, key=mood_counts.get) if mood_counts else "neutral"

        return {
            "days_analyzed": len(entries),
            "avg_daily_net_profit_inr": avg_daily_net,
            "max_single_day_profit_inr": max_single_day,
            "best_day_of_week": best_day,
            "most_consistent_item": most_consistent_item,
            "7_day_profit_trend": trend,
            "dominant_mood": dominant_mood,
        }
    except Exception as e:
        print(f"Error computing metrics for {vendor_id}: {e}")
        return {}


def generate_insights(vendor_id: str, supabase) -> dict:
    """
    Computes metrics and runs them through Groq to get Hindi insight sentences.
    Persists the output in vendor_insights table.
    """
    metrics = compute_metrics(vendor_id, supabase)
    if not metrics:
        return {"insights": [], "metrics": {}}

    client = get_groq_client()
    try:
        response = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": INSIGHT_PROMPT.format(metrics=json.dumps(metrics, ensure_ascii=False))
                }
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.4,
        )
        raw = response.choices[0].message.content.strip()
        sentences = [s.strip() for s in raw.split("\n") if s.strip()][:3]
    except Exception as e:
        print(f"Groq insight error: {e}")
        sentences = []

    # Persist into vendor_insights table
    try:
        import datetime
        record = {
            "vendor_id": vendor_id,
            "insight_date": datetime.date.today().isoformat(),
            "insight_type": "pattern",
            "content": sentences,
            "metrics": metrics,
        }
        supabase.table("vendor_insights").upsert(record, on_conflict="vendor_id,insight_date,insight_type").execute()
    except Exception as e:
        print(f"Warning: Could not persist insights: {e}")

    return {"insights": sentences, "metrics": metrics}
