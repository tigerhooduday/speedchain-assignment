// src/App.jsx
import React, { useEffect, useState } from "react";
import AssistantButton from "./components/AssistantButton"; 
import "./styles/Homepage.css";

export default function App() {
  const [doctors, setDoctors] = useState([]);

  // Fetch doctors dynamically from backend
  useEffect(() => {
    async function fetchDoctors() {
      try {
        const res = await fetch("http://localhost:8000/api/doctors");
        const data = await res.json();
        if (data && Array.isArray(data)) setDoctors(data);
      } catch (err) {
        console.error("Error fetching doctors:", err);
      }
    }
    fetchDoctors();
  }, []);

  const openAssistant = () => {
    const el = document.querySelector(".assistant-orb-modern") || document.querySelector(".assistant-orb");
    if (el && typeof el.click === "function") el.click();
  };

  return (
    <div className="hc-app">
      {/* Header bar */}
      <header className="hc-topbar">
        <div className="hc-topbar-inner">
          <div className="hc-brand">
            <div className="hc-logo">NW-C</div>
            <div className="brand-text">
              <div className="brand-title">NovaCare Wellness Clinic</div>
              <div className="brand-sub">Voice-first booking • Real people care</div>
            </div>
          </div>

          <nav className="hc-navbar">
            <ul>
              <li><a href="#home">Home</a></li>
              <li><a href="#doctors">Specialists</a></li>
              <li><a href="#services">Services</a></li>
              <li><a href="#contact">Contact</a></li>
            </ul>
            <div className="nav-actions">
              <button className="btn-outline" onClick={() => window.open("/admin", "_self")}>Admin</button>
              <button className="btn-cta" onClick={openAssistant}>Book Now</button>
            </div>
          </nav>
        </div>
      </header>

      <main className="hc-main">
        <section className="hero">
          <div className="hero-left">
            <h1>Appointments made effortless</h1>
            <p className="lead">
              Speak to Astra — our friendly virtual receptionist — and book appointments in seconds. 
              Real-time voice, human-like follow-ups, and instant confirmations.
            </p>

            <div className="hero-actions">
              <button className="btn-cta" onClick={openAssistant}>Talk to Astra</button>
              <a className="btn-link" href="#doctors">See specialists</a>
            </div>

            <div className="trust-row">
              <div className="trust-pill">Secure booking</div>
              <div className="trust-pill">Email confirmations</div>
              <div className="trust-pill">24/7 voice assistance</div>
            </div>
          </div>

          <div className="hero-right">
            <div className="clinic-card">
              <div className="clinic-figure">NC</div>
              <div className="clinic-meta">
                <div className="clinic-name">NovaCare Wellness</div>
                <div className="clinic-loc">Town Center — Open Mon–Sat</div>
                <div style={{ marginTop: 8 }}>
                  <button className="btn-small" onClick={openAssistant}>Start booking</button>
                </div>
              </div>
            </div>

            <div className="feature-grid">
              <div className="feature">
                <div className="f-title">Smart suggestions</div>
                <div className="f-desc">Astra suggests the best specialist based on your symptoms.</div>
              </div>
              <div className="feature">
                <div className="f-title">Flexible slots</div>
                <div className="f-desc">Multiple patients can book the same slot if needed.</div>
              </div>
              <div className="feature">
                <div className="f-title">Notes & follow-ups</div>
                <div className="f-desc">Add patient notes and receive confirmations instantly.</div>
              </div>
            </div>
          </div>
        </section>

        <section id="doctors" className="doctors-section">
          <h2 className="section-heading">Our Specialists</h2>

          <div className="doctor-grid">
            {doctors.length > 0 ? (
              doctors.map((d) => (
                <article className="doc-card" key={d.id}>
                  <div className="doc-avatar">
                    {d.name
                      .split(" ")
                      .map((n) => n[0])
                      .join("")
                      .slice(0, 2)
                      .toUpperCase()}
                  </div>
                  <div className="doc-body">
                    <div className="doc-name">{d.name}</div>
                    <div className="doc-spec">
                      {d.specialization}{" "}
                      <span className="doc-sub">{d.subtitle || ""}</span>
                    </div>
                    {d.slots && (
                      <div className="doc-slots">Slots: {d.slots.join(", ")}</div>
                    )}
                  </div>
                  <div className="doc-actions">
                    <button className="btn-outline" onClick={openAssistant}>Book</button>
                  </div>
                </article>
              ))
            ) : (
              <div style={{ padding: "10px", color: "#64748b" }}>Loading doctors...</div>
            )}
          </div>
        </section>
      </main>

      <footer className="hc-footer">
        <div className="footer-inner">
          <div>© {new Date().getFullYear()} NovaCare Wellness Clinic</div>
          <div className="footer-right">
            Built for speedchain-assignment — voice booking demo
          </div>
        </div>
      </footer>

      <AssistantButton />
    </div>
  );
}
