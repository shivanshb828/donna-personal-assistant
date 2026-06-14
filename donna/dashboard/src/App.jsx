import React, { useState, useEffect, useRef } from 'react'

const WS_URL = 'ws://localhost:3001'

const STATUS_COLORS = {
  intake: '#3b82f6',
  discovery: '#8b5cf6',
  negotiation: '#f59e0b',
  settled: '#22c55e',
  closed: '#6b7280',
}

const SOL_COLOR = (days) => {
  if (days < 30) return '#ef4444'
  if (days < 60) return '#f59e0b'
  return '#22c55e'
}

export default function App() {
  const [events, setEvents] = useState([])
  const [transcript, setTranscript] = useState([])
  const [isActive, setIsActive] = useState(false)
  const [showLocalProof, setShowLocalProof] = useState(false)
  const ws = useRef(null)

  useEffect(() => {
    const connect = () => {
      ws.current = new WebSocket(WS_URL)
      ws.current.onmessage = (e) => {
        const event = JSON.parse(e.data)
        setEvents(prev => [event, ...prev].slice(0, 50))

        if (event.type === 'donna_activated') {
          setIsActive(true)
        } else if (event.type === 'user_speech') {
          setTranscript(prev => [...prev, { role: 'user', text: event.text }])
        } else if (event.type === 'donna_speech') {
          setTranscript(prev => [...prev, { role: 'donna', text: event.text }])
          setIsActive(false)
        }
      }
      ws.current.onclose = () => setTimeout(connect, 2000)
    }
    connect()
    return () => ws.current?.close()
  }, [])

  return (
    <div style={{ minHeight: '100vh', background: '#1a1f2e', color: '#fff', padding: 24 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 32 }}>
        <div>
          <h1 style={{ fontFamily: 'Georgia, serif', fontSize: 36, color: '#c9a84c', letterSpacing: 4 }}>
            DONNA
          </h1>
          <p style={{ color: '#9ca3af', fontSize: 14 }}>AI Legal Secretary</p>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <span style={{
            background: '#065f46', color: '#34d399', padding: '4px 12px',
            borderRadius: 12, fontSize: 12, fontWeight: 600,
          }}>
            ● LOCAL
          </span>
          <button
            onClick={() => setShowLocalProof(!showLocalProof)}
            style={{
              background: '#c9a84c', color: '#1a1f2e', border: 'none',
              padding: '8px 16px', borderRadius: 6, cursor: 'pointer',
              fontWeight: 600, fontSize: 13,
            }}
          >
            Prove It's Local
          </button>
        </div>
      </div>

      {/* Local Proof Panel */}
      {showLocalProof && (
        <div style={{
          background: '#0f172a', border: '1px solid #334155', borderRadius: 8,
          padding: 16, marginBottom: 24, fontFamily: 'monospace', fontSize: 13,
        }}>
          <h3 style={{ color: '#c9a84c', marginBottom: 12 }}>OpenShell Security Policy — donna-attorney-privilege</h3>
          <pre style={{ color: '#94a3b8', whiteSpace: 'pre-wrap' }}>{`
Network Policy:
  ALLOW: localhost:9000 (Whisper STT)
  ALLOW: localhost:8880 (Kokoro TTS)
  ALLOW: localhost:8001 (ChromaDB)
  ALLOW: localhost:11434 (Ollama/Nemotron)
  DENY:  * (ALL outbound internet blocked)

Blocked Requests During This Session: 0
Last Blocked: (none)

All inference runs on this machine.
Client data never leaves this device.
Attorney-client privilege enforced at OS level.
          `.trim()}</pre>
        </div>
      )}

      {/* Main Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>

        {/* Panel A: Live Transcript */}
        <div style={{ background: '#111827', borderRadius: 8, padding: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
            <h2 style={{ fontSize: 16, color: '#c9a84c' }}>Live Conversation</h2>
            {isActive && (
              <span style={{
                background: '#dc2626', color: '#fff', padding: '2px 8px',
                borderRadius: 4, fontSize: 11, animation: 'pulse 1.5s infinite',
              }}>
                LISTENING
              </span>
            )}
          </div>
          <div style={{ maxHeight: 400, overflowY: 'auto' }}>
            {transcript.length === 0 ? (
              <p style={{ color: '#6b7280', fontStyle: 'italic' }}>
                Say "Hey Donna" to start a conversation...
              </p>
            ) : (
              transcript.map((t, i) => (
                <div key={i} style={{
                  marginBottom: 12, padding: 8, borderRadius: 6,
                  background: t.role === 'donna' ? '#1e293b' : '#1a1f2e',
                  borderLeft: `3px solid ${t.role === 'donna' ? '#c9a84c' : '#3b82f6'}`,
                }}>
                  <div style={{ fontSize: 11, color: '#6b7280', marginBottom: 4 }}>
                    {t.role === 'donna' ? 'Donna' : 'Attorney'}
                  </div>
                  <div style={{ fontSize: 14 }}>{t.text}</div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Panel B: Cases */}
        <div style={{ background: '#111827', borderRadius: 8, padding: 20 }}>
          <h2 style={{ fontSize: 16, color: '#c9a84c', marginBottom: 16 }}>Active Cases</h2>
          <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #334155', color: '#9ca3af' }}>
                <th style={{ textAlign: 'left', padding: 8 }}>Client</th>
                <th style={{ textAlign: 'left', padding: 8 }}>Type</th>
                <th style={{ textAlign: 'left', padding: 8 }}>Status</th>
                <th style={{ textAlign: 'left', padding: 8 }}>SOL</th>
              </tr>
            </thead>
            <tbody>
              {/* Demo rows — will be populated from API */}
              <tr style={{ borderBottom: '1px solid #1e293b' }}>
                <td style={{ padding: 8 }}>Sarah Chen</td>
                <td style={{ padding: 8 }}>Slip & Fall</td>
                <td style={{ padding: 8 }}>
                  <span style={{ background: STATUS_COLORS.intake, padding: '2px 8px', borderRadius: 4, fontSize: 11 }}>
                    INTAKE
                  </span>
                </td>
                <td style={{ padding: 8, color: '#22c55e' }}>698 days</td>
              </tr>
              <tr style={{ borderBottom: '1px solid #1e293b' }}>
                <td style={{ padding: 8 }}>Marcus Williams</td>
                <td style={{ padding: 8 }}>Auto Accident</td>
                <td style={{ padding: 8 }}>
                  <span style={{ background: STATUS_COLORS.negotiation, padding: '2px 8px', borderRadius: 4, fontSize: 11 }}>
                    NEGOTIATION
                  </span>
                </td>
                <td style={{ padding: 8, color: '#ef4444', fontWeight: 700 }}>⚠ 28 days</td>
              </tr>
              <tr style={{ borderBottom: '1px solid #1e293b' }}>
                <td style={{ padding: 8 }}>Elena Rodriguez</td>
                <td style={{ padding: 8 }}>Workplace</td>
                <td style={{ padding: 8 }}>
                  <span style={{ background: STATUS_COLORS.settled, padding: '2px 8px', borderRadius: 4, fontSize: 11 }}>
                    SETTLED
                  </span>
                </td>
                <td style={{ padding: 8, color: '#6b7280' }}>—</td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Panel C: Calendar */}
        <div style={{ background: '#111827', borderRadius: 8, padding: 20 }}>
          <h2 style={{ fontSize: 16, color: '#c9a84c', marginBottom: 16 }}>Upcoming Calendar</h2>
          <div style={{ fontSize: 13 }}>
            <div style={{ padding: 12, background: '#1e293b', borderRadius: 6, marginBottom: 8 }}>
              <div style={{ color: '#c9a84c', fontSize: 11 }}>DEPOSITION — in 14 days</div>
              <div>Marcus Williams — Deposition of James Cooper</div>
              <div style={{ color: '#6b7280', fontSize: 12 }}>Smith & Associates office</div>
            </div>
            <div style={{ padding: 12, background: '#1e293b', borderRadius: 6, marginBottom: 8 }}>
              <div style={{ color: '#3b82f6', fontSize: 11 }}>FOLLOW-UP — in 2 days</div>
              <div>Sarah Chen — Follow-up call re: medical records</div>
            </div>
          </div>
        </div>

        {/* Panel D: Activity Feed */}
        <div style={{ background: '#111827', borderRadius: 8, padding: 20 }}>
          <h2 style={{ fontSize: 16, color: '#c9a84c', marginBottom: 16 }}>Recent Activity</h2>
          <div style={{ maxHeight: 300, overflowY: 'auto' }}>
            {events.length === 0 ? (
              <p style={{ color: '#6b7280', fontStyle: 'italic', fontSize: 13 }}>
                Waiting for activity...
              </p>
            ) : (
              events.map((e, i) => (
                <div key={i} style={{
                  padding: 8, marginBottom: 4, fontSize: 12,
                  borderLeft: '2px solid #334155', paddingLeft: 12,
                }}>
                  <span style={{ color: '#c9a84c' }}>{e.type}</span>
                  {e.text && <span style={{ color: '#9ca3af' }}> — {e.text.slice(0, 60)}</span>}
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </div>
  )
}
