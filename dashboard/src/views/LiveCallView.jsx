import { useEffect, useRef, useState } from 'react'
import { PHASES, PHASE_IDS, TOOL_LABELS } from '../lib/constants.js'

function fmt(ts) {
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function fmtDuration(ms) {
  const s = Math.floor(ms / 1000)
  const m = Math.floor(s / 60)
  const sec = s % 60
  return `${m}:${sec.toString().padStart(2, '0')}`
}

// ── Intake Pipeline Steps ─────────────────────────────────────────────────────

function WorkflowSteps({ currentPhase, completedPhases }) {
  return (
    <div className="flex items-start">
      {PHASES.map((phase, i) => {
        const isCompleted = completedPhases.includes(phase.id)
        const isActive = currentPhase === phase.id
        const isPending = !isCompleted && !isActive

        return (
          <div key={phase.id} className="flex-1 flex items-start">
            <div className="flex-1 flex flex-col items-center">
              {/* Step circle */}
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center border-2 transition-all duration-500 ${
                  isCompleted
                    ? 'bg-legal-forest border-legal-forest text-white'
                    : isActive
                    ? 'bg-legal-navy border-legal-navy text-white'
                    : 'bg-white border-parchment-300 text-ink-400'
                }`}
              >
                {isCompleted ? (
                  <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
                    <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143z" clipRule="evenodd" />
                  </svg>
                ) : isActive ? (
                  <span className="w-2 h-2 rounded-full bg-white dot-live" />
                ) : (
                  <span className="text-xs font-semibold">{i + 1}</span>
                )}
              </div>

              {/* Label */}
              <div className="mt-2 text-center px-1">
                <p className={`text-[11px] font-semibold leading-tight ${
                  isCompleted ? 'text-legal-forest' : isActive ? 'text-legal-navy' : 'text-ink-400'
                }`}>
                  {phase.label}
                </p>
                <p className="text-[10px] text-ink-400 mt-0.5 leading-tight hidden sm:block">
                  {phase.desc}
                </p>
              </div>
            </div>

            {/* Connector line */}
            {i < PHASES.length - 1 && (
              <div className={`h-px flex-shrink-0 w-8 mt-4 transition-all duration-500 ${
                completedPhases.includes(phase.id) ? 'bg-legal-forest' : 'bg-parchment-200'
              }`} />
            )}
          </div>
        )
      })}
    </div>
  )
}

// ── Call Banner ───────────────────────────────────────────────────────────────

function CallBanner({ activeCall, pipelineStatus }) {
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    if (!activeCall) return
    const iv = setInterval(() => setElapsed(Date.now() - activeCall.startedAt), 500)
    return () => clearInterval(iv)
  }, [activeCall])

  const statusLabel = {
    listening: 'Listening',
    processing: 'Processing',
    speaking: 'Speaking',
    ready: 'Ready',
    idle: 'Idle',
  }

  const statusStyle = {
    listening: { bg: 'bg-legal-forest-light border border-legal-forest-border', text: 'text-legal-forest', dot: 'bg-emerald-500' },
    processing: { bg: 'bg-legal-amber-light border border-legal-amber-border', text: 'text-legal-amber', dot: 'bg-amber-500' },
    speaking: { bg: 'bg-legal-navy-light border border-blue-200', text: 'text-legal-navy', dot: 'bg-legal-navy' },
    ready: { bg: 'bg-legal-forest-light border border-legal-forest-border', text: 'text-legal-forest', dot: 'bg-emerald-500' },
    idle: { bg: 'bg-parchment-100 border border-parchment-200', text: 'text-ink-600', dot: 'bg-ink-400' },
  }

  const ss = statusStyle[pipelineStatus] ?? statusStyle.idle

  return (
    <div className="rounded-lg border border-legal-navy/20 overflow-hidden" style={{ backgroundColor: '#1B3A6B' }}>
      <div className="px-5 py-4 flex items-center gap-5">
        {/* LIVE indicator */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className="w-2 h-2 rounded-full bg-emerald-400 dot-live" />
          <span className="text-[10px] font-bold uppercase tracking-widest text-emerald-300">Live</span>
        </div>

        <div className="w-px h-8 bg-white/15 flex-shrink-0" />

        {/* Caller info */}
        <div className="flex-1 min-w-0">
          <p className="text-white font-semibold text-base font-mono tracking-wide">{activeCall.callerPhone}</p>
          <p className="text-blue-200 text-xs mt-0.5">
            {activeCall.agentMode === 'inbound_intake' ? 'Inbound Intake' : 'Outbound Lead'}
            {activeCall.isReturning && ' · Returning Caller'}
          </p>
        </div>

        {/* Duration */}
        <div className="text-right flex-shrink-0">
          <p className="text-white font-mono font-bold text-xl tabular-nums">{fmtDuration(elapsed)}</p>
          <p className="text-blue-300 text-[10px] mt-0.5 uppercase tracking-widest">Duration</p>
        </div>

        {/* Status badge */}
        <div className={`flex-shrink-0 flex items-center gap-2 rounded px-3 py-1.5 ${ss.bg}`}>
          {pipelineStatus === 'speaking' ? (
            <span className={`speaking-wave ${ss.text}`}>
              <span /><span /><span />
            </span>
          ) : (
            <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${ss.dot} ${pipelineStatus === 'listening' ? 'dot-live' : ''}`} />
          )}
          <span className={`text-xs font-semibold ${ss.text}`}>{statusLabel[pipelineStatus] ?? pipelineStatus}</span>
        </div>
      </div>

      {/* Gold accent bar */}
      <div className="h-0.5 bg-gradient-to-r from-legal-gold/50 via-legal-gold-border to-legal-gold/50" />
    </div>
  )
}

// ── Transcript ────────────────────────────────────────────────────────────────

function TranscriptFeed({ transcript, pipelineStatus, activeCall }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [transcript])

  if (!activeCall && transcript.length === 0) return null

  return (
    <div className="bg-white rounded-lg border border-parchment-200 shadow-card flex flex-col h-full overflow-hidden">
      <div className="px-5 py-3 border-b border-parchment-200 flex items-center gap-2.5">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} className="w-4 h-4 text-ink-400">
          <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 0 1 .865-.501 48.172 48.172 0 0 0 3.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0 0 12 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
        </svg>
        <h3 className="text-[13px] font-semibold text-ink-800">Transcript</h3>
        {pipelineStatus === 'listening' && (
          <span className="ml-auto flex items-center gap-1.5 text-[11px] text-legal-forest font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 dot-live" />
            Listening
          </span>
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {transcript.length === 0 && (
          <p className="text-center text-sm text-ink-400 py-10">Waiting for conversation to begin…</p>
        )}
        {transcript.map((msg) => (
          <div
            key={msg.id}
            className={`msg-enter flex gap-2.5 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            {msg.role === 'donna' && (
              <div className="w-7 h-7 rounded-full bg-legal-navy flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-white text-[10px] font-bold tracking-wide">D</span>
              </div>
            )}
            <div className={`max-w-[78%] flex flex-col gap-1 ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
              <div className={`px-3.5 py-2.5 rounded-lg text-sm leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-parchment-100 text-ink-800 border border-parchment-200'
                  : 'bg-legal-navy text-white'
              }`}>
                {msg.text}
              </div>
              <span className="text-[10px] text-ink-400 px-1">{fmt(msg.ts)}</span>
            </div>
            {msg.role === 'user' && (
              <div className="w-7 h-7 rounded-full bg-parchment-200 flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-ink-600 text-[10px] font-bold">C</span>
              </div>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

// ── Activity / AI Actions ─────────────────────────────────────────────────────

function ToolCallCard({ activity }) {
  const [open, setOpen] = useState(false)
  const isOk = activity.result?.ok !== false
  const toolLabel = TOOL_LABELS[activity.tool] ?? activity.tool

  return (
    <div className="activity-enter">
      <button onClick={() => setOpen(!open)} className="w-full text-left">
        <div className="flex items-start gap-3 py-2.5 px-3 rounded hover:bg-parchment-50 transition-colors">
          <div className={`w-6 h-6 rounded flex items-center justify-center flex-shrink-0 mt-0.5 border ${
            isOk
              ? 'bg-legal-forest-light border-legal-forest-border'
              : 'bg-legal-crimson-light border-legal-crimson-border'
          }`}>
            {isOk ? (
              <svg viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5 text-legal-forest">
                <path d="M13.854 3.646a.5.5 0 0 1 0 .708l-7 7a.5.5 0 0 1-.708 0l-3.5-3.5a.5.5 0 1 1 .708-.708L6.5 10.293l6.646-6.647a.5.5 0 0 1 .708 0z" />
              </svg>
            ) : (
              <svg viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5 text-legal-crimson">
                <path d="M4.646 4.646a.5.5 0 0 1 .708 0L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 0 1 0-.708z" />
              </svg>
            )}
          </div>

          <div className="flex-1 min-w-0">
            <p className="text-xs font-mono text-ink-600 leading-tight">{activity.tool}</p>
            <p className="text-[11px] text-ink-400 mt-0.5 leading-tight">{toolLabel}</p>
            <p className="text-[10px] text-parchment-400 mt-0.5">{fmt(activity.ts)}</p>
          </div>

          <svg
            viewBox="0 0 20 20"
            fill="currentColor"
            className={`w-3.5 h-3.5 text-ink-300 flex-shrink-0 mt-1 transition-transform ${open ? 'rotate-180' : ''}`}
          >
            <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 0 1 1.06.02L10 11.168l3.71-3.938a.75.75 0 1 1 1.08 1.04l-4.25 4.5a.75.75 0 0 1-1.08 0l-4.25-4.5a.75.75 0 0 1 .02-1.06z" clipRule="evenodd" />
          </svg>
        </div>
      </button>

      {open && (
        <div className="mx-3 mb-1 rounded border border-parchment-200 bg-parchment-50 p-3 text-[11px] font-mono text-ink-600 overflow-x-auto">
          <pre className="whitespace-pre-wrap break-all">{JSON.stringify({ args: activity.args, result: activity.result }, null, 2)}</pre>
        </div>
      )}
    </div>
  )
}

function ActivityFeed({ activities, activeCall }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [activities])

  const toolActivities = activities.filter((a) => ['tool_call', 'system', 'call_ended'].includes(a.type))

  return (
    <div className="bg-white rounded-lg border border-parchment-200 shadow-card flex flex-col h-full overflow-hidden">
      <div className="px-5 py-3 border-b border-parchment-200 flex items-center gap-2.5">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} className="w-4 h-4 text-ink-400">
          <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
        </svg>
        <h3 className="text-[13px] font-semibold text-ink-800">AI Actions</h3>
        {toolActivities.length > 0 && (
          <span className="ml-auto text-[10px] bg-parchment-100 text-ink-500 font-medium rounded px-2 py-0.5">
            {toolActivities.filter((a) => a.type === 'tool_call').length} calls
          </span>
        )}
      </div>

      <div className="flex-1 overflow-y-auto py-2">
        {toolActivities.length === 0 && (
          <p className="text-center text-sm text-ink-400 py-10">Actions will appear here</p>
        )}

        {toolActivities.map((activity) => {
          if (activity.type === 'system') {
            return (
              <div key={activity.id} className="activity-enter px-4 py-2">
                <div className="flex items-center gap-2 text-[11px] text-ink-400">
                  <span className="w-1 h-1 rounded-full bg-parchment-300 flex-shrink-0" />
                  <span>{activity.text}</span>
                  <span className="ml-auto font-mono">{fmt(activity.ts)}</span>
                </div>
              </div>
            )
          }

          if (activity.type === 'call_ended') {
            return (
              <div key={activity.id} className="activity-enter px-4 py-3">
                <div className="rounded border border-parchment-200 bg-parchment-50 px-4 py-3 text-center">
                  <p className="text-sm font-semibold text-ink-700">Call Ended</p>
                  <p className="text-xs text-ink-400 mt-1">
                    Duration: {activity.duration}s · Outcome: {activity.outcome}
                  </p>
                </div>
              </div>
            )
          }

          return <ToolCallCard key={activity.id} activity={activity} />
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

// ── Idle State ────────────────────────────────────────────────────────────────

function IdleState({ stats, demoRunning, onRunDemo }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center px-8 py-16">
      {/* Emblem */}
      <div className="w-16 h-16 rounded-xl border-2 border-legal-gold-border bg-legal-gold-light flex items-center justify-center mb-6 shadow-md">
        <svg viewBox="0 0 24 24" fill="none" stroke="#B8860B" strokeWidth={1.5} className="w-8 h-8">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v1.5M12 3 9 6M12 3l3 3M6 9l-3 3 3 3M18 9l3 3-3 3M3 12h18M6 9h12M6 15h12M9 21h6M12 18v3" />
        </svg>
      </div>

      <h1 className="text-2xl font-semibold text-ink-900 text-center" style={{ fontFamily: "'Playfair Display', Georgia, serif" }}>
        Donna is standing by
      </h1>
      <p className="text-ink-500 mt-2 text-center max-w-sm text-sm leading-relaxed">
        Waiting for inbound calls. Donna will handle intake, qualification, and scheduling automatically.
      </p>

      {/* Stats */}
      <div className="mt-10 grid grid-cols-3 gap-4 w-full max-w-md">
        {[
          { label: 'Calls Today', value: stats.callsToday },
          { label: 'Cases Created', value: stats.casesCreated },
          { label: 'Consultations', value: stats.consultationsBooked },
        ].map(({ label, value }) => (
          <div key={label} className="bg-white rounded-lg border border-parchment-200 shadow-card px-4 py-4 text-center">
            <p className="text-3xl font-bold text-legal-navy" style={{ fontFamily: "'Playfair Display', Georgia, serif" }}>{value}</p>
            <p className="text-[11px] text-ink-500 mt-1 font-medium">{label}</p>
          </div>
        ))}
      </div>

      {/* Demo CTA */}
      <button
        onClick={onRunDemo}
        disabled={demoRunning}
        className={`mt-8 flex items-center gap-2.5 px-6 py-3 rounded-md text-sm font-semibold transition-all ${
          demoRunning
            ? 'bg-parchment-100 text-ink-400 border border-parchment-200 cursor-not-allowed'
            : 'bg-legal-navy text-white hover:bg-legal-navy-hover shadow-card-md'
        }`}
      >
        <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
          <path fillRule="evenodd" d="M4.5 5.653c0-1.427 1.529-2.33 2.779-1.643l11.54 6.347c1.295.712 1.295 2.573 0 3.286L7.28 19.99c-1.25.687-2.779-.217-2.779-1.643V5.653z" clipRule="evenodd" />
        </svg>
        {demoRunning ? 'Demo in progress…' : 'Run Demo Intake Call'}
      </button>

      <p className="mt-3 text-[11px] text-ink-400 text-center">
        Simulates a full PI intake call · ~60 seconds
      </p>
    </div>
  )
}

// ── Main view ─────────────────────────────────────────────────────────────────

export default function LiveCallView({
  activeCall,
  currentPhase,
  completedPhases,
  transcript,
  activities,
  pipelineStatus,
  stats,
  demoRunning,
  onRunDemo,
}) {
  const hasActivity = activeCall || transcript.length > 0 || activities.length > 0

  return (
    <div className="flex-1 overflow-hidden flex flex-col">
      {/* Page header */}
      <div className="flex-shrink-0 px-6 py-4 border-b border-parchment-200 bg-white">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-ink-900" style={{ fontFamily: "'Playfair Display', Georgia, serif" }}>
              Live Call
            </h2>
            <p className="text-[12px] text-ink-400 mt-0.5">Real-time intake monitoring</p>
          </div>
          {!activeCall && !demoRunning && (
            <button
              onClick={onRunDemo}
              className="flex items-center gap-2 px-3.5 py-2 rounded-md bg-legal-navy text-white text-[13px] font-semibold hover:bg-legal-navy-hover transition-colors"
            >
              <svg viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5">
                <path d="M6.3 2.841A1.5 1.5 0 0 0 4 4.11V15.89a1.5 1.5 0 0 0 2.3 1.269l9.344-5.89a1.5 1.5 0 0 0 0-2.538L6.3 2.84z" />
              </svg>
              Simulate Demo
            </button>
          )}
        </div>
      </div>

      {!hasActivity ? (
        <IdleState stats={stats} demoRunning={demoRunning} onRunDemo={onRunDemo} />
      ) : (
        <div className="flex-1 overflow-hidden flex flex-col px-6 py-5 gap-4">
          {/* Call banner */}
          {activeCall && (
            <div className="flex-shrink-0 animate-slide-up">
              <CallBanner activeCall={activeCall} pipelineStatus={pipelineStatus} />
            </div>
          )}

          {/* Intake Pipeline */}
          {activeCall && (
            <div className="flex-shrink-0 bg-white rounded-lg border border-parchment-200 shadow-card px-6 py-4 animate-fade-in">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-[13px] font-semibold text-ink-800">Intake Pipeline</h3>
                {currentPhase && (
                  <span className="text-[11px] bg-legal-navy-light text-legal-navy font-semibold px-2.5 py-1 rounded">
                    {currentPhase}
                  </span>
                )}
              </div>
              <WorkflowSteps currentPhase={currentPhase} completedPhases={completedPhases} />
            </div>
          )}

          {/* Transcript + Actions panels */}
          <div className="flex-1 overflow-hidden grid grid-cols-3 gap-4 min-h-0">
            <div className="col-span-2 min-h-0">
              <TranscriptFeed transcript={transcript} pipelineStatus={pipelineStatus} activeCall={activeCall} />
            </div>
            <div className="col-span-1 min-h-0">
              <ActivityFeed activities={activities} activeCall={activeCall} />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
