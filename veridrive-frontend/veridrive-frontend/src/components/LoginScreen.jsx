import { useState, useRef } from 'react'
import { Turnstile } from '@marsidev/react-turnstile'
import { useAuth } from '../AuthContext'

// ---------------------------------------------------------------------------
// Get a free site key at https://dash.cloudflare.com/?to=/:account/turnstile
// Set it in .env as VITE_TURNSTILE_SITE_KEY. The matching SECRET key goes
// into Supabase dashboard → Authentication → Settings → Bot and Abuse
// Protection → enable CAPTCHA, select Turnstile, paste the secret key there.
// Without both halves configured, the widget still renders (using
// Cloudflare's public test key as a fallback below) but won't actually be
// enforced server-side.
// ---------------------------------------------------------------------------
const TURNSTILE_SITE_KEY =
  import.meta.env.VITE_TURNSTILE_SITE_KEY || '1x00000000000000000000AA' // Cloudflare's "always passes" test key

export default function LoginScreen({ onSuccess, onBack }) {
  const [mode, setMode] = useState('login') // 'login' | 'signup'
  const [step, setStep] = useState('form') // 'form' | 'otp'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [otpCode, setOtpCode] = useState('')
  const [captchaToken, setCaptchaToken] = useState(null)
  const [otpCaptchaToken, setOtpCaptchaToken] = useState(null)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [resendCooldown, setResendCooldown] = useState(0)
  const [showResendCaptcha, setShowResendCaptcha] = useState(false)
  const turnstileRef = useRef(null)
  const otpTurnstileRef = useRef(null)
  const { login, signup, verifyOtp, resendOtp } = useAuth()

  function resetCaptcha() {
    // The Turnstile widget now remounts automatically on mode switch via its
    // key={mode} prop, which clears any stale challenge state. This function
    // still clears our own captchaToken state, and still calls .reset() for
    // the case where the SAME form (e.g. after a failed submit) needs a
    // fresh challenge without switching modes.
    turnstileRef.current?.reset()
    setCaptchaToken(null)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')

    if (!captchaToken) {
      setError('Please complete the verification check below.')
      return
    }

    setSubmitting(true)
    try {
      if (mode === 'login') {
        await login(email, password, captchaToken)
        onSuccess()
      } else {
        await signup(email, password, captchaToken)
        // Supabase emails a 6-digit code (configured for OTP rather than a
        // magic link — see README for the dashboard setting). Move to the
        // code-entry step rather than logging in yet.
        setStep('otp')
      }
    } catch (err) {
      setError(err.message || 'Something went wrong. Please try again.')
      resetCaptcha()
    } finally {
      setSubmitting(false)
    }
  }

  async function handleVerifyOtp(e) {
    e.preventDefault()
    setError('')
    if (otpCode.trim().length !== 6) {
      setError('Enter the 6-digit code from your email.')
      return
    }
    setSubmitting(true)
    try {
      await verifyOtp(email, otpCode.trim())
      onSuccess() // verifyOtp returns a real session — user is logged in now
    } catch (err) {
      setError(err.message || 'Invalid or expired code. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleResend() {
    if (resendCooldown > 0) return
    setError('')
    if (!otpCaptchaToken) {
      setError('Please complete the verification check below before resending.')
      return
    }
    try {
      await resendOtp(email, otpCaptchaToken)
      setResendCooldown(30)
      const interval = setInterval(() => {
        setResendCooldown((s) => {
          if (s <= 1) { clearInterval(interval); return 0 }
          return s - 1
        })
      }, 1000)
    } catch (err) {
      setError(err.message || 'Could not resend the code.')
    } finally {
      // Tokens are single-use — always reset after an attempt, success or not.
      otpTurnstileRef.current?.reset()
      setOtpCaptchaToken(null)
      setShowResendCaptcha(false)
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

      <div className="flex-1 flex items-center justify-center px-4 py-16">
        <div className="w-full max-w-sm">
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-7">

            {step === 'form' && (
              <>
                <div className="flex gap-1 mb-6 border-b border-gray-100">
                  <button
                    type="button"
                    onClick={() => { setMode('login'); setError(''); resetCaptcha() }}
                    className={`pb-3 px-1 mr-5 text-sm font-semibold border-b-2 transition ${
                      mode === 'login' ? 'border-brand-600 text-brand-600' : 'border-transparent text-gray-400'
                    }`}
                  >
                    Log in
                  </button>
                  <button
                    type="button"
                    onClick={() => { setMode('signup'); setError(''); resetCaptcha() }}
                    className={`pb-3 px-1 text-sm font-semibold border-b-2 transition ${
                      mode === 'signup' ? 'border-brand-600 text-brand-600' : 'border-transparent text-gray-400'
                    }`}
                  >
                    Sign up
                  </button>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4">
                  <div>
                    <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide block mb-1.5">Email</label>
                    <input
                      type="email"
                      required
                      placeholder="you@example.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="w-full px-4 py-3 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide block mb-1.5">Password</label>
                    <input
                      type="password"
                      required
                      minLength={6}
                      placeholder="••••••••"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="w-full px-4 py-3 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                    />
                  </div>

                  <div className="flex justify-center">
                    <Turnstile
                      key={mode}
                      ref={turnstileRef}
                      siteKey={TURNSTILE_SITE_KEY}
                      onSuccess={setCaptchaToken}
                      onExpire={() => setCaptchaToken(null)}
                      options={{ theme: 'light', size: 'normal' }}
                    />
                  </div>

                  {error && (
                    <p className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
                      {error}
                    </p>
                  )}

                  <button
                    type="submit"
                    disabled={submitting}
                    className="w-full py-3 bg-brand-600 text-white rounded-xl font-semibold hover:bg-brand-700 active:scale-95 transition text-sm disabled:opacity-50"
                  >
                    {submitting ? 'Please wait...' : mode === 'login' ? 'Log in' : 'Create account'}
                  </button>
                </form>
              </>
            )}

            {step === 'otp' && (
              <form onSubmit={handleVerifyOtp} className="space-y-4">
                <div className="text-center mb-2">
                  <div className="text-3xl mb-2">📧</div>
                  <p className="font-semibold text-gray-800 mb-1">Check your email</p>
                  <p className="text-sm text-gray-500">
                    We sent a 6-digit code to {email}. Enter it below to verify your account.
                  </p>
                </div>

                <div>
                  <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide block mb-1.5">Verification code</label>
                  <input
                    type="text"
                    inputMode="numeric"
                    maxLength={6}
                    required
                    placeholder="123456"
                    value={otpCode}
                    onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ''))}
                    className="w-full px-4 py-3 rounded-xl border border-gray-200 text-center text-lg tracking-[0.3em] font-mono focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                </div>

                {error && (
                  <p className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
                    {error}
                  </p>
                )}

                <button
                  type="submit"
                  disabled={submitting}
                  className="w-full py-3 bg-brand-600 text-white rounded-xl font-semibold hover:bg-brand-700 active:scale-95 transition text-sm disabled:opacity-50"
                >
                  {submitting ? 'Verifying...' : 'Verify & continue'}
                </button>

                {!showResendCaptcha ? (
                  <button
                    type="button"
                    onClick={() => setShowResendCaptcha(true)}
                    disabled={resendCooldown > 0}
                    className="w-full text-xs text-gray-400 hover:text-brand-600 disabled:opacity-50"
                  >
                    {resendCooldown > 0 ? `Resend code in ${resendCooldown}s` : "Didn't get a code? Resend"}
                  </button>
                ) : (
                  <div className="space-y-3">
                    <p className="text-xs text-gray-400 text-center">Complete the check below, then tap resend.</p>
                    <div className="flex justify-center">
                      <Turnstile
                        key="otp-resend"
                        ref={otpTurnstileRef}
                        siteKey={TURNSTILE_SITE_KEY}
                        onSuccess={setOtpCaptchaToken}
                        onExpire={() => setOtpCaptchaToken(null)}
                        options={{ theme: 'light', size: 'normal' }}
                      />
                    </div>
                    <button
                      type="button"
                      onClick={handleResend}
                      disabled={resendCooldown > 0 || !otpCaptchaToken}
                      className="w-full text-xs text-brand-600 font-semibold hover:underline disabled:opacity-50 disabled:no-underline"
                    >
                      {resendCooldown > 0 ? `Resend code in ${resendCooldown}s` : 'Resend code'}
                    </button>
                  </div>
                )}

                <button
                  type="button"
                  onClick={() => { setStep('form'); setOtpCode(''); setError(''); setShowResendCaptcha(false); setOtpCaptchaToken(null) }}
                  className="w-full text-xs text-gray-400 hover:text-gray-600"
                >
                  ← Use a different email
                </button>
              </form>
            )}
          </div>
        </div>
      </div>

      <footer className="text-center py-4 text-xs text-gray-400 border-t border-gray-100">
        VeriDrive — BCS 410-1 Graduation Project · Supervisor: Dr. Yasir Faheem
      </footer>
    </div>
  )
}
