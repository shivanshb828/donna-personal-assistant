import { useState } from 'react'

const INCIDENT_LABELS = {
  auto_accident: 'Auto Accident',
  slip_fall: 'Slip & Fall',
  workplace: 'Workplace Injury',
  medical_malpractice: 'Medical Malpractice',
  other: 'Other',
}

const STAGE_STYLES = {
  intake:   'bg-legal-navy-light text-legal-navy border-blue-200',
  active:   'bg-legal-forest-light text-legal-forest border-legal-forest-border',
  closed:   'bg-parchment-100 text-ink-500 border-parchment-300',
  declined: 'bg-legal-crimson-light text-legal-crimson border-legal-crimson-border',
}

function daysUntil(dateStr) {
  if (!dateStr) return null
  return Math.floor((new Date(dateStr) - new Date()) / 86400000)
}

function SOLBadge({ solDate }) {
  const days = daysUntil(solDate)
  if (days === null) return null

  if (days <= 30) {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-legal-crimson bg-legal-crimson-light border border-legal-crimson-border px-2 py-0.5 rounded">
        <svg viewBox="0 0 16 16" fill="currentColor" className="w-3 h-3">
          <path d="M8.22 2a.75.75 0 0 0-1.44 0L.22 13a.75.75 0 0 0 .66 1.11h14.24a.75.75 0 0 0 .66-1.11L8.22 2zm-.97 4.5a.75.75 0 0 1 1.5 0v3a.75.75 0 0 1-1.5 0v-3zm.75 6a1 1 0 1 1 0-2 1 1 0 0 1 0 2z" />
        </svg>
        {days}d
      </span>
    )
  }
  if (days <= 90) {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-legal-amber bg-legal-amber-light border border-legal-amber-border px-2 py-0.5 rounded">
        {days}d
      </span>
    )
  }
  return <span className="text-[11px] text-ink-400 font-mono">{new Date(solDate).toLocaleDateString()}</span>
}

