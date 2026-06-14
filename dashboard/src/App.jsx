import { useReducer, useRef, useCallback, useEffect, useState } from 'react'
import { useDonnaWS } from './hooks/useDonnaWS.js'
import { PHASE_IDS, TOOL_TO_PHASE, API_URL } from './lib/constants.js'
import { DEMO_SEQUENCE, DEMO_CASES, DEMO_EVENTS, DEMO_LEADS } from './lib/demo.js'
import Sidebar from './components/Sidebar.jsx'
import LiveCallView from './views/LiveCallView.jsx'
import CasesView from './views/CasesView.jsx'
import CalendarView from './views/CalendarView.jsx'
import EmailsView from './views/EmailsView.jsx'
import LeadsView from './views/LeadsView.jsx'

// ── Initial state ─────────────────────────────────────────────────────────────

const initialState = {
  wsConnected: false,
  activeCall: null,
  currentPhase: null,
  completedPhases: [],
  transcript: [],
  activities: [],
  pipelineStatus: 'idle',
  emailDrafts: [],
  activeTab: 'live',
  demoRunning: false,
  // session stats (today)
  stats: { callsToday: 0, casesCreated: 0, consultationsBooked: 0 },
}

// ── Reducer ───────────────────────────────────────────────────────────────────

function reducer(state, action) {
  const ts = action.ts || Date.now()

  switch (action.type) {
    case '__connected':
      return { ...state, wsConnected: true }

    case '__disconnected':
      return { ...state, wsConnected: false }

    case 'call_started': {
      const { callSid, callerPhone, agentMode, isReturning } = action
      return {
        ...state,
        activeCall: { callSid, callerPhone, agentMode, isReturning, startedAt: ts },
        currentPhase: 'DISCLOSURE',
        completedPhases: [],
        transcript: [],
        activities: [
          {
            id: `sys-${ts}`,
            type: 'system',
            text: isReturning ? 'Returning caller — prior session found' : 'New inbound call',
            ts,
          },
        ],
        pipelineStatus: 'ready',
        activeTab: 'live',
        stats: { ...state.stats, callsToday: state.stats.callsToday + 1 },
      }
    }

    case 'call_ended': {
      const { duration, outcome } = action
      return {
        ...state,
        activeCall: null,
        currentPhase: null,
        completedPhases: [],
        pipelineStatus: 'idle',
        demoRunning: false,
        activities: [
          ...state.activities,
          {
            id: `end-${ts}`,
            type: 'call_ended',
            duration,
            outcome,
            ts,
          },
        ],
      }
    }

    case 'user_speech':
      if (!state.activeCall && (action.callSid || action.sessionId)) {
        return {
          ...state,
          activeCall: {
            callSid: action.callSid || action.sessionId,
            callerPhone: action.callerPhone || 'Local Mic',
            agentMode: action.agentMode || 'local_assistant',
            isReturning: false,
            startedAt: ts,
          },
          currentPhase: state.currentPhase || 'DISCLOSURE',
          pipelineStatus: state.pipelineStatus === 'idle' ? 'ready' : state.pipelineStatus,
          activeTab: 'live',
          transcript: [
            ...state.transcript,
            { id: `u-${ts}-${Math.random()}`, role: 'user', text: action.text, ts },
          ],
        }
      }
      return {
        ...state,
        transcript: [
          ...state.transcript,
          { id: `u-${ts}-${Math.random()}`, role: 'user', text: action.text, ts },
        ],
      }

    case 'donna_speech':
      return {
        ...state,
        transcript: [
          ...state.transcript,
          { id: `d-${ts}-${Math.random()}`, role: 'donna', text: action.text, ts },
        ],
      }

    case 'pipeline_status':
      return { ...state, pipelineStatus: action.status }

    case 'tool_result':
    case 'tool_call': {
      const newPhase = TOOL_TO_PHASE[action.tool] ?? state.currentPhase
      const oldIdx = PHASE_IDS.indexOf(state.currentPhase)
      const newIdx = PHASE_IDS.indexOf(newPhase)
      const completed = [...state.completedPhases]

      if (newIdx > oldIdx && oldIdx >= 0) {
        for (let i = oldIdx; i < newIdx; i++) {
          if (!completed.includes(PHASE_IDS[i])) completed.push(PHASE_IDS[i])
        }
      }

      const isCaseCreate = action.tool === 'case.create'
      const isCalendar = action.tool === 'calendar.create_event'

      return {
        ...state,
        currentPhase: newPhase,
        completedPhases: completed,
        activities: [
          ...state.activities,
          {
            id: `tool-${ts}-${Math.random()}`,
            type: 'tool_call',
            tool: action.tool,
            args: action.args,
            result: action.result,
            ts,
          },
        ],
        stats: {
          ...state.stats,
          casesCreated: isCaseCreate ? state.stats.casesCreated + 1 : state.stats.casesCreated,
          consultationsBooked: isCalendar ? state.stats.consultationsBooked + 1 : state.stats.consultationsBooked,
        },
      }
    }

    case 'email_draft_pending':
      return {
        ...state,
        emailDrafts: [
          ...state.emailDrafts,
          { ...action, ts },
        ],
      }

    case 'email_sent':
    case 'email_rejected':
      return {
        ...state,
        emailDrafts: state.emailDrafts.filter((d) => d.draft_id !== action.draft_id),
      }

    case 'set_tab':
      return { ...state, activeTab: action.tab }

    case 'set_demo_running':
      return { ...state, demoRunning: action.value }

    default:
      return state
  }
}

// ── App ───────────────────────────────────────────────────────────────────────

