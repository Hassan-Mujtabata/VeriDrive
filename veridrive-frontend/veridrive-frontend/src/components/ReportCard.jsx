import { useState } from 'react'
import TrustScoreGauge from './TrustScoreGauge.jsx'
import SubScores from './SubScores.jsx'
import RedFlags from './RedFlags.jsx'
import PriceAnalysis from './PriceAnalysis.jsx'
import VehicleHeader from './VehicleHeader.jsx'
import VoiceCall from './VoiceCall.jsx'
import VINReport from './VINReport.jsx'
import Recommendation from './Recommendation.jsx'
import { exportFullReportToPdf } from '../exportFullReportPdf.js'

const SECTIONS = [
  { key: 'overview', label: 'Overview', icon: 'layout' },
  { key: 'redflags', label: 'Red flags', icon: 'alert' },
  { key: 'price', label: 'Price analysis', icon: 'tag' },
  { key: 'voice', label: 'Seller verification', icon: 'phone' },
  { key: 'vin', label: 'Vehicle history', icon: 'shield' },
]

function Icon({ name, className = 'w-4 h-4' }) {
  const paths = {
    layout: 'M3 3h18v18H3V3zm0 6h18M9 9v12',
    alert: 'M12 9v4m0 4h.01M10.29 3.86l-8.18 14.18A1 1 0 003 19.5h18a1 1 0 00.89-1.46L13.71 3.86a1 1 0 00-1.42 0z',
    tag: 'M20.59 13.41L11 3.83A2 2 0 009.59 3H4a1 1 0 00-1 1v5.59a2 2 0 00.59 1.41l9.58 9.58a2 2 0 002.82 0l4.6-4.6a2 2 0 000-2.82zM7 7h.01',
    phone: 'M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72c.127.96.361 1.903.7 2.81a2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0122 16.92z',
    shield: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z',
    download: 'M12 3v12m0 0l-4-4m4 4l4-4M5 21h14',
  }
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={paths[name]} />
    </svg>
  )
}

export default function ReportCard({ report, onReset }) {
  const [active, setActive] = useState('overview')

  // Guard against null/undefined report or missing fields — a saved report
  // loaded from history may have been saved under an older schema version
  // with different or missing keys. Rather than crashing, show a recovery screen.
  if (!report) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="text-center max-w-md">
          <p className="text-gray-400 text-sm mb-4">This report could not be loaded — the data may be incomplete.</p>
          <button onClick={onReset} className="px-6 py-3 bg-brand-600 text-white rounded-xl font-semibold hover:bg-brand-700 transition text-sm">
            ← Back to home
          </button>
        </div>
      </div>
    )
  }

  const {
    listing = {},
    trust_score = {},
    price_analysis,
    vin_report,
    red_flags,
    voice_call,
  } = report

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Top nav */}
      <nav className="bg-white border-b border-gray-100 px-6 py-4">
        <div className="flex items-center justify-between">
          <button onClick={onReset} className="flex items-center gap-3">
            <div className="w-8 h-8 bg-brand-600 rounded-lg flex items-center justify-center">
              <svg viewBox="0 0 24 24" fill="white" className="w-5 h-5">
                <path d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
            </div>
            <span className="text-lg font-bold text-gray-900">VeriDrive</span>
          </button>
          <div className="flex items-center gap-4">
            <button
              onClick={() => exportFullReportToPdf(report)}
              className="text-sm text-gray-500 font-semibold hover:text-brand-600 flex items-center gap-1.5"
            >
              <Icon name="download" />
              Export PDF
            </button>
            <button
              onClick={onReset}
              className="text-sm text-brand-600 font-semibold hover:underline"
            >
              ← Verify Another
            </button>
          </div>
        </div>
      </nav>

      <div className="flex">
        {/* Sidebar */}
        <aside className="w-60 min-h-[calc(100vh-65px)] bg-white border-r border-gray-100 px-4 py-6 flex-shrink-0">
          <div className="mb-6 px-2">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">Vehicle</p>
            <p className="text-sm font-bold text-gray-900 truncate">
              {listing?.year} {listing?.make} {listing?.model || 'Unknown vehicle'}
            </p>
          </div>

          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2 px-2">Report sections</p>
          <nav className="space-y-1">
            {SECTIONS.map((s) => (
              <button
                key={s.key}
                onClick={() => setActive(s.key)}
                className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm font-medium transition text-left ${
                  active === s.key
                    ? 'bg-brand-50 text-brand-700'
                    : 'text-gray-500 hover:bg-gray-50 hover:text-gray-700'
                }`}
              >
                <Icon name={s.icon} />
                {s.label}
              </button>
            ))}
          </nav>

          <div className="mt-8 px-2">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Composite score</p>
            <div className="flex items-center gap-2">
              <span className="text-2xl font-bold text-gray-900">{trust_score?.composite_score ?? '—'}</span>
              <span className="text-xs text-gray-400">/ 100</span>
            </div>
          </div>
        </aside>

        {/* Main content */}
        <main className="flex-1 px-6 py-8 max-w-3xl">
          {active === 'overview' && (
            <div className="space-y-6">
              <VehicleHeader listing={listing} />
              <div className="bg-white rounded-2xl border border-gray-100 p-6 shadow-sm">
                <h3 className="text-base font-bold text-gray-800 mb-4 text-center">Composite Trust Score</h3>
                <div className="flex justify-center mb-5">
                  <TrustScoreGauge score={trust_score.composite_score} />
                </div>
                <Recommendation
                  score={trust_score.composite_score}
                  recommendation={trust_score.recommendation}
                />
              </div>
              <div className="bg-white rounded-2xl border border-gray-100 p-6 shadow-sm">
                <SubScores
                  trustScore={trust_score}
                  vinAvailable={vin_report?.available || false}
                />
              </div>
            </div>
          )}

          {active === 'redflags' && (
            <div className="bg-white rounded-2xl border border-gray-100 p-6 shadow-sm">
              <RedFlags flags={red_flags} />
            </div>
          )}

          {active === 'price' && (
            <div className="bg-white rounded-2xl border border-gray-100 p-6 shadow-sm">
              {price_analysis ? (
                <PriceAnalysis
                  priceAnalysis={price_analysis}
                  askingPrice={listing.asking_price_aed}
                />
              ) : (
                <div className="text-center py-8">
                  <p className="text-gray-400 text-sm">Price analysis not available for this report.</p>
                  <p className="text-gray-300 text-xs mt-1">Run a full listing verification to see market comparison.</p>
                </div>
              )}
            </div>
          )}

          {active === 'voice' && (
            <div className="bg-white rounded-2xl border border-gray-100 p-6 shadow-sm">
              {voice_call ? (
                <VoiceCall voiceCall={voice_call} />
              ) : (
                <div className="text-center py-8">
                  <p className="text-gray-400 text-sm">Seller verification not available for this report.</p>
                  <p className="text-gray-300 text-xs mt-1">Run a full listing verification to see the AI call summary.</p>
                </div>
              )}
            </div>
          )}

          {active === 'vin' && (
            <div className="bg-white rounded-2xl border border-gray-100 p-6 shadow-sm">
              <VINReport vinReport={vin_report} />
            </div>
          )}

          <p className="text-center text-xs text-gray-400 pt-8">
            VeriDrive · BCS 410-1 Graduation Project · Supervisor: Dr. Yasir Faheem
          </p>
        </main>
      </div>
    </div>
  )
}
