from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
import os
from sqlalchemy.orm import Session
from services.groq_service import GroqService
from services.stt_service import STTService
from db.database import get_db
from db import models

router = APIRouter()
groq_service = GroqService()
stt_service = STTService()

class LedgerEntryResponse(BaseModel):
    ledger: dict
    feedback: dict

@router.post("/record", response_model=LedgerEntryResponse)
async def record_audio(file: UploadFile = File(...), db: Session = Depends(get_db)):
    # 1. Save temporary audio file
    temp_filename = f"temp_{file.filename}"
    with open(temp_filename, "wb") as buffer:
        buffer.write(await file.read())
    
    try:
        # 2. Transcribe using STT Service
        transcript = await stt_service.transcribe(temp_filename)
        
        # 3. Process with Groq LLM
        result = await groq_service.process_transcript(transcript)
        
        # 4. Save to Database
        # Extract data from LLM response
        ledger_data = result.get("ledger", {})
        feedback_data = result.get("feedback", {})
        
        db_entry = models.LedgerEntry(
            transcript=transcript,
            clarification_question=feedback_data.get("clarification_question"),
            anomaly_alert=feedback_data.get("anomaly_alert"),
            tomorrow_tip=feedback_data.get("tomorrow_tip"),
            total_profit=ledger_data.get("total_profit", 0)
        )
        db.add(db_entry)
        db.commit()
        db.refresh(db_entry)
        
        # Add Sales Items
        for item in ledger_data.get("sales", []):
            db_sale = models.SalesItem(
                ledger_id=db_entry.id,
                item=item.get("item"),
                qty=str(item.get("qty")),
                price=item.get("price"),
                uncertain=item.get("uncertain", False)
            )
            db.add(db_sale)
            
        # Add Expense Items
        for expense in ledger_data.get("expenses", []):
            db_expense = models.ExpenseItem(
                ledger_id=db_entry.id,
                type=expense.get("type"),
                amount=expense.get("amount")
            )
            db.add(db_expense)
            
        db.commit()
        
        # 5. Cleanup
        os.remove(temp_filename)
        
        return result
    except Exception as e:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/entries")
async def get_entries(db: Session = Depends(get_db)):
    entries = db.query(models.LedgerEntry).order_by(models.LedgerEntry.created_at.desc()).all()
    
    # Simple serialization for now
    result = []
    for e in entries:
        result.append({
            "id": e.id,
            "created_at": e.created_at,
            "total_profit": e.total_profit,
            "sales": [{"item": s.item, "qty": s.qty, "price": s.price, "uncertain": s.uncertain} for s in e.sales],
            "expenses": [{"type": ex.type, "amount": ex.amount} for ex in e.expenses],
            "feedback": {
                "clarification_question": e.clarification_question,
                "anomaly_alert": e.anomaly_alert,
                "tomorrow_tip": e.tomorrow_tip
            }
        })
    return {"entries": result}
