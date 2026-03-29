"""
services/inventory.py

Real inventory management for VyapaarSaathi.

Handles:
- Catalog CRUD (vendor sets up items they sell)
- Today's stock management (daily_stock → current_stock)
- Auto-deduction when voice entries contain quantity
- History aggregation for AI stock suggestions
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from collections import defaultdict

from supabase_config import get_supabase

logger = logging.getLogger(__name__)

TABLE = "inventory"
LEDGER = "ledger"


# ─── Today's date helper ──────────────────────────────────────────────────────

def _today() -> str:
    return date.today().isoformat()


# ─── Catalog & daily stock operations ────────────────────────────────────────

def get_inventory(phone: str) -> List[Dict[str, Any]]:
    """
    Return today's inventory for a vendor.

    Merges TWO sources:
    1. Manual catalog rows from `inventory` table (vendor set these up)
    2. Voice-detected items aggregated from `ledger` table (auto-discovered)

    Manual catalog items take priority. Items only seen in voice are shown as
    "auto" items with sales history but no explicit daily_stock target.
    """
    supabase = get_supabase()
    today = _today()
    cutoff_30d = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    # ── Source 1: Manual catalog items ───────────────────────────────────────
    # Try given phone first; if empty, fallback to 'web-client'
    manual_rows = (
        supabase.table(TABLE)
        .select("*")
        .eq("phone", phone)
        .eq("stock_date", today)
        .eq("is_active", True)
        .order("item_name")
        .execute()
    ).data or []

    if not manual_rows and phone != "web-client":
        manual_rows = (
            supabase.table(TABLE)
            .select("*")
            .eq("phone", "web-client")
            .eq("stock_date", today)
            .eq("is_active", True)
            .order("item_name")
            .execute()
        ).data or []


    manual_items: Dict[str, Dict[str, Any]] = {r["item_name"]: r for r in manual_rows}

    # ── Source 2: Voice-detected items from ledger (last 30 days) ────────────
    ledger_rows = (
        supabase.table(LEDGER)
        .select("category,quantity,amount,created_at")
        .eq("phone", phone)
        .eq("type", "income")
        .gte("created_at", cutoff_30d)
        .order("created_at", desc=False)
        .limit(1000)
        .execute()
    ).data or []

    # Aggregate by item: total qty sold today, total ever, avg
    item_today_qty: Dict[str, float] = defaultdict(float)
    item_total_qty: Dict[str, float] = defaultdict(float)
    item_total_amt: Dict[str, float] = defaultdict(float)
    item_days: Dict[str, set] = defaultdict(set)

    for row in ledger_rows:
        cat = str(row.get("category") or "general").strip().lower()
        day = str(row.get("created_at", ""))[:10]
        try:
            amt = float(row.get("amount") or 0)
        except (TypeError, ValueError):
            amt = 0.0
        try:
            qty = float(row.get("quantity") or 0)
        except (TypeError, ValueError):
            qty = 0.0

        item_total_amt[cat] += amt
        item_days[cat].add(day)
        if qty > 0:
            item_total_qty[cat] += qty
            if day == today:
                item_today_qty[cat] += qty

    # ── Merge both sources ────────────────────────────────────────────────────
    all_items: List[Dict[str, Any]] = []

    # All items seen in ledger (voice data)
    all_item_names = set(item_days.keys()) | set(manual_items.keys())

    for item_name in sorted(all_item_names):
        if item_name in manual_items:
            # Manual catalog item — show with full stock data
            row = dict(manual_items[item_name])
            # Add voice-derived stats as extra fields
            row["voice_sold_today"] = item_today_qty.get(item_name, 0)
            row["voice_total_sold"] = item_total_qty.get(item_name, 0)
            row["voice_total_revenue"] = round(item_total_amt.get(item_name, 0), 2)
            row["voice_days_tracked"] = len(item_days.get(item_name, set()))
            row["source"] = "catalog"
            all_items.append(row)
        else:
            # Voice-only item — auto-discovered from recordings
            n_days = max(len(item_days[item_name]), 1)
            avg_qty = item_total_qty[item_name] / n_days if item_total_qty[item_name] > 0 else 0
            avg_rev = item_total_amt[item_name] / n_days
            all_items.append({
                "id": None,
                "phone": phone,
                "item_name": item_name,
                "item_name_hi": item_name,
                "unit": "piece",
                # Synthesised stock from voice history
                "daily_stock": round(avg_qty * 1.1) if avg_qty > 0 else 0,
                "current_stock": max(0, round(avg_qty - item_today_qty.get(item_name, 0))),
                "price_per_unit": round(avg_rev / avg_qty, 2) if avg_qty > 0 else round(avg_rev, 2),
                "stock_date": today,
                "is_active": True,
                "source": "voice",           # flag: auto-discovered, not manually configured
                "voice_sold_today": item_today_qty.get(item_name, 0),
                "voice_total_sold": item_total_qty[item_name],
                "voice_total_revenue": round(item_total_amt[item_name], 2),
                "voice_days_tracked": n_days,
            })

    return all_items



def upsert_inventory_item(
    phone: str,
    item_name: str,
    daily_stock: int,
    unit: str = "piece",
    price_per_unit: float = 0.0,
    item_name_hi: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create or update an item in the vendor's catalog for today.
    If the item already exists for today, update stock settings.
    If it's new, set current_stock = daily_stock.
    """
    supabase = get_supabase()
    today = _today()

    # Check if row already exists for today
    existing = (
        supabase.table(TABLE)
        .select("id,current_stock")
        .eq("phone", phone)
        .eq("item_name", item_name.lower().strip())
        .eq("stock_date", today)
        .execute()
    )

    payload: Dict[str, Any] = {
        "phone": phone,
        "item_name": item_name.lower().strip(),
        "item_name_hi": item_name_hi or item_name,
        "unit": unit,
        "daily_stock": daily_stock,
        "current_stock": daily_stock,  # Reset to full stock when vendor updates catalog
        "price_per_unit": price_per_unit,
        "stock_date": today,
        "is_active": True,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    rows = existing.data or []
    if rows:
        # Update existing; preserve current_stock deductions already made today
        existing_id = rows[0]["id"]
        existing_current = rows[0].get("current_stock", daily_stock)
        # Only increase current_stock proportionally if daily_stock changed
        payload["current_stock"] = min(existing_current, daily_stock)
        result = (
            supabase.table(TABLE)
            .update(payload)
            .eq("id", existing_id)
            .execute()
        )
    else:
        result = supabase.table(TABLE).insert(payload).execute()

    return (result.data or [payload])[0]


def delete_inventory_item(phone: str, item_name: str) -> bool:
    """Soft-delete an inventory item (marks is_active=False for all dates)."""
    supabase = get_supabase()
    supabase.table(TABLE).update({"is_active": False}).eq("phone", phone).eq("item_name", item_name.lower().strip()).execute()
    return True


def reset_daily_stock(phone: str) -> int:
    """
    Reset current_stock = daily_stock for all active items for this vendor.
    Called each morning (by scheduler or when vendor opens app).
    Also creates today's rows by copying yesterday's catalog if needed.
    """
    supabase = get_supabase()
    today = _today()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    # Check if today's rows already exist
    today_check = (
        supabase.table(TABLE)
        .select("id")
        .eq("phone", phone)
        .eq("stock_date", today)
        .eq("is_active", True)
        .execute()
    )

    if today_check.data:
        # Today exists — just reset current_stock = daily_stock
        supabase.table(TABLE).update({
            "current_stock": supabase.table(TABLE).select("daily_stock"),  # not valid inline
        })
        # Fetch all today's rows and reset individually
        rows = supabase.table(TABLE).select("id,daily_stock").eq("phone", phone).eq("stock_date", today).eq("is_active", True).execute().data or []
        for row in rows:
            supabase.table(TABLE).update({"current_stock": row["daily_stock"], "updated_at": datetime.now(timezone.utc).isoformat()}).eq("id", row["id"]).execute()
        return len(rows)

    # Today's rows don't exist — copy from yesterday's catalog
    yesterday_rows = (
        supabase.table(TABLE)
        .select("*")
        .eq("phone", phone)
        .eq("stock_date", yesterday)
        .eq("is_active", True)
        .execute()
    ).data or []

    if not yesterday_rows:
        return 0

    new_rows = []
    for row in yesterday_rows:
        new_rows.append({
            "phone": phone,
            "item_name": row["item_name"],
            "item_name_hi": row.get("item_name_hi", row["item_name"]),
            "unit": row["unit"],
            "daily_stock": row["daily_stock"],
            "current_stock": row["daily_stock"],  # Fresh day — full stock
            "price_per_unit": row.get("price_per_unit", 0),
            "stock_date": today,
            "is_active": True,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

    supabase.table(TABLE).insert(new_rows).execute()
    return len(new_rows)


# ─── Auto-deduct after voice entry ───────────────────────────────────────────

def deduct_stock(phone: str, item_name: str, quantity: float) -> Optional[Dict[str, Any]]:
    """
    Deduct `quantity` from current_stock for `item_name` today.

    Called automatically after a voice entry with a quantity is saved.
    Returns the updated row, or None if item not found in inventory.
    Tries given phone first, then falls back to 'web-client' so WhatsApp
    and web UI share the same inventory.
    """
    if quantity <= 0:
        return None

    supabase = get_supabase()
    today = _today()
    item_key = item_name.lower().strip()

    # Try given phone first, then fallback to 'web-client'
    phones_to_try = [phone]
    if phone != "web-client":
        phones_to_try.append("web-client")

    rows = []
    for try_phone in phones_to_try:
        rows = (
            supabase.table(TABLE)
            .select("id,item_name,current_stock,daily_stock,unit")
            .eq("phone", try_phone)
            .eq("stock_date", today)
            .eq("is_active", True)
            .execute()
        ).data or []
        if rows:
            break

    # Try exact match first, then partial/fuzzy match
    matched = None
    for row in rows:
        if row["item_name"] == item_key:
            matched = row
            break
    if not matched:
        # Normalize: remove spaces, try substring match both ways
        item_norm = item_key.replace(" ", "")
        for row in rows:
            row_norm = row["item_name"].replace(" ", "")
            if item_norm in row_norm or row_norm in item_norm:
                matched = row
                break

    if not matched:
        logger.info("No inventory item found for '%s' on %s — skipping deduction", item_name, today)
        return None


    new_stock = max(0, int(matched["current_stock"]) - int(quantity))
    updated = (
        supabase.table(TABLE)
        .update({"current_stock": new_stock, "updated_at": datetime.now(timezone.utc).isoformat()})
        .eq("id", matched["id"])
        .execute()
    )
    row = (updated.data or [matched])[0]
    stockout = new_stock == 0
    logger.info(
        "Deducted %g %s of '%s'. Stock: %d → %d%s",
        quantity, matched["unit"], item_name,
        matched["current_stock"], new_stock,
        " ⚠️ STOCKOUT" if stockout else ""
    )
    return {**row, "stockout": stockout}


# ─── History aggregation for AI suggestions ───────────────────────────────────

def get_item_stats_from_ledger(phone: str, days: int = 14) -> List[Dict[str, Any]]:
    """
    Aggregate real quantity data from ledger history for AI stock suggestions.

    This pulls rows where quantity IS NOT NULL (i.e., vendor mentioned a count)
    and builds the `item_stats` schema required by the AI suggestion prompt.
    """
    supabase = get_supabase()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    result = (
        supabase.table(LEDGER)
        .select("category,quantity,amount,created_at")
        .eq("phone", phone)
        .eq("type", "income")
        .gte("created_at", cutoff)
        .not_.is_("quantity", "null")
        .order("created_at", desc=False)
        .limit(1000)
        .execute()
    )
    rows = result.data or []

    if not rows:
        return []  # Caller falls back to amount-based heuristic

    # Build: item → date → list of quantities
    item_daily: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        cat = str(row.get("category") or "general").strip().lower()
        qty = row.get("quantity")
        if qty is None:
            continue
        try:
            qty = float(qty)
        except (TypeError, ValueError):
            continue
        day = str(row.get("created_at", ""))[:10]
        item_daily[cat][day].append(qty)

    # Also fetch today's inventory for unit/price metadata
    inv_rows = get_inventory(phone)
    inv_meta: Dict[str, Dict[str, Any]] = {r["item_name"]: r for r in inv_rows}

    stats: List[Dict[str, Any]] = []
    for item_name, day_map in item_daily.items():
        # Per-day totals
        daily_totals = {day: sum(qtys) for day, qtys in day_map.items()}
        sorted_days = sorted(daily_totals.keys())
        sorted_vals = [daily_totals[d] for d in sorted_days]

        n = len(sorted_vals)
        avg = sum(sorted_vals) / n
        last3 = sum(sorted_vals[-3:]) / min(n, 3)

        # Determine trend
        if n >= 3:
            first_half = sum(sorted_vals[:n//2])
            second_half = sum(sorted_vals[n//2:])
            if second_half > first_half * 1.15:
                trend = "increasing"
            elif second_half < first_half * 0.85:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "stable"

        meta = inv_meta.get(item_name, {})

        stats.append({
            "item_name": item_name,
            "item_name_hi": meta.get("item_name_hi", item_name),
            "unit": meta.get("unit", "piece"),
            "days_tracked": n,
            "avg_qty_sold": round(avg, 1),
            "max_qty_sold": round(max(sorted_vals), 1),
            "min_qty_sold": round(min(sorted_vals), 1),
            "total_qty_sold": round(sum(sorted_vals), 1),
            "stockout_days": 0,  # TODO: track via inventory.current_stock == 0 snapshots
            "waste_days": 0,
            "sell_through_rate": min(1.0, n / days),
            "trend": trend,
            "last_3_days_avg": round(last3, 1),
            "price_per_unit": float(meta.get("price_per_unit", 0)),
        })

    stats.sort(key=lambda s: s["days_tracked"], reverse=True)
    return stats
