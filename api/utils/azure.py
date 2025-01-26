# api/utils/azure.py

import os
from openai import AzureOpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version="2024-06-01",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

def transcribe_audio(audio_file_path: str) -> str:
    """
    Transcribes audio using Azure OpenAI's Whisper model.
    """
    try:
        deployment_id = os.getenv('AZURE_OPENAI_WHISPER_DEPLOYMENT_ID')  # Your Whisper deployment name
        print(f"deployment_id: {deployment_id}")
        with open(audio_file_path, 'rb') as audio_file:
            transcript = client.audio.transcriptions.create(
                model=deployment_id,
                file=audio_file
            )
        return transcript.text
    except Exception as e:
        print(f"Error transcribing audio: {e}")
        return None
