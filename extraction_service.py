import os
import json
from groq import Groq

_client = None

def get_groq_client():
    global _client
    if _client is None:
        _client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    return _client

SYSTEM_PROMPT = """
You are a highly accurate Hinglish data extractor for VyapaarSaathi, an app for Indian street vendors.
Your task is to read the transcript of a vendor's voice note and extract the sales, expenses, and mood.
Important: Keep item/expense names in the same language form used in transcript (Hindi/Hinglish). Do not translate labels to English.
Return ONLY a valid JSON object with the following schema:
{
    "items_sold": [{"item_name": "string", "quantity": "integer or null", "confidence": "high|medium|low"}],
    "expenses": [{"item_name": "string", "amount": "number or null", "confidence": "high|medium|low"}],
    "total_earned": "number based on mentioned earnings, 0 if none",
    "total_spent": "number based on expenses, 0 if none",
    "stockout_mentions": ["list of strings for items running out"],
    "mood_indicator": "good|neutral|bad"
}

Examples:
Transcript: "Aaj 50 cup chai bechi. 200 rupaye ki shakkar aayi. Doodh khatam ho gaya hai. Mood theek hai."
JSON:
{
    "items_sold": [{"item_name": "chai", "quantity": 50, "confidence": "high"}],
    "expenses": [{"item_name": "shakkar", "amount": 200, "confidence": "high"}],
    "total_earned": 0,
    "total_spent": 200,
    "stockout_mentions": ["doodh"],
    "mood_indicator": "good"
}

Transcript: "Aaj kuch khaas dhanda nahi hua. bas 12 kele bike. 50 rupaye ka auto bhada laga."
JSON:
{
    "items_sold": [{"item_name": "kele", "quantity": 12, "confidence": "high"}],
    "expenses": [{"item_name": "auto bhada", "amount": 50, "confidence": "high"}],
    "total_earned": 0,
    "total_spent": 50,
    "stockout_mentions": [],
    "mood_indicator": "bad"
}
"""

def extract_data_from_transcript(transcript: str) -> dict:
    """
    Uses Llama 3 via Groq API to extract structured data from a Hindi/Hinglish transcript.
    """
    client = get_groq_client()
    
    response = client.chat.completions.create(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Transcript: '{transcript}'"}
        ],
        model="llama-3.3-70b-versatile",
        temperature=0,
        response_format={"type": "json_object"}
    )
    
    content = response.choices[0].message.content
    try:
        data = json.loads(content)
        return data
    except json.JSONDecodeError:
        print("Failed to parse JSON from Groq:", content)
        return {
            "items_sold": [],
            "expenses": [],
            "total_earned": 0,
            "total_spent": 0,
            "stockout_mentions": [],
            "mood_indicator": "neutral"
        }
