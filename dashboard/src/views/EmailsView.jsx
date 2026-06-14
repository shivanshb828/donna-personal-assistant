import { useState } from 'react'

const EMAIL_TYPE_LABELS = {
  adjuster_follow_up: 'Adjuster Follow-up',
  records_request: 'Records Request',
  client_update: 'Client Update',
  deposition_notice: 'Deposition Notice',
  lien_notice: 'Lien Notice',
  appointment_confirmation: 'Appointment Confirmation',
  demand_acknowledgment: 'Demand Acknowledgment',
}

const EMAIL_TYPE_COLORS = {
  adjuster_follow_up: 'bg-blue-50 text-blue-700',
  records_request: 'bg-violet-50 text-violet-700',
  client_update: 'bg-emerald-50 text-emerald-700',
  deposition_notice: 'bg-orange-50 text-orange-700',
  lien_notice: 'bg-red-50 text-red-700',
  appointment_confirmation: 'bg-green-50 text-green-700',
  demand_acknowledgment: 'bg-slate-50 text-slate-600',
}

function fmt(isoStr) {
  return new Date(isoStr).toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function DraftCard({ draft, onApprove, onReject }) {
  const [rejecting, setRejecting] = useState(false)
  const [reason, setReason] = useState('')
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="bg-white rounded-2xl border border-amber-200 shadow-sm overflow-hidden animate-slide-up">
      {/* Pending badge strip */}
      <div className="bg-amber-50 border-b border-amber-100 px-5 py-2.5 flex items-center gap-2">
        <span className="w-2 h-2 rounded-full bg-amber-500 dot-live" />
        <span className="text-[11px] font-bold uppercase tracking-wider text-amber-700">
          Awaiting Approval
        </span>
        <span className="ml-auto text-[11px] text-amber-600">
          {fmt(draft.created_at ?? draft.ts)}
        </span>
      </div>

      <div className="px-5 py-4">
        {/* Header row */}
        <div className="flex items-start gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-1">
              <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${EMAIL_TYPE_COLORS[draft.email_type] ?? 'bg-slate-50 text-slate-600'}`}>
                {EMAIL_TYPE_LABELS[draft.email_type] ?? draft.email_type}
              </span>
            </div>
            <h4 className="text-sm font-bold text-slate-800 leading-snug">{draft.subject}</h4>
            <p className="text-xs text-slate-500 mt-0.5">To: {draft.to}</p>
          </div>
        </div>

        {/* Preview */}
        <div className="mt-3 bg-slate-50 rounded-xl px-4 py-3 text-sm text-slate-600 leading-relaxed">
          {draft.preview ?? draft.body ?? '(No preview available)'}
          {draft.preview && '…'}
        </div>

        {/* Donna's reasoning */}
        {draft.donna_reasoning && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="mt-2 w-full text-left"
          >
            <div className="flex items-center gap-2 text-[11px] text-slate-400 hover:text-slate-600 transition-colors">
              <svg viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5">
                <path d="M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0zm.93 6.588-2.29.287-.082.38.45.083c.294.07.352.176.288.469l-.738 3.468c-.194.897.105 1.319.808 1.319.545 0 1.178-.252 1.465-.598l.088-.416c-.2.176-.492.246-.686.246-.275 0-.375-.193-.304-.533L8.93 6.588zM8 5.5a1 1 0 1 0 0-2 1 1 0 0 0 0 2z" />
              </svg>
              <span>Donna's reasoning {expanded ? '▲' : '▼'}</span>
            </div>
            {expanded && (
              <div className="mt-2 bg-blue-50 rounded-xl px-4 py-3 text-xs text-blue-700 italic leading-relaxed">
                {draft.donna_reasoning}
              </div>
            )}
          </button>
        )}

        {/* Reject reason input */}
        {rejecting && (
          <div className="mt-3">
            <input
              type="text"
              placeholder="Reason for rejection (optional)…"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="w-full px-3 py-2 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400"
            />
          </div>
        )}

        {/* Action buttons */}
        <div className="mt-4 flex items-center gap-2">
          <button
            onClick={() => onApprove(draft)}
            className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl bg-emerald-600 text-white text-sm font-semibold hover:bg-emerald-700 transition-colors shadow-md shadow-emerald-500/20"
          >
            <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
              <path fillRule="evenodd" d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16zm3.857-9.809a.75.75 0 0 0-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 1 0-1.06 1.061l2.5 2.5a.75.75 0 0 0 1.137-.089l4-5.5z" clipRule="evenodd" />
            </svg>
            Approve & Send
          </button>

          {!rejecting ? (
            <button
              onClick={() => setRejecting(true)}
              className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl border border-slate-200 text-slate-600 text-sm font-semibold hover:bg-red-50 hover:border-red-200 hover:text-red-600 transition-all"
            >
              <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
                <path fillRule="evenodd" d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM8.28 7.22a.75.75 0 0 0-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 1 0 1.06 1.06L10 11.06l1.72 1.72a.75.75 0 1 0 1.06-1.06L11.06 10l1.72-1.72a.75.75 0 0 0-1.06-1.06L10 8.94 8.28 7.22z" clipRule="evenodd" />
              </svg>
              Reject
            </button>
          ) : (
            <>
              <button
                onClick={() => onReject(draft, reason)}
                className="px-4 py-2.5 rounded-xl bg-red-600 text-white text-sm font-semibold hover:bg-red-700 transition-colors"
              >
                Confirm Reject
              </button>
              <button
                onClick={() => { setRejecting(false); setReason('') }}
                className="px-3 py-2.5 rounded-xl border border-slate-200 text-slate-600 text-sm hover:bg-slate-50 transition-colors"
              >
                Cancel
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default function EmailsView({ drafts, onApprove, onReject }) {
  return (
    <div className="flex-1 overflow-hidden flex flex-col">
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-5 border-b border-slate-200/60 bg-white/60 backdrop-blur-sm">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Email Approvals</h2>
            <p className="text-sm text-slate-500 mt-0.5">
              Donna-drafted emails pending your review
            </p>
          </div>
          {drafts.length > 0 && (
            <span className="bg-amber-100 text-amber-700 text-sm font-bold px-3 py-1.5 rounded-full">
              {drafts.length} pending
            </span>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5">
        {drafts.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 text-slate-400">
            <div className="w-16 h-16 rounded-2xl bg-slate-100 flex items-center justify-center mb-4">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-8 h-8 text-slate-300">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z" />
              </svg>
            </div>
            <p className="text-sm font-semibold text-slate-500">All caught up</p>
            <p className="text-xs text-slate-400 mt-1">
              Email drafts requiring your approval will appear here
            </p>
          </div>
        ) : (
          <div className="space-y-4 max-w-2xl">
            {drafts.map((draft) => (
              <DraftCard
                key={draft.draft_id}
                draft={draft}
                onApprove={onApprove}
                onReject={onReject}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
