import { useState } from 'react'

export default function URLInput({ onSubmit, onDemo, onPriceCheckClick, user, onLoginClick, onHistoryClick, onLogout }) {
  const [url, setUrl] = useState('')
  const [urlError, setUrlError] = useState('')

  function validate(value) {
    if (!value.trim()) return 'Please paste a Dubizzle listing URL.'
    if (!value.includes('dubizzle.com')) return 'URL must be from dubizzle.com.'
    return ''
  }

  function handleSubmit(e) {
    e.preventDefault()
    const err = validate(url)
    if (err) { setUrlError(err); return }
    setUrlError('')
    onSubmit(url.trim())
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* Nav */}
      <nav className="bg-white border-b border-gray-100 px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-brand-600 rounded-lg flex items-center justify-center">
              <svg viewBox="0 0 24 24" fill="white" className="w-5 h-5">
                <path d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
            </div>
            <span className="text-xl font-bold text-gray-900">VeriDrive</span>
          </div>
          <div className="flex items-center gap-4 text-sm">
            {user ? (
              <>
                <button onClick={onHistoryClick} className="text-gray-500 hover:text-brand-600 font-medium">
                  My Reports
                </button>
                <span className="text-gray-300">|</span>
                <span className="text-gray-400">{user.email}</span>
                <button onClick={onLogout} className="text-gray-400 hover:text-gray-600">
                  Log out
                </button>
              </>
            ) : (
              <button onClick={onLoginClick} className="text-brand-600 font-semibold hover:underline">
                Log in
              </button>
            )}
          </div>
        </div>
      </nav>

      {/* Hero */}
      <div className="flex-1 flex items-center justify-center px-4 py-16">
        <div className="w-full max-w-2xl text-center">
          <div className="inline-flex items-center gap-2 bg-brand-50 text-brand-700 px-4 py-1.5 rounded-full text-sm font-medium mb-6 border border-brand-100">
            <span className="w-2 h-2 bg-brand-500 rounded-full animate-pulse"></span>
            AI-Powered Used Car Verification for the UAE
          </div>

          <h1 className="text-4xl sm:text-5xl font-extrabold text-gray-900 mb-4 leading-tight">
            Know the truth before
            <span className="text-brand-600"> you buy.</span>
          </h1>
          <p className="text-lg text-gray-500 mb-10 max-w-xl mx-auto">
            Paste any Dubizzle car listing. VeriDrive calls the seller, checks the VIN, compares the price, and gives you a verified trust score in minutes.
          </p>

          {/* Input form */}
          <form onSubmit={handleSubmit} className="w-full">
            <div className="flex flex-col sm:flex-row gap-3">
              <input
                type="url"
                value={url}
                onChange={(e) => { setUrl(e.target.value); setUrlError('') }}
                placeholder="https://dubai.dubizzle.com/motors/used-cars/..."
                className={`flex-1 px-4 py-4 rounded-xl border text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 transition ${
                  urlError ? 'border-red-400 bg-red-50' : 'border-gray-200 bg-white'
                }`}
              />
              <button
                type="submit"
                className="px-6 py-4 bg-brand-600 text-white rounded-xl font-semibold hover:bg-brand-700 active:scale-95 transition text-sm whitespace-nowrap"
              >
                Verify Listing
              </button>
            </div>
            {urlError && (
              <p className="text-red-500 text-sm mt-2 text-left">{urlError}</p>
            )}
          </form>

          <div className="flex items-center gap-3 my-6">
            <div className="flex-1 h-px bg-gray-200" />
            <span className="text-xs text-gray-400 uppercase tracking-wide">or</span>
            <div className="flex-1 h-px bg-gray-200" />
          </div>

          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <button
              onClick={onDemo}
              className="px-6 py-3 border border-brand-600 text-brand-600 rounded-xl font-semibold hover:bg-brand-50 transition text-sm"
            >
              View Demo Report
            </button>
            <button
              onClick={onPriceCheckClick}
              className="px-6 py-3 border border-gray-300 text-gray-700 rounded-xl font-semibold hover:bg-gray-50 transition text-sm flex items-center justify-center gap-1.5"
            >
              💰 Check market price
            </button>
          </div>

          {/* Trust badges */}
          <div className="mt-12 grid grid-cols-2 sm:grid-cols-4 gap-4 text-center">
            {[
              { icon: '📞', label: 'AI Calls Seller' },
              { icon: '🔍', label: 'VIN Cross-Check' },
              { icon: '💰', label: 'Market Price Analysis' },
              { icon: '📋', label: 'Trust Score Report' }
            ].map((item) => (
              <div key={item.label} className="bg-white rounded-xl p-4 border border-gray-100 shadow-sm">
                <div className="text-2xl mb-1">{item.icon}</div>
                <div className="text-xs font-medium text-gray-600">{item.label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="text-center py-4 text-xs text-gray-400 border-t border-gray-100">
        VeriDrive — BCS 410-1 Graduation Project · Supervisor: Dr. Yasir Faheem
      </footer>
    </div>
  )
}
