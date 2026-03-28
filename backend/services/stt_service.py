import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class STTService:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)
        else:
            self.client = None

    async def transcribe(self, audio_path: str):
        if not self.client:
            return "Bhaiya, aaj 20 chai bechi 10 rupaye wali, aur 50 ka doodh liya."

        try:
            with open(audio_path, "rb") as audio_file:
                transcription = self.client.audio.transcriptions.create(
                    model="whisper-1", 
                    file=audio_file,
                    prompt="Street vendor narrating business sales in Hindi and English (Hinglish)."
                )
                return transcription.text
        except Exception as e:
            print(f"STT Error: {e}. Falling back to mock transcript.")
            return "Bhaiya, aaj 20 chai bechi 10 rupaye wali, aur 50 ka doodh liya."
