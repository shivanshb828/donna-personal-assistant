const EVENT_TYPE_STYLES = {
  consult:    'bg-legal-navy-light text-legal-navy border border-blue-200',
  deposition: 'bg-legal-crimson-light text-legal-crimson border border-legal-crimson-border',
  follow_up:  'bg-legal-forest-light text-legal-forest border border-legal-forest-border',
  court_date: 'bg-legal-amber-light text-legal-amber border border-legal-amber-border',
}

function fmtTime(isoStr) {
  return new Date(isoStr).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function fmtDateShort(isoStr) {
  return new Date(isoStr).toLocaleDateString([], { month: 'short', day: 'numeric' })
}

function isToday(isoStr) {
  const d = new Date(isoStr)
  const now = new Date()
  return d.toDateString() === now.toDateString()
}

function isTomorrow(isoStr) {
  const d = new Date(isoStr)
  const t = new Date()
  t.setDate(t.getDate() + 1)
  return d.toDateString() === t.toDateString()
}

function dayLabel(isoStr) {
  if (isToday(isoStr)) return 'Today'
  if (isTomorrow(isoStr)) return 'Tomorrow'
  return fmtDateShort(isoStr)
}

function EventCard({ event }) {
  const typeStyle = EVENT_TYPE_STYLES[event.event_type] ?? 'bg-parchment-100 text-ink-600 border border-parchment-200'

  return (
    <div className="bg-white rounded-lg border border-parchment-200 shadow-card p-4 hover:border-parchment-300 transition-colors animate-fade-in">
      <div className="flex items-start gap-4">
        {/* Time */}
        <div className="flex-shrink-0 text-center w-14">
          <p className="text-xl font-bold text-ink-900" style={{ fontFamily: "'Playfair Display', Georgia, serif" }}>
            {fmtTime(event.scheduled_at)}
          </p>
          <p className="text-[11px] text-ink-400 mt-0.5">{event.duration_minutes}min</p>
        </div>

        <div className="w-px self-stretch bg-parchment-200 flex-shrink-0" />

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h4 className="text-[13px] font-semibold text-ink-800 leading-snug">{event.title}</h4>
              {event.attendee && (
                <p className="text-[12px] text-ink-500 mt-0.5">{event.attendee}</p>
              )}
            </div>
            <span className={`text-[11px] font-semibold px-2 py-0.5 rounded flex-shrink-0 capitalize ${typeStyle}`}>
              {(event.event_type ?? '').replace('_', ' ')}
            </span>
          </div>

          <div className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1">
            {event.lawyer_name && (
              <span className="flex items-center gap-1.5 text-[11px] text-ink-400">
                <svg viewBox="0 0 16 16" fill="currentColor" className="w-3 h-3">
                  <path d="M8 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM12.735 14c.618 0 1.093-.561.872-1.139a6.002 6.002 0 0 0-11.215 0c-.22.578.254 1.139.872 1.139h9.47z" />
                </svg>
                {event.lawyer_name}
              </span>
            )}
            {event.location && (
              <span className="flex items-center gap-1.5 text-[11px] text-ink-400">
                <svg viewBox="0 0 16 16" fill="currentColor" className="w-3 h-3">
                  <path fillRule="evenodd" d="M11.536 3.464a5 5 0 0 1 0 7.072L8 14.07l-3.536-3.534a5 5 0 1 1 7.072-7.072v.001zm-1.06 6.01A3.5 3.5 0 1 0 5.525 4.525a3.5 3.5 0 0 0 4.95 4.95v-.001zM8 7a1 1 0 1 1 0-2 1 1 0 0 1 0 2z" clipRule="evenodd" />
                </svg>
                {event.location}
              </span>
            )}
            {event.case_id && (
              <span className="text-[10px] text-ink-400 font-mono">{event.case_id.slice(0, 18)}…</span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default function CalendarView({ events }) {
  const groups = {}
  events.forEach((e) => {
    const key = new Date(e.scheduled_at).toDateString()
    if (!groups[key]) groups[key] = { label: dayLabel(e.scheduled_at), items: [] }
    groups[key].items.push(e)
  })

  const today = new Date()
  const upcomingCount = events.filter((e) => new Date(e.scheduled_at) > today).length

  return (
    <div className="flex-1 overflow-hidden flex flex-col">
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-4 border-b border-parchment-200 bg-white">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-ink-900" style={{ fontFamily: "'Playfair Display', Georgia, serif" }}>
              Calendar
            </h2>
            <p className="text-[12px] text-ink-400 mt-0.5">
              {upcomingCount} upcoming appointment{upcomingCount !== 1 ? 's' : ''}
            </p>
          </div>

          {/* Legend */}
          <div className="flex gap-2 flex-wrap">
            {[
              { type: 'consult', label: 'Consultation' },
              { type: 'deposition', label: 'Deposition' },
              { type: 'follow_up', label: 'Follow-up' },
              { type: 'court_date', label: 'Court Date' },
            ].map(({ type, label }) => (
              <span key={type} className={`text-[11px] font-medium px-2.5 py-0.5 rounded ${EVENT_TYPE_STYLES[type] ?? ''}`}>
                {label}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Events list */}
      <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">
        {Object.values(groups).length === 0 && (
          <div className="flex flex-col items-center justify-center py-20 text-ink-400">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-12 h-12 mb-3 text-parchment-300">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 0 1 2.25-2.25h13.5A2.25 2.25 0 0 1 21 7.5v11.25m-18 0A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75m-18 0v-7.5A2.25 2.25 0 0 1 5.25 9h13.5A2.25 2.25 0 0 1 21 11.25v7.5" />
            </svg>
            <p className="text-[13px] text-ink-500 font-medium">No upcoming appointments</p>
          </div>
        )}

        {Object.values(groups).map((group) => (
          <div key={group.label}>
            <div className="flex items-center gap-3 mb-3">
              <h3 className="text-[13px] font-semibold text-ink-600">{group.label}</h3>
              <div className="flex-1 h-px bg-parchment-200" />
              <span className="text-[11px] text-ink-400">
                {group.items.length} event{group.items.length !== 1 ? 's' : ''}
              </span>
            </div>
            <div className="space-y-2.5">
              {group.items.map((event) => (
                <EventCard key={event.event_id} event={event} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
