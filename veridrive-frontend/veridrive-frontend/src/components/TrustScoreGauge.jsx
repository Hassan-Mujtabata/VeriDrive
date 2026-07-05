import { useEffect, useState } from 'react'

function getScoreColor(score) {
  if (score >= 75) return { stroke: '#10b981', text: 'text-emerald-600', label: 'Low Risk', bg: 'bg-emerald-50' }
  if (score >= 50) return { stroke: '#f59e0b', text: 'text-amber-600', label: 'Moderate Risk', bg: 'bg-amber-50' }
  return { stroke: '#ef4444', text: 'text-red-500', label: 'High Risk', bg: 'bg-red-50' }
}

export default function TrustScoreGauge({ score }) {
  const [animated, setAnimated] = useState(0)

  useEffect(() => {
    const timer = setTimeout(() => setAnimated(score), 300)
    return () => clearTimeout(timer)
  }, [score])

  const { stroke, text, label, bg } = getScoreColor(score)

  // SVG arc math — 240-degree gauge
  const R = 80
  const CX = 100
  const CY = 105
  const circumference = 2 * Math.PI * R
  const arcLength = (240 / 360) * circumference
  const gap = circumference - arcLength
  const filledLength = (animated / 100) * arcLength
  const dashoffset = arcLength - filledLength

  // Rotation to start gauge at 150 degrees (bottom-left)
  const rotation = 150

  return (
    <div className="flex flex-col items-center">
      <div className="relative">
        <svg width="200" height="160" viewBox="0 0 200 160">
          {/* Background track */}
          <circle
            cx={CX}
            cy={CY}
            r={R}
            fill="none"
            stroke="#e5e7eb"
            strokeWidth="14"
            strokeDasharray={`${arcLength} ${gap}`}
            strokeDashoffset="0"
            strokeLinecap="round"
            transform={`rotate(${rotation}, ${CX}, ${CY})`}
          />
          {/* Filled arc */}
          <circle
            cx={CX}
            cy={CY}
            r={R}
            fill="none"
            stroke={stroke}
            strokeWidth="14"
            strokeDasharray={`${filledLength} ${circumference - filledLength}`}
            strokeDashoffset="0"
            strokeLinecap="round"
            transform={`rotate(${rotation}, ${CX}, ${CY})`}
            className="score-ring"
            style={{
              transition: 'stroke-dasharray 1.2s ease-in-out',
            }}
          />
          {/* Score text */}
          <text
            x={CX}
            y={CY - 8}
            textAnchor="middle"
            fontSize="36"
            fontWeight="800"
            fontFamily="Inter, sans-serif"
            fill="#111827"
          >
            {score}
          </text>
          <text
            x={CX}
            y={CY + 14}
            textAnchor="middle"
            fontSize="12"
            fontWeight="500"
            fontFamily="Inter, sans-serif"
            fill="#6b7280"
          >
            out of 100
          </text>
        </svg>
      </div>
      <div className={`px-4 py-1.5 rounded-full text-sm font-semibold ${bg} ${text} -mt-2`}>
        {label}
      </div>
    </div>
  )
}
