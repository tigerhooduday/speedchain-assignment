# backend/services/time_utils.py
from datetime import datetime, timezone, timedelta
try:
    # Python 3.9+ zoneinfo (may require tzdata on some systems)
    from zoneinfo import ZoneInfo
    _HAS_ZONEINFO = True
except Exception:
    ZoneInfo = None
    _HAS_ZONEINFO = False

def now_ist_iso():
    """
    Return ISO timestamp string for current time in IST (Asia/Kolkata).
    Tries ZoneInfo("Asia/Kolkata") first; if not available, falls back to fixed +5:30 offset.
    """
    if _HAS_ZONEINFO and ZoneInfo is not None:
        try:
            ist = datetime.now(tz=ZoneInfo("Asia/Kolkata"))
            return ist.isoformat()
        except Exception:
            pass
    # fallback using fixed offset +05:30
    ist = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    return ist.isoformat()
