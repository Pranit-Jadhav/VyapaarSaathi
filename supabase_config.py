import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Load local .env if it exists
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

from typing import Optional

supabase: Optional[Client] = None

if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"Error initializing Supabase client: {e}")
else:
    print("Warning: SUPABASE_URL or SUPABASE_KEY not set. Check your environment variables.")

def get_supabase() -> Client:
    """Returns the initialized Supabase client."""
    if not supabase:
        raise ValueError("Supabase client is not initialized. Make sure SUPABASE_URL and SUPABASE_KEY are provided.")
    return supabase
