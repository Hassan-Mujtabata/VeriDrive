import { useState } from 'react'
import URLInput from './components/URLInput.jsx'
import LoadingState from './components/LoadingState.jsx'
import ReportCard from './components/ReportCard.jsx'
import LoginScreen from './components/LoginScreen.jsx'
import HistoryScreen from './components/HistoryScreen.jsx'
import PriceCheckScreen from './components/PriceCheckScreen.jsx'
import { SAMPLE_REPORT } from './sampleData.js'
import { AuthProvider, useAuth } from './AuthContext.jsx'
import { saveReportToHistory } from './history.js'

const API_BASE = '/api'
const POLL_INTERVAL_MS = 5000
const POLL_MAX_ATTEMPTS = 60

function AppInner() {
  const [screen, setScreen] = useState('input') // 'input' | 'loading' | 'report' | 'error' | 'login' | 'history' | 'pricecheck'
  const [report, setReport] = useState(null)
  const [errorMsg, setErrorMsg] = useState('')
  const { user, logout } = useAuth()

  async function handleSubmit(url) {
    setScreen('loading')
    try {
      // Step 1: Submit URL to backend
      const submitRes = await fetch(`${API_BASE}/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ listing_url: url })
      })
      if (!submitRes.ok) throw new Error('Failed to submit listing URL.')
      const { request_id } = await submitRes.json()

      // Step 2: Poll for completion
      for (let i = 0; i < POLL_MAX_ATTEMPTS; i++) {
        await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS))
        const pollRes = await fetch(`${API_BASE}/report/${request_id}`)
        if (!pollRes.ok) continue
        const data = await pollRes.json()
        if (data.status === 'complete') {
          setReport(data)
          setScreen('report')
          if (user?.id) saveReportToHistory(user.id, data) // fire-and-forget
          return
        }
        if (data.status === 'error') {
          throw new Error(data.error || 'Verification failed.')
        }
      }
      throw new Error('Verification is taking longer than expected — the call may still be running. Please check back in a moment or try again.')
    } catch (err) {
      setErrorMsg(err.message)
      setScreen('error')
    }
  }

  async function handleVinLookup(vin) {
    setScreen('loading')
    try {
      const res = await fetch(`http://localhost:8001/api/vin-score/${vin.trim().toUpperCase()}`)
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `VIN lookup returned ${res.status}`)
      }
      const { vin_report: vinData, trust_score } = await res.json()

      const report = {
        listing: {
          make: vinData.sources?.vehicle_databases?.basic?.make || vinData.sources?.nhtsa?.Make || 'Unknown',
          model: vinData.sources?.vehicle_databases?.basic?.model || vinData.sources?.nhtsa?.Model || 'Unknown',
          year: vinData.sources?.vehicle_databases?.basic?.year || vinData.sources?.nhtsa?.ModelYear || '',
          asking_price_aed: null,
          mileage_km: null,
          emirate: 'UAE',
          seller_name: null,
          listing_url: null,
          photos: [],
        },
        trust_score,
        vin_report: vinData,
        red_flags: trust_score.red_flags || [],
        price_analysis: null,
        voice_call: null,
      }

      setReport(report)
      setScreen('report')
    } catch (err) {
      setErrorMsg(err.message)
      setScreen('error')
    }
  }

  function handleDemo() {
    setReport(SAMPLE_REPORT)
    setScreen('report')
    // Demo reports are intentionally not saved to history — they're not
    // a real verification result.
  }

  function handleReset() {
    setReport(null)
    setErrorMsg('')
    setScreen('input')
  }

  function openSavedReport(savedReport) {
    setReport(savedReport)
    setScreen('report')
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {screen === 'input' && (
        <URLInput
          onSubmit={handleSubmit}
          onDemo={handleDemo}
          onPriceCheckClick={() => setScreen('pricecheck')}
          user={user}
          onLoginClick={() => setScreen('login')}
          onHistoryClick={() => setScreen('history')}
          onLogout={logout}
        />
      )}
      {screen === 'pricecheck' && (
        <PriceCheckScreen onBack={() => setScreen('input')} />
      )}
      {screen === 'loading' && <LoadingState />}
      {screen === 'report' && report && (
        <ReportCard report={report} onReset={handleReset} />
      )}
      {screen === 'login' && (
        <LoginScreen onSuccess={() => setScreen('input')} onBack={() => setScreen('input')} />
      )}
      {screen === 'history' && (
        <HistoryScreen onBack={() => setScreen('input')} onOpenReport={openSavedReport} />
      )}
      {screen === 'error' && (
        <div className="min-h-screen flex items-center justify-center px-4">
          <div className="text-center max-w-md">
            <div className="text-5xl mb-4">⚠️</div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">Something went wrong</h2>
            <p className="text-gray-500 mb-6">{errorMsg}</p>
            <button
              onClick={handleReset}
              className="px-6 py-3 bg-brand-600 text-white rounded-xl font-semibold hover:bg-brand-700 transition"
            >
              Try Again
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AppInner />
    </AuthProvider>
  )
}
