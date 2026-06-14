// Scripted demo sequence that plays through a complete PI intake call
// Each item: { delay (ms from start), event (WebSocket event object) }
export const DEMO_SEQUENCE = [
  {
    delay: 0,
    event: {
      type: 'call_started',
      callSid: 'demo-CA001',
      callerPhone: '+1 (415) 555-0182',
      agentMode: 'inbound_intake',
      isReturning: false,
    },
  },
  { delay: 600, event: { type: 'pipeline_status', status: 'speaking' } },
  {
    delay: 900,
    event: {
      type: 'donna_speech',
      text: "Thank you for calling Mitchell & Associates. I'm Donna, an AI legal assistant. This call may be recorded for quality assurance. Do I have your consent to record our conversation today?",
    },
  },
  { delay: 5500, event: { type: 'pipeline_status', status: 'listening' } },
  {
    delay: 7800,
    event: {
      type: 'user_speech',
      text: "Yes, that's fine. I was involved in a car accident last week and I really need to speak with an attorney.",
    },
  },
  { delay: 8300, event: { type: 'pipeline_status', status: 'processing' } },
  {
    delay: 8900,
    event: {
      type: 'tool_call',
      tool: 'record_consent',
      args: { consent_type: 'recording', granted: true },
      result: { ok: true, data: { consent_type: 'recording', granted: true } },
    },
  },
  {
    delay: 9300,
    event: {
      type: 'tool_call',
      tool: 'record_consent',
      args: { consent_type: 'ai_disclosure', granted: true },
      result: { ok: true, data: { consent_type: 'ai_disclosure', granted: true } },
    },
  },
  { delay: 9700, event: { type: 'pipeline_status', status: 'speaking' } },
  {
    delay: 10200,
    event: {
      type: 'donna_speech',
      text: "I'm so sorry to hear that. I'm going to start your intake now so we can get you the help you need. Can I start with your full name?",
    },
  },
  { delay: 13500, event: { type: 'pipeline_status', status: 'listening' } },
  {
    delay: 15800,
    event: { type: 'user_speech', text: "My name is Sarah Chen." },
  },
  { delay: 16200, event: { type: 'pipeline_status', status: 'processing' } },
  {
    delay: 16800,
    event: {
      type: 'tool_call',
      tool: 'intake.start',
      args: { caller_name: 'Sarah Chen', phone: '+14155550182' },
      result: { ok: true, data: { intake_id: 'intk-demo-abc1', fields: { caller_name: 'Sarah Chen' } } },
    },
  },
  { delay: 17200, event: { type: 'pipeline_status', status: 'speaking' } },
  {
    delay: 17700,
    event: {
      type: 'donna_speech',
      text: "Thank you, Sarah. Can you tell me where and when the accident happened, and briefly describe the injuries you sustained?",
    },
  },
  { delay: 21500, event: { type: 'pipeline_status', status: 'listening' } },
  {
    delay: 24500,
    event: {
      type: 'user_speech',
      text: "It was on Highway 101 near San Francisco on December 10th. The other driver ran a red light and T-boned my car. I have whiplash and a fractured wrist — I went to the ER the same night.",
    },
  },
  { delay: 25000, event: { type: 'pipeline_status', status: 'processing' } },
  {
    delay: 25800,
    event: {
      type: 'tool_call',
      tool: 'intake.update',
      args: {
        incident_date: '2025-12-10',
        incident_location: 'Highway 101, San Francisco, CA',
        injury_summary: 'Whiplash and fractured wrist',
        fault_party: 'Other driver — ran red light',
        treatment_status: 'ER visit same night',
      },
      result: { ok: true, data: { intake_id: 'intk-demo-abc1', updated: { incident_date: '2025-12-10' } } },
    },
  },
  { delay: 26200, event: { type: 'pipeline_status', status: 'speaking' } },
  {
    delay: 26700,
    event: {
      type: 'donna_speech',
      text: "I've noted all of that. One more question — do you currently have another attorney representing you for this incident?",
    },
  },
  { delay: 30000, event: { type: 'pipeline_status', status: 'listening' } },
  {
    delay: 31800,
    event: { type: 'user_speech', text: "No, I don't have an attorney yet. That's why I'm calling." },
  },
  { delay: 32300, event: { type: 'pipeline_status', status: 'processing' } },
  {
    delay: 33100,
    event: {
      type: 'tool_call',
      tool: 'intake.update',
      args: { prior_attorney: false },
      result: { ok: true, data: {} },
    },
  },
  {
    delay: 33800,
    event: {
      type: 'tool_call',
      tool: 'case.qualify',
      args: {
        jurisdiction: 'CA',
        injury_present: true,
        at_fault_clear: true,
        prior_attorney: false,
      },
      result: {
        ok: true,
        data: {
          qualified: true,
          reasons: [],
          next_step: 'calendar.create_event',
        },
      },
    },
  },
  { delay: 34500, event: { type: 'pipeline_status', status: 'speaking' } },
  {
    delay: 35000,
    event: {
      type: 'donna_speech',
      text: "Great news, Sarah — based on what you've described, this looks like a strong personal injury case for our firm. I'd like to schedule you for a free consultation with one of our attorneys. Are you available this Thursday at 2:00 PM?",
    },
  },
  { delay: 40000, event: { type: 'pipeline_status', status: 'listening' } },
  {
    delay: 42000,
    event: { type: 'user_speech', text: "Yes, Thursday at 2 works perfectly for me." },
  },
  { delay: 42500, event: { type: 'pipeline_status', status: 'processing' } },
  {
    delay: 43400,
    event: {
      type: 'tool_call',
      tool: 'calendar.create_event',
      args: {
        client_id: 'client-demo-sc',
        title: 'Initial Consultation — Sarah Chen',
        scheduled_at: '2026-06-19T14:00:00',
        duration_minutes: 60,
        attendee: 'Sarah Chen',
      },
      result: {
        ok: true,
        data: {
          status: 'booked',
          event_id: 'evt-demo-001',
          formatted_confirmation: 'Done. Initial Consultation scheduled for Thursday, June 19 at 2:00 PM.',
        },
      },
    },
  },
  { delay: 44200, event: { type: 'pipeline_status', status: 'speaking' } },
  {
    delay: 44700,
    event: {
      type: 'donna_speech',
      text: "Perfect! I've booked your initial consultation for Thursday, June 19th at 2:00 PM. You'll receive a confirmation by text. The attorney will review your case details before the meeting. Is there anything else you'd like to add?",
    },
  },
  { delay: 50000, event: { type: 'pipeline_status', status: 'listening' } },
  {
    delay: 51800,
    event: { type: 'user_speech', text: "No, that covers everything. Thank you so much." },
  },
  { delay: 52300, event: { type: 'pipeline_status', status: 'processing' } },
  {
    delay: 53000,
    event: {
      type: 'tool_call',
      tool: 'notify.dashboard',
      args: {
        body: 'New PI intake — Sarah Chen | MVA on Hwy 101, San Francisco, Dec 10 2025 | Injuries: whiplash + fractured wrist | Qualified ✓ | Consult booked Thu Jun 19 @ 2:00 PM',
      },
      result: { ok: true, data: { sent: true } },
    },
  },
  { delay: 53800, event: { type: 'pipeline_status', status: 'speaking' } },
  {
    delay: 54300,
    event: {
      type: 'donna_speech',
      text: "You're very welcome, Sarah. I've sent a summary to our legal team — they'll be prepared for your Thursday appointment. We look forward to helping you. Take care and feel better soon.",
    },
  },
  {
    delay: 59000,
    event: {
      type: 'call_ended',
      callSid: 'demo-CA001',
      duration: 59,
      outcome: 'BOOKING',
    },
  },
]

