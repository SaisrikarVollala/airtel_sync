"""
=============================================================================
AGENT: Sarvam AI Indic LLM & Speech SDK Client (sarvam_llm_client.py)
=============================================================================
Production Client for Sarvam AI Indic models:
- Chat & Extraction: `sarvam-105b-conversations`
- Speech-to-Text: `saaras:v3`
- Text-to-Speech: `bulbul:v3`

Raises explicit configuration errors if SARVAM_API_KEY is not configured
or if upstream API requests fail. No mock responses or fake success fallbacks.
=============================================================================
"""

import os
import requests
from pathlib import Path
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional

# Load .env from both project root and backend directory
FILE_PATH = Path(__file__).resolve()
ROOT_DIR = FILE_PATH.parent.parent.parent
BACKEND_DIR = FILE_PATH.parent.parent

load_dotenv(ROOT_DIR / ".env")
load_dotenv(BACKEND_DIR / ".env")
load_dotenv()

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "").strip()
SARVAM_CHAT_MODEL = os.getenv("SARVAM_CHAT_MODEL", "sarvam-105b-conversations")
SARVAM_STT_MODEL = os.getenv("SARVAM_STT_MODEL", "saaras:v3")
SARVAM_TTS_MODEL = os.getenv("SARVAM_TTS_MODEL", "bulbul:v3")


class SarvamLLMClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("SARVAM_API_KEY", "").strip() or SARVAM_API_KEY
        self.base_url = "https://api.sarvam.ai"

    def _ensure_api_key(self):
        if not self.api_key:
            self.api_key = os.getenv("SARVAM_API_KEY", "").strip()
        if not self.api_key:
            raise ValueError(
                "SARVAM_API_KEY is missing or empty. Please configure SARVAM_API_KEY in your environment/.env file."
            )

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.0,
        response_format: Optional[Dict[str, str]] = None
    ) -> str:
        """Sends chat messages to Sarvam AI LLM with given temperature."""
        self._ensure_api_key()

        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "api-subscription-key": self.api_key,
            "Content-Type": "application/json"
        }
        payload: Dict[str, Any] = {
            "model": model or SARVAM_CHAT_MODEL,
            "messages": messages,
            "temperature": temperature
        }
        if response_format:
            payload["response_format"] = response_format

        resp = requests.post(url, json=payload, headers=headers, timeout=25)
        if resp.status_code != 200:
            raise RuntimeError(
                f"Sarvam AI Chat API request failed with status code {resp.status_code}: {resp.text}"
            )
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    def speech_to_text(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        mime_type: str = "audio/wav"
    ) -> Dict[str, Any]:
        """Uploads audio stream to Sarvam Saaras:v3 STT engine."""
        self._ensure_api_key()

        clean_mime = (mime_type or "audio/wav").split(";")[0].strip()
        url = f"{self.base_url}/speech-to-text"
        headers = {"api-subscription-key": self.api_key}
        files = {"file": (filename, audio_bytes, clean_mime)}
        data = {"model": SARVAM_STT_MODEL, "with_diarization": "false"}

        resp = requests.post(url, headers=headers, files=files, data=data, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(
                f"Sarvam Speech-to-Text API request failed with status code {resp.status_code}: {resp.text}"
            )
        return resp.json()

    def text_to_speech(
        self,
        text: str,
        target_language_code: str = "en-IN",
        speaker: str = "kavya",
        model: Optional[str] = None
    ) -> Optional[str]:
        """
        Synthesizes text into natural voice audio using Sarvam bulbul:v3 model.
        Returns base64 encoded audio string or None if request fails.
        """
        self._ensure_api_key()
        if not text or not text.strip():
            return None

        # Clean text for TTS (limit to first 300 chars to ensure low latency)
        clean_text = text.strip()[:300]

        # Valid language codes for bulbul:v3
        valid_lang_codes = {
            "hi-IN", "te-IN", "ta-IN", "kn-IN", "ml-IN", "mr-IN",
            "bn-IN", "gu-IN", "od-IN", "pa-IN", "en-IN"
        }
        lang_code = target_language_code if target_language_code in valid_lang_codes else "en-IN"

        url = f"{self.base_url}/text-to-speech"
        headers = {
            "api-subscription-key": self.api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "inputs": [clean_text],
            "target_language_code": lang_code,
            "speaker": speaker,
            "model": model or SARVAM_TTS_MODEL
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                audios = data.get("audios", [])
                if audios and len(audios) > 0:
                    return audios[0]
            else:
                print(f"Warning: Sarvam TTS returned {resp.status_code}: {resp.text}")
        except Exception as ex:
            print(f"Warning: Sarvam TTS synthesis error: {ex}")

        return None


sarvam_llm_client = SarvamLLMClient()
