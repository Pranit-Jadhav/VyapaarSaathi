-- VyapaarSaathi Inventory System Migration
-- Run this in your Supabase SQL editor

-- 1. Add quantity column to ledger table (nullable — only set when voice mentions count)
ALTER TABLE ledger ADD COLUMN IF NOT EXISTS quantity DECIMAL(10,2) DEFAULT NULL;

-- 2. Create inventory catalog table
-- Each row represents one item a vendor sells, with their daily starting stock
CREATE TABLE IF NOT EXISTS inventory (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Identifies the vendor (matches ledger.phone)
    phone VARCHAR(32) NOT NULL,

    -- Item details
    item_name VARCHAR(100) NOT NULL,
    item_name_hi VARCHAR(100),        -- Hindi name (Set by AI or user)
    unit VARCHAR(30) NOT NULL DEFAULT 'piece',  -- cup, piece, kg, litre, etc.

    -- Stock management
    daily_stock INT NOT NULL DEFAULT 0,        -- How much vendor prepares per day
    current_stock INT NOT NULL DEFAULT 0,      -- Today's remaining stock
    price_per_unit DECIMAL(10,2) DEFAULT 0,    -- Approx selling price per unit

    -- Tracking
    stock_date DATE NOT NULL DEFAULT CURRENT_DATE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- One row per item per day per vendor
    UNIQUE(phone, item_name, stock_date)
);

-- Index for fast lookups by phone + date
CREATE INDEX IF NOT EXISTS idx_inventory_phone_date
    ON inventory (phone, stock_date DESC);

-- Enable RLS (backend uses service role key so RLS is bypassed)
ALTER TABLE inventory ENABLE ROW LEVEL SECURITY;

-- 3. Realtime for live stock updates on frontend dashboard
ALTER TABLE inventory REPLICA IDENTITY FULL;

DO $$
BEGIN
    BEGIN
        ALTER PUBLICATION supabase_realtime ADD TABLE inventory;
    EXCEPTION
        WHEN duplicate_object THEN NULL;
    END;
END;
$$;
