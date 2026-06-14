import { useState } from 'react'

const SOURCE_LABELS = {
  web_form: 'Web Form',
  referral: 'Referral',
  inbound_call: 'Inbound Call',
  outbound: 'Outbound',
  other: 'Other',
}

const STATUS_STYLES = {
  new:       'bg-legal-navy-light text-legal-navy border border-blue-200',
  contacted: 'bg-legal-amber-light text-legal-amber border border-legal-amber-border',
  qualified: 'bg-legal-forest-light text-legal-forest border border-legal-forest-border',
  converted: 'bg-legal-forest-light text-legal-forest border border-legal-forest-border',
  dead:      'bg-parchment-100 text-ink-400 border border-parchment-200',
}

function fmtAgo(isoStr) {
  const ms = Date.now() - new Date(isoStr).getTime()
  const m = Math.floor(ms / 60000)
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

function AddLeadModal({ onClose, onAdd }) {
  const [form, setForm] = useState({ name: '', phone: '', source: 'web_form', incident_summary: '' })
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.name || !form.phone) return
    setLoading(true)
    await onAdd(form)
    setLoading(false)
    onClose()
  }

  const inputClass = "w-full px-3.5 py-2.5 text-sm bg-parchment-50 border border-parchment-200 rounded focus:outline-none focus:ring-2 focus:ring-legal-navy/20 focus:border-legal-navy/40 transition-all"

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ backgroundColor: 'rgba(26,30,41,0.35)' }}
      onClick={onClose}
    >
      <div
        className="bg-white rounded-lg shadow-panel w-full max-w-md mx-4 overflow-hidden animate-slide-up"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-6 py-4 border-b border-parchment-200 flex items-center justify-between">
          <h3 className="text-base font-semibold text-ink-900" style={{ fontFamily: "'Playfair Display', Georgia, serif" }}>
            Add New Lead
          </h3>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded hover:bg-parchment-100 flex items-center justify-center transition-colors"
          >
            <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 text-ink-400">
              <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22z" />
            </svg>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          <div>
            <label className="block text-[11px] uppercase tracking-wider font-semibold text-ink-400 mb-1.5">Full Name *</label>
            <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="Sarah Chen" className={inputClass} required />
          </div>
          <div>
            <label className="block text-[11px] uppercase tracking-wider font-semibold text-ink-400 mb-1.5">Phone Number *</label>
            <input type="tel" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })}
              placeholder="+1 (415) 555-0182" className={inputClass} required />
          </div>
          <div>
            <label className="block text-[11px] uppercase tracking-wider font-semibold text-ink-400 mb-1.5">Source</label>
            <select value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })} className={inputClass}>
              {Object.entries(SOURCE_LABELS).map(([val, label]) => (
                <option key={val} value={val}>{label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-[11px] uppercase tracking-wider font-semibold text-ink-400 mb-1.5">Incident Summary</label>
            <textarea value={form.incident_summary} onChange={(e) => setForm({ ...form, incident_summary: e.target.value })}
              placeholder="Brief description of the incident…" rows={3} className={`${inputClass} resize-none`} />
          </div>

          <div className="flex gap-3 pt-1">
            <button type="submit" disabled={loading}
              className="flex-1 py-2.5 rounded bg-legal-navy text-white text-sm font-semibold hover:bg-legal-navy-hover transition-colors disabled:opacity-60">
              {loading ? 'Adding…' : 'Add Lead'}
            </button>
            <button type="button" onClick={onClose}
              className="px-5 py-2.5 rounded border border-parchment-200 text-ink-600 text-sm font-medium hover:bg-parchment-50 transition-colors">
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function LeadsView({ leads, onAdd, onCall }) {
  const [showModal, setShowModal] = useState(false)
  const [callingId, setCallingId] = useState(null)
  const [search, setSearch] = useState('')

  const filtered = leads.filter(
    (l) => !search || l.name?.toLowerCase().includes(search.toLowerCase()) || l.phone?.includes(search)
  )

  const handleCall = async (lead) => {
    setCallingId(lead.id)
    await onCall(lead)
    setCallingId(null)
  }

  const newCount = leads.filter((l) => l.status === 'new').length

  return (
    <div className="flex-1 overflow-hidden flex flex-col">
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-4 border-b border-parchment-200 bg-white">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-base font-semibold text-ink-900" style={{ fontFamily: "'Playfair Display', Georgia, serif" }}>
              Leads &amp; CRM
            </h2>
            <p className="text-[12px] text-ink-400 mt-0.5">
              {leads.length} total · {newCount} new
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div className="relative">
              <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 text-ink-400 absolute left-3 top-1/2 -translate-y-1/2">
                <path fillRule="evenodd" d="M9 3.5a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11zM2 9a7 7 0 1 1 12.452 4.391l3.328 3.329a.75.75 0 1 1-1.06 1.06l-3.329-3.328A7 7 0 0 1 2 9z" clipRule="evenodd" />
              </svg>
              <input
                type="text"
                placeholder="Search leads…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9 pr-4 py-2 text-sm bg-parchment-50 border border-parchment-200 rounded focus:outline-none focus:ring-2 focus:ring-legal-navy/20 focus:border-legal-navy/40 w-48 transition-all"
              />
            </div>
            <button
              onClick={() => setShowModal(true)}
              className="flex items-center gap-2 px-4 py-2 rounded bg-legal-navy text-white text-[13px] font-semibold hover:bg-legal-navy-hover transition-colors"
            >
              <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
                <path d="M10.75 4.75a.75.75 0 0 0-1.5 0v4.5h-4.5a.75.75 0 0 0 0 1.5h4.5v4.5a.75.75 0 0 0 1.5 0v-4.5h4.5a.75.75 0 0 0 0-1.5h-4.5v-4.5z" />
              </svg>
              Add Lead
            </button>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto px-6 py-5">
        <div className="bg-white rounded-lg border border-parchment-200 shadow-card overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-parchment-200 bg-parchment-50">
                {['Name', 'Phone', 'Source', 'Status', 'Summary', 'Added', ''].map((h) => (
                  <th key={h} className="text-left px-5 py-3 text-[11px] uppercase tracking-wider text-ink-400 font-semibold">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={7} className="text-center py-14 text-sm text-ink-400">
                    No leads found
                  </td>
                </tr>
              )}
              {filtered.map((lead, idx) => (
                <tr
                  key={lead.id}
                  className={`border-b border-parchment-100 hover:bg-legal-navy-light transition-colors ${idx % 2 !== 0 ? 'bg-parchment-50/30' : ''}`}
                >
                  <td className="px-5 py-3.5">
                    <p className="text-[13px] font-semibold text-ink-800">{lead.name}</p>
                  </td>
                  <td className="px-5 py-3.5">
                    <p className="text-[13px] font-mono text-ink-600">{lead.phone}</p>
                  </td>
                  <td className="px-5 py-3.5">
                    <span className="text-[12px] text-ink-500">{SOURCE_LABELS[lead.source] ?? lead.source ?? '—'}</span>
                  </td>
                  <td className="px-5 py-3.5">
                    <span className={`text-[11px] font-semibold px-2 py-0.5 rounded capitalize ${STATUS_STYLES[lead.status] ?? 'bg-parchment-100 text-ink-500 border border-parchment-200'}`}>
                      {lead.status}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 max-w-[200px]">
                    <p className="text-[12px] text-ink-400 truncate">{lead.incident_summary ?? '—'}</p>
                  </td>
                  <td className="px-5 py-3.5">
                    <span className="text-[12px] text-ink-400">{fmtAgo(lead.created_at)}</span>
                  </td>
                  <td className="px-5 py-3.5">
                    <button
                      onClick={() => handleCall(lead)}
                      disabled={callingId === lead.id || lead.status === 'converted'}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-[12px] font-semibold transition-all ${
                        callingId === lead.id
                          ? 'bg-legal-amber-light text-legal-amber border border-legal-amber-border cursor-wait'
                          : lead.status === 'converted'
                          ? 'bg-parchment-100 text-parchment-300 border border-parchment-200 cursor-not-allowed'
                          : 'bg-legal-navy-light text-legal-navy border border-blue-200 hover:bg-legal-navy hover:text-white hover:border-legal-navy transition-all'
                      }`}
                    >
                      <svg viewBox="0 0 16 16" fill="currentColor" className="w-3 h-3">
                        <path fillRule="evenodd" d="M1.885.511a1.745 1.745 0 0 1 2.61.163L6.29 2.98c.329.423.445.974.315 1.494l-.547 2.19a.678.678 0 0 0 .178.643l2.457 2.457a.678.678 0 0 0 .644.178l2.189-.547a1.745 1.745 0 0 1 1.494.315l2.306 1.794c.829.645.905 1.87.163 2.611l-1.034 1.034c-.74.74-1.846 1.065-2.877.702a18.634 18.634 0 0 1-7.01-4.42 18.634 18.634 0 0 1-4.42-7.009c-.362-1.03-.037-2.137.703-2.877L1.885.511z" clipRule="evenodd" />
                      </svg>
                      {callingId === lead.id ? 'Calling…' : 'Call'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {showModal && <AddLeadModal onClose={() => setShowModal(false)} onAdd={onAdd} />}
    </div>
  )
}
