// src/components/AssistantButton.jsx
import React, { useEffect, useRef, useState } from "react";
import axios from "axios";
import "./AssistantButton.css"; // ensure you have styles, user provided earlier

const API_BASE = "http://localhost:8000/api";

function new_uuid() {
  return Math.random().toString(36).slice(2, 10);
}

async function typeTextReplay(text, onUpdate, speed = 8) {
  let acc = "";
  for (let i = 0; i < text.length; i++) {
    acc += text[i];
    onUpdate(acc);
    await new Promise((r) => setTimeout(r, speed));
  }
}

export default function AssistantButton() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([
    { id: new_uuid(), from: "bot", text: "Hi — I'm Astra. Click & hold Record or type to book an appointment.", time: new Date() },
  ]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState(localStorage.getItem("astra_session_id") || null);
  const [thinking, setThinking] = useState(false);
  const [recording, setRecording] = useState(false);
  const [recordStartAt, setRecordStartAt] = useState(null);

  const [suggestion, setSuggestion] = useState(null);
  const [showBookingModal, setShowBookingModal] = useState(false);
  const [doctorsList, setDoctorsList] = useState([]);
  const [selectedDoctorId, setSelectedDoctorId] = useState(null);
  const [selectedSlot, setSelectedSlot] = useState("");
  const [patientName, setPatientName] = useState(localStorage.getItem("astra_patient_name") || "");
  const [patientEmail, setPatientEmail] = useState(localStorage.getItem("astra_patient_email") || "");
  const [toast, setToast] = useState(null);

  const mediaRecorderRef = useRef(null);
  const recordedRef = useRef([]);
  const messagesEl = useRef(null);
  const recordingPlaceholderIdRef = useRef(null);

  useEffect(() => {
    if (!sessionId) {
      const id = new_uuid();
      setSessionId(id);
      localStorage.setItem("astra_session_id", id);
    }
  }, []);

  useEffect(() => {
    if (messagesEl.current) {
      messagesEl.current.scrollTop = messagesEl.current.scrollHeight + 300;
    }
  }, [messages, thinking, showBookingModal, toast]);

  function appendMessage(from, text) {
    setMessages((prev) => [...prev, { id: new_uuid(), from, text, time: new Date() }]);
  }
  function replaceLastBotText(text) {
    setMessages((prev) => {
      const arr = [...prev];
      for (let i = arr.length - 1; i >= 0; i--) {
        if (arr[i].from === "bot") {
          arr[i] = { ...arr[i], text, time: new Date() };
          return arr;
        }
      }
      arr.push({ id: new_uuid(), from: "bot", text, time: new Date() });
      return arr;
    });
  }

  function setRecordingPlaceholder(text = "Recording...") {
    if (recordingPlaceholderIdRef.current) {
      const pid = recordingPlaceholderIdRef.current;
      setMessages((prev) => prev.map(m => m.id === pid ? { ...m, text, time: new Date() } : m));
    } else {
      const id = new_uuid();
      recordingPlaceholderIdRef.current = id;
      setMessages((prev) => [...prev, { id, from: "bot", text, time: new Date() }]);
    }
  }
  function clearRecordingPlaceholder() {
    const pid = recordingPlaceholderIdRef.current;
    if (!pid) return;
    setMessages((prev) => prev.filter(m => m.id !== pid));
    recordingPlaceholderIdRef.current = null;
  }

  function toggleOpen() { setOpen(v => !v); }

  // Hold-to-record
  const MIN_HOLD_MS = 200;

  async function startRecordingHold() {
    recordedRef.current = [];
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      let options = {};
      try {
        if (MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) {
          options = { mimeType: "audio/webm;codecs=opus" };
        } else if (MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported("audio/webm")) {
          options = { mimeType: "audio/webm" };
        } else {
          options = {};
        }
      } catch (e) {
        options = {};
      }
      const mr = new MediaRecorder(stream, options);
      mediaRecorderRef.current = mr;

      mr.ondataavailable = (e) => {
        if (e.data && e.data.size) recordedRef.current.push(e.data);
      };

      mr.onstop = async () => {
        try { stream.getTracks().forEach(t => t.stop()); } catch (err) {}
        const heldMs = Date.now() - (recordStartAt || Date.now());
        setRecordStartAt(null);
        setRecording(false);
        setThinking(false);

        const blob = new Blob(recordedRef.current, { type: recordedRef.current.length ? recordedRef.current[0].type || 'audio/webm' : 'audio/webm' });

        clearRecordingPlaceholder();

        if (!blob || !blob.size || blob.size === 0) {
          showTemporaryToast({ title: "No audio recorded", text: "Hold the record button longer or allow microphone access." }, 2200);
          return;
        }

        if (heldMs < MIN_HOLD_MS && blob.size < 1000) {
          showTemporaryToast({ title: "No audio recorded", text: "Hold the button longer to record speech." }, 2200);
          return;
        }

        await handleAudioBlob(blob);
      };

      mr.start();
      setRecording(true);
      setRecordStartAt(Date.now());
      setThinking(true);
      setRecordingPlaceholder("Recording...");
    } catch (e) {
      console.error("mic error", e);
      replaceLastBotText("Microphone access denied or not available.");
      setRecording(false);
      setThinking(false);
      setRecordStartAt(null);
      clearRecordingPlaceholder();
    }
  }

  function stopRecordingHold() {
    const mr = mediaRecorderRef.current;
    if (mr && mr.state !== "inactive") {
      try { mr.stop(); } catch (e) { console.warn(e); }
    } else {
      setRecording(false);
      setThinking(false);
      setRecordStartAt(null);
      clearRecordingPlaceholder();
    }
  }

  function onRecordPointerDown(e) { e.preventDefault(); startRecordingHold(); }
  function onRecordPointerUp(e) { e.preventDefault(); stopRecordingHold(); }
  function onRecordPointerCancel(e) {
    e.preventDefault();
    const mr = mediaRecorderRef.current;
    if (mr && mr.state !== "inactive") {
      try { mr.stop(); } catch (ex) {}
    }
    setRecording(false);
    setThinking(false);
    setRecordStartAt(null);
    clearRecordingPlaceholder();
  }

  async function handleAudioBlob(blob) {
    appendMessage("user", "[voice message]");
    const fd = new FormData();
    fd.append("file", blob, "speech.webm");
    try {
      const r = await axios.post(`${API_BASE}/voice/transcribe`, fd, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 120000 });
      if (r.data && (r.data.ok || r.data.text || r.data.transcript)) {
        const text = (r.data.text || r.data.transcript || "").trim();
        appendMessage("bot", `Transcription: "${text}"`);
        if (!text) {
          appendMessage("bot", "I couldn't hear that clearly — please hold and speak again.");
          return;
        }
        await sendConverse(text);
      } else {
        appendMessage("bot", "Transcription failed: " + (r.data && r.data.error ? r.data.error : "unknown"));
      }
    } catch (e) {
      console.error(e);
      appendMessage("bot", "Transcription error.");
    }
  }

  // Conversation
  async function sendConverse(text) {
    try {
      appendMessage("user", text);
      setThinking(true);
      appendMessage("bot", ""); // placeholder
      setSuggestion(null);

      const res = await axios.post(`${API_BASE}/voice/converse`, { session_id: sessionId, text }, { timeout: 120000 });
      setThinking(false);

      if (res.data && res.data.session_id) {
        setSessionId(res.data.session_id);
        localStorage.setItem("astra_session_id", res.data.session_id);
      }

      let serverReply = "";
      if (res.data && res.data.error) {
        console.warn("Server error field:", res.data.error);
        serverReply = "Sorry — I couldn't process that. Could you say it again?";
      } else if (res.data && (res.data.reply !== undefined && res.data.reply !== null)) {
        serverReply = String(res.data.reply);
        if (serverReply.trim() === "" && res.data.ok) serverReply = "Okay.";
      } else if (res.data && res.data.ok) {
        serverReply = "Okay.";
      } else {
        serverReply = "Sorry — server error.";
      }

      await typeTextReplay(serverReply, replaceLastBotText, 8);

      if (res.data && res.data.audio_base64) {
        try {
          const audio = new Audio("data:audio/mp3;base64," + res.data.audio_base64);
          audio.play().catch(() => {});
        } catch (e) {
          console.warn("audio play failed", e);
        }
      }

      // If backend returned doctors, open booking modal and prefill
      if (res.data && res.data.doctors && Array.isArray(res.data.doctors)) {
        try {
          const docs = res.data.doctors;
          setDoctorsList(docs);
          if (docs.length > 0) {
            setSelectedDoctorId(docs[0].id);
            setSelectedSlot(docs[0].available_slots && docs[0].available_slots.length > 0 ? docs[0].available_slots[0] : "");
          }
        } catch (err) {
          console.warn("apply doctors failed", err);
        }
        setShowBookingModal(true);
      }

      // open booking modal if backend expects patient info
      if (res.data && res.data.expect === "ask_patient_info") {
        if ((!doctorsList || doctorsList.length === 0)) {
          try {
            const docsRes = await axios.get(`${API_BASE}/doctors`);
            setDoctorsList(docsRes.data || []);
          } catch (err) {
            console.warn("failed to load doctors list", err);
          }
        }
        setShowBookingModal(true);
      }

      // heuristics: also open booking form when assistant suggests specialty lines
      const low = serverReply.toLowerCase();
      if (!res.data?.doctors && (low.includes("suggest") || low.includes("we have:") || low.includes("i suggest") || low.includes("based on that"))) {
        // try to extract a specialty and fetch doctors
        let specialty = null;
        const suggestMatch = serverReply.match(/suggest\s+([A-Za-z\s]+)/i);
        if (suggestMatch && suggestMatch[1]) specialty = suggestMatch[1].trim();
        const known = ["Dermatology", "Cardiology", "Ophthalmology", "Dentistry", "General Medicine"];
        if (!specialty) {
          for (const k of known) if (low.includes(k.toLowerCase())) { specialty = k; break; }
        }
        if (specialty) {
          try {
            const docs = (await axios.get(`${API_BASE}/doctors?specialization=${encodeURIComponent(specialty)}`)).data || [];
            setDoctorsList(docs);
            setSuggestion({ specialty, doctors: docs });
            if (docs.length > 0) {
              setSelectedDoctorId(docs[0].id);
              setSelectedSlot(docs[0].available_slots && docs[0].available_slots.length > 0 ? docs[0].available_slots[0] : "");
            }
            setShowBookingModal(true);
          } catch (err) {
            setSuggestion({ specialty, doctors: [] });
            setShowBookingModal(true);
          }
        }
      }

    } catch (err) {
      console.error("converse error", err);
      setThinking(false);
      replaceLastBotText("Server error — try again.");
    }
  }

  function onSendClick() {
    if (!input.trim()) return;
    const t = input.trim();
    setInput("");
    sendConverse(t);
  }
  function onEnter(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSendClick();
    }
  }

  async function clearChat() {
    setMessages([{ id: new_uuid(), from: "bot", text: "Hi — I'm Astra. Click & hold Record or type to book an appointment.", time: new Date() }]);
    setSuggestion(null);
    try {
      const r = await axios.post(`${API_BASE}/session/new`, {}, { timeout: 5000 });
      if (r.data && r.data.session_id) {
        const id = r.data.session_id;
        setSessionId(id);
        localStorage.setItem("astra_session_id", id);
        showTemporaryToast({ title: "Session reset", text: "Conversation cleared." }, 2000);
      } else {
        const id = new_uuid();
        setSessionId(id);
        localStorage.setItem("astra_session_id", id);
        showTemporaryToast({ title: "Session reset (local)", text: "Conversation cleared." }, 2000);
      }
    } catch (e) {
      console.warn("session new failed", e);
      const id = new_uuid();
      setSessionId(id);
      localStorage.setItem("astra_session_id", id);
      showTemporaryToast({ title: "Session reset (local)", text: "Conversation cleared." }, 2000);
    }
  }

  async function openBookingFormManual() {
    try {
      const res = await axios.get(`${API_BASE}/doctors`);
      const docs = res.data || [];
      setDoctorsList(docs);
      if (docs.length > 0) {
        setSelectedDoctorId(docs[0].id);
        setSelectedSlot(docs[0].available_slots && docs[0].available_slots.length > 0 ? docs[0].available_slots[0] : "");
      }
    } catch (e) {
      console.warn("failed to load doctors", e);
    }
    setShowBookingModal(true);
  }

  function onClickBookNow() {
    if (suggestion && suggestion.doctors && suggestion.doctors.length > 0) {
      setDoctorsList(suggestion.doctors);
      setSelectedDoctorId(suggestion.doctors[0].id);
      setSelectedSlot(suggestion.doctors[0].available_slots && suggestion.doctors[0].available_slots.length > 0 ? suggestion.doctors[0].available_slots[0] : "");
    } else if (doctorsList && doctorsList.length > 0) {
      setSelectedDoctorId(doctorsList[0].id);
      setSelectedSlot(doctorsList[0].available_slots && doctorsList[0].available_slots.length > 0 ? doctorsList[0].available_slots[0] : "");
    }
    setShowBookingModal(true);
  }

  async function submitBooking() {
    if (!selectedDoctorId) {
      alert("Please select a doctor.");
      return;
    }
    if (!patientName || !patientEmail || !selectedSlot) {
      alert("Please fill patient name, email and select slot.");
      return;
    }
    localStorage.setItem("astra_patient_name", patientName);
    localStorage.setItem("astra_patient_email", patientEmail);
    try {
      const payload = { doctor_id: selectedDoctorId, patient_name: patientName, patient_email: patientEmail, requested_slot: selectedSlot, note: suggestion && suggestion.specialty ? `Problem category: ${suggestion.specialty}` : "" };
      const r = await axios.post(`${API_BASE}/bookings/create`, payload, { timeout: 120000 });
      if (r.data && r.data.ok) {
        const booking = r.data.booking;
        setShowBookingModal(false);
        setSuggestion(null);
        setToast({ title: "Booking Confirmed", text: `#${booking.id} confirmed for ${booking.patient_name} at ${booking.requested_slot}` });
        appendMessage("bot", `✅ Booking confirmed — patient ${patientName}.`);
        setTimeout(() => setToast(null), 6000);
      } else {
        alert("Booking failed: " + (r.data && r.data.detail ? r.data.detail : "unknown"));
      }
    } catch (err) {
      console.error("booking error", err);
      // alert("Booking error: " + (err.response && err.response.data && err.response.data.detail ? err.response.data.detail : err.message || err));
    }
  }

  function renderSuggestionBox() {
    if (!suggestion) return null;
    const docs = (suggestion.doctors || []).slice(0, 3);
    return (
      <div className="suggestion-box">
        <div>
          <div className="suggest-title">Suggested: {suggestion.specialty}</div>
          <div className="suggest-sub">{docs.length ? docs.map((d) => d.name).join(" • ") : "No doctors found"}</div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn-primary" onClick={onClickBookNow}>Book Now</button>
          <button className="btn-ghost" onClick={() => setShowBookingModal(true)}>Open Form</button>
        </div>
      </div>
    );
  }

  function showTemporaryToast(obj, ms = 3000) { setToast(obj); setTimeout(() => setToast(null), ms); }

  return (
    <>
      <div className={`assistant-orb-modern ${open ? "orb-open" : ""}`} onClick={toggleOpen} title="Open assistant">
        <div className="orb-glow" />
        <div className="orb-center">A</div>
      </div>

      {open && (
        <div className="overlay-modern" onClick={(e) => { if (e.target.className === "overlay-modern") setOpen(false); }}>
          <div className="assistant-panel-modern" onClick={(e) => e.stopPropagation()}>
            <div className="assistant-header-modern">
              <div className="assistant-avatar-modern">A</div>
              <div style={{ flex: 1 }}>
                <div className="assistant-title-modern">Astra — Booking Assistant <span className="online-dot" /></div>
                <div className="assistant-sub-modern">Virtual receptionist — voice + chat</div>
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <button className="btn-ghost" onClick={clearChat}>Clear</button>
                <button className="btn-ghost" onClick={openBookingFormManual}>Open Booking Form</button>
                <button className="btn-ghost" onClick={() => setOpen(false)}>Close</button>
              </div>
            </div>

            <div ref={messagesEl} className="assistant-body-modern">
              {messages.map((m) => (
                <div key={m.id} className={`message-row ${m.from === "user" ? "msg-user" : "msg-bot"}`}>
                  <div className={`message-bubble ${m.from === "user" ? "bubble-user" : "bubble-bot"}`}>
                    <div className="bubble-text">{m.text || (m.from === "bot" ? "…" : "")}</div>
                    <div className="bubble-meta">{m.time ? new Date(m.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ""}</div>
                  </div>
                </div>
              ))}

              {renderSuggestionBox()}

              {thinking && (
                <div className="message-row msg-bot">
                  <div className="message-bubble bubble-bot typing">
                    <div className="typing-dots"><span /><span /><span /></div>
                  </div>
                </div>
              )}
            </div>

            <div className="assistant-controls-modern">
              <div className="record-container">
                <div
                  className={`record-button ${recording ? "recording" : ""}`}
                  onMouseDown={onRecordPointerDown}
                  onMouseUp={onRecordPointerUp}
                  onMouseLeave={onRecordPointerCancel}
                  onTouchStart={onRecordPointerDown}
                  onTouchEnd={onRecordPointerUp}
                  onTouchCancel={onRecordPointerCancel}
                  aria-label="Hold to record"
                  title="Hold to record"
                >
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="white" strokeWidth="1.4" /></svg>
                  <div className="record-label">{recording ? "Release to stop" : "Hold to record"}</div>
                </div>
              </div>

              <textarea value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={onEnter}
                placeholder="Type your message or hold Record..." className="assistant-input-modern" />

              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <button className="btn-primary" onClick={onSendClick}>Send</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {showBookingModal && (
        <div className="overlay-modern" onClick={() => setShowBookingModal(false)}>
          <div className="booking-modal-modern" onClick={(e) => e.stopPropagation()}>
            <div className="booking-header-modern">
              <div>
                <div style={{ fontWeight: 800 }}>Quick Booking</div>
                <div style={{ color: "#64748b", fontSize: 13 }}>{suggestion ? suggestion.specialty : "Fill details to book"}</div>
              </div>
              <div><button className="btn-ghost" onClick={() => setShowBookingModal(false)}>Close</button></div>
            </div>

            <div className="booking-body-modern">
              <label className="field-label">Patient name</label>
              <input className="field-input" value={patientName} onChange={(e) => setPatientName(e.target.value)} />

              <label className="field-label">Patient email</label>
              <input className="field-input" value={patientEmail} onChange={(e) => setPatientEmail(e.target.value)} />

              <label className="field-label">Choose doctor</label>
              <select className="field-input" value={selectedDoctorId || ""} onChange={(e) => {
                const id = parseInt(e.target.value);
                setSelectedDoctorId(id);
                const doc = (doctorsList || []).find(d => d.id === id);
                setSelectedSlot(doc && doc.available_slots && doc.available_slots[0] ? doc.available_slots[0] : "");
              }}>
                {(doctorsList || []).map(d => <option key={d.id} value={d.id}>{d.name} — {d.specialization}</option>)}
              </select>

              <label className="field-label">Choose slot</label>
              <select className="field-input" value={selectedSlot} onChange={(e) => setSelectedSlot(e.target.value)}>
                {(() => {
                  const doc = (doctorsList || []).find(d => d.id === selectedDoctorId);
                  const slots = (doc && doc.available_slots) || [];
                  if (slots.length === 0) return <option value="">No slots available</option>;
                  return slots.map(s => <option key={s} value={s}>{s}</option>);
                })()}
              </select>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 12 }}>
                <button className="btn-ghost" onClick={() => setShowBookingModal(false)}>Cancel</button>
                <button className="btn-primary" onClick={submitBooking}>Confirm Booking</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {toast && (
        <div className="toast-modern">
          <div style={{ fontWeight: 800 }}>{toast.title}</div>
          <div style={{ opacity: 0.95 }}>{toast.text}</div>
        </div>
      )}
    </>
  );
}
