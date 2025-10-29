# backend/services/email_service.py
import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path
import json
import datetime
from typing import Union, Dict, Any, Optional

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
SMTP_FILE = DATA_DIR / "smtp.json"

def load_smtp_config() -> Optional[Dict[str, Any]]:
    if not SMTP_FILE.exists():
        return None
    try:
        data = json.loads(SMTP_FILE.read_text(encoding="utf-8"))
        return data
    except Exception as e:
        print("Failed to read smtp.json:", e)
        return None

def _clean_header_value(s: Optional[str]) -> str:
    """Remove CR/LF from strings used as email headers and trim whitespace."""
    if s is None:
        return ""
    # remove any carriage returns or newlines
    return str(s).replace("\r", " ").replace("\n", " ").strip()

def _safe_booking_obj(booking: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Ensure booking is a dict. If it's a JSON string, parse it.
    Provide reasonable defaults for missing keys.
    """
    if isinstance(booking, str):
        try:
            booking = json.loads(booking)
        except Exception:
            booking = {"id": None, "patient_name": None, "doctor_name": None, "requested_slot": None, "note": str(booking)}
    if not isinstance(booking, dict):
        booking = {"id": None, "patient_name": None, "doctor_name": None, "requested_slot": None, "note": str(booking)}
    # Ensure keys exist and sanitize strings
    booking_id = booking.get("id")
    patient_name = _clean_header_value(booking.get("patient_name") or booking.get("patient") or "Patient")
    doctor_name = _clean_header_value(booking.get("doctor_name") or booking.get("doctor") or "Doctor")
    requested_slot = _clean_header_value(booking.get("requested_slot") or booking.get("slot") or "TBD")
    note = _clean_header_value(booking.get("note") or "")
    created_at_iso = booking.get("created_at_iso") or booking.get("created_at") or datetime.datetime.now().isoformat()
    # if created_at_iso is not string, stringify
    if not isinstance(created_at_iso, str):
        created_at_iso = str(created_at_iso)
    booking_safe = {
        "id": booking_id,
        "patient_name": patient_name,
        "doctor_name": doctor_name,
        "requested_slot": requested_slot,
        "note": note,
        "created_at_iso": created_at_iso
    }
    return booking_safe

def _build_plain_text(booking: Dict[str, Any], clinic_name: str) -> str:
    created_at = booking.get("created_at_iso") or datetime.datetime.now().isoformat()
    lines = [
        f"{clinic_name} — Appointment Confirmation",
        "",
        f"Booking ID: {booking.get('id')}",
        f"Patient name: {booking.get('patient_name')}",
        f"Doctor: {booking.get('doctor_name')}",
        f"Slot: {booking.get('requested_slot')}",
        f"Notes: {booking.get('note') or 'N/A'}",
        "",
        f"Created: {created_at}",
        "",
        "If you need to change or cancel, reply to this email or contact the clinic.",
        "",
        f"Thanks,\n{clinic_name} Team"
    ]
    return "\n".join(lines)

def _build_html(booking: Dict[str, Any], clinic_name: str, clinic_url: Optional[str] = None) -> str:
    created_at = booking.get("created_at_iso") or datetime.datetime.now().isoformat()
    # Minimal inline-styled HTML
    html = f"""
        <!doctype html>
        <html>
        <head>
        <meta charset="utf-8">
        <title>{clinic_name} — Appointment Confirmation</title>
        <meta name="viewport" content="width=device-width,initial-scale=1">
        </head>
        <body style="margin:0; padding:24px; background:linear-gradient(180deg,#eef2ff 0%, #fbfdfd 100%); font-family:Inter, system-ui, -apple-system, 'Segoe UI', Roboto, Arial, sans-serif; -webkit-font-smoothing:antialiased;">
        <center style="width:100%;">
            <div style="max-width:720px; width:100%; margin:0 auto;">
            <!-- Card -->
            <table role="presentation" cellspacing="0" cellpadding="0" style="width:100%; border-collapse:collapse;">
                <tr>
                <td style="padding:0;">
                    <div style="background:linear-gradient(90deg,#6d28d9 0%, #06b6d4 100%); border-radius:14px 14px 0 0; color:#fff; padding:20px 24px;">
                    <table role="presentation" width="100%" style="border-collapse:collapse;">
                        <tr>
                        <td style="vertical-align:middle;">
                            <h1 style="margin:0; font-size:20px; font-weight:700; letter-spacing:0.2px;">{clinic_name}</h1>
                            <p style="margin:6px 0 0 0; opacity:0.92; font-size:13px;">Appointment confirmed ✅</p>
                        </td>
                        <td style="vertical-align:middle; text-align:right; width:72px;">
                            <!-- friendly doctor icon -->
                            <svg width="56" height="56" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                            <rect width="24" height="24" rx="6" fill="rgba(255,255,255,0.12)"/>
                            <path d="M12 12a3 3 0 100-6 3 3 0 000 6z" fill="white"/>
                            <path d="M4 20c0-3.314 4.03-6 8-6s8 2.686 8 6" stroke="white" stroke-opacity="0.9" stroke-width="1.2" stroke-linecap="round"/>
                            </svg>
                        </td>
                        </tr>
                    </table>
                    </div>

                    <div style="background:#ffffff; padding:22px; border-radius:0 0 14px 14px; box-shadow:0 8px 30px rgba(15,23,42,0.06); color:#0f172a;">
                    <p style="margin:0 0 12px 0; font-size:15px;">Hello <strong>{booking.get('patient_name')}</strong>,</p>
                    <p style="margin:0 0 18px 0; color:#334155;">We're excited to see you — your appointment is all set. Below are the details.</p>

                    <!-- Details grid -->
                    <table role="presentation" cellspacing="0" cellpadding="0" style="width:100%; border-collapse:collapse; margin-bottom:18px; font-size:14px;">
                        <tr>
                        <td style="padding:10px; background:linear-gradient(90deg,#f8fafc, #ffffff); border-radius:10px; width:50%; vertical-align:top;">
                            <div style="color:#64748b; font-size:12px; margin-bottom:6px;">Booking ID</div>
                            <div style="font-weight:600;">{booking.get('id')}</div>
                        </td>
                        <td style="padding:10px; background:linear-gradient(90deg,#fff7ed, #fff); border-radius:10px; width:50%; vertical-align:top; margin-left:12px;">
                            <div style="color:#64748b; font-size:12px; margin-bottom:6px;">Doctor</div>
                            <div style="font-weight:600;">{booking.get('doctor_name')}</div>
                        </td>
                        </tr>
                        <tr style="height:10px;"><td colspan="2" style="height:10px;"></td></tr>
                        <tr>
                        <td style="padding:10px; background:linear-gradient(90deg,#effdf6, #ffffff); border-radius:10px; width:50%; vertical-align:top;">
                            <div style="color:#64748b; font-size:12px; margin-bottom:6px;">Slot</div>
                            <div style="font-weight:600;">{booking.get('requested_slot')}</div>
                        </td>
                        <td style="padding:10px; background:linear-gradient(90deg,#f0f9ff,#ffffff); border-radius:10px; width:50%; vertical-align:top;">
                            <div style="color:#64748b; font-size:12px; margin-bottom:6px;">Created</div>
                            <div style="font-weight:600;">{created_at}</div>
                        </td>
                        </tr>
                        <tr style="height:10px;"><td colspan="2" style="height:10px;"></td></tr>
                        <tr>
                        <td colspan="2" style="padding:10px; background:#fff; border-radius:10px;">
                            <div style="color:#64748b; font-size:12px; margin-bottom:6px;">Notes</div>
                            <div style="font-size:14px; color:#0f172a;">{booking.get('note') or 'N/A'}</div>
                        </td>
                        </tr>
                    </table>

                    <!-- CTA -->
                    <table role="presentation" cellspacing="0" cellpadding="0" style="width:100%; margin-bottom:6px;">
                        <tr>
                        <td style="padding-right:8px; vertical-align:middle;">
                            {"<a href='" + (clinic_url or "#") + "' style='display:inline-block; text-decoration:none; padding:12px 16px; background:linear-gradient(90deg,#10b981,#06b6d4); color:white; border-radius:10px; font-weight:600;'>🔎 View booking</a>" if clinic_url else ""}
                        </td>
                        <td style="text-align:right; vertical-align:middle;">
                            <a href="mailto:reply@clinic.example.com?subject=Reschedule%20Request%20-%20{booking.get('id')}" style="font-size:13px; color:#475569; text-decoration:none;">Need to reschedule?</a>
                        </td>
                        </tr>
                    </table>

                    <p style="margin:14px 0 0 0; color:#475569; font-size:13px;">If you have any questions, reply to this email or call the clinic. Please arrive 10 minutes early for paperwork, and bring any necessary documents or ID.</p>

                    <!-- small info / tips -->
                    <div style="margin-top:16px; padding:12px; border-radius:10px; background:linear-gradient(90deg,#fff,#fbfbff); border:1px solid rgba(99,102,241,0.06); font-size:13px; color:#475569;">
                        <strong style="display:inline-block; margin-right:8px;">Tip:</strong>
                        Wear comfortable clothing suitable for your appointment.
                    </div>
                    </div>

                    <!-- Footer -->
                    <div style="margin-top:12px; text-align:center; font-size:13px; color:#94a3b8;">
                    <div style="display:flex; gap:8px; align-items:center; justify-content:center; margin-bottom:8px;">
                        <span style="background:#eef2ff; color:#3730a3; padding:6px 10px; border-radius:20px; font-weight:600;">{clinic_name}</span>
                        <span style="color:#94a3b8;">•</span>
                        <span>Delivering care with a smile</span>
                    </div>
                    <div style="font-size:12px; color:#9ca3af;">{clinic_name} · <a href="#" style="color:#9ca3af; text-decoration:underline;">Contact</a> · <a href="#" style="color:#9ca3af; text-decoration:underline;">Privacy</a></div>
                    </div>

                    <!-- legal small -->
                    <div style="margin-top:8px; text-align:center; font-size:11px; color:#c7d2fe; opacity:0.9;">
                    <div style="padding:6px 10px; display:inline-block; border-radius:8px;">You received this email because you booked an appointment at {clinic_name}.</div>
                    </div>
                </td>
                </tr>
            </table>
            </div>
        </center>
        </body>
        </html>
        """
    return html

def _send_smtp_message(host: str, port: int, username: Optional[str], password: Optional[str],
                       use_tls: bool, msg: EmailMessage, timeout: int = 15) -> None:
    """
    Low-level SMTP sending. Raises exception on failure to bubble up meaningful message.
    """
    if use_tls:
        server = smtplib.SMTP(host, port, timeout=timeout)
        server.ehlo()
        server.starttls()
        server.ehlo()
    else:
        server = smtplib.SMTP(host, port, timeout=timeout)
    # login if credentials provided
    if username and password:
        server.login(username, password)
    server.send_message(msg)
    server.quit()

def send_confirmation_email_to_patient(to_email: str, booking: Union[str, Dict[str, Any]],
                                       clinic_name: str = "NovaCare Clinic",
                                       clinic_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Send a confirmation email. Returns a dict: {"ok": True} or {"ok": False, "error": "..."}.
    booking may be a dict or JSON string.
    """
    try:
        cfg = load_smtp_config()
        if not cfg:
            return {"ok": False, "error": "SMTP configuration not found (backend/data/smtp.json)"}

        booking_obj = _safe_booking_obj(booking)
        plain = _build_plain_text(booking_obj, clinic_name)
        html = _build_html(booking_obj, clinic_name, clinic_url=clinic_url)

        # Build EmailMessage and sanitize header fields
        msg = EmailMessage()
        subject_raw = f"{clinic_name} — Appointment confirmed (#{booking_obj.get('id')})"
        subject = _clean_header_value(subject_raw)
        msg["Subject"] = subject

        # From header: prefer explicit from_email in config; use formataddr to be safe
        cfg_from_raw = cfg.get("from_email") or cfg.get("username") or f"no-reply@{cfg.get('host','clinic')}"
        # if cfg_from_raw is like "Name <email@domain>" we should split safely
        # Try to parse naive form "Name <email>" else fallback
        try:
            if "<" in cfg_from_raw and ">" in cfg_from_raw:
                name_part = cfg_from_raw.split("<", 1)[0].strip().strip('"')
                email_part = cfg_from_raw.split("<", 1)[1].split(">", 1)[0].strip()
                from_header = formataddr(( _clean_header_value(name_part), _clean_header_value(email_part) ))
            else:
                # if raw is just email or just a name, sanitize accordingly
                if "@" in cfg_from_raw:
                    from_header = formataddr((clinic_name, _clean_header_value(cfg_from_raw)))
                else:
                    from_header = formataddr((_clean_header_value(cfg_from_raw), f"no-reply@{_clean_header_value(cfg.get('host','clinic'))}"))
        except Exception:
            from_header = _clean_header_value(cfg_from_raw)

        msg["From"] = from_header
        msg["To"] = _clean_header_value(to_email)

        # set plain and html parts
        msg.set_content(plain)
        msg.add_alternative(html, subtype="html")

        host = _clean_header_value(cfg.get("host") or "")
        port = int(cfg.get("port", 587))
        username = cfg.get("username")
        password = cfg.get("password")
        use_tls = bool(cfg.get("use_tls", True))

        # send
        try:
            _send_smtp_message(host=host, port=port, username=username, password=password,
                               use_tls=use_tls, msg=msg)
        except Exception as e:
            err_text = f"SMTP send failed: {e}"
            print(err_text)
            return {"ok": False, "error": err_text}

        return {"ok": True}
    except Exception as e:
        print("send_confirmation_email_to_patient error:", e)
        return {"ok": False, "error": str(e)}

# Backwards-compatible wrapper keeping old function name used in routes/booking.py
def send_confirmation_email(to_email: str, booking: Union[str, Dict[str, Any]], clinic_name: str = "NovaCare Clinic") -> bool:
    try:
        res = send_confirmation_email_to_patient(to_email, booking, clinic_name=clinic_name)
        return bool(res.get("ok"))
    except Exception as e:
        print("send_confirmation_email wrapper error:", e)
        return False
