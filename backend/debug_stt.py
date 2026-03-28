import asyncio
import os
from services.stt_service import STTService

async def main():
    service = STTService()
    print(f"Client initialized: {service.client is not None}")
    
    # Create a dummy file for testing
    with open("test.wav", "wb") as f:
        f.write(b"dummy audio data")
    
    print("Testing transcription...")
    try:
        result = await service.transcribe("test.wav")
        print(f"Result: {result}")
    except Exception as e:
        print(f"UNCAUGHT ERROR: {e}")
    finally:
        if os.path.exists("test.wav"):
            os.remove("test.wav")

if __name__ == "__main__":
    asyncio.run(main())
