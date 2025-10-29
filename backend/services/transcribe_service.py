# backend/services/transcribe_service.py
"""
Transcription service with explicit, helpful error messages when OpenAI client is not available.
If OpenAI client (v1.x) is installed, uses the new client.
If not installed and faster-whisper is available, uses local transcription as fallback.
If neither is possible, returns a clear error instructing how to fix it.
"""

import io
import tempfile
from pathlib import Path
import json

OPENAI_CFG_FILE = Path(__file__).resolve().parents[2] / "data" / "openai.json"

def _load_openai_key():
    if OPENAI_CFG_FILE.exists():
        try:
            data = json.loads(OPENAI_CFG_FILE.read_text())
            return data.get("api_key")
        except Exception:
            return None
    return None

def _openai_client_available():
    try:
        # try new client import
        from openai import OpenAI  # type: ignore
        return True
    except Exception:
        return False

def transcribe_audio_bytes(file_bytes: bytes, filename_hint: str = "audio.webm"):
    """
    Strategy:
      1. If OpenAI key present and new client importable -> call new client audio transcription.
      2. Else if faster-whisper installed -> use local faster-whisper.
      3. Else return instructive error.
    Returns: {"ok": True, "text": "..."} or {"ok": False, "error": "..."}
    """
    key = _load_openai_key()
    if key and _openai_client_available():
        try:
            from openai import OpenAI  # type: ignore
            client = OpenAI(api_key=key)
            audio_file = io.BytesIO(file_bytes)
            audio_file.name = filename_hint
            # Use the new client's audio transcription interface
            resp = client.audio.transcriptions.create(model="whisper-1", file=audio_file)
            # the exact shape may vary; try common access patterns
            text = ""
            try:
                text = getattr(resp, "text", None) or (resp.get("text") if isinstance(resp, dict) else None)
            except Exception:
                text = None
            if not text:
                try:
                    # sometimes responses have choices or output_text
                    text = getattr(resp, "output_text", None) or str(resp)
                except Exception:
                    text = str(resp)
            return {"ok": True, "text": text}
        except Exception as e:
            # error when using new client
            return {"ok": False, "error": f"OpenAI transcription attempt failed: {e}. If you're using an older openai package, upgrade it with: pip install --upgrade 'openai>=1.0.0'."}

    # fallback: try faster-whisper (local)
    try:
        from faster_whisper import WhisperModel  # type: ignore
        import tempfile
        model_size = "small"
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename_hint).suffix) as tf:
            tf.write(file_bytes)
            tmp_path = tf.name
        segments, info = model.transcribe(tmp_path, beam_size=5)
        text_parts = [segment.text for segment in segments]
        text = " ".join(text_parts).strip()
        return {"ok": True, "text": text}
    except Exception as e_local:
        # final helpful instruction
        msg = (
            "No working transcription method available. Tried OpenAI client and local faster-whisper but both failed.\n\n"
            "To enable cloud transcription, install/upgrade OpenAI Python SDK (recommended):\n"
            "    pip install --upgrade 'openai>=1.0.0'\n\n"
            "Then add your OpenAI API key to data/openai.json:\n"
            '{ "api_key": "sk-REPLACE_WITH_YOUR_KEY" }\n\n'
            "Or, to use the older OpenAI SDK (legacy), pin to the old version:\n"
            "    pip install 'openai==0.28.1'\n\n"
            f"Details of local error: {e_local}"
        )
        return {"ok": False, "error": msg}
