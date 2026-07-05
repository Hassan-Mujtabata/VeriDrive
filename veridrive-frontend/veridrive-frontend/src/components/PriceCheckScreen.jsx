import { useState } from 'react'
import PriceAnalysis from './PriceAnalysis.jsx'

// Calls the price engine API via the /api/price Vite proxy
// (which forwards to http://localhost:8002/estimate).
// Takes 30-60 seconds — show a loading state before calling.
async function fetchPriceEstimate({ make, model, year, mileage_km, asking_price_aed }) {
  const body = { make, model, year: Number(year), mileage_km: Number(mileage_km) }
  if (asking_price_aed) body.asking_price_aed = Number(asking_price_aed)

  const res = await fetch('/api/price/estimate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Price engine returned ${res.status}.`)
  }
  return res.json()
}

function Field({ label, children, hint }) {
  return (
    <div>
      <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide block mb-1.5">
        {label}
        {hint && <span className="ml-1 text-gray-300 normal-case font-normal">{hint}</span>}
      </label>
      {children}
    </div>
  )
}

const INPUT = "w-full px-3 py-2.5 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"

export default function PriceCheckScreen({ onBack }) {
  const [form, setForm] = useState({ make: '', model: '', year: '', mileage_km: '', asking_price_aed: '' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)

  function update(field, value) {
    setForm((f) => ({ ...f, [field]: value }))
  }

  function validate() {
    if (!form.make.trim()) return 'Make is required.'
    if (!form.model.trim()) return 'Model is required.'
    const y = Number(form.year)
    if (!y || y < 1990 || y > new Date().getFullYear() + 1) return 'Enter a valid year (1990 or later).'
    const m = Number(form.mileage_km)
    if (form.mileage_km === '' || m < 0) return 'Enter a valid mileage.'
    if (form.asking_price_aed && Number(form.asking_price_aed) <= 0) return 'Asking price must be greater than 0.'
    return ''
  }

  async function handleSubmit(e) {
    e.preventDefault()
    const err = validate()
    if (err) { setError(err); return }
    setError('')
    setLoading(true)
    setResult(null)
    try {
      const data = await fetchPriceEstimate({
        make: form.make.trim(),
        model: form.model.trim(),
        year: form.year,
        mileage_km: form.mileage_km,
        asking_price_aed: form.asking_price_aed || null,
      })
      setResult(data)
    } catch (err) {
      setError(err.message || 'Could not fetch a price estimate. Make sure the price engine is running on port 8002.')
    } finally {
      setLoading(false)
    }
  }

  // Map API response to PriceAnalysis.jsx's expected priceAnalysis shape
  function toPriceAnalysis(data) {
    return {
      comparable_count: data.comparable_count,
      median_market_price: data.median_market_price,
      price_difference_percent: data.price_difference_percent ?? 0,
      fairness_score: data.fairness_score ?? null,
      recommended_min_aed: data.recommended_min_aed,
      recommended_max_aed: data.recommended_max_aed,
    }
  }

  return (
    <div className="min-h-screen flex flex-col">
      <nav className="bg-white border-b border-gray-100 px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <button onClick={onBack} className="flex items-center gap-3">
            <div className="w-8 h-8 bg-brand-600 rounded-lg flex items-center justify-center">
              <svg viewBox="0 0 24 24" fill="white" className="w-5 h-5">
                <path d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
            </div>
            <span className="text-xl font-bold text-gray-900">VeriDrive</span>
          </button>
        </div>
      </nav>

      <div className="flex-1 px-4 py-12">
        <div className="max-w-lg mx-auto">
          <div className="text-center mb-8">
            <h1 className="text-3xl font-extrabold text-gray-900 mb-2">Check market price</h1>
            <p className="text-gray-500 text-sm">
              Enter your car's details and see a fair market price based on comparable Dubizzle listings.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Make">
                <input type="text" placeholder="Toyota" value={form.make}
                  onChange={(e) => update('make', e.target.value)} className={INPUT} />
              </Field>
              <Field label="Model">
                <input type="text" placeholder="Corolla" value={form.model}
                  onChange={(e) => update('model', e.target.value)} className={INPUT} />
              </Field>
              <Field label="Year">
                <input type="number" placeholder="2021" value={form.year}
                  onChange={(e) => update('year', e.target.value)} className={INPUT} />
              </Field>
              <Field label="Mileage (km)">
                <input type="number" placeholder="45000" value={form.mileage_km}
                  onChange={(e) => update('mileage_km', e.target.value)} className={INPUT} />
              </Field>
            </div>

            <Field label="Asking price (AED)" hint="— optional">
              <input
                type="number"
                placeholder="e.g. 48000 — leave blank for market estimate only"
                value={form.asking_price_aed}
                onChange={(e) => update('asking_price_aed', e.target.value)}
                className={INPUT}
              />
              <p className="text-xs text-gray-400 mt-1">
                If provided, we'll compare the asking price to the market and show a fairness score.
              </p>
            </Field>

            {error && (
              <p className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">{error}</p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-brand-600 text-white rounded-xl font-semibold hover:bg-brand-700 active:scale-95 transition text-sm disabled:opacity-50"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                    <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeDasharray="40 20" strokeLinecap="round"/>
                  </svg>
                  Scanning {form.year} {form.make} {form.model} listings…
                </span>
              ) : 'Check market price'}
            </button>

            {loading && (
              <p className="text-xs text-gray-400 text-center">
                Scraping up to 5 pages of comparable listings — this usually takes 30–60 seconds.
              </p>
            )}
          </form>

          {result && (
            <div className="mt-6 bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
              {result.verdict && (
                <div className="mb-4 px-4 py-3 bg-brand-50 border border-brand-100 rounded-xl">
                  <p className="text-sm font-semibold text-brand-700">{result.verdict}</p>
                </div>
              )}
              <PriceAnalysis
                priceAnalysis={toPriceAnalysis(result)}
                askingPrice={result.asking_price_aed || result.median_market_price}
              />
            </div>
          )}
        </div>
      </div>

      <footer className="text-center py-4 text-xs text-gray-400 border-t border-gray-100">
        VeriDrive — BCS 410-1 Graduation Project · Supervisor: Dr. Yasir Faheem
      </footer>
    </div>
  )
}
