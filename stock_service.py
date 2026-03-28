"""
stock_service.py
Stock Suggestion Engine: Computes tomorrow's recommended stock levels per item.
Uses last 7 days of entries + Open-Meteo (free, no API key) weather forecast.
"""
import os
import math
import requests
from datetime import date, timedelta

# Default location: Mumbai, Maharashtra (fallback)
DEFAULT_LAT = 19.0760
DEFAULT_LON = 72.8777

# Weather multipliers for certain drink/food combos
HOT_DRINK_ITEMS = ["chai", "tea", "chai patti", "coffee"]
COLD_DRINK_ITEMS = ["limbu pani", "lassi", "sharbat", "juice", "cold drink"]


def get_weather_forecast(lat: float = DEFAULT_LAT, lon: float = DEFAULT_LON) -> dict:
    """
    Fetches tomorrow's weather forecast from Open-Meteo (completely free, no key needed).
    Returns a simplified weather summary.
    """
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
        f"&timezone=Asia%2FKolkata"
        f"&start_date={tomorrow}&end_date={tomorrow}"
    )
    try:
        res = requests.get(url, timeout=5)
        data = res.json().get("daily", {})
        return {
            "date": tomorrow,
            "max_temp": data.get("temperature_2m_max", [None])[0],
            "min_temp": data.get("temperature_2m_min", [None])[0],
            "precipitation_mm": data.get("precipitation_sum", [0])[0] or 0,
        }
    except Exception as e:
        print(f"Warning: Could not fetch weather data: {e}")
        return {"date": tomorrow, "max_temp": None, "min_temp": None, "precipitation_mm": 0}


def apply_weather_multiplier(item_name: str, weather: dict) -> float:
    """
    Returns a demand multiplier based on upcoming weather and item type.
    """
    name = item_name.lower().strip()
    multiplier = 1.0
    max_temp = weather.get("max_temp") or 25
    rain = (weather.get("precipitation_mm") or 0) > 2.0  # significant rain

    is_hot_drink = any(hot in name for hot in HOT_DRINK_ITEMS)
    is_cold_drink = any(cold in name for cold in COLD_DRINK_ITEMS)

    if is_hot_drink and rain:
        multiplier = 1.20  # Rain -> more chai!
    elif is_cold_drink and max_temp > 35:
        multiplier = 1.25  # Hot day -> more cold drinks!
    elif is_hot_drink and max_temp > 38:
        multiplier = 0.90  # Extremely hot -> less chai
    return multiplier


def generate_stock_suggestions(vendor_id: str, supabase, lat: float = DEFAULT_LAT, lon: float = DEFAULT_LON) -> dict:
    """
    Analyzes last 7 days of entries, checks stockouts, applies weather multipliers,
    and returns tomorrow's suggested stock quantities per item.
    """
    try:
        res = (
            supabase.table("daily_entries")
            .select("entry_date, items_sold, stockout_mentions")
            .eq("vendor_id", vendor_id)
            .order("entry_date", desc=True)
            .limit(7)
            .execute()
        )
        entries = res.data
        if not entries:
            return {"suggestions": [], "weather": {}}

        # Aggregate quantities per item
        item_quantities = {}
        stockout_items = set()

        for e in entries:
            for item in (e.get("items_sold") or []):
                name = item.get("item_name", "Unknown").lower().strip()
                qty = item.get("quantity") or 0
                item_quantities[name] = item_quantities.get(name, 0) + qty
            for so in (e.get("stockout_mentions") or []):
                stockout_items.add(so.lower().strip())

        if not item_quantities:
            return {"suggestions": [], "weather": {}}

        days = len(entries)
        weather = get_weather_forecast(lat, lon)

        suggestions = []
        for item, total_qty in item_quantities.items():
            avg_daily = total_qty / days
            # Add 20% buffer if this item ran out recently
            if item in stockout_items:
                avg_daily *= 1.2
            # Apply weather multiplier
            weather_mult = apply_weather_multiplier(item, weather)
            suggested_qty = math.ceil(avg_daily * weather_mult / 5) * 5  # Round up to nearest 5
            suggestions.append({
                "item_name": item,
                "avg_daily_sold": round(avg_daily, 1),
                "suggested_qty": suggested_qty,
                "weather_boost": weather_mult > 1.0,
                "stockout_risk": item in stockout_items,
            })

        # Sort by suggested quantity descending
        suggestions.sort(key=lambda x: x["suggested_qty"], reverse=True)

        # Persist into vendor_insights table
        try:
            import datetime as dt
            record = {
                "vendor_id": vendor_id,
                "insight_date": dt.date.today().isoformat(),
                "insight_type": "stock_suggestion",
                "content": suggestions,
                "metrics": {"weather": weather},
            }
            supabase.table("vendor_insights").upsert(record, on_conflict="vendor_id,insight_date,insight_type").execute()
        except Exception as e:
            print(f"Warning: Could not persist stock suggestions: {e}")

        return {"suggestions": suggestions, "weather": weather}

    except Exception as e:
        print(f"Error generating stock suggestions for {vendor_id}: {e}")
        return {"suggestions": [], "weather": {}}
