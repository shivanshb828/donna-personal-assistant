import { EVENT_TYPE_COLORS } from '../lib/constants.js'

function fmtTime(isoStr) {
  return new Date(isoStr).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function fmtDate(isoStr) {
  return new Date(isoStr).toLocaleDateString([], {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  })
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
  const tomorrow = new Date()
  tomorrow.setDate(tomorrow.getDate() + 1)
  return d.toDateString() === tomorrow.toDateString()
}

function dayLabel(isoStr) {
  if (isToday(isoStr)) return 'Today'
  if (isTomorrow(isoStr)) return 'Tomorrow'
  return fmtDateShort(isoStr)
}

function EventCard({ event }) {
  const typeColor = EVENT_TYPE_COLORS[event.event_type] ?? 'bg-slate-100 text-slate-600'

  return (
    <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5 hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 cursor-default animate-fade-in">
      <div className="flex items-start gap-4">
        {/* Time column */}
        <div className="flex-shrink-0 w-16 text-center">
          <p className="text-xl font-bold text-slate-900 leading-none">{fmtTime(event.scheduled_at)}</p>
          <p className="text-[11px] text-slate-400 mt-1 font-medium">{event.duration_minutes}min</p>
        </div>

        {/* Divider */}
        <div className="w-px self-stretch bg-slate-100 flex-shrink-0" />

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h4 className="text-sm font-semibold text-slate-800 leading-snug">{event.title}</h4>
              {event.attendee && (
                <p className="text-xs text-slate-500 mt-0.5">{event.attendee}</p>
              )}
            </div>
            <span className={`text-[11px] font-semibold px-2.5 py-1 rounded-full flex-shrink-0 capitalize ${typeColor}`}>
              {event.event_type.replace('_', ' ')}
            </span>
          </div>

          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1">
            {event.lawyer_name && (
              <span className="flex items-center gap-1.5 text-[11px] text-slate-500">
                <svg viewBox="0 0 16 16" fill="currentColor" className="w-3 h-3 text-slate-400">
                  <path d="M8 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM12.735 14c.618 0 1.093-.561.872-1.139a6.002 6.002 0 0 0-11.215 0c-.22.578.254 1.139.872 1.139h9.47z" />
                </svg>
                {event.lawyer_name}
              </span>
            )}
            {event.location && (
              <span className="flex items-center gap-1.5 text-[11px] text-slate-500">
                <svg viewBox="0 0 16 16" fill="currentColor" className="w-3 h-3 text-slate-400">
                  <path fillRule="evenodd" d="M11.536 3.464a5 5 0 0 1 0 7.072L8 14.07l-3.536-3.534a5 5 0 1 1 7.072-7.072v.001zm-1.06 6.01A3.5 3.5 0 1 0 5.525 4.525a3.5 3.5 0 0 0 4.95 4.95v-.001zM8 7a1 1 0 1 1 0-2 1 1 0 0 1 0 2z" clipRule="evenodd" />
                </svg>
                {event.location}
              </span>
            )}
            {event.case_id && (
              <span className="flex items-center gap-1.5 text-[11px] text-slate-400 font-mono">
                {event.case_id.slice(0, 18)}…
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default function CalendarView({ events }) {
  // Group events by date
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
      <div className="flex-shrink-0 px-6 py-5 border-b border-slate-200/60 bg-white/60 backdrop-blur-sm">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Calendar</h2>
            <p className="text-sm text-slate-500 mt-0.5">
              {upcomingCount} upcoming event{upcomingCount !== 1 ? 's' : ''}
            </p>
          </div>

          {/* Event type legend */}
          <div className="flex gap-2 flex-wrap">
            {[
              { type: 'consult', label: 'Consult' },
              { type: 'deposition', label: 'Deposition' },
              { type: 'follow_up', label: 'Follow-up' },
              { type: 'court_date', label: 'Court' },
            ].map(({ type, label }) => (
              <span key={type} className={`text-[11px] font-medium px-2 py-0.5 rounded-full ${EVENT_TYPE_COLORS[type]}`}>
                {label}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Events */}
      <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">
        {Object.values(groups).length === 0 && (
          <div className="flex flex-col items-center justify-center py-20 text-slate-400">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-12 h-12 mb-3 text-slate-300">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 0 1 2.25-2.25h13.5A2.25 2.25 0 0 1 21 7.5v11.25m-18 0A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75m-18 0v-7.5A2.25 2.25 0 0 1 5.25 9h13.5A2.25 2.25 0 0 1 21 11.25v7.5" />
            </svg>
            <p className="text-sm">No upcoming events</p>
          </div>
        )}

        {Object.values(groups).map((group) => (
          <div key={group.label}>
            {/* Day header */}
            <div className="flex items-center gap-3 mb-3">
              <h3 className="text-sm font-bold text-slate-700">{group.label}</h3>
              <div className="flex-1 h-px bg-slate-100" />
              <span className="text-[11px] text-slate-400 font-medium">
                {group.items.length} event{group.items.length !== 1 ? 's' : ''}
              </span>
            </div>

            <div className="space-y-3">
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