export const DEMO_CASES = [
  {
    case_id: 'case-20250301-a1b2c3',
    client_name: 'Marcus Rivera',
    case_type: 'auto_accident',
    incident_date: '2025-03-01',
    stage: 'active',
    sol_date: '2027-03-01',
  },
  {
    case_id: 'case-20250115-d4e5f6',
    client_name: 'Jennifer Park',
    case_type: 'slip_fall',
    incident_date: '2025-01-15',
    stage: 'active',
    sol_date: '2027-01-15',
  },
  {
    case_id: 'case-20241210-g7h8i9',
    client_name: 'David Okafor',
    case_type: 'workplace',
    incident_date: '2024-12-10',
    stage: 'intake',
    sol_date: '2026-12-10',
    sol_warning: '180 days to SOL',
  },
  {
    case_id: 'case-20240620-j1k2l3',
    client_name: 'Priya Sharma',
    case_type: 'medical_malpractice',
    incident_date: '2024-06-20',
    stage: 'closed',
    sol_date: '2026-06-20',
    sol_warning: '6 days to SOL',
  },
  {
    case_id: 'case-20250501-m4n5o6',
    client_name: 'Tom Fitzgerald',
    case_type: 'auto_accident',
    incident_date: '2025-05-01',
    stage: 'intake',
    sol_date: '2027-05-01',
  },
]

