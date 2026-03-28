from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from db.database import get_db
from db import models

router = APIRouter()

@router.get("/pdf-data")
async def get_pdf_data(db: Session = Depends(get_db)):
    # This endpoint returns data for jsPDF to use on the frontend
    entries = db.query(models.LedgerEntry).order_by(models.LedgerEntry.created_at.desc()).limit(30).all()
    
    report_data = []
    for e in entries:
        report_data.append({
            "date": e.created_at.strftime("%Y-%m-%d"),
            "profit": e.total_profit,
            "sales_count": len(e.sales),
            "expenses_total": sum(ex.amount for ex in e.expenses)
        })
        
    return {
        "vendor_name": "Raju Bhai (Demo)",
        "report_period": "Last 30 Days",
        "total_earnings": sum(r["profit"] for r in report_data),
        "data": report_data
    }
