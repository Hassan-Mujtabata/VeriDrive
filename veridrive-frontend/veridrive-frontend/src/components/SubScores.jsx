function ScoreBar({ value }) {
  const color = value >= 75 ? 'bg-emerald-500' : value >= 50 ? 'bg-amber-400' : 'bg-red-500'
  return (
    <div className="w-full bg-gray-100 rounded-full h-2 mt-2">
      <div
        className={`${color} h-2 rounded-full transition-all duration-1000`}
        style={{ width: `${value}%` }}
      />
    </div>
  )
}

function SubScoreCard({ icon, label, score, description }) {
  const color =
    score >= 75 ? 'text-emerald-600' : score >= 50 ? 'text-amber-500' : 'text-red-500'
  const border =
    score >= 75 ? 'border-emerald-100' : score >= 50 ? 'border-amber-100' : 'border-red-100'
  const bg =
    score >= 75 ? 'bg-emerald-50' : score >= 50 ? 'bg-amber-50' : 'bg-red-50'

  return (
    <div className={`rounded-xl p-5 border ${border} ${bg}`}>
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <span className="text-xl">{icon}</span>
          <span className="text-sm font-semibold text-gray-700">{label}</span>
        </div>
        <span className={`text-2xl font-extrabold ${color}`}>{score}</span>
      </div>
      <ScoreBar value={score} />
      <p className="text-xs text-gray-500 mt-2">{description}</p>
    </div>
  )
}

export default function SubScores({ trustScore, vinAvailable }) {
  const scores = [
    {
      icon: '📞',
      label: 'Seller Credibility',
      score: trustScore.seller_credibility_subscore,
      description: 'Based on consistency and completeness of seller responses during the AI verification call.'
    },
    {
      icon: '💰',
      label: 'Price Fairness',
      score: trustScore.price_fairness_subscore,
      description: 'Asking price compared to live market median for equivalent vehicles on Dubizzle and YallaMotor.'
    },
    {
      icon: '🔍',
      label: 'VIN History',
      score: vinAvailable ? trustScore.vin_history_subscore : null,
      description: vinAvailable
        ? 'Cross-referenced against NHTSA and Vehicle Databases for accident, title, and salvage records.'
        : 'VIN not provided by seller. This sub-score was not included in the composite calculation.'
    }
  ]

  return (
    <div>
      <h3 className="text-base font-bold text-gray-800 mb-3">Sub-Scores</h3>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {scores.map((s) => (
          s.score !== null ? (
            <SubScoreCard key={s.label} {...s} />
          ) : (
            <div key={s.label} className="rounded-xl p-5 border border-gray-100 bg-gray-50">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xl">{s.icon}</span>
                <span className="text-sm font-semibold text-gray-500">{s.label}</span>
              </div>
              <p className="text-xs text-gray-400 mt-2">{s.description}</p>
            </div>
          )
        ))}
      </div>
    </div>
  )
}
