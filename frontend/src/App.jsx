import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Mic, Square, Trash2, Calendar, TrendingUp, AlertCircle, FileText, ChevronRight } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const BASE_URL = 'http://localhost:5000/api';

function App() {
  const [isRecording, setIsRecording] = useState(false);
  const [entries, setEntries] = useState([]);
  const [insights, setInsights] = useState({ insights: [], suggestions: [] });
  const [loading, setLoading] = useState(false);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const eRes = await axios.get(`${BASE_URL}/entries`);
      setEntries(eRes.data.entries);
      const iRes = await axios.get(`${BASE_URL}/insights`);
      setInsights(iRes.data);
    } catch (err) {
      console.error("Fetch Error:", err);
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorderRef.current = new MediaRecorder(stream);
      audioChunksRef.current = [];

      mediaRecorderRef.current.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      mediaRecorderRef.current.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
        await uploadAudio(audioBlob);
      };

      mediaRecorderRef.current.start();
      setIsRecording(true);
    } catch (err) {
      alert("Mic access denied!");
    }
  };

  const stopRecording = () => {
    mediaRecorderRef.current.stop();
    setIsRecording(false);
  };

  const uploadAudio = async (blob) => {
    setLoading(true);
    const formData = new FormData();
    formData.append('audio', blob, 'recording.wav');

    try {
      await axios.post(`${BASE_URL}/record`, formData);
      fetchData();
    } catch (err) {
      console.error("Upload Error:", err);
      alert("Processing failed. Check backend console.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container" style={{ maxWidth: '1000px', margin: '0 auto', padding: '40px 20px' }}>
      <header style={{ marginBottom: '40px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: '32px', fontWeight: '700', letterSpacing: '-0.5px' }}>VoiceTrace <span style={{ color: 'var(--accent)' }}>AI</span></h1>
          <p style={{ color: 'var(--text-dim)', marginTop: '4px' }}>Smart Business Assistant for Vendors</p>
        </div>
        <div className="glass" style={{ padding: '8px 16px', fontSize: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--success)' }}></div>
          Server Live
        </div>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: '24px' }}>
        <main>
          {/* Recorder Section */}
          <section className="glass card" style={{ textAlign: 'center', py: '60px' }}>
            <h2 style={{ marginBottom: '20px' }}>{isRecording ? "Recording your day..." : "Tell me about your sales"}</h2>
            <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '20px' }}>
              <button 
                className={`btn-mic ${isRecording ? 'recording' : ''}`}
                onClick={isRecording ? stopRecording : startRecording}
                disabled={loading}
              >
                {isRecording ? <Square size={32} color="white" fill="white" /> : <Mic size={40} color="white" />}
              </button>
            </div>
            {loading && <p style={{ color: 'var(--accent)' }}>Processing voice with AI...</p>}
            {!isRecording && !loading && (
              <p style={{ color: 'var(--text-dim)', fontSize: '14px' }}>Example: "Aaj 5 kilo seb beche 100 rupaye kilo ke hisab se..."</p>
            )}
          </section>

          {/* Digital Khata Section */}
          <section className="glass card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
              <h2 style={{ fontSize: '20px' }}>Digital Khata (Ledger)</h2>
              <button style={{ background: 'transparent', border: 'none', color: 'var(--accent)', cursor: 'pointer', fontSize: '14px', display: 'flex', alignItems: 'center' }}>
                View Full Report <ChevronRight size={16} />
              </button>
            </div>
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Item / Type</th>
                    <th>Qty</th>
                    <th>Price/Amount</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.length === 0 ? (
                    <tr><td colSpan="5" style={{ textAlign: 'center', color: 'var(--text-dim)' }}>No entries yet. Speak into the mic to start!</td></tr>
                  ) : (
                    entries.flatMap(entry => [
                        ...entry.sales.map(s => (
                            <tr key={`${entry.id}-s-${s.item}`} className={s.uncertain ? 'uncertain' : ''}>
                                <td style={{ fontSize: '12px', color: 'var(--text-dim)' }}>{new Date(entry.created_at).toLocaleDateString()}</td>
                                <td>{s.item}</td>
                                <td>{s.qty}</td>
                                <td>₹{s.price}</td>
                                <td>{s.uncertain ? <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><AlertCircle size={14}/> Clarify</span> : 'Verified'}</td>
                            </tr>
                        )),
                        ...entry.expenses.map(ex => (
                            <tr key={`${entry.id}-ex-${ex.type}`}>
                                <td style={{ fontSize: '12px', color: 'var(--text-dim)' }}>{new Date(entry.created_at).toLocaleDateString()}</td>
                                <td style={{ color: '#fb7185' }}>{ex.type} (Expense)</td>
                                <td>-</td>
                                <td style={{ color: '#fb7185' }}>₹{ex.amount}</td>
                                <td>Verified</td>
                            </tr>
                        ))
                    ])
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </main>

        <aside>
          {/* Insights Panel */}
          <section className="glass card" style={{ height: 'fit-content' }}>
            <h3 style={{ fontSize: '18px', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <TrendingUp size={20} color="var(--accent)" /> Agli Taiyari
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {insights.suggestions.length > 0 ? (
                insights.suggestions.map((s, i) => (
                  <div key={i} style={{ fontSize: '14px', padding: '12px', borderLeft: '3px solid var(--accent)', background: 'rgba(59,130,246,0.05)' }}>
                    {s}
                  </div>
                ))
              ) : (
                <p style={{ fontSize: '13px', color: 'var(--text-dim)' }}>More data needed to predict tomorrow's stock.</p>
              )}
            </div>
          </section>

          {/* Business Patterns */}
          <section className="glass card" style={{ height: 'fit-content' }}>
            <h3 style={{ fontSize: '18px', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Calendar size={20} color="var(--success)" /> Insights
            </h3>
            <ul style={{ listStyle: 'none', fontSize: '13px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {insights.insights.map((ins, i) => (
                <li key={i} style={{ display: 'flex', gap: '8px' }}>
                  <div style={{ marginTop: '4px', minWidth: '6px', height: '6px', borderRadius: '50%', background: 'var(--success)' }}></div>
                  {ins}
                </li>
              ))}
            </ul>
          </section>
        </aside>
      </div>
    </div>
  );
}

export default App;
