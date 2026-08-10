import os
import tempfile
import requests

from dotenv import load_dotenv
from groq import Groq

from backend.config import CARTESIA_API_KEY


load_dotenv()


# -----------------------------
# GROQ WHISPER CLIENT
# -----------------------------

groq_client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)


# -----------------------------
# CARTESIA CONFIG
# -----------------------------

CARTESIA_VOICE_ID = (
    "a167e0f3-df7e-4d52-a9c3-f949145efdab"
)



# -----------------------------
# SPEECH TO TEXT
# -----------------------------

def speech_to_text(audio_bytes):
    """
    Convert microphone audio into text
    using Groq Whisper.
    """


    with tempfile.NamedTemporaryFile(
        suffix=".wav",
        delete=False
    ) as audio_file:

        audio_file.write(
            audio_bytes
        )

        audio_path = audio_file.name



    with open(
        audio_path,
        "rb"
    ) as file:


        response = groq_client.audio.transcriptions.create(
            file=file,
            model="whisper-large-v3-turbo",
            response_format="text"
        )


    os.remove(
        audio_path
    )


    return response.strip()



# -----------------------------
# TEXT TO SPEECH
# -----------------------------

def text_to_speech(text):
    """
    Convert assistant response into
    natural voice using Cartesia.
    """

    if not CARTESIA_API_KEY:
        raise ValueError("CARTESIA_API_KEY is not configured.")

    url = "https://api.cartesia.ai/tts/bytes"

    headers = {
        "X-API-Key": CARTESIA_API_KEY,
        "Cartesia-Version": "2025-04-16",
        "Content-Type": "application/json",
    }

    payload = {
        "model_id": "sonic-3.5",
        "transcript": text,
        "voice": {
            "mode": "id",
            "id": CARTESIA_VOICE_ID,
        },
        "output_format": {
            "container": "wav",
            "encoding": "pcm_s16le",
            "sample_rate": 44100,
        },
    }



    response = requests.post(

        url,

        headers=headers,

        json=payload,

        timeout=60

    )


    if response.status_code != 200:

        raise Exception(
            f"Cartesia Error: {response.text}"
        )


    return response.content