function CaseDrawer({ caseItem, onClose }) {
  return (
    <div className="fixed inset-0 z-50 flex justify-end" style={{ backgroundColor: 'rgba(26,30,41,0.35)' }} onClick={onClose}>
      <div
        className="w-full max-w-md bg-white h-full shadow-panel overflow-y-auto animate-slide-right"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-6 py-4 border-b border-parchment-200 flex items-center justify-between sticky top-0 bg-white z-10">
          <div>
            <h3 className="text-base font-semibold text-ink-900" style={{ fontFamily: "'Playfair Display', Georgia, serif" }}>
              {caseItem.client_name}
            </h3>
            <p className="text-[11px] text-ink-400 font-mono mt-0.5">{caseItem.case_id.slice(0, 24)}…</p>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded hover:bg-parchment-100 flex items-center justify-center transition-colors"
          >
            <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 text-ink-400">
              <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22z" />
            </svg>
          </button>
        </div>

        <div className="px-6 py-5 space-y-6">
          <div className="grid grid-cols-2 gap-5">
            {[
              { label: 'Stage', content: (
                <span className={`text-xs font-semibold px-2.5 py-1 rounded border capitalize ${STAGE_STYLES[caseItem.stage] ?? 'bg-parchment-100 text-ink-600 border-parchment-200'}`}>
                  {caseItem.stage}
                </span>
              )},
              { label: 'Case Type', content: <p className="text-sm text-ink-700">{INCIDENT_LABELS[caseItem.case_type] ?? caseItem.case_type}</p> },
              { label: 'Incident Date', content: <p className="text-sm text-ink-700">{new Date(caseItem.incident_date).toLocaleDateString()}</p> },
              { label: 'Statute of Limitations', content: <SOLBadge solDate={caseItem.sol_date} /> },
            ].map(({ label, content }) => (
              <div key={label}>
                <p className="text-[10px] uppercase tracking-wider text-ink-400 font-semibold mb-1.5">{label}</p>
                {content}
              </div>
            ))}
          </div>

          {caseItem.sol_warning && (
            <div className="rounded border border-legal-amber-border bg-legal-amber-light px-4 py-3">
              <p className="text-sm text-legal-amber font-medium">{caseItem.sol_warning}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

const STAGE_FILTERS = ['all', 'intake', 'active', 'closed', 'declined']

export default function CasesView({ cases }) {
  const [filter, setFilter] = useState('all')
  const [selected, setSelected] = useState(null)
  const [search, setSearch] = useState('')

  const filtered = cases.filter((c) => {
    const matchStage = filter === 'all' || c.stage === filter
    const matchSearch =
      !search ||
      c.client_name.toLowerCase().includes(search.toLowerCase()) ||
      c.case_id.toLowerCase().includes(search.toLowerCase())
    return matchStage && matchSearch
  })

  return (
    <div className="flex-1 overflow-hidden flex flex-col">
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-4 border-b border-parchment-200 bg-white">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-base font-semibold text-ink-900" style={{ fontFamily: "'Playfair Display', Georgia, serif" }}>
              Case Files
            </h2>
            <p className="text-[12px] text-ink-400 mt-0.5">{cases.length} total cases</p>
          </div>

          {/* Search */}
          <div className="relative">
            <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 text-ink-400 absolute left-3 top-1/2 -translate-y-1/2">
              <path fillRule="evenodd" d="M9 3.5a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11zM2 9a7 7 0 1 1 12.452 4.391l3.328 3.329a.75.75 0 1 1-1.06 1.06l-3.329-3.328A7 7 0 0 1 2 9z" clipRule="evenodd" />
            </svg>
            <input
              type="text"
              placeholder="Search by client or ID…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 pr-4 py-2 text-sm bg-parchment-50 border border-parchment-200 rounded focus:outline-none focus:ring-2 focus:ring-legal-navy/20 focus:border-legal-navy/40 w-60 transition-all"
            />
          </div>
        </div>

        {/* Stage filter */}
        <div className="flex gap-2 mt-4">
          {STAGE_FILTERS.map((stage) => (
            <button
              key={stage}
              onClick={() => setFilter(stage)}
              className={`px-3 py-1.5 rounded text-[12px] font-medium transition-all capitalize ${
                filter === stage
                  ? 'bg-legal-navy text-white'
                  : 'bg-white text-ink-600 border border-parchment-200 hover:border-parchment-300 hover:bg-parchment-50'
              }`}
            >
              {stage === 'all' ? 'All Cases' : stage}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto px-6 py-5">
        <div className="bg-white rounded-lg border border-parchment-200 shadow-card overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-parchment-200 bg-parchment-50">
                {['Client', 'Case Type', 'Incident Date', 'Stage', 'SOL'].map((h) => (
                  <th key={h} className="text-left px-5 py-3 text-[11px] uppercase tracking-wider text-ink-400 font-semibold">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={5} className="text-center py-14 text-sm text-ink-400">
                    No cases match your filter
                  </td>
                </tr>
              )}
              {filtered.map((c, idx) => (
                <tr
                  key={c.case_id}
                  onClick={() => setSelected(c)}
                  className={`border-b border-parchment-100 hover:bg-legal-navy-light cursor-pointer transition-colors group ${
                    idx % 2 === 0 ? '' : 'bg-parchment-50/40'
                  }`}
                >
                  <td className="px-5 py-3.5">
                    <p className="text-[13px] font-semibold text-ink-800 group-hover:text-legal-navy transition-colors">
                      {c.client_name}
                    </p>
                    <p className="text-[11px] text-ink-400 font-mono mt-0.5">{c.case_id.slice(0, 18)}…</p>
                  </td>
                  <td className="px-5 py-3.5">
                    <span className="text-[13px] text-ink-600">{INCIDENT_LABELS[c.case_type] ?? c.case_type}</span>
                  </td>
                  <td className="px-5 py-3.5">
                    <span className="text-[13px] text-ink-600">{new Date(c.incident_date).toLocaleDateString()}</span>
                  </td>
                  <td className="px-5 py-3.5">
                    <span className={`text-[11px] font-semibold px-2.5 py-1 rounded border capitalize ${STAGE_STYLES[c.stage] ?? 'bg-parchment-100 text-ink-500 border-parchment-200'}`}>
                      {c.stage}
                    </span>
                  </td>
                  <td className="px-5 py-3.5">
                    <SOLBadge solDate={c.sol_date} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {selected && <CaseDrawer caseItem={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}
