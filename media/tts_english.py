import asyncio
import edge_tts
import os

class TTSEngine:
    default_voice = "en-US-ChristopherNeural"

    @staticmethod
    async def generate_audio(text: str, output_path: str, voice: str = None):
        """
        Generates high-quality English narration using edge-tts.
        """
        if not voice:
            voice = TTSEngine.default_voice
            
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)
        print(f"Audio saved to {output_path}")

if __name__ == "__main__":
    # Test generation
    text = "Breaking news: A major international event is unfolding right now. More updates will follow."
    output = "test_narration.mp3"
    asyncio.run(TTSEngine.generate_audio(text, output))
