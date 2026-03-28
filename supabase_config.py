import logging
import os

from dotenv import load_dotenv
from supabase import Client, create_client

# Load local .env if it exists
load_dotenv()

from typing import Optional

supabase: Optional[Client] = None
logger = logging.getLogger(__name__)


def _init_supabase_client() -> Client:
    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    supabase_key = service_role_key or os.getenv("SUPABASE_KEY", "").strip()

    if not supabase_url or not supabase_key:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY/SUPABASE_KEY must be set.")

    if not service_role_key:
        logger.warning(
            "SUPABASE_SERVICE_ROLE_KEY is not set. Inserts may fail if RLS blocks SUPABASE_KEY."
        )

    return create_client(supabase_url, supabase_key)

def get_supabase() -> Client:
    """Returns the initialized Supabase client."""
    global supabase
    if supabase is None:
        supabase = _init_supabase_client()
    return supabase
