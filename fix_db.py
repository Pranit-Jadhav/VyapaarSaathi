"""
Run this once to fix the Supabase database:
1. Drop the duplicate key constraint on daily_entries
2. Drop and recreate the vendor_insights table with correct columns
"""
from supabase_config import get_supabase

def fix_database():
    supabase = get_supabase()
    
    print("Running database migration fixes...")

    # Fix 1: Drop unique constraint from daily_entries
    try:
        supabase.rpc("drop_unique_constraint").execute()
    except Exception:
        pass
    
    # We'll use raw SQL via the postgres extensions approach
    # Since we can't run raw DDL from the python client easily, print the SQL for the user
    sql = """
-- Run this in your Supabase SQL Editor to fix the schema:

-- 1. Drop the unique constraint on daily_entries
ALTER TABLE daily_entries DROP CONSTRAINT IF EXISTS daily_entries_vendor_id_entry_date_key;

-- 2. Drop and recreate vendor_insights with the correct columns used by our code
DROP TABLE IF EXISTS vendor_insights;
CREATE TABLE vendor_insights (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vendor_id UUID REFERENCES vendors(id) ON DELETE CASCADE,
    insight_date DATE NOT NULL DEFAULT CURRENT_DATE,
    insight_type VARCHAR(50) NOT NULL,
    content JSONB DEFAULT '[]'::jsonb,
    metrics JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(vendor_id, insight_date, insight_type)
);

-- 3. Keep RLS disabled for backend testing
ALTER TABLE daily_entries DISABLE ROW LEVEL SECURITY;
ALTER TABLE vendor_insights DISABLE ROW LEVEL SECURITY;

-- Done!
"""
    print(sql)
    print("\\n✅ Copy and paste the above SQL into Supabase SQL Editor and run it!")

if __name__ == "__main__":
    fix_database()
