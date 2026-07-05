import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, ReferenceLine
} from 'recharts'

function formatAED(value) {
  return `AED ${value.toLocaleString()}`
}

function CustomTooltip({ active, payload, label }) {
  if (active && payload && payload.length) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg shadow-lg px-3 py-2 text-xs">
        <p className="font-semibold text-gray-700 mb-1">{label}</p>
        <p className="text-brand-600 font-bold">{formatAED(payload[0].value)}</p>
      </div>
    )
  }
  return null
}

export default function PriceAnalysis({ priceAnalysis, askingPrice }) {
  const {
    comparable_count,
    median_market_price,
    price_difference_percent,
    fairness_score,
    recommended_min_aed,
    recommended_max_aed
  } = priceAnalysis

  const isUnderpriced = price_difference_percent < -10
  const isOverpriced = price_difference_percent > 10

  const chartData = [
    { name: 'Asking Price', value: askingPrice, color: '#0d9488' },
    { name: 'Market Median', value: median_market_price, color: '#6b7280' },
    { name: 'Recommended Min', value: recommended_min_aed, color: '#10b981' },
    { name: 'Recommended Max', value: recommended_max_aed, color: '#10b981' }
  ]

  const diff = Math.abs(price_difference_percent).toFixed(1)
  const diffLabel = isUnderpriced
    ? `${diff}% below market median`
    : isOverpriced
    ? `${diff}% above market median`
    : 'Aligned with market median'

  const diffColor = isUnderpriced
    ? 'text-emerald-600'
    : isOverpriced
    ? 'text-red-500'
    : 'text-gray-600'

  return (
    <div>
      <h3 className="text-base font-bold text-gray-800 mb-4">Market Price Analysis</h3>

      {/* Stats row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
        <div className="bg-white rounded-xl border border-gray-100 p-3 text-center">
          <p className="text-xs text-gray-400 mb-1">Asking Price</p>
          <p className="text-sm font-bold text-gray-900">{formatAED(askingPrice)}</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-100 p-3 text-center">
          <p className="text-xs text-gray-400 mb-1">Market Median</p>
          <p className="text-sm font-bold text-gray-900">{formatAED(median_market_price)}</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-100 p-3 text-center">
          <p className="text-xs text-gray-400 mb-1">Vs. Market</p>
          <p className={`text-sm font-bold ${diffColor}`}>{diffLabel}</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-100 p-3 text-center">
          <p className="text-xs text-gray-400 mb-1">Comparables</p>
          <p className="text-sm font-bold text-gray-900">{comparable_count} listings</p>
        </div>
      </div>

      {/* Chart */}
      <div className="bg-white rounded-xl border border-gray-100 p-4">
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={chartData} barSize={40}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" vertical={false} />
            <XAxis
              dataKey="name"
              tick={{ fontSize: 11, fill: '#6b7280' }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
              tick={{ fontSize: 11, fill: '#6b7280' }}
              axisLine={false}
              tickLine={false}
              width={40}
            />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="value" radius={[6, 6, 0, 0]}>
              {chartData.map((entry, index) => (
                <Cell key={index} fill={entry.color} opacity={index === 0 ? 1 : 0.55} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Recommended range */}
      <div className="mt-3 bg-emerald-50 border border-emerald-100 rounded-xl p-4">
        <p className="text-xs font-semibold text-emerald-700 mb-0.5">Recommended Negotiation Range</p>
        <p className="text-base font-bold text-emerald-800">
          {formatAED(recommended_min_aed)} — {formatAED(recommended_max_aed)}
        </p>
        <p className="text-xs text-emerald-600 mt-0.5">
          Based on {comparable_count} comparable listings from Dubizzle and YallaMotor
        </p>
      </div>
    </div>
  )
}
