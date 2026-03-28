"""
scheduler.py
Nightly background job using APScheduler to run Pattern Engine,
Stock Suggestions, and Anomaly Detection for all active vendors.
Runs at 2 AM IST every night.
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from supabase_config import get_supabase
from analytics_service import generate_insights
from stock_service import generate_stock_suggestions
from anomaly_service import detect_anomalies

scheduler = BackgroundScheduler(timezone=pytz.timezone("Asia/Kolkata"))

def run_nightly_jobs():
    """
    Fetches all vendors who have at least 4 entries and runs Phase 2 analytics.
    """
    print("[Scheduler] Starting nightly analytics job...")
    supabase = get_supabase()
    try:
        # Get all unique vendor_ids with >= 4 entries
        res = supabase.table("daily_entries").select("vendor_id").execute()
        if not res.data:
            print("[Scheduler] No daily entries found.")
            return
        
        # Count per vendor
        counts = {}
        for row in res.data:
            vid = row["vendor_id"]
            counts[vid] = counts.get(vid, 0) + 1
        
        active_vendors = [vid for vid, count in counts.items() if count >= 4]
        print(f"[Scheduler] Running jobs for {len(active_vendors)} active vendors.")
        
        for vendor_id in active_vendors:
            try:
                generate_insights(vendor_id, supabase)
                generate_stock_suggestions(vendor_id, supabase)
                detect_anomalies(vendor_id, supabase)
                print(f"[Scheduler] ✅ Done for vendor {vendor_id}")
            except Exception as e:
                print(f"[Scheduler] ❌ Error for vendor {vendor_id}: {e}")
    except Exception as e:
        print(f"[Scheduler] Fatal error: {e}")
    print("[Scheduler] Nightly job complete.")


def start_scheduler():
    """Call this once on app startup to register the cron job."""
    scheduler.add_job(
        run_nightly_jobs,
        CronTrigger(hour=2, minute=0, timezone=pytz.timezone("Asia/Kolkata")),
        id="nightly_analytics",
        replace_existing=True,
    )
    scheduler.start()
    print("[Scheduler] Nightly analytics scheduler started (runs at 2 AM IST).")


def stop_scheduler():
    """Call this on app shutdown."""
    if scheduler.running:
        scheduler.shutdown()
