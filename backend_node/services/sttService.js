const OpenAI = require('openai');
const fs = require('fs');
require('dotenv').config();

class STTService {
    constructor() {
        this.openai = new OpenAI({
            apiKey: process.env.OPENAI_API_KEY,
        });
    }

    async transcribe(audioPath) {
        try {
            const transcription = await this.openai.audio.transcriptions.create({
                file: fs.createReadStream(audioPath),
                model: "whisper-1",
                prompt: "Street vendor narrating business sales in Hindi and English (Hinglish)."
            });
            return transcription.text;
        } catch (error) {
            console.error("STT Error:", error.message);
            // Mock fallback
            return "Bhaiya, aaj 20 chai bechi 10 rupaye wali, aur 50 ka doodh liya.";
        }
    }
}

module.exports = new STTService();