export default function App() {
  const [state, dispatch] = useReducer(reducer, initialState)
  const dispatchRef = useRef(dispatch)
  dispatchRef.current = dispatch

  // Stable event handler for WebSocket
  const handleEvent = useCallback((event) => {
    dispatchRef.current(event)
  }, [])

  useDonnaWS(handleEvent)

  // Demo simulation timers
  const demoTimers = useRef([])

  const runDemo = useCallback(() => {
    if (state.demoRunning) return
    dispatch({ type: 'set_demo_running', value: true })

    demoTimers.current.forEach(clearTimeout)
    demoTimers.current = []

    DEMO_SEQUENCE.forEach(({ delay, event }) => {
      const t = setTimeout(() => {
        dispatchRef.current({ ...event, ts: Date.now() })
      }, delay)
      demoTimers.current.push(t)
    })
  }, [state.demoRunning])

  // Leads / cases / calendar / email drafts from backend API
  const [leads, setLeads] = useState([])
  const [cases, setCases] = useState(DEMO_CASES)
  const [calendarEvents, setCalendarEvents] = useState(DEMO_EVENTS)
  const [apiEmailDrafts, setApiEmailDrafts] = useState([])
  const [backendConnected, setBackendConnected] = useState(false)

  const refreshBackend = useCallback(async () => {
    try {
      const health = await fetch(`${API_URL}/health`)
      if (!health.ok) {
        setBackendConnected(false)
        return
      }
      setBackendConnected(true)

      const [leadsRes, casesRes, eventsRes, draftsRes] = await Promise.all([
        fetch(`${API_URL}/api/leads`),
        fetch(`${API_URL}/api/cases`),
        fetch(`${API_URL}/api/calendar/events`),
        fetch(`${API_URL}/api/emails/drafts`),
      ])

      if (leadsRes.ok) {
        const data = await leadsRes.json()
        setLeads(data.leads ?? [])
      }
      if (casesRes.ok) {
        const data = await casesRes.json()
        if (data.cases?.length) setCases(data.cases)
      }
      if (eventsRes.ok) {
        const data = await eventsRes.json()
        if (data.events?.length) setCalendarEvents(data.events)
      }
      if (draftsRes.ok) {
        const data = await draftsRes.json()
        setApiEmailDrafts(data.drafts ?? [])
      }
    } catch {
      setBackendConnected(false)
    }
  }, [])

  useEffect(() => {
    refreshBackend()
    const interval = setInterval(refreshBackend, 15000)
    return () => clearInterval(interval)
  }, [refreshBackend])

  const emailDrafts = (() => {
    const merged = new Map()
    for (const draft of [...apiEmailDrafts, ...state.emailDrafts]) {
      if (draft?.draft_id) merged.set(draft.draft_id, draft)
    }
    return [...merged.values()]
  })()

  const addLead = useCallback(async (lead) => {
    try {
      const res = await fetch(`${API_URL}/api/leads`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(lead),
      })
      if (res.ok) {
        const data = await res.json()
        setLeads((prev) => [data.lead, ...prev])
      }
    } catch {
      setLeads((prev) => [{ id: `local-${Date.now()}`, ...lead, status: 'new', created_at: new Date().toISOString() }, ...prev])
    }
    refreshBackend()
  }, [refreshBackend])

  const callLead = useCallback(async (lead) => {
    try {
      await fetch(`${API_URL}/api/calls/outbound`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone: lead.phone, lead_id: lead.id }),
      })
      setLeads((prev) =>
        prev.map((l) => (l.id === lead.id ? { ...l, status: 'contacted' } : l))
      )
      refreshBackend()
    } catch {
      // show graceful error
    }
  }, [refreshBackend])

  const approveEmail = useCallback(async (draft) => {
    try {
      await fetch(`${API_URL}/api/emails/${draft.draft_id}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ case_id: draft.case_id }),
      })
    } catch {}
    dispatch({ type: 'email_sent', draft_id: draft.draft_id })
    refreshBackend()
  }, [refreshBackend])

  const rejectEmail = useCallback(async (draft, reason) => {
    try {
      await fetch(`${API_URL}/api/emails/${draft.draft_id}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ case_id: draft.case_id, reason }),
      })
    } catch {}
    dispatch({ type: 'email_rejected', draft_id: draft.draft_id })
    refreshBackend()
  }, [refreshBackend])

  const views = {
    live: (
      <LiveCallView
        activeCall={state.activeCall}
        currentPhase={state.currentPhase}
        completedPhases={state.completedPhases}
        transcript={state.transcript}
        activities={state.activities}
        pipelineStatus={state.pipelineStatus}
        stats={state.stats}
        demoRunning={state.demoRunning}
        onRunDemo={runDemo}
      />
    ),
    cases: <CasesView cases={cases} />,
    calendar: <CalendarView events={calendarEvents} />,
    emails: (
      <EmailsView
        drafts={emailDrafts}
        onApprove={approveEmail}
        onReject={rejectEmail}
      />
    ),
    leads: (
      <LeadsView
        leads={leads}
        onAdd={addLead}
        onCall={callLead}
      />
    ),
  }

  return (
    <div className="flex h-screen overflow-hidden bg-[#F0F4F8]">
      <Sidebar
        activeTab={state.activeTab}
        onTabChange={(tab) => dispatch({ type: 'set_tab', tab })}
        wsConnected={state.wsConnected}
        activeCall={state.activeCall}
        emailDraftsCount={emailDrafts.length}
        newLeadsCount={leads.filter((l) => l.status === 'new').length}
        pipelineStatus={state.pipelineStatus}
        backendConnected={backendConnected}
      />
      <main className="flex-1 overflow-hidden flex flex-col">
        {views[state.activeTab]}
      </main>
    </div>
  )
}
