export const PHASES = [
  {
    id: 'DISCLOSURE',
    label: 'Consent',
    desc: 'AI disclosure & recording consent',
    color: 'indigo',
  },
  {
    id: 'INTAKE',
    label: 'Intake',
    desc: 'Gathering incident details',
    color: 'blue',
  },
  {
    id: 'QUALIFICATION',
    label: 'Qualify',
    desc: 'Case qualification check',
    color: 'violet',
  },
  {
    id: 'BOOKING',
    label: 'Schedule',
    desc: 'Booking consultation',
    color: 'emerald',
  },
  {
    id: 'CLOSE',
    label: 'Complete',
    desc: 'Summary & next steps',
    color: 'green',
  },
]

export const PHASE_IDS = PHASES.map((p) => p.id)

export const TOOL_TO_PHASE = {
  record_consent: 'DISCLOSURE',
  'intake.start': 'INTAKE',
  'intake.update': 'INTAKE',
  'case.qualify': 'QUALIFICATION',
  'case.create': 'CLOSE',
  'case.decline': 'CLOSE',
  'calendar.create_event': 'BOOKING',
  'notify.dashboard': 'CLOSE',
}

export const TOOL_LABELS = {
  record_consent: 'Record Consent',
  'intake.start': 'Start Intake',
  'intake.update': 'Update Intake',
  'case.qualify': 'Qualify Case',
  'case.create': 'Create Case File',
  'case.decline': 'Decline Case',
  'calendar.create_event': 'Book Consultation',
  'notify.dashboard': 'Notify Dashboard',
}

export const CASE_STAGE_COLORS = {
  intake: 'bg-blue-100 text-blue-700',
  qualification: 'bg-violet-100 text-violet-700',
  booking: 'bg-emerald-100 text-emerald-700',
  active: 'bg-green-100 text-green-700',
  closed: 'bg-slate-100 text-slate-600',
  declined: 'bg-red-100 text-red-600',
}

export const EVENT_TYPE_COLORS = {
  consult: 'bg-blue-100 text-blue-700',
  deposition: 'bg-violet-100 text-violet-700',
  follow_up: 'bg-amber-100 text-amber-700',
  court_date: 'bg-red-100 text-red-700',
  filing_deadline: 'bg-orange-100 text-orange-700',
  other: 'bg-slate-100 text-slate-600',
}

export const WS_URL = import.meta.env.VITE_WS_URL ?? 'ws://localhost:3001'
export const API_URL = import.meta.env.VITE_API_URL ?? ''
