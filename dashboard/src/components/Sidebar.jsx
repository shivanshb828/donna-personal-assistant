const NAV = [
  {
    id: 'live',
    label: 'Live Call',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} className="w-5 h-5">
        <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 0 0 2.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 0 1-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 0 0-1.091-.852H4.5A2.25 2.25 0 0 0 2.25 4.5v2.25z" />
      </svg>
    ),
  },
  {
    id: 'cases',
    label: 'Case Files',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} className="w-5 h-5">
        <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 0 1 4.5 9.75h15A2.25 2.25 0 0 1 21.75 12v.75m-8.69-6.44-2.12-2.12a1.5 1.5 0 0 0-1.061-.44H4.5A2.25 2.25 0 0 0 2.25 6v8.25A2.25 2.25 0 0 0 4.5 16.5h15a2.25 2.25 0 0 0 2.25-2.25V9a2.25 2.25 0 0 0-2.25-2.25h-5.379a1.5 1.5 0 0 1-1.06-.44z" />
      </svg>
    ),
  },
  {
    id: 'calendar',
    label: 'Calendar',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} className="w-5 h-5">
        <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 0 1 2.25-2.25h13.5A2.25 2.25 0 0 1 21 7.5v11.25m-18 0A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75m-18 0v-7.5A2.25 2.25 0 0 1 5.25 9h13.5A2.25 2.25 0 0 1 21 11.25v7.5" />
      </svg>
    ),
  },
  {
    id: 'emails',
    label: 'Email Drafts',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} className="w-5 h-5">
        <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 0 1-2.25 2.25h-15a2.25 2.25 0 0 1-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0 0 19.5 4.5h-15a2.25 2.25 0 0 0-2.25 2.25m19.5 0v.243a2.25 2.25 0 0 1-1.07 1.916l-7.5 4.615a2.25 2.25 0 0 1-2.36 0L3.32 8.91a2.25 2.25 0 0 1-1.07-1.916V6.75" />
      </svg>
    ),
  },
  {
    id: 'leads',
    label: 'Leads & CRM',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} className="w-5 h-5">
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 0 0 2.625.372 9.337 9.337 0 0 0 4.121-.952 4.125 4.125 0 0 0-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 0 1 8.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0 1 11.964-3.07M12 6.375a3.375 3.375 0 1 1-6.75 0 3.375 3.375 0 0 1 6.75 0zm8.25 2.25a2.625 2.625 0 1 1-5.25 0 2.625 2.625 0 0 1 5.25 0z" />
      </svg>
    ),
  },
]

function ServiceDot({ connected, label }) {
  return (
    <div className="flex items-center gap-2.5">
      <span
        className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
          connected ? 'bg-emerald-400 dot-live' : 'bg-slate-600'
        }`}
      />
      <span className="text-[11px] text-slate-400">{label}</span>
    </div>
  )
}

function LiveCallBadge({ activeCall, pipelineStatus }) {
  if (!activeCall) return null

  const statusColor = {
    listening: 'text-emerald-400',
    speaking: 'text-blue-400',
    processing: 'text-amber-400',
    ready: 'text-emerald-400',
    idle: 'text-ink-400',
  }

  const statusLabel = {
    listening: 'Listening…',
    speaking: 'Speaking',
    processing: 'Processing',
    ready: 'Ready',
    idle: 'Idle',
  }

  return (
    <div className="mx-3 mb-2 rounded border border-blue-500/25 bg-blue-500/8 p-3"
      style={{ backgroundColor: 'rgba(59,130,246,0.07)' }}>
      <div className="flex items-center gap-2 mb-1.5">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 dot-live flex-shrink-0" />
        <span className="text-[10px] font-bold uppercase tracking-widest text-blue-300">Live Call</span>
      </div>
      <p className="text-white text-xs font-semibold font-mono truncate">{activeCall.callerPhone}</p>
      <p className={`text-[11px] mt-0.5 font-medium ${statusColor[pipelineStatus] ?? 'text-ink-400'}`}>
        {statusLabel[pipelineStatus] ?? 'Active'}
      </p>
    </div>
  )
}

export default function Sidebar({
  activeTab,
  onTabChange,
  wsConnected,
  activeCall,
  emailDraftsCount,
  newLeadsCount,
  pipelineStatus,
}) {
  return (
    <aside className="w-56 flex-shrink-0 flex flex-col h-full border-r border-white/5" style={{ backgroundColor: '#181C26' }}>

      {/* Wordmark */}
      <div className="px-5 pt-7 pb-6 border-b border-white/5">
        <div className="flex items-center gap-3">
          {/* Scales of justice icon */}
          <div className="w-8 h-8 rounded bg-legal-gold/15 border border-legal-gold/30 flex items-center justify-center flex-shrink-0">
            <svg viewBox="0 0 24 24" fill="none" stroke="#B8860B" strokeWidth={1.5} className="w-5 h-5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v1.5M12 3 9 6M12 3l3 3M6 9l-3 3 3 3M18 9l3 3-3 3M3 12h18M6 9h12M6 15h12M9 21h6M12 18v3" />
            </svg>
          </div>
          <div>
            <p className="text-white font-semibold text-sm leading-none tracking-tight" style={{ fontFamily: "'Playfair Display', Georgia, serif" }}>
              Donna
            </p>
            <p className="text-ink-400 text-[10px] mt-1 leading-none tracking-wide uppercase">AI Legal Secretary</p>
          </div>
        </div>
      </div>

      {/* Live call badge */}
      <div className="pt-3">
        <LiveCallBadge activeCall={activeCall} pipelineStatus={pipelineStatus} />
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-2 py-1 overflow-y-auto space-y-0.5">
        {NAV.map((item) => {
          const isActive = activeTab === item.id
          const badge =
            item.id === 'emails' && emailDraftsCount > 0
              ? emailDraftsCount
              : item.id === 'leads' && newLeadsCount > 0
              ? newLeadsCount
              : null

          return (
            <button
              key={item.id}
              onClick={() => onTabChange(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded text-left transition-all duration-150 group relative ${
                isActive
                  ? 'text-white'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
              }`}
              style={isActive ? { backgroundColor: 'rgba(255,255,255,0.10)' } : {}}
            >
              {/* Active left border */}
              {isActive && (
                <span className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-r bg-legal-gold-mid" />
              )}

              <span className={`flex-shrink-0 transition-colors ${isActive ? 'text-white' : 'text-slate-500 group-hover:text-slate-300'}`}>
                {item.icon}
              </span>
              <span className="text-[13px] font-medium">{item.label}</span>

              {badge && (
                <span className={`ml-auto min-w-[18px] h-[18px] rounded-full text-[10px] font-bold flex items-center justify-center px-1 ${
                  isActive
                    ? 'bg-legal-gold/20 text-legal-gold-border'
                    : 'bg-legal-amber/20 text-amber-400'
                }`}>
                  {badge}
                </span>
              )}
            </button>
          )
        })}
      </nav>

      {/* Service health */}
      <div className="px-4 py-4 border-t border-white/5 space-y-2">
        <p className="text-[10px] uppercase tracking-widest text-slate-600 mb-2.5 font-semibold">Services</p>
        <ServiceDot connected={wsConnected} label="Dashboard" />
        <ServiceDot connected label="Ollama LLM" />
        <ServiceDot connected label="Whisper STT" />
        <ServiceDot connected label="Kokoro TTS" />
      </div>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-white/5">
        <p className="text-[10px] text-ink-600 text-center tracking-wide">
          Dell × NVIDIA · 2026
        </p>
      </div>
    </aside>
  )
}
