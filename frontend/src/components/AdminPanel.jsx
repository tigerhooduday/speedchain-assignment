import React, { useEffect, useState } from "react";
import axios from "axios";

const API_BASE = "http://localhost:8000/api";

export default function AdminPanel({ refreshDoctors }) {
  const [doctors, setDoctors] = useState([]);
  const [token, setToken] = useState("");
  const [login, setLogin] = useState({username:"admin", password:"admin123"});
  const [editing, setEditing] = useState(null);
  const [bookings, setBookings] = useState([]);

  useEffect(() => {
    fetchDoctors();
    fetchBookings();
  }, []);

  async function fetchDoctors() {
    try {
      const res = await axios.get(`${API_BASE}/doctors/`);
      setDoctors(res.data);
    } catch (err) {
      console.error(err);
    }
  }

  async function doLogin() {
    try {
      const res = await axios.post(`${API_BASE}/auth/login`, login);
      setToken(res.data.token);
      alert("Logged in (demo token saved)");
    } catch (err) {
      alert("Login failed");
      console.error(err);
    }
  }

  function startEdit(doc) {
    setEditing({...doc});
  }

  async function saveEdit() {
    try {
      if(typeof editing.available_slots === "string"){
        editing.available_slots = editing.available_slots.split(",").map(s => s.trim()).filter(Boolean);
      }
      const res = await axios.put(`${API_BASE}/doctors/${editing.id}?admin_token=${token}`, editing);
      alert("Saved");
      setEditing(null);
      fetchDoctors();
      if(typeof refreshDoctors === "function") refreshDoctors();
    } catch (err) {
      alert("Save failed. Make sure you're logged in.");
      console.error(err);
    }
  }

  async function fetchBookings(){
    try {
      const res = await axios.get(`${API_BASE}/bookings/list`);
      if(res.data.ok){
        setBookings(res.data.bookings || []);
      } else {
        setBookings([]);
      }
    } catch (err) {
      console.error(err);
      setBookings([]);
    }
  }

  return (
    <div>
      <div style={{marginBottom:12}}>
        <h4>Admin Login</h4>
        <input placeholder="username" value={login.username} onChange={e=>setLogin({...login, username:e.target.value})} />
        <input placeholder="password" type="password" value={login.password} onChange={e=>setLogin({...login, password:e.target.value})} />
        <button className="btn" onClick={doLogin}>Login</button>
      </div>

      <div style={{marginBottom:12}}>
        <h4>Doctors</h4>
        {doctors.map(d => (
          <div key={d.id} style={{border:"1px solid #eee", padding:8, borderRadius:8, marginBottom:8}}>
            <strong>{d.name}</strong> — <em>{d.specialization}</em>
            <div style={{fontSize:13}}>{d.bio}</div>
            <div style={{fontSize:13}}><strong>Slots:</strong> {d.available_slots.join(", ")}</div>
            <div style={{marginTop:8}}>
              <button className="btn secondary" onClick={()=>startEdit(d)}>Edit</button>
            </div>
          </div>
        ))}
      </div>

      {editing && (
        <div style={{marginTop:12}}>
          <h4>Edit Doctor #{editing.id}</h4>
          <label>Name</label>
          <input value={editing.name} onChange={e=>setEditing({...editing, name: e.target.value})} />
          <label>Specialization</label>
          <input value={editing.specialization} onChange={e=>setEditing({...editing, specialization: e.target.value})} />
          <label>Bio</label>
          <textarea value={editing.bio} onChange={e=>setEditing({...editing, bio: e.target.value})} />
          <label>Available slots (comma separated)</label>
          <input value={editing.available_slots.join ? editing.available_slots.join(", ") : editing.available_slots} onChange={e=>setEditing({...editing, available_slots: e.target.value})} />
          <div style={{marginTop:8}}>
            <button className="btn" onClick={saveEdit}>Save</button>
            <button className="btn secondary" style={{marginLeft:8}} onClick={()=>setEditing(null)}>Cancel</button>
          </div>
        </div>
      )}

      <div style={{marginTop:12}}>
        <h4>Bookings</h4>
        <button className="btn alt" onClick={fetchBookings}>Refresh Bookings</button>
        <div style={{marginTop:10}}>
          {bookings.length === 0 && <div style={{color:"#64748b"}}>No bookings yet.</div>}
          {bookings.map(b => (
            <div key={b.id} style={{border:"1px solid #eef2ff", padding:10, borderRadius:8, marginBottom:8}}>
              <div><strong>#{b.id}</strong> — <strong>{b.doctor_name}</strong> @ {b.requested_slot}</div>
              <div>{b.patient_name} — {b.patient_email}</div>
              <div style={{color:"#64748b"}}>{b.note}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
