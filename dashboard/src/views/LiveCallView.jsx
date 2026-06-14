import { useEffect, useRef, useState } from 'react'
import { PHASES, PHASE_IDS, TOOL_LABELS } from '../lib/constants.js'

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(ts) {
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function fmtDuration(ms) {
  const s = Math.floor(ms / 1000)
  const m = Math.floor(s / 60)
  const sec = s % 60
  return `${m}:${sec.toString().padStart(2, '0')}`
}

// ── WorkflowSteps ─────────────────────────────────────────────────────────────

function WorkflowSteps({ currentPhase, completedPhases }) {
  return (
    <div className="flex items-start gap-0">
      {PHASES.map((phase, i) => {
        const isCompleted = completedPhases.includes(phase.id)
        const isActive = currentPhase === phase.id
        const isPending = !isCompleted && !isActive

        return (
          <div key={phase.id} className="flex-1 flex items-center">
            <div className="flex-1 flex flex-col items-center">
              {/* Circle */}
              <div className="relative flex items-center justify-center">
                <div
                  className={`w-9 h-9 rounded-full flex items-center justify-center border-2 transition-all duration-500 ${
                    isCompleted
                      ? 'bg-emerald-500 border-emerald-500 shadow-emerald-200 shadow-lg'
                      : isActive
                      ? 'bg-blue-600 border-blue-600 shadow-blue-200 shadow-lg step-active-ring'
                      : 'bg-white border-slate-200'
                  }`}
                >
                  {isCompleted ? (
                    <svg viewBox="0 0 20 20" fill="white" className="w-5 h-5">
                      <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143z" clipRule="evenodd" />
                    </svg>
                  ) : isActive ? (
                    <div className="w-2.5 h-2.5 rounded-full bg-white animate-pulse" />
                  ) : (
                    <span className="text-xs font-semibold text-slate-400">{i + 1}</span>
                  )}
                </div>
              </div>

              {/* Label */}
              <div className="mt-2 text-center px-1">
                <p
                  className={`text-[11px] font-semibold leading-tight ${
                    isCompleted
                      ? 'text-emerald-600'
                      : isActive
                      ? 'text-blue-700'
                      : 'text-slate-400'
                  }`}
                >
                  {phase.label}
                </p>
                <p className="text-[10px] text-slate-400 mt-0.5 leading-tight hidden sm:block">
                  {phase.desc}
                </p>
              </div>
            </div>

            {/* Connector */}
            {i < PHASES.length - 1 && (
              <div
                className={`h-0.5 flex-shrink-0 w-8 mt-[-20px] transition-all duration-500 ${
                  completedPhases.includes(phase.id)
                    ? 'bg-emerald-400'
                    : currentPhase === phase.id
                    ? 'bg-gradient-to-r from-blue-400 to-slate-200'
                    : 'bg-slate-200'
                }`}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}

// ── Call banner ───────────────────────────────────────────────────────────────

function CallBanner({ activeCall, pipelineStatus }) {
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    if (!activeCall) return
    const iv = setInterval(() => setElapsed(Date.now() - activeCall.startedAt), 500)
    return () => clearInterval(iv)
  }, [activeCall])

  const statusLabel = {
    listening: 'Listening…',
    processing: 'Processing…',
    speaking: 'Speaking',
    ready: 'Ready',
    idle: 'Idle',
  }

  const statusDotColor = {
    listening: 'bg-emerald-400',
    processing: 'bg-amber-400',
    speaking: 'bg-blue-400',
    ready: 'bg-emerald-400',
    idle: 'bg-slate-400',
  }

  return (
    <div className="call-banner-shimmer rounded-2xl px-6 py-4 flex items-center gap-6 shadow-xl shadow-blue-900/20">
      {/* Live indicator */}
      <div className="flex items-center gap-2 flex-shrink-0">
        <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 dot-live" />
        <span className="text-[11px] font-bold uppercase tracking-widest text-white/90">Live</span>
      </div>

      {/* Divider */}
      <div className="w-px h-8 bg-white/20 flex-shrink-0" />

      {/* Phone */}
      <div className="flex-1 min-w-0">
        <p className="text-white font-bold text-lg tracking-wide font-mono">
          {activeCall.callerPhone}
        </p>
        <p className="text-blue-200 text-xs mt-0.5">
          {activeCall.agentMode === 'inbound_intake' ? 'Inbound Intake' : 'Outbound Lead'}
          {activeCall.isReturning && ' · Returning Caller'}
        </p>
      </div>

      {/* Duration */}
      <div className="text-right flex-shrink-0">
        <p className="text-white font-mono font-bold text-xl">{fmtDuration(elapsed)}</p>
        <p className="text-blue-200 text-[11px] mt-0.5">Duration</p>
      </div>

      {/* Donna status */}
      <div className="flex-shrink-0 flex items-center gap-2 bg-white/10 rounded-xl px-3 py-2">
        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${statusDotColor[pipelineStatus] ?? 'bg-slate-400'}`} />
        {pipelineStatus === 'speaking' && (
          <span className="speaking-wave text-white flex gap-0.5">
            <span /><span /><span />
          </span>
        )}
        <span className="text-white text-xs font-medium">
          {statusLabel[pipelineStatus] ?? pipelineStatus}
        </span>
      </div>
    </div>
  )
}

// ── Transcript feed ───────────────────────────────────────────────────────────

function TranscriptFeed({ transcript, pipelineStatus, activeCall }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [transcript])

  if (!activeCall && transcript.length === 0) return null

  return (
    <div className="bg-white rounded-2xl border border-slate-100 shadow-sm flex flex-col h-full overflow-hidden">
      <div className="px-5 py-3.5 border-b border-slate-100 flex items-center gap-2">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-4 h-4 text-slate-400">
          <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 0 1 .865-.501 48.172 48.172 0 0 0 3.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0 0 12 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
        </svg>
        <h3 className="text-sm font-semibold text-slate-700">Conversation</h3>
        {pipelineStatus === 'listening' && (
          <span className="ml-auto flex items-center gap-1.5 text-[11px] text-emerald-600 font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 dot-live" />
            Listening
          </span>
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {transcript.length === 0 && (
          <p className="text-center text-sm text-slate-400 py-8">
            Waiting for conversation to begin…
          </p>
        )}
        {transcript.map((msg) => (
          <div
            key={msg.id}
            className={`msg-enter flex gap-2.5 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            {msg.role === 'donna' && (
              <div className="w-7 h-7 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center flex-shrink-0 mt-0.5 shadow">
                <span className="text-white text-[10px] font-bold">D</span>
              </div>
            )}
            <div className={`max-w-[80%] ${msg.role === 'user' ? 'items-end' : 'items-start'} flex flex-col gap-1`}>
              <div
                className={`px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-slate-100 text-slate-800 rounded-tr-sm'
                    : 'bg-blue-600 text-white rounded-tl-sm shadow-md shadow-blue-600/20'
                }`}
              >
                {msg.text}
              </div>
              <span className="text-[10px] text-slate-400 px-1">{fmt(msg.ts)}</span>
            </div>
            {msg.role === 'user' && (
              <div className="w-7 h-7 rounded-full bg-slate-200 flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-slate-600 text-[10px] font-bold">C</span>
              </div>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

// ── Activity feed ─────────────────────────────────────────────────────────────

function ToolCallCard({ activity }) {
  const [open, setOpen] = useState(false)
  const isOk = activity.result?.ok !== false

  const toolLabel = TOOL_LABELS[activity.tool] ?? activity.tool
  const phaseColors = {
    record_consent: 'text-indigo-600 bg-indigo-50',
    'intake.start': 'text-blue-600 bg-blue-50',
    'intake.update': 'text-blue-600 bg-blue-50',
    'case.qualify': 'text-violet-600 bg-violet-50',
    'case.create': 'text-green-600 bg-green-50',
    'case.decline': 'text-red-600 bg-red-50',
    'calendar.create_event': 'text-emerald-600 bg-emerald-50',
    'notify.dashboard': 'text-slate-600 bg-slate-50',
  }

  return (
    <div className="activity-enter">
      <button
        onClick={() => setOpen(!open)}
        className="w-full text-left"
      >
        <div className="flex items-start gap-3 py-2.5 px-3 rounded-xl hover:bg-slate-50 transition-colors">
          {/* Status icon */}
          <div className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5 ${isOk ? 'bg-emerald-50' : 'bg-red-50'}`}>
            {isOk ? (
              <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 text-emerald-500">
                <path fillRule="evenodd" d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16zm3.857-9.809a.75.75 0 0 0-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 1 0-1.06 1.061l2.5 2.5a.75.75 0 0 0 1.137-.089l4-5.5z" clipRule="evenodd" />
              </svg>
            ) : (
              <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 text-red-500">
                <path fillRule="evenodd" d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM8.28 7.22a.75.75 0 0 0-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 1 0 1.06 1.06L10 11.06l1.72 1.72a.75.75 0 1 0 1.06-1.06L11.06 10l1.72-1.72a.75.75 0 0 0-1.06-1.06L10 8.94 8.28 7.22z" clipRule="evenodd" />
              </svg>
            )}
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-md font-mono ${phaseColors[activity.tool] ?? 'text-slate-600 bg-slate-50'}`}>
                {activity.tool}
              </span>
            </div>
            <p className="text-xs text-slate-600 mt-0.5">{toolLabel}</p>
            <p className="text-[10px] text-slate-400 mt-0.5">{fmt(activity.ts)}</p>
          </div>

          <svg
            viewBox="0 0 20 20"
            fill="currentColor"
            className={`w-4 h-4 text-slate-300 flex-shrink-0 mt-1 transition-transform ${open ? 'rotate-180' : ''}`}
          >
            <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 0 1 1.06.02L10 11.168l3.71-3.938a.75.75 0 1 1 1.08 1.04l-4.25 4.5a.75.75 0 0 1-1.08 0l-4.25-4.5a.75.75 0 0 1 .02-1.06z" clipRule="evenodd" />
          </svg>
        </div>
      </button>

      {open && (
        <div className="mx-3 mb-2 rounded-xl bg-slate-50 border border-slate-100 p-3 text-[11px] font-mono text-slate-600 overflow-x-auto">
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

  const toolActivities = activities.filter((a) => a.type === 'tool_call' || a.type === 'system' || a.type === 'call_ended')

  return (
    <div className="bg-white rounded-2xl border border-slate-100 shadow-sm flex flex-col h-full overflow-hidden">
      <div className="px-5 py-3.5 border-b border-slate-100 flex items-center gap-2">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-4 h-4 text-slate-400">
          <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
        </svg>
        <h3 className="text-sm font-semibold text-slate-700">AI Actions</h3>
        {toolActivities.length > 0 && (
          <span className="ml-auto text-[11px] bg-slate-100 text-slate-500 font-medium rounded-full px-2 py-0.5">
            {toolActivities.filter((a) => a.type === 'tool_call').length} calls
          </span>
        )}
      </div>

      <div className="flex-1 overflow-y-auto py-2">
        {toolActivities.length === 0 && (
          <p className="text-center text-sm text-slate-400 py-8">
            AI actions will appear here
          </p>
        )}

        {toolActivities.map((activity) => {
          if (activity.type === 'system') {
            return (
              <div key={activity.id} className="activity-enter px-4 py-2">
                <div className="flex items-center gap-2 text-[11px] text-slate-400">
                  <span className="w-1 h-1 rounded-full bg-slate-300" />
                  <span>{activity.text}</span>
                  <span className="ml-auto">{fmt(activity.ts)}</span>
                </div>
              </div>
            )
          }

          if (activity.type === 'call_ended') {
            return (
              <div key={activity.id} className="activity-enter px-4 py-3">
                <div className="rounded-xl bg-slate-50 border border-slate-200 px-4 py-3 text-center">
                  <p className="text-sm font-semibold text-slate-700">Call Ended</p>
                  <p className="text-xs text-slate-500 mt-1">
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

// ── Empty / idle state ────────────────────────────────────────────────────────

function IdleState({ stats, demoRunning, onRunDemo }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center px-8 py-16">
      {/* Hero */}
      <div className="w-20 h-20 rounded-3xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-2xl shadow-blue-500/30 mb-6">
        <svg viewBox="0 0 24 24" fill="white" className="w-10 h-10">
          <path d="M12 1.5c-1.921 0-3.816.111-5.68.327-1.497.174-2.57 1.46-2.57 2.93V21.75a.75.75 0 0 0 1.029.696l3.471-1.388 3.472 1.388a.75.75 0 0 0 .556 0l3.472-1.388 3.471 1.388a.75.75 0 0 0 1.029-.696V4.757c0-1.47-1.073-2.756-2.57-2.93A49.255 49.255 0 0 0 12 1.5z" />
        </svg>
      </div>

      <h1 className="text-2xl font-bold text-slate-900 text-center">Donna is ready</h1>
      <p className="text-slate-500 mt-2 text-center max-w-sm text-sm leading-relaxed">
        Waiting for inbound calls. All intake, qualification, and scheduling happens automatically.
      </p>

      {/* Stats */}
      <div className="mt-10 grid grid-cols-3 gap-5 w-full max-w-md">
        {[
          { label: 'Calls Today', value: stats.callsToday },
          { label: 'Cases Created', value: stats.casesCreated },
          { label: 'Consultations', value: stats.consultationsBooked },
        ].map(({ label, value }) => (
          <div key={label} className="bg-white rounded-2xl px-4 py-4 border border-slate-100 shadow-sm text-center">
            <p className="text-3xl font-bold text-slate-900">{value}</p>
            <p className="text-[11px] text-slate-500 mt-1 font-medium">{label}</p>
          </div>
        ))}
      </div>

      {/* Demo button */}
      <button
        onClick={onRunDemo}
        disabled={demoRunning}
        className={`mt-8 flex items-center gap-3 px-6 py-3.5 rounded-2xl font-semibold text-sm transition-all shadow-lg ${
          demoRunning
            ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
            : 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white hover:from-blue-700 hover:to-indigo-700 shadow-blue-500/30 hover:shadow-xl hover:-translate-y-0.5'
        }`}
      >
        <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
          <path fillRule="evenodd" d="M4.5 5.653c0-1.427 1.529-2.33 2.779-1.643l11.54 6.347c1.295.712 1.295 2.573 0 3.286L7.28 19.99c-1.25.687-2.779-.217-2.779-1.643V5.653z" clipRule="evenodd" />
        </svg>
        {demoRunning ? 'Demo running…' : 'Simulate Demo Call'}
      </button>

      <p className="mt-3 text-[11px] text-slate-400 text-center">
        Plays a scripted PI intake call end-to-end. ~60 seconds.
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
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-5 border-b border-slate-200/60 bg-white/60 backdrop-blur-sm">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Live Call</h2>
            <p className="text-sm text-slate-500 mt-0.5">Real-time intake workflow</p>
          </div>
          {!activeCall && !demoRunning && (
            <button
              onClick={onRunDemo}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 transition-colors shadow-md shadow-blue-500/20"
            >
              <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
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
        <div className="flex-1 overflow-hidden flex flex-col px-6 py-5 gap-5">
          {/* Call banner */}
          {activeCall && (
            <div className="flex-shrink-0 animate-slide-up">
              <CallBanner activeCall={activeCall} pipelineStatus={pipelineStatus} />
            </div>
          )}

          {/* Workflow steps */}
          {activeCall && (
            <div className="flex-shrink-0 bg-white rounded-2xl border border-slate-100 shadow-sm px-6 py-5 animate-fade-in">
              <div className="flex items-center justify-between mb-5">
                <h3 className="text-sm font-semibold text-slate-700">Intake Pipeline</h3>
                {currentPhase && (
                  <span className="text-[11px] bg-blue-50 text-blue-700 font-semibold px-2.5 py-1 rounded-full">
                    {currentPhase}
                  </span>
                )}
              </div>
              <WorkflowSteps currentPhase={currentPhase} completedPhases={completedPhases} />
            </div>
          )}

          {/* Main panels */}
          <div className="flex-1 overflow-hidden grid grid-cols-3 gap-5 min-h-0">
            {/* Transcript — 2/3 width */}
            <div className="col-span-2 min-h-0">
              <TranscriptFeed
                transcript={transcript}
                pipelineStatus={pipelineStatus}
                activeCall={activeCall}
              />
            </div>

            {/* Activity feed — 1/3 width */}
            <div className="col-span-1 min-h-0">
              <ActivityFeed activities={activities} activeCall={activeCall} />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
