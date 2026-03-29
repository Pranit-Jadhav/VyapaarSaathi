from services.voice_ledger import _build_inventory_snapshot_message, _looks_like_inventory_request


def test_inventory_keyword_variants_are_detected():
    assert _looks_like_inventory_request("mujhe mere inventry dekhne he")
    assert _looks_like_inventory_request("mujhe meri inventory dekhni hai")
    assert _looks_like_inventory_request("mera stock dikhao")


def test_inventory_keyword_detector_ignores_updates_and_sales():
    assert not _looks_like_inventory_request("50 samosa stock update karo")
    assert not _looks_like_inventory_request("aaj 10 samosa beche")


def test_inventory_snapshot_message_contains_stock_and_price():
    message = _build_inventory_snapshot_message(
        [
            {
                "item_name": "samosa",
                "item_name_hi": "samosa",
                "unit": "piece",
                "current_stock": 22,
                "daily_stock": 50,
                "price_per_unit": 15,
            }
        ]
    )

    assert "Aapki inventory" in message
    assert "samosa" in message
    assert "22/50 piece" in message
    assert "15/piece" in message
    assert "Instant Alert: Abhi koi critical low-stock item nahi hai" in message


def test_inventory_snapshot_message_includes_low_stock_alerts():
    message = _build_inventory_snapshot_message(
        [
            {
                "item_name": "chai",
                "item_name_hi": "chai",
                "unit": "cup",
                "current_stock": 8,
                "daily_stock": 50,
                "price_per_unit": 12,
            }
        ]
    )

    assert "Instant Alert: Low stock" in message
    assert "chai: 8/50 left" in message


def test_inventory_snapshot_message_includes_stockout_alerts():
    message = _build_inventory_snapshot_message(
        [
            {
                "item_name": "vada pav",
                "item_name_hi": "vada pav",
                "unit": "piece",
                "current_stock": 0,
                "daily_stock": 40,
                "price_per_unit": 20,
            }
        ]
    )

    assert "Instant Alert: Stockout" in message
    assert "vada pav: stockout" in message
