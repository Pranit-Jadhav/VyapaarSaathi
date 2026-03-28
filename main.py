import os
import uuid
import datetime
import tempfile
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List

from supabase_config import get_supabase
from transcription_service import transcribe_audio
from extraction_service import extract_data_from_transcript
from analytics_service import generate_insights
from stock_service import generate_stock_suggestions
from anomaly_service import detect_anomalies
from scheduler import start_scheduler, stop_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()

app = FastAPI(
    title="VyapaarSaathi API",
    description="Backend for the VyapaarSaathi app.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

WEB_APP_PATH = Path(__file__).resolve().parent / "web" / "index.html"
WEB_DIR = Path(__file__).resolve().parent / "web"

app.mount("/web", StaticFiles(directory=str(WEB_DIR)), name="web")

@app.get("/")
def read_root():
    """Serves the production web client."""
    try:
        return HTMLResponse(WEB_APP_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading web app: {e}")

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "VyapaarSaathi API"}

@app.post("/record")
async def upload_record(audio: UploadFile = File(...), vendor_id: str = Form(...)):
    """
    Receives an audio file, transcribes it, extracts structured data,
    saves the audio to Supabase Storage, and inserts the data into the database.
    """
    supabase = get_supabase()
    
    suffix = os.path.splitext(audio.filename)[1] if audio.filename else ".webm"
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await audio.read()
            tmp.write(content)
            tmp_path = tmp.name
            
        # Transcribe & Extract
        transcription_result = transcribe_audio(tmp_path)
        transcript = transcription_result["text"]
        detected_language = transcription_result["language"]
        
        extracted_data = extract_data_from_transcript(transcript)
        
        # Audio Upload
        date_str = datetime.date.today().isoformat()
        storage_path = f"{vendor_id}/{date_str}/{uuid.uuid4()}{suffix}"
        
        try:
            with open(tmp_path, "rb") as f:
                # Ensure the bucket 'audio_records' is created in Supabase
                supabase.storage.from_("audio_records").upload(storage_path, f.read())
        except Exception as e:
            print("Warning: Storage upload failed. Is the 'audio_records' bucket created? Error:", e)
            storage_path = None
            
        # Insert Data
        entry_data = {
            "vendor_id": vendor_id,
            "entry_date": date_str,
            "audio_path": storage_path,
            "transcription": transcript,
            "detected_language": detected_language,
            "items_sold": extracted_data.get("items_sold", []),
            "expenses": extracted_data.get("expenses", []),
            "total_earned": extracted_data.get("total_earned", 0),
            "total_spent": extracted_data.get("total_spent", 0),
            "stockout_mentions": extracted_data.get("stockout_mentions", []),
            "mood_indicator": extracted_data.get("mood_indicator", "neutral")
        }
        
        db_res = supabase.table("daily_entries").insert(entry_data).execute()
        os.remove(tmp_path)
        
        return JSONResponse({"status": "success", "data": db_res.data[0] if db_res.data else entry_data})
    except Exception as e:
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/entries")
def get_entries(vendor_id: str, limit: int = 7):
    """Fetches the latest entries for a vendor."""
    supabase = get_supabase()
    try:
        res = supabase.table("daily_entries").select("*").eq("vendor_id", vendor_id).order("entry_date", desc=True).limit(limit).execute()
        return {"entries": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/insights")
def get_insights(vendor_id: str, refresh: bool = False):
    """Returns analytics insights. Set ?refresh=true to recompute on the fly."""
    supabase = get_supabase()
    if refresh:
        result = generate_insights(vendor_id, supabase)
        anomalies = detect_anomalies(vendor_id, supabase)
        return {"patterns": result.get("insights", []), "metrics": result.get("metrics", {}), "alerts": anomalies.get("alerts", [])}
    try:
        res = (
            supabase.table("vendor_insights")
            .select("*")
            .eq("vendor_id", vendor_id)
            .in_("insight_type", ["pattern", "anomaly"])
            .order("insight_date", desc=True)
            .limit(10)
            .execute()
        )
        return {"insights": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/suggestions")
def get_stock_suggestions(vendor_id: str, lat: float = 19.0760, lon: float = 72.8777, refresh: bool = False):
    """Returns tomorrow's stock suggestions. Set ?refresh=true to recompute with latest weather."""
    supabase = get_supabase()
    if refresh:
        return generate_stock_suggestions(vendor_id, supabase, lat, lon)
    try:
        res = (
            supabase.table("vendor_insights")
            .select("*")
            .eq("vendor_id", vendor_id)
            .eq("insight_type", "stock_suggestion")
            .order("insight_date", desc=True)
            .limit(1)
            .execute()
        )
        if res.data:
            return {"suggestions": res.data[0].get("content", []), "weather": res.data[0].get("metrics", {}).get("weather", {})}
        return generate_stock_suggestions(vendor_id, supabase, lat, lon)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/score")
def get_loan_score(vendor_id: str):
    return {"score": 0, "eligible_schemes": []}

@app.get("/pdf")
def generate_pdf_data(vendor_id: str):
    return {"vendor_name": "", "total_earned": 0, "daily_breakdown": []}

class ConfirmationItem(BaseModel):
    item_name: str
    quantity: Optional[int] = None
    unknown: bool = False

@app.post("/confirm")
def confirm_entry(vendor_id: str, entry_id: str, confirmations: List[ConfirmationItem]):
    return {"status": "confirmed"}
