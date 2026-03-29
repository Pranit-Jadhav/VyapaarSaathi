import os
from dataclasses import dataclass
from functools import lru_cache
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()


def _to_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_whatsapp_number: str
    groq_api_key: str
    supabase_url: str
    supabase_key: str
    supabase_service_role_key: str
    groq_llm_model: str
    groq_whisper_model: str
    ffmpeg_binary: str
    validate_twilio_signature: bool
    enable_weekly_summary: bool
    enable_weekly_summary_tts: bool
    enable_instant_stock_alerts: bool
    instant_stock_alert_interval_seconds: int
    instant_stock_alert_units_threshold: int
    instant_stock_alert_recipients: str

    def missing_required(self) -> List[str]:
        missing: List[str] = []
        required = {
            "TWILIO_ACCOUNT_SID": self.twilio_account_sid,
            "TWILIO_AUTH_TOKEN": self.twilio_auth_token,
            "TWILIO_WHATSAPP_NUMBER": self.twilio_whatsapp_number,
            "GROQ_API_KEY": self.groq_api_key,
            "SUPABASE_URL": self.supabase_url,
        }
        for key, value in required.items():
            if not value:
                missing.append(key)
        if not (self.supabase_service_role_key or self.supabase_key):
            missing.append("SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY")
        return missing


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        twilio_account_sid=os.getenv("TWILIO_ACCOUNT_SID", ""),
        twilio_auth_token=os.getenv("TWILIO_AUTH_TOKEN", ""),
        twilio_whatsapp_number=os.getenv("TWILIO_WHATSAPP_NUMBER", ""),
        groq_api_key=os.getenv("GROQ_API_KEY", ""),
        supabase_url=os.getenv("SUPABASE_URL", ""),
        supabase_key=os.getenv("SUPABASE_KEY", ""),
        supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
        groq_llm_model=os.getenv("GROQ_LLM_MODEL", "llama-3.3-70b-versatile"),
        groq_whisper_model=os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo"),
        ffmpeg_binary=os.getenv("FFMPEG_BINARY", "ffmpeg"),
        validate_twilio_signature=_to_bool(os.getenv("TWILIO_VALIDATE_SIGNATURE"), default=True),
        enable_weekly_summary=_to_bool(os.getenv("ENABLE_WEEKLY_SUMMARY"), default=False),
        enable_weekly_summary_tts=_to_bool(os.getenv("ENABLE_WEEKLY_SUMMARY_TTS"), default=False),
        enable_instant_stock_alerts=_to_bool(os.getenv("ENABLE_INSTANT_STOCK_ALERTS"), default=True),
        instant_stock_alert_interval_seconds=max(
            30,
            int(os.getenv("INSTANT_STOCK_ALERT_INTERVAL_SECONDS", "60") or "60"),
        ),
        instant_stock_alert_units_threshold=max(
            1,
            int(os.getenv("INSTANT_STOCK_ALERT_UNITS_THRESHOLD", "20") or "20"),
        ),
        instant_stock_alert_recipients=os.getenv("INSTANT_STOCK_ALERT_RECIPIENTS", ""),
    )


def ensure_required_settings() -> None:
    missing = get_settings().missing_required()
    if missing:
        raise RuntimeError(
            "Missing required environment variables: " + ", ".join(sorted(missing))
        )
