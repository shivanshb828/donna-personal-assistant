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

const EMAIL_TYPE_STYLES = {
  adjuster_follow_up: 'bg-legal-navy-light text-legal-navy border-blue-200',
  records_request: 'bg-purple-50 text-purple-700 border-purple-200',
  client_update: 'bg-legal-forest-light text-legal-forest border-legal-forest-border',
  deposition_notice: 'bg-legal-amber-light text-legal-amber border-legal-amber-border',
  lien_notice: 'bg-legal-crimson-light text-legal-crimson border-legal-crimson-border',
  appointment_confirmation: 'bg-legal-forest-light text-legal-forest border-legal-forest-border',
  demand_acknowledgment: 'bg-parchment-100 text-ink-600 border-parchment-300',
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
    <div className="bg-white rounded-lg border border-legal-gold-border shadow-card overflow-hidden animate-slide-up">
      {/* Approval strip */}
      <div className="bg-legal-gold-light border-b border-legal-gold-border px-5 py-2.5 flex items-center gap-2">
        <span className="w-1.5 h-1.5 rounded-full bg-legal-gold-mid dot-live" />
        <span className="text-[11px] font-bold uppercase tracking-wider text-legal-gold">
          Awaiting Your Approval
        </span>
        <span className="ml-auto text-[11px] text-legal-gold font-mono">
          {fmt(draft.created_at ?? draft.ts)}
        </span>
      </div>

      <div className="px-5 py-4">
        <div className="flex items-start gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-1.5">
              <span className={`text-[11px] font-semibold px-2 py-0.5 rounded border ${EMAIL_TYPE_STYLES[draft.email_type] ?? 'bg-parchment-100 text-ink-600 border-parchment-300'}`}>
                {EMAIL_TYPE_LABELS[draft.email_type] ?? draft.email_type}
              </span>
            </div>
            <h4 className="text-[14px] font-semibold text-ink-900 leading-snug">{draft.subject}</h4>
            <p className="text-[12px] text-ink-400 mt-0.5">To: {draft.to}</p>
          </div>
        </div>

        {/* Email body preview */}
        <div className="mt-3 bg-parchment-50 rounded border border-parchment-200 px-4 py-3 text-[13px] text-ink-600 leading-relaxed font-serif" style={{ fontFamily: 'Georgia, serif' }}>
          {draft.preview ?? draft.body ?? '(No preview available)'}
          {draft.preview && '…'}
        </div>

        {/* Donna's reasoning */}
        {draft.donna_reasoning && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="mt-2.5 w-full text-left"
          >
            <div className="flex items-center gap-2 text-[11px] text-ink-400 hover:text-ink-600 transition-colors">
              <svg viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5">
                <path d="M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0zm.93 6.588-2.29.287-.082.38.45.083c.294.07.352.176.288.469l-.738 3.468c-.194.897.105 1.319.808 1.319.545 0 1.178-.252 1.465-.598l.088-.416c-.2.176-.492.246-.686.246-.275 0-.375-.193-.304-.533L8.93 6.588zM8 5.5a1 1 0 1 0 0-2 1 1 0 0 0 0 2z" />
              </svg>
              <span>Donna's reasoning {expanded ? '▲' : '▼'}</span>
            </div>
            {expanded && (
              <div className="mt-2 bg-legal-navy-light border border-blue-100 rounded px-4 py-3 text-[12px] text-legal-navy italic leading-relaxed">
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
              className="w-full px-3 py-2 text-sm bg-parchment-50 border border-parchment-200 rounded focus:outline-none focus:ring-2 focus:ring-legal-navy/20 focus:border-legal-navy/40"
            />
          </div>
        )}

        {/* Action buttons */}
        <div className="mt-4 flex items-center gap-2">
          <button
            onClick={() => onApprove(draft)}
            className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded bg-legal-forest text-white text-[13px] font-semibold hover:opacity-90 transition-opacity"
          >
            <svg viewBox="0 0 16 16" fill="currentColor" className="w-4 h-4">
              <path d="M13.854 3.646a.5.5 0 0 1 0 .708l-7 7a.5.5 0 0 1-.708 0l-3.5-3.5a.5.5 0 1 1 .708-.708L6.5 10.293l6.646-6.647a.5.5 0 0 1 .708 0z" />
            </svg>
            Approve &amp; Send
          </button>

          {!rejecting ? (
            <button
              onClick={() => setRejecting(true)}
              className="flex items-center gap-1.5 px-4 py-2.5 rounded border border-parchment-200 text-ink-600 text-[13px] font-medium hover:bg-legal-crimson-light hover:border-legal-crimson-border hover:text-legal-crimson transition-all"
            >
              Reject
            </button>
          ) : (
            <>
              <button
                onClick={() => onReject(draft, reason)}
                className="px-4 py-2.5 rounded bg-legal-crimson text-white text-[13px] font-semibold hover:opacity-90 transition-opacity"
              >
                Confirm Reject
              </button>
              <button
                onClick={() => { setRejecting(false); setReason('') }}
                className="px-3 py-2.5 rounded border border-parchment-200 text-ink-600 text-[13px] hover:bg-parchment-50 transition-colors"
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
      <div className="flex-shrink-0 px-6 py-4 border-b border-parchment-200 bg-white">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-ink-900" style={{ fontFamily: "'Playfair Display', Georgia, serif" }}>
              Email Approvals
            </h2>
            <p className="text-[12px] text-ink-400 mt-0.5">Donna-drafted correspondence pending your signature</p>
          </div>
          {drafts.length > 0 && (
            <span className="bg-legal-gold-light text-legal-gold border border-legal-gold-border text-[12px] font-bold px-3 py-1.5 rounded">
              {drafts.length} pending review
            </span>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5">
        {drafts.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 text-ink-400">
            <div className="w-14 h-14 rounded-lg bg-parchment-100 border border-parchment-200 flex items-center justify-center mb-4">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-7 h-7 text-parchment-300">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z" />
              </svg>
            </div>
            <p className="text-[13px] font-semibold text-ink-500">No pending approvals</p>
            <p className="text-[12px] text-ink-400 mt-1">
              Email drafts requiring your review will appear here
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
