from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.database import get_db
from db import models
from services.groq_service import GroqService
from datetime import datetime, timedelta

router = APIRouter()
groq_service = GroqService()

@router.get("/insights")
async def get_insights(db: Session = Depends(get_db)):
    # Fetch last 7 days of entries
    seven_days_ago = datetime.now() - timedelta(days=7)
    entries = db.query(models.LedgerEntry).filter(models.LedgerEntry.created_at >= seven_days_ago).all()
    
    if len(entries) < 1:
        return {"insights": ["Not enough data yet. Record at least one day."], "suggestions": []}
    
    # Prepare data for LLM
    summary_text = "Here are the last 7 days of business data:\n"
    for e in entries:
        summary_text += f"- Date: {e.created_at.date()}, Profit: {e.total_profit}\n"
        for s in e.sales:
            summary_text += f"  - Sold: {s.item}, Qty: {s.qty}, Price: {s.price}\n"
            
    # Use Groq to generate a few-line summary
    prompt = f"""
    Based on the following 7-day business data, generate 3 short, helpful insights in Hinglish for a street vendor.
    Also generate 1-2 stock suggestions for tomorrow.
    Data:
    {summary_text}
    
    Format: JSON
    {{ "insights": ["line1", "line2", "line3"], "suggestions": ["item1", "item2"] }}
    """
    
    try:
        # In a real app, I'd add a method to groq_service for this, but for now:
        if not groq_service.client:
            return {
                "insights": ["Aaj ka kaam badhiya raha!", "Chai ki bikri badh rahi hai.", "Kharche thode kam karein."],
                "suggestions": ["Kal 5 liter extra doodh lein.", "Samosa ka stock badha dein."]
            }
            
        chat_completion = groq_service.client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama3-7b-8192", # Using a smaller model for faster insights
            response_format={"type": "json_object"}
        )
        import json
        return json.loads(chat_completion.choices[0].message.content)
    except Exception as e:
        return {"error": str(e)}
