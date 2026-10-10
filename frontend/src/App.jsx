import React, { useState, useRef, useEffect } from 'react';
import { Send, Stethoscope, CalendarCheck, Plus, Paperclip, X } from 'lucide-react';
import { TypewriterBubble } from './components/TypewriterBubble';
import { DoctorCard } from './components/DoctorCard';
import { DiagnosisBubble } from './components/DiagnosisBubble';
import { TreatmentBubble } from './components/TreatmentBubble';
import { BookingBubble } from './components/BookingBubble';
import { MsgRow } from './components/MsgRow';
import './style.css';

const API = import.meta.env.VITE_API_URL;

const GREETING = {
  role: 'assistant', type: 'text', instant: true,
  text: "Hello! I'm ACDSS — your AI clinical assistant.\n\nAttach a photo of your lab report, or just tell me what's going on. I'll take it from there.",
};


export default function App() {
  const [messages, setMessages] = useState([GREETING]);
  const [sessionId, setSessionId] = useState(null);
  const [patient, setPatient] = useState({ name: '', age: '', gender: '', phone: '' });
  const [input, setInput] = useState('');
  const [pendingImage, setPendingImage] = useState(null);   // staged until Send
  const [busy, setBusy] = useState(false);
  const [backendOk, setBackendOk] = useState(null);

  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 120) + 'px';
  }, [input]);

  useEffect(() => {
    fetch(`${API}/`).then(r => setBackendOk(r.ok)).catch(() => setBackendOk(false));
  }, []);


  const addMsg = msg => setMessages(prev => [...prev, msg]);

  function patientJson() {
    return JSON.stringify({
      name:   patient.name || null,
      age:    Number(patient.age) || null,
      gender: patient.gender || null,
      phone:  patient.phone || null,
    });
  }


  function sendChat() {
    return send({ message: input.trim(), image: pendingImage, clearInput: true });
  }


  function ask(message) {
    return send({ message });
  }

  /* The Treatment button is not a special path — it types a message for you.
     The agent already has the conversation, so nothing needs to be composed. */
  function requestTreatment() {
    return send({ message: 'Please build my treatment plan.' });
  }

  async function send({ message = '', image = null, clearInput = false }) {
    if (busy) return;
    if (!message && !image) return;

    if (clearInput) setInput('');
    if (image) setPendingImage(null);
    setBusy(true);

    if (image) {
      addMsg({
        role: 'user', type: 'image', src: image.preview,
        name: image.file.name, notes: message, instant: true,
      });
    } else {
      addMsg({ role: 'user', type: 'text', text: message, instant: true });
    }

    try {
      const form = new FormData();
      form.append('message', message);
      form.append('session_id', sessionId || '');
      form.append('patient', patientJson());
      if (image) form.append('file', image.file);

      const res = await fetch(`${API}/chat`, { method: 'POST', body: form });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Error ${res.status}`);
      }

      const data = await res.json();
      setSessionId(data.session_id);
      setBackendOk(true);

      addMsg({ role: 'assistant', type: 'text', text: data.reply });
      (data.events || []).forEach(evt =>
        addMsg({ role: 'assistant', type: evt.kind, data: evt.data, instant: true })
      );
    } catch (err) {
      const offline = err?.name === 'TypeError' || /failed to fetch/i.test(err?.message || '');
      addMsg({
        role: 'assistant', type: 'text', instant: true,
        text: offline
          ? "I can't reach the server right now. Make sure the backend is running, then try again."
          : `Something went wrong: ${err.message}`,
      });
      if (offline) setBackendOk(false);
    }

    setBusy(false);
  }

  async function bookAppointment(doctor, slot) {
    if (busy) return;                     
    setBusy(true);
    try {
      const res = await fetch(`${API}/appointments`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          patient_name: patient.name || 'Guest',
          age:    Number(patient.age) || null,
          gender: patient.gender || null,
          phone:  patient.phone || null,
          doctor_id: doctor.id,
          slot,
          session_id: sessionId,
        }),
      });
      if (!res.ok) throw new Error();
      addMsg({ role: 'assistant', type: 'booking', data: await res.json(), instant: true });
    } catch {
      addMsg({
        role: 'assistant', type: 'text', instant: true,
        text: 'That slot could not be booked. Please try another one.',
      });
    } finally {
      setBusy(false);
    }
  }

  function newSession() {
    setMessages([{
      role: 'assistant', type: 'text', instant: true,
      text: "New session started. Attach a lab report or tell me what's going on.",
    }]);
    setInput('');
    setPendingImage(null);
    setSessionId(null);   
  }

  function stageImage(file) {
    const reader = new FileReader();
    reader.onload = e => setPendingImage({ file, preview: e.target.result });
    reader.readAsDataURL(file);
  }

  return (
    <div className="app">
      {/* ── SIDEBAR ──────────────────────────────────────────────────────── */}
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="brand-icon"><Stethoscope size={20} color="white" /></div>
          <div className="brand-text">
            <h2>ACDSS</h2>
            <span>Clinical AI System</span>
          </div>
        </div>

        <button id="new-chat-btn" className="new-chat-btn" onClick={newSession}>
          <Plus size={14} /> New Session
        </button>

        <div className="patient-section">
          <div className="section-label">Patient Info</div>
          <div className="patient-form">
            <div className="form-field">
              <label htmlFor="pat-name">Full Name</label>
              <input id="pat-name" placeholder="e.g. Priya Sharma"
                value={patient.name}
                onChange={e => setPatient(p => ({ ...p, name: e.target.value }))} />
            </div>
            <div className="form-field">
              <label htmlFor="pat-age">Age</label>
              <input id="pat-age" type="number" placeholder="Years"
                value={patient.age}
                onChange={e => setPatient(p => ({ ...p, age: e.target.value }))} />
            </div>
            <div className="form-field">
              <label>Gender</label>
              <div className="gender-row">
                {['Male', 'Female', 'Other'].map(g => (
                  <button key={g} id={`gender-${g.toLowerCase()}`}
                    className={`gender-chip${patient.gender === g ? ' active' : ''}`}
                    onClick={() => setPatient(p => ({ ...p, gender: g }))}>
                    {g}
                  </button>
                ))}
              </div>
            </div>
            <div className="form-field">
              <label htmlFor="pat-phone">Phone</label>
              <input id="pat-phone" placeholder="+91 XXXXX XXXXX"
                value={patient.phone}
                onChange={e => setPatient(p => ({ ...p, phone: e.target.value }))} />
            </div>
          </div>
        </div>

        <div className="status-badge" style={backendOk === false
          ? { background: 'rgba(239,68,68,0.08)', borderColor: 'rgba(239,68,68,0.2)', color: 'var(--danger)' }
          : {}}>
          <div className="status-dot" style={backendOk === false ? { background: 'var(--danger)' } : {}} />
          {backendOk === null ? 'Connecting…' : backendOk ? 'Backend Connected' : 'Backend Offline'}
        </div>
      </aside>

      {/* ── MAIN AREA ─────────────────────────────────────────────────────── */}
      <main className="chat-area">
        <header className="chat-header">
          <div className="header-text">
            <h1>Autonomous Clinical Decision Support</h1>
            <p>Ask anything, attach a report, or book a specialist — in any order.</p>
          </div>
          <div className="header-tags">
            <span className="tag">🧬 RAG Diagnosis</span>
            <span className="tag">⚖ Evaluator Nodes</span>
            <span className="tag">💊 Treatment Plan</span>
            <span className="tag">📅 Booking</span>
          </div>
        </header>

        <section className="messages" id="message-feed">
          {messages.map((m, i) => {
            if (m.role === 'user' && m.type === 'image') return (
              <MsgRow key={i} role="user">
                <div className="msg-bubble user image">
                  <img src={m.src} alt={m.name || 'upload'} className="chat-image" />
                  {m.notes ? <div className="chat-image-note">{m.notes}</div> : null}
                </div>
              </MsgRow>
            );

            if (m.role === 'user') return (
              <MsgRow key={i} role="user">
                <div className="msg-bubble user">{m.text}</div>
              </MsgRow>
            );

            if (m.type === 'diagnosis') return (
              <MsgRow key={i} role="assistant">
                <DiagnosisBubble
                  data={m.data}
                  onWantTreatment={requestTreatment}
                  onWantDoctors={() => ask('Can you find me a specialist for this?')}
                />
              </MsgRow>
            );

            if (m.type === 'treatment') return (
              <MsgRow key={i} role="assistant">
                <TreatmentBubble data={m.data} problem={m.data.problem} />
              </MsgRow>
            );

            if (m.type === 'booking') return (
              <MsgRow key={i} role="assistant">
                <BookingBubble data={m.data} />
              </MsgRow>
            );

            if (m.type === 'doctors') return (
              <MsgRow key={i} role="assistant">
                <div className="doctor-panel inline">
                  <div className="doctor-panel-header">
                    <CalendarCheck size={15} color="var(--text-secondary)" />
                    <h2>{m.data.specialization}s</h2>
                    <span className="count-badge">{m.data.doctors.length}</span>
                  </div>
                  <div className="doctor-grid">
                    {m.data.doctors.map(d => (
                      <DoctorCard key={d.id} doctor={d} onBook={bookAppointment} />
                    ))}
                  </div>
                </div>
              </MsgRow>
            );

            return (
              <MsgRow key={i} role="assistant">
                {m.instant
                  ? <div className="msg-bubble assistant">{m.text}</div>
                  : <TypewriterBubble text={m.text} />}
              </MsgRow>
            );
          })}

          {busy && (
            <MsgRow role="assistant">
              <div className="thinking">
                <div className="thinking-dot" />
                <div className="thinking-dot" />
                <div className="thinking-dot" />
              </div>
            </MsgRow>
          )}

          <div ref={messagesEndRef} />
        </section>

        {/* ── Composer ───────────────────────────────────────────────────── */}
        <footer className="composer">
          {pendingImage && (
            <div className="pending-attach">
              <img src={pendingImage.preview} alt="attachment" className="pending-thumb" />
              <span className="pending-name">{pendingImage.file.name}</span>
              <span className="pending-hint">Press Send</span>
              <button className="pending-remove" title="Remove"
                onClick={() => setPendingImage(null)}>
                <X size={14} />
              </button>
            </div>
          )}

          <div className="composer-inner">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/jpg,image/bmp,image/tiff"
              style={{ display: 'none' }}
              onChange={e => {
                const f = e.target.files[0];
                e.target.value = '';
                if (f) stageImage(f);
              }}
            />
            <button type="button" className="attach-btn" title="Attach a lab report"
              disabled={busy} onClick={() => fileInputRef.current?.click()}>
              <Paperclip size={18} />
            </button>

            <textarea ref={textareaRef} id="symptom-input" rows={1}
              placeholder={pendingImage
                ? 'Add anything relevant — symptoms, medications — then press Send…'
                : 'Attach a report 📎 or type your question…'}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); }
              }}
            />
            <button id="send-btn" className="send-btn" onClick={sendChat}
              disabled={(!input.trim() && !pendingImage) || busy}>
              <Send size={16} />
            </button>
          </div>
          <p className="composer-hint">
            ACDSS is an assistant, not a doctor — confirm anything clinical with a licensed physician.
          </p>
        </footer>
      </main>
    </div>
  );
}
