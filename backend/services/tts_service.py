# backend/services/tts_service.py
"""
TTS service. Prefer ElevenLabs if data/elevenlabs.json exists with {api_key, voice_id}.
Fallback to gTTS otherwise.
Returns base64-encoded mp3 audio.
"""

import io
import base64
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
ELEVEN_FILE = DATA_DIR / "elevenlabs.json"

def _load_eleven_cfg():
    if ELEVEN_FILE.exists():
        try:
            return json.loads(ELEVEN_FILE.read_text())
        except Exception:
            return None
    return None

def _eleven_available():
    cfg = _load_eleven_cfg()
    return cfg and cfg.get("api_key") and cfg.get("voice_id")

def _eleven_tts(text: str) -> dict:
    """
    Call ElevenLabs TTS API. Returns {"ok": True, "audio_base64": "..."} or {"ok": False, "error": "..."}
    """
    cfg = _load_eleven_cfg()
    if not cfg:
        return {"ok": False, "error": "No elevenlabs config"}
    api_key = cfg.get("api_key")
    voice_id = cfg.get("voice_id")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    try:
        import requests
        headers = {
            "xi-api-key": api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "text": text,
            "voice_settings": {
                "stability": 0.4,
                "similarity_boost": 0.75
            }
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        if resp.status_code != 200:
            return {"ok": False, "error": f"ElevenLabs TTS failed: {resp.status_code} {resp.text}"}
        audio_bytes = resp.content
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        return {"ok": True, "audio_base64": audio_b64}
    except Exception as e:
        return {"ok": False, "error": f"ElevenLabs request failed: {e}"}

def _gtts_tts(text: str, lang: str = "en") -> dict:
    try:
        from gtts import gTTS
        mp3_fp = io.BytesIO()
        tts = gTTS(text=text, lang=lang, slow=False)
        tts.write_to_fp(mp3_fp)
        mp3_fp.seek(0)
        audio_b64 = base64.b64encode(mp3_fp.read()).decode("utf-8")
        return {"ok": True, "audio_base64": audio_b64}
    except Exception as e:
        return {"ok": False, "error": f"gTTS failed: {e}"}

def text_to_speech_base64(text: str, lang: str = "en") -> dict:
    # prefer ElevenLabs if configured
    if _eleven_available():
        r = _eleven_tts(text)
        if r.get("ok"):
            return r
        # otherwise fall back to gTTS
    return _gtts_tts(text, lang=lang)
