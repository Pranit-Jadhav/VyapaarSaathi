const Groq = require('groq-sdk');
require('dotenv').config();

class GroqService {
    constructor() {
        this.groq = new Groq({
            apiKey: process.env.GROQ_API_KEY,
        });
    }

    async processTranscript(transcript) {
        const systemPrompt = `
        ### ROLE
        You are a Business Auditor for Indian street vendors. Your goal is to extract a structured ledger from informal "Hinglish" transcripts.

        ### RULES
        1. Extract: Items Sold (Qty, Price), Expenses (Category, Amount), and Net Cash.
        2. If a value is missing (e.g., "Sold apples" but no price), set value to null and "uncertain": true.
        3. Compare today's data to history: If expenses are 2x higher than usual, flag an "Anomaly."
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
        `;

        try {
            const chatCompletion = await this.groq.chat.completions.create({
                messages: [
                    { role: "system", content: systemPrompt },
                    { role: "user", content: transcript }
                ],
                model: "llama3-70b-8192",
                response_format: { type: "json_object" }
            });
            return JSON.parse(chatCompletion.choices[0].message.content);
        } catch (error) {
            console.error("Groq Error:", error.message);
            return this._getMockResponse(transcript);
        }
    }

    _getMockResponse(transcript) {
        return {
            ledger: {
                sales: [{ item: "Mock Item", qty: "10", price: 100, uncertain: false }],
                expenses: [{ type: "Mock Expense", amount: 20 }],
                total_profit: 80
            },
            feedback: {
                clarification_question: "Bhaiya, sab sahi hai?",
                anomaly_alert: null,
                tomorrow_tip: "Kal thoda zyada doodh lena."
            }
        };
    }
}

module.exports = new GroqService();
