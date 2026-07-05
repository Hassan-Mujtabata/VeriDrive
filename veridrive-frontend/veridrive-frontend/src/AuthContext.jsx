import { createContext, useContext, useState, useEffect } from 'react'
import { supabase } from './supabaseClient'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setUser(data.session?.user ?? null)
      setLoading(false)
    })

    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null)
    })

    return () => listener.subscription.unsubscribe()
  }, [])

  // captchaToken comes from the Turnstile widget on the login form.
  // Requires "Enable CAPTCHA protection" turned on in Supabase dashboard
  // (Authentication → Settings → Bot and Abuse Protection), with the
  // matching Turnstile secret key entered there. Without that setting
  // enabled, Supabase just ignores the token — login/signup still work,
  // but the CAPTCHA isn't actually being enforced server-side.
  async function login(email, password, captchaToken) {
    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password,
      options: { captchaToken },
    })
    if (error) throw error
    return data.user
  }

  async function signup(email, password, captchaToken) {
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: { captchaToken },
    })
    if (error) throw error
    return data.user
  }

  // Verifies the 6-digit code Supabase emailed after signup. On success
  // this logs the user in directly — no separate login step needed after
  // verifying, since Supabase returns a real session here.
  async function verifyOtp(email, token) {
    const { data, error } = await supabase.auth.verifyOtp({
      email,
      token,
      type: 'signup',
    })
    if (error) throw error
    return data.user
  }

  // Re-sends the OTP code, e.g. if the user didn't receive it or it expired.
  // Requires its own captchaToken — the original signup's token is single-use
  // and already consumed by that point, so resend needs a fresh one.
  async function resendOtp(email, captchaToken) {
    const { error } = await supabase.auth.resend({
      type: 'signup',
      email,
      options: { captchaToken },
    })
    if (error) throw error
  }

  async function logout() {
    const { error } = await supabase.auth.signOut()
    if (error) throw error
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, signup, verifyOtp, resendOtp, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
