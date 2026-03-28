"""
anomaly_service.py
Anomaly Detection & Mood Tracker: Detects abnormal profit spikes/drops and mood streaks.
"""
import math
import datetime

def detect_anomalies(vendor_id: str, supabase) -> dict:
    """
    Computes 7-day rolling average net profit.
    Flags today's entry as an anomaly if it deviates by more than 2 std deviations.
    Also detects if vendor has had 3+ consecutive bad mood days.
    """
    try:
        res = (
            supabase.table("daily_entries")
            .select("entry_date, total_earned, total_spent, mood_indicator")
            .eq("vendor_id", vendor_id)
            .order("entry_date", desc=True)
            .limit(8)
            .execute()
        )
        entries = res.data
        if not entries or len(entries) < 4:
            return {"alerts": [], "mood_alert": False}

        alerts = []

        # Net profits ordered oldest to newest
        nets = [(e["total_earned"] - e["total_spent"]) for e in reversed(entries)]
        today_net = nets[-1]
        baseline = nets[:-1]

        mean = sum(baseline) / len(baseline)
        variance = sum((x - mean) ** 2 for x in baseline) / len(baseline)
        std = math.sqrt(variance) if variance > 0 else 1

        z_score = (today_net - mean) / std

        if z_score > 2.0:
            alerts.append({
                "type": "profit_spike",
                "message": f"Aaj ka profit bahut zyada tha! ({today_net:.0f} Rs vs avg {mean:.0f} Rs). Kya kuch khaas hua?",
                "severity": "info"
            })
        elif z_score < -2.0:
            alerts.append({
                "type": "profit_drop",
                "message": f"Aaj ka profit bahut kam tha ({today_net:.0f} Rs vs avg {mean:.0f} Rs). Kya koi dikkat aayi?",
                "severity": "warning"
            })

        # Mood streak detection: check for 3 consecutive bad days
        moods = [e.get("mood_indicator", "neutral") for e in entries[:3]]
        mood_alert = all(m == "bad" for m in moods)
        if mood_alert:
            alerts.append({
                "type": "mood_streak",
                "message": "3 din se mood bad hai. Kya hum kuch help kar sakte hain? Kal kuch naya try karein!",
                "severity": "support"
            })

        # Persist alerts into vendor_insights
        if alerts:
            record = {
                "vendor_id": vendor_id,
                "insight_date": datetime.date.today().isoformat(),
                "insight_type": "anomaly",
                "content": alerts,
                "metrics": {
                    "today_net": today_net,
                    "baseline_mean": round(mean, 2),
                    "z_score": round(z_score, 2),
                }
            }
            try:
                supabase.table("vendor_insights").upsert(record, on_conflict="vendor_id,insight_date,insight_type").execute()
            except Exception as e:
                print(f"Warning: Could not persist anomaly alerts: {e}")

        return {"alerts": alerts, "mood_alert": mood_alert}

    except Exception as e:
        print(f"Error detecting anomalies for {vendor_id}: {e}")
        return {"alerts": [], "mood_alert": False}
