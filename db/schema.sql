-- VyapaarSaathi Supabase Schema

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Vendors Table
CREATE TABLE IF NOT EXISTS vendors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phone VARCHAR(20) UNIQUE NOT NULL,
    pin_hash VARCHAR(255),  -- For 4-digit PIN auth without email
    name VARCHAR(255),
    vendor_type VARCHAR(50), -- e.g., chai, fruit, food, tailor, sabzi, other
    language VARCHAR(10) DEFAULT 'hi', -- 'hi' or 'en'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Daily Entries Table
CREATE TABLE IF NOT EXISTS daily_entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vendor_id UUID REFERENCES vendors(id) ON DELETE CASCADE,
    entry_date DATE NOT NULL DEFAULT CURRENT_DATE,
    audio_path TEXT,
    transcription TEXT,
    detected_language VARCHAR(10),
    items_sold JSONB DEFAULT '[]'::jsonb,
    expenses JSONB DEFAULT '[]'::jsonb,
    total_earned DECIMAL(10, 2) DEFAULT 0.0,
    total_spent DECIMAL(10, 2) DEFAULT 0.0,
    stockout_mentions JSONB DEFAULT '[]'::jsonb,
    mood_indicator VARCHAR(20),
    confidence_levels JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    -- No unique constraint: multiple recordings per day are allowed
);

-- 3. Pending Confirmations Table (for low-confidence items)
CREATE TABLE IF NOT EXISTS pending_confirmations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vendor_id UUID REFERENCES vendors(id) ON DELETE CASCADE,
    entry_id UUID REFERENCES daily_entries(id) ON DELETE CASCADE,
    item_name VARCHAR(255) NOT NULL,
    question_text VARCHAR(500) NOT NULL, -- e.g., "आपने केले का ज़िक्र किया — कितने बेचे?"
    status VARCHAR(20) DEFAULT 'pending', -- pending, resolved, discarded
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_at TIMESTAMP WITH TIME ZONE
);

-- 4. Vendor Insights Table
-- Stores pattern cards, stock suggestions, and anomaly alerts per vendor per day
CREATE TABLE IF NOT EXISTS vendor_insights (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vendor_id UUID REFERENCES vendors(id) ON DELETE CASCADE,
    insight_date DATE NOT NULL DEFAULT CURRENT_DATE,
    insight_type VARCHAR(50) NOT NULL, -- 'pattern', 'stock_suggestion', 'anomaly'
    content JSONB DEFAULT '[]'::jsonb,   -- list of insight strings or suggestion objects
    metrics JSONB DEFAULT '{}'::jsonb,   -- raw computed metrics
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(vendor_id, insight_date, insight_type)
);

-- 5. Audio Segments Table
CREATE TABLE IF NOT EXISTS audio_segments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vendor_id UUID REFERENCES vendors(id) ON DELETE CASCADE,
    entry_id UUID REFERENCES daily_entries(id) ON DELETE CASCADE,
    entity_type VARCHAR(50), -- e.g., 'items_sold', 'expenses'
    entity_name VARCHAR(255),
    start_ms INTEGER NOT NULL,
    end_ms INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Row Level Security (RLS) Policies
-- Note: Replace these with actual Supabase Auth checks if connecting from frontend directly.
-- Using simple stubs here for backend-only access (backend uses Service Key to bypass RLS).
ALTER TABLE vendors ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE pending_confirmations ENABLE ROW LEVEL SECURITY;
ALTER TABLE vendor_insights ENABLE ROW LEVEL SECURITY;
ALTER TABLE audio_segments ENABLE ROW LEVEL SECURITY;

-- If only the FastAPI backend accesses the DB using the Service Role Key, 
-- RLS policies are bypassed. If frontend accesses Supabase too, add policies here.

-- 6. WhatsApp Voice Ledger Table
CREATE TABLE IF NOT EXISTS ledger (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phone VARCHAR(32) NOT NULL,
    amount DECIMAL(12, 2) NOT NULL CHECK (amount > 0),
    type VARCHAR(10) NOT NULL CHECK (type IN ('income', 'expense')),
    category VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    audio_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ledger_phone_created_at
    ON ledger (phone, created_at DESC);

ALTER TABLE ledger ENABLE ROW LEVEL SECURITY;

-- Realtime setup for frontend dashboard updates.
ALTER TABLE ledger REPLICA IDENTITY FULL;

DO $$
BEGIN
    BEGIN
        ALTER PUBLICATION supabase_realtime ADD TABLE ledger;
    EXCEPTION
        WHEN duplicate_object THEN
            NULL;
    END;
END;
$$;
