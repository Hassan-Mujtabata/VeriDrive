export default function Recommendation({ score, recommendation }) {
  const isGood = score >= 75
  const isMid = score >= 50 && score < 75
  const isBad = score < 50

  const config = isGood
    ? { bg: 'bg-emerald-50', border: 'border-emerald-200', icon: '✅', title: 'Looks Good — Proceed with Care', titleColor: 'text-emerald-800', textColor: 'text-emerald-700' }
    : isMid
    ? { bg: 'bg-amber-50', border: 'border-amber-200', icon: '⚠️', title: 'Proceed with Caution', titleColor: 'text-amber-800', textColor: 'text-amber-700' }
    : { bg: 'bg-red-50', border: 'border-red-200', icon: '🚨', title: 'High Risk — Do Not Proceed Without Further Checks', titleColor: 'text-red-800', textColor: 'text-red-700' }

  return (
    <div className={`rounded-2xl border ${config.border} ${config.bg} p-5`}>
      <div className="flex items-center gap-3 mb-2">
        <span className="text-2xl">{config.icon}</span>
        <h3 className={`text-base font-bold ${config.titleColor}`}>{config.title}</h3>
      </div>
      <p className={`text-sm leading-relaxed ${config.textColor}`}>{recommendation}</p>
    </div>
  )
}
