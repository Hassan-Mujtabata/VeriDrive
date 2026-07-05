const SEVERITY_CONFIG = {
  high:   { bg: 'bg-red-50',    border: 'border-red-200',   dot: 'bg-red-500',   text: 'text-red-700',   badge: 'bg-red-100 text-red-700',   label: 'HIGH' },
  medium: { bg: 'bg-amber-50',  border: 'border-amber-200', dot: 'bg-amber-500', text: 'text-amber-700', badge: 'bg-amber-100 text-amber-700', label: 'MEDIUM' },
  low:    { bg: 'bg-blue-50',   border: 'border-blue-100',  dot: 'bg-blue-400',  text: 'text-blue-700',  badge: 'bg-blue-100 text-blue-700',   label: 'LOW' }
}

const MODULE_LABELS = {
  VIN:   'VIN Report',
  Voice: 'Voice Call',
  Price: 'Price Analysis',
  Listing: 'Listing Analysis'
}

export default function RedFlags({ flags }) {
  if (!flags || flags.length === 0) {
    return (
      <div>
        <h3 className="text-base font-bold text-gray-800 mb-3">Red Flags</h3>
        <div className="rounded-xl border border-emerald-100 bg-emerald-50 p-5 flex items-center gap-3">
          <span className="text-2xl">✅</span>
          <p className="text-sm text-emerald-700 font-medium">No red flags detected. This listing passed all verification checks.</p>
        </div>
      </div>
    )
  }

  const sorted = [...flags].sort((a, b) => {
    const order = { high: 0, medium: 1, low: 2 }
    return order[a.severity] - order[b.severity]
  })

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-base font-bold text-gray-800">Red Flags</h3>
        <span className="text-xs text-gray-400 font-medium">{flags.length} detected</span>
      </div>
      <div className="space-y-3">
        {sorted.map((flag, idx) => {
          const cfg = SEVERITY_CONFIG[flag.severity] || SEVERITY_CONFIG.low
          return (
            <div key={idx} className={`rounded-xl border ${cfg.border} ${cfg.bg} p-4`}>
              <div className="flex items-start gap-3">
                <div className={`w-2 h-2 rounded-full ${cfg.dot} flex-shrink-0 mt-1.5`} />
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2 mb-1">
                    <span className="text-sm font-semibold text-gray-900">{flag.title}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-bold ${cfg.badge}`}>
                      {cfg.label}
                    </span>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-500 font-medium">
                      {MODULE_LABELS[flag.source_module] || flag.source_module}
                    </span>
                  </div>
                  <p className="text-xs text-gray-600 leading-relaxed">{flag.description}</p>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
