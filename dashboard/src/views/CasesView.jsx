import { useState } from 'react'
import { CASE_STAGE_COLORS } from '../lib/constants.js'

const INCIDENT_LABELS = {
  auto_accident: 'Auto Accident',
  slip_fall: 'Slip & Fall',
  workplace: 'Workplace Injury',
  medical_malpractice: 'Medical Malpractice',
  other: 'Other',
}

function daysUntil(dateStr) {
  if (!dateStr) return null
  const d = new Date(dateStr)
  const now = new Date()
  return Math.floor((d - now) / 86400000)
}

function SOLBadge({ solDate }) {
  const days = daysUntil(solDate)
  if (days === null) return null

  if (days <= 30) {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-red-600 bg-red-50 border border-red-200 px-2 py-0.5 rounded-full">
        <svg viewBox="0 0 16 16" fill="currentColor" className="w-3 h-3">
          <path d="M8.22 2a.75.75 0 0 0-1.44 0L.22 13a.75.75 0 0 0 .66 1.11h14.24a.75.75 0 0 0 .66-1.11L8.22 2zm-.97 4.5a.75.75 0 0 1 1.5 0v3a.75.75 0 0 1-1.5 0v-3zm.75 6a1 1 0 1 1 0-2 1 1 0 0 1 0 2z" />
        </svg>
        {days}d to SOL
      </span>
    )
  }
  if (days <= 90) {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-amber-600 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full">
        {days}d to SOL
      </span>
    )
  }
  return (
    <span className="text-[11px] text-slate-400 font-mono">{new Date(solDate).toLocaleDateString()}</span>
  )
}

function CaseDrawer({ caseItem, onClose }) {
  return (
    <div className="fixed inset-0 z-50 flex justify-end" onClick={onClose}>
      <div
        className="w-full max-w-md bg-white h-full shadow-2xl overflow-y-auto animate-slide-right"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-6 py-5 border-b border-slate-100 flex items-center justify-between sticky top-0 bg-white z-10">
          <h3 className="text-base font-bold text-slate-900">{caseItem.client_name}</h3>
          <button onClick={onClose} className="w-8 h-8 rounded-lg hover:bg-slate-100 flex items-center justify-center transition-colors">
            <svg viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5 text-slate-400">
              <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22z" />
            </svg>
          </button>
        </div>

        <div className="px-6 py-5 space-y-5">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold mb-1">Case ID</p>
              <p className="text-xs font-mono text-slate-600">{caseItem.case_id}</p>
            </div>
            <div>
              <p className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold mb-1">Stage</p>
              <span className={`text-xs font-semibold px-2 py-0.5 rounded-full capitalize ${CASE_STAGE_COLORS[caseItem.stage] ?? 'bg-slate-100 text-slate-600'}`}>
                {caseItem.stage}
              </span>
            </div>
            <div>
              <p className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold mb-1">Type</p>
              <p className="text-sm text-slate-700">{INCIDENT_LABELS[caseItem.case_type] ?? caseItem.case_type}</p>
            </div>
            <div>
              <p className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold mb-1">Incident Date</p>
              <p className="text-sm text-slate-700">{new Date(caseItem.incident_date).toLocaleDateString()}</p>
            </div>
          </div>

          <div>
            <p className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold mb-2">Statute of Limitations</p>
            <SOLBadge solDate={caseItem.sol_date} />
          </div>

          {caseItem.sol_warning && (
            <div className="rounded-xl bg-amber-50 border border-amber-200 px-4 py-3">
              <p className="text-sm text-amber-700 font-medium">{caseItem.sol_warning}</p>
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
      <div className="flex-shrink-0 px-6 py-5 border-b border-slate-200/60 bg-white/60 backdrop-blur-sm">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Case Files</h2>
            <p className="text-sm text-slate-500 mt-0.5">{cases.length} total cases</p>
          </div>

          {/* Search */}
          <div className="relative">
            <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2">
              <path fillRule="evenodd" d="M9 3.5a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11zM2 9a7 7 0 1 1 12.452 4.391l3.328 3.329a.75.75 0 1 1-1.06 1.06l-3.329-3.328A7 7 0 0 1 2 9z" clipRule="evenodd" />
            </svg>
            <input
              type="text"
              placeholder="Search cases…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 pr-4 py-2 text-sm bg-white border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400 w-56 transition-all"
            />
          </div>
        </div>

        {/* Stage filter pills */}
        <div className="flex gap-2 mt-4">
          {STAGE_FILTERS.map((stage) => (
            <button
              key={stage}
              onClick={() => setFilter(stage)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all capitalize ${
                filter === stage
                  ? 'bg-blue-600 text-white shadow-md shadow-blue-500/20'
                  : 'bg-white text-slate-600 border border-slate-200 hover:border-slate-300'
              }`}
            >
              {stage === 'all' ? 'All Cases' : stage}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto px-6 py-4">
        <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-100">
                {['Client', 'Type', 'Incident Date', 'Stage', 'SOL Date'].map((h) => (
                  <th key={h} className="text-left px-5 py-3.5 text-[11px] uppercase tracking-wider text-slate-400 font-semibold">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={5} className="text-center py-12 text-sm text-slate-400">
                    No cases found
                  </td>
                </tr>
              )}
              {filtered.map((c) => (
                <tr
                  key={c.case_id}
                  onClick={() => setSelected(c)}
                  className="border-b border-slate-50 hover:bg-blue-50/40 cursor-pointer transition-colors group"
                >
                  <td className="px-5 py-3.5">
                    <p className="text-sm font-semibold text-slate-800 group-hover:text-blue-700 transition-colors">
                      {c.client_name}
                    </p>
                    <p className="text-[11px] text-slate-400 font-mono mt-0.5">{c.case_id.slice(0, 20)}…</p>
                  </td>
                  <td className="px-5 py-3.5">
                    <span className="text-sm text-slate-600">{INCIDENT_LABELS[c.case_type] ?? c.case_type}</span>
                  </td>
                  <td className="px-5 py-3.5">
                    <span className="text-sm text-slate-600">{new Date(c.incident_date).toLocaleDateString()}</span>
                  </td>
                  <td className="px-5 py-3.5">
                    <span className={`text-xs font-semibold px-2.5 py-1 rounded-full capitalize ${CASE_STAGE_COLORS[c.stage] ?? 'bg-slate-100 text-slate-600'}`}>
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
