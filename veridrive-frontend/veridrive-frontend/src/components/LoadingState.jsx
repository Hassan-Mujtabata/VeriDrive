import { useState, useEffect } from 'react'

const STEPS = [
  { id: 1, label: 'Scraping Dubizzle listing',       detail: 'Extracting vehicle details, photos, and seller info...' },
  { id: 2, label: 'Analyzing listing with AI',        detail: 'Identifying claims, gaps, and suspicious patterns...' },
  { id: 3, label: 'Calling seller via AI voice agent',detail: 'Conducting structured verification call in English...' },
  { id: 4, label: 'Checking VIN history',             detail: 'Cross-referencing accident and ownership records...' },
  { id: 5, label: 'Analyzing market pricing',         detail: 'Comparing against live Dubizzle and YallaMotor listings...' },
  { id: 6, label: 'Generating trust report',          detail: 'Computing composite score and red flags...' }
]

export default function LoadingState() {
  const [activeStep, setActiveStep] = useState(0)

  useEffect(() => {
    const interval = setInterval(() => {
      setActiveStep((prev) => {
        if (prev < STEPS.length - 1) return prev + 1
        clearInterval(interval)
        return prev
      })
    }, 8000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-16 bg-gray-50">
      {/* Logo */}
      <div className="flex items-center gap-3 mb-12">
        <div className="w-8 h-8 bg-brand-600 rounded-lg flex items-center justify-center">
          <svg viewBox="0 0 24 24" fill="white" className="w-5 h-5">
            <path d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
          </svg>
        </div>
        <span className="text-xl font-bold text-gray-900">VeriDrive</span>
      </div>

      <h2 className="text-2xl font-bold text-gray-900 mb-2 text-center">Verifying your listing</h2>
      <p className="text-gray-500 mb-10 text-center text-sm">This typically takes 3 to 5 minutes. Please keep this tab open.</p>

      <div className="w-full max-w-lg space-y-3">
        {STEPS.map((step, idx) => {
          const isDone = idx < activeStep
          const isActive = idx === activeStep
          const isPending = idx > activeStep

          return (
            <div
              key={step.id}
              className={`flex items-start gap-4 p-4 rounded-xl border transition-all duration-500 ${
                isDone
                  ? 'bg-brand-50 border-brand-200'
                  : isActive
                  ? 'bg-white border-brand-400 shadow-sm'
                  : 'bg-white border-gray-100 opacity-40'
              }`}
            >
              <div className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center mt-0.5 ${
                isDone ? 'bg-brand-600' : isActive ? 'bg-brand-600' : 'bg-gray-200'
              }`}>
                {isDone ? (
                  <svg viewBox="0 0 20 20" fill="white" className="w-4 h-4">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                ) : isActive ? (
                  <svg className="w-4 h-4 animate-spin text-white" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                ) : (
                  <span className="text-gray-400 text-xs font-bold">{step.id}</span>
                )}
              </div>
              <div>
                <p className={`text-sm font-semibold ${isDone || isActive ? 'text-gray-900' : 'text-gray-400'}`}>
                  {step.label}
                </p>
                {isActive && (
                  <p className="text-xs text-gray-500 mt-0.5">{step.detail}</p>
                )}
                {isDone && (
                  <p className="text-xs text-brand-600 mt-0.5">Complete</p>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
