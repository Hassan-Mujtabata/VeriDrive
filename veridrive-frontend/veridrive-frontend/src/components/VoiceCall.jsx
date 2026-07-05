function formatDuration(seconds) {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}m ${s}s`
}

export default function VoiceCall({ voiceCall }) {
  if (!voiceCall || !voiceCall.available) {
    return (
      <div>
        <h3 className="text-base font-bold text-gray-800 mb-3">AI Seller Verification Call</h3>
        <div className="rounded-xl border border-gray-100 bg-gray-50 p-5">
          <p className="text-sm text-gray-500">No call data available. The seller may not have answered.</p>
        </div>
      </div>
    )
  }

  const { seller_credibility_score, call_outcome, duration_seconds, transcript_summary } = voiceCall

  const scoreColor =
    seller_credibility_score >= 75
      ? 'text-emerald-600'
      : seller_credibility_score >= 50
      ? 'text-amber-500'
      : 'text-red-500'

  const outcomeLabel = {
    completed: 'Call Completed',
    no_answer: 'No Answer',
    voicemail: 'Voicemail',
    declined: 'Declined'
  }[call_outcome] || call_outcome

  return (
    <div>
      <h3 className="text-base font-bold text-gray-800 mb-3">AI Seller Verification Call</h3>
      <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
        {/* Call meta */}
        <div className="grid grid-cols-3 divide-x divide-gray-50 border-b border-gray-50">
          <div className="p-3 text-center">
            <p className="text-xs text-gray-400 mb-0.5">Outcome</p>
            <p className="text-sm font-semibold text-gray-700">{outcomeLabel}</p>
          </div>
          <div className="p-3 text-center">
            <p className="text-xs text-gray-400 mb-0.5">Duration</p>
            <p className="text-sm font-semibold text-gray-700">{formatDuration(duration_seconds)}</p>
          </div>
          <div className="p-3 text-center">
            <p className="text-xs text-gray-400 mb-0.5">Credibility Score</p>
            <p className={`text-lg font-extrabold ${scoreColor}`}>{seller_credibility_score}/100</p>
          </div>
        </div>

        {/* Transcript summary */}
        {transcript_summary && (
          <div className="p-4">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Call Summary</p>
            <p className="text-sm text-gray-600 leading-relaxed">{transcript_summary}</p>
          </div>
        )}
      </div>
    </div>
  )
}
