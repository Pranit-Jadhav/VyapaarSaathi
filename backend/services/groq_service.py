import os
from groq import Groq
import json
from dotenv import load_dotenv

load_dotenv()

class GroqService:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        if self.api_key:
            self.client = Groq(api_key=self.api_key)
        else:
            self.client = None

    async def process_transcript(self, transcript: str):
        if not self.client:
            return self._mock_response(transcript)

        system_prompt = """
        ### ROLE
        You are a Business Auditor for Indian street vendors. Your goal is to extract a structured ledger from informal "Hinglish" transcripts.

        ### RULES
        1. Extract: Items Sold (Qty, Price), Expenses (Category, Amount), and Net Cash.
        2. If a value is missing (e.g., "Sold apples" but no price), set value to null and "uncertain": true.
        3. Compare today's data to history: If expenses are 2x higher than usual, flag an "Anomaly." (Assume history is okay for now).
        4. Generate a 1-line "Next-Day Suggestion" in simple Hinglish.

        ### OUTPUT FORMAT (STRICT JSON)
        {
          "ledger": {
            "sales": [{"item": "string", "qty": "string", "price": number, "uncertain": boolean}],
            "expenses": [{"type": "string", "amount": number}],
            "total_profit": number
          },
          "feedback": {
            "clarification_question": "string (e.g., Bhaiya, tamatar kitne ke beche?)",
            "anomaly_alert": "string | null",
            "tomorrow_tip": "string"
          }
        }
        """
        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": transcript}
                ],
                model="llama3-70b-8192",
                response_format={"type": "json_object"}
            )
            return json.loads(chat_completion.choices[0].message.content)
        except Exception as e:
            print(f"Groq Error: {e}. Falling back to mock response.")
            return self._mock_response(transcript)

    def _mock_response(self, transcript: str):
        return {
            "ledger": {
                "sales": [{"item": "Mock Item", "qty": "10", "price": 100, "uncertain": False}],
                "expenses": [{"type": "Mock Expense", "amount": 20}],
                "total_profit": 80
            },
            "feedback": {
                "clarification_question": "Bhaiya, sab sahi hai?",
                "anomaly_alert": None,
                "tomorrow_tip": "Kal thoda zyada doodh lena."
            }
        }