export const DEMO_EVENTS = [
  {
    event_id: 'evt-001',
    title: 'Initial Consultation — Marcus Rivera',
    event_type: 'consult',
    scheduled_at: '2026-06-19T14:00:00',
    duration_minutes: 60,
    attendee: 'Marcus Rivera',
    lawyer_name: 'Atty. Chen',
    location: 'Office Suite 400',
    case_id: 'case-20250301-a1b2c3',
  },
  {
    event_id: 'evt-002',
    title: 'Deposition Prep — Jennifer Park',
    event_type: 'deposition',
    scheduled_at: '2026-06-20T10:00:00',
    duration_minutes: 120,
    attendee: 'Jennifer Park',
    lawyer_name: 'Atty. Williams',
    location: 'Conference Room B',
    case_id: 'case-20250115-d4e5f6',
  },
  {
    event_id: 'evt-003',
    title: 'Follow-up Call — David Okafor',
    event_type: 'follow_up',
    scheduled_at: '2026-06-21T15:30:00',
    duration_minutes: 30,
    attendee: 'David Okafor',
    lawyer_name: 'Atty. Chen',
    case_id: 'case-20241210-g7h8i9',
  },
  {
    event_id: 'evt-004',
    title: 'Court Appearance — Sharma v. UCSF',
    event_type: 'court_date',
    scheduled_at: '2026-06-25T09:00:00',
    duration_minutes: 180,
    attendee: 'Priya Sharma',
    lawyer_name: 'Atty. Williams',
    location: 'SF Superior Court, Dept 302',
    case_id: 'case-20240620-j1k2l3',
  },
]

export const DEMO_LEADS = [
  {
    id: 'lead-001',
    name: 'Robert Kim',
    phone: '+1 (650) 555-0234',
    source: 'web_form',
    status: 'new',
    incident_summary: 'Rear-end collision on I-280',
    created_at: new Date(Date.now() - 3600000).toISOString(),
  },
  {
    id: 'lead-002',
    name: 'Angela Torres',
    phone: '+1 (408) 555-0345',
    source: 'referral',
    status: 'new',
    incident_summary: 'Slip and fall at grocery store',
    created_at: new Date(Date.now() - 7200000).toISOString(),
  },
  {
    id: 'lead-003',
    name: 'Kevin Walsh',
    phone: '+1 (415) 555-0456',
    source: 'inbound_call',
    status: 'contacted',
    incident_summary: 'Dog bite incident',
    created_at: new Date(Date.now() - 86400000).toISOString(),
  },
]
