import { useState } from 'react'

const SOURCE_LABELS = {
  web_form: 'Web Form',
  referral: 'Referral',
  inbound_call: 'Inbound Call',
  outbound: 'Outbound',
  other: 'Other',
}

const STATUS_STYLES = {
  new: 'bg-blue-100 text-blue-700',
  contacted: 'bg-amber-100 text-amber-700',
  qualified: 'bg-emerald-100 text-emerald-700',
  converted: 'bg-green-100 text-green-700',
  dead: 'bg-slate-100 text-slate-500',
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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden animate-slide-up"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-6 py-5 border-b border-slate-100 flex items-center justify-between">
          <h3 className="text-base font-bold text-slate-900">Add New Lead</h3>
          <button onClick={onClose} className="w-8 h-8 rounded-lg hover:bg-slate-100 flex items-center justify-center transition-colors">
            <svg viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5 text-slate-400">
              <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22z" />
            </svg>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1.5">Full Name *</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="Sarah Chen"
              className="w-full px-3.5 py-2.5 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400 transition-all"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1.5">Phone Number *</label>
            <input
              type="tel"
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
              placeholder="+1 (415) 555-0182"
              className="w-full px-3.5 py-2.5 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400 transition-all"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1.5">Source</label>
            <select
              value={form.source}
              onChange={(e) => setForm({ ...form, source: e.target.value })}
              className="w-full px-3.5 py-2.5 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400 transition-all"
            >
              {Object.entries(SOURCE_LABELS).map(([val, label]) => (
                <option key={val} value={val}>{label}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1.5">Incident Summary</label>
            <textarea
              value={form.incident_summary}
              onChange={(e) => setForm({ ...form, incident_summary: e.target.value })}
              placeholder="Brief description of the incident…"
              rows={3}
              className="w-full px-3.5 py-2.5 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400 transition-all resize-none"
            />
          </div>

          <div className="flex gap-3 pt-1">
            <button
              type="submit"
              disabled={loading}
              className="flex-1 py-2.5 rounded-xl bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 transition-colors shadow-md shadow-blue-500/20 disabled:opacity-60"
            >
              {loading ? 'Adding…' : 'Add Lead'}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="px-5 py-2.5 rounded-xl border border-slate-200 text-slate-600 text-sm font-semibold hover:bg-slate-50 transition-colors"
            >
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
    (l) =>
      !search ||
      l.name?.toLowerCase().includes(search.toLowerCase()) ||
      l.phone?.includes(search)
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
      <div className="flex-shrink-0 px-6 py-5 border-b border-slate-200/60 bg-white/60 backdrop-blur-sm">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Leads</h2>
            <p className="text-sm text-slate-500 mt-0.5">
              {leads.length} leads · {newCount} new
            </p>
          </div>

          <div className="flex items-center gap-3">
            {/* Search */}
            <div className="relative">
              <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2">
                <path fillRule="evenodd" d="M9 3.5a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11zM2 9a7 7 0 1 1 12.452 4.391l3.328 3.329a.75.75 0 1 1-1.06 1.06l-3.329-3.328A7 7 0 0 1 2 9z" clipRule="evenodd" />
              </svg>
              <input
                type="text"
                placeholder="Search leads…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9 pr-4 py-2 text-sm bg-white border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400 w-48 transition-all"
              />
            </div>

            <button
              onClick={() => setShowModal(true)}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 transition-colors shadow-md shadow-blue-500/20"
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
      <div className="flex-1 overflow-auto px-6 py-4">
        <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-100">
                {['Name', 'Phone', 'Source', 'Status', 'Summary', 'Added', 'Action'].map((h) => (
                  <th key={h} className="text-left px-5 py-3.5 text-[11px] uppercase tracking-wider text-slate-400 font-semibold">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={7} className="text-center py-12 text-sm text-slate-400">
                    No leads found
                  </td>
                </tr>
              )}
              {filtered.map((lead) => (
                <tr
                  key={lead.id}
                  className="border-b border-slate-50 hover:bg-slate-50/60 transition-colors group"
                >
                  <td className="px-5 py-3.5">
                    <p className="text-sm font-semibold text-slate-800">{lead.name}</p>
                  </td>
                  <td className="px-5 py-3.5">
                    <p className="text-sm font-mono text-slate-600">{lead.phone}</p>
                  </td>
                  <td className="px-5 py-3.5">
                    <span className="text-xs text-slate-500">{SOURCE_LABELS[lead.source] ?? lead.source ?? '—'}</span>
                  </td>
                  <td className="px-5 py-3.5">
                    <span className={`text-xs font-semibold px-2.5 py-1 rounded-full capitalize ${STATUS_STYLES[lead.status] ?? 'bg-slate-100 text-slate-600'}`}>
                      {lead.status}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 max-w-xs">
                    <p className="text-xs text-slate-500 truncate">{lead.incident_summary ?? '—'}</p>
                  </td>
                  <td className="px-5 py-3.5">
                    <span className="text-xs text-slate-400">{fmtAgo(lead.created_at)}</span>
                  </td>
                  <td className="px-5 py-3.5">
                    <button
                      onClick={() => handleCall(lead)}
                      disabled={callingId === lead.id || lead.status === 'converted'}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                        callingId === lead.id
                          ? 'bg-amber-50 text-amber-600 cursor-wait'
                          : lead.status === 'converted'
                          ? 'bg-slate-50 text-slate-300 cursor-not-allowed'
                          : 'bg-blue-50 text-blue-700 hover:bg-blue-600 hover:text-white'
                      }`}
                    >
                      <svg viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
                        <path fillRule="evenodd" d="M2 3.5A1.5 1.5 0 0 1 3.5 2h1.148a1.5 1.5 0 0 1 1.465 1.175l.716 3.223a1.5 1.5 0 0 1-1.052 1.767l-.933.267c-.41.117-.643.555-.48.95a11.542 11.542 0 0 0 6.254 6.254c.395.163.833-.07.95-.48l.267-.933a1.5 1.5 0 0 1 1.767-1.052l3.223.716A1.5 1.5 0 0 1 18 15.352V16.5a1.5 1.5 0 0 1-1.5 1.5H15c-1.149 0-2.263-.15-3.326-.43A13.022 13.022 0 0 1 2.43 8.326 13.019 13.019 0 0 1 2 5V3.5z" clipRule="evenodd" />
                      </svg>
                      {callingId === lead.id ? 'Calling…' : 'Call Now'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {showModal && (
        <AddLeadModal onClose={() => setShowModal(false)} onAdd={onAdd} />
      )}
    </div>
  )
}
