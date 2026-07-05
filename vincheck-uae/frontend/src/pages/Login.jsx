import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Icon } from '../components/Icon';
import { useAuth } from '../AuthContext';

export default function Login() {
  const [mode, setMode] = useState('login'); // 'login' | 'signup'
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [signupSuccess, setSignupSuccess] = useState(false);
  const { login, signup } = useAuth();
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      if (mode === 'login') {
        await login(email, password);
        navigate('/dashboard');
      } else {
        await signup(email, password);
        // Supabase sends a confirmation email by default — the user isn't
        // logged in yet at this point, so don't navigate away.
        setSignupSuccess(true);
      }
    } catch (err) {
      setError(err.message || 'Something went wrong. Please try again.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
      }}
    >
      <div style={{ width: '100%', maxWidth: 380 }}>
        <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'center', marginBottom: 32 }}>
          <Icon name="car" size={20} />
          <span style={{ fontWeight: 600, fontSize: 15 }}>VinCheck UAE</span>
        </Link>

        <div
          style={{
            background: 'var(--surface)',
            border: '0.5px solid var(--border)',
            borderRadius: 'var(--radius-lg)',
            padding: '28px 28px 24px',
          }}
        >
          <div style={{ display: 'flex', gap: 4, marginBottom: 22, borderBottom: '0.5px solid var(--border)' }}>
            <TabButton active={mode === 'login'} onClick={() => { setMode('login'); setError(''); setSignupSuccess(false); }}>Log in</TabButton>
            <TabButton active={mode === 'signup'} onClick={() => { setMode('signup'); setError(''); setSignupSuccess(false); }}>Sign up</TabButton>
          </div>

          {signupSuccess ? (
            <div style={{ textAlign: 'center', padding: '12px 0' }}>
              <Icon name="check" size={28} style={{ color: 'var(--green)', marginBottom: 10 }} />
              <p style={{ fontSize: 14, fontWeight: 500, marginBottom: 6 }}>Check your email</p>
              <p style={{ fontSize: 13, color: 'var(--muted)' }}>
                We sent a confirmation link to {email}. Confirm it, then log in.
              </p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <Field label="Email">
                <input
                  type="email"
                  required
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </Field>
              <Field label="Password">
                <input
                  type="password"
                  required
                  minLength={6}
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </Field>

              {mode === 'login' && (
                <div style={{ textAlign: 'right', fontSize: 12, color: 'var(--muted)' }}>
                  Forgot password?
                </div>
              )}

              {error && (
                <p style={{ fontSize: 12, color: 'var(--accent)', background: 'var(--accent-bg)', padding: '8px 10px', borderRadius: 'var(--radius-sm)' }}>
                  {error}
                </p>
              )}

              <button type="submit" className="btn-primary" style={{ padding: 12, marginTop: 6 }} disabled={submitting}>
                {submitting ? 'Please wait...' : mode === 'login' ? 'Log in' : 'Create account'}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}

function TabButton({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      type="button"
      style={{
        background: 'transparent',
        padding: '8px 4px 10px',
        marginRight: 18,
        fontSize: 13,
        fontWeight: 500,
        color: active ? 'var(--text)' : 'var(--muted)',
        borderBottom: active ? '2px solid var(--text)' : '2px solid transparent',
        borderRadius: 0,
      }}
    >
      {children}
    </button>
  );
}

function Field({ label, children }) {
  return (
    <label style={{ display: 'block' }}>
      <span className="eyebrow" style={{ display: 'block', marginBottom: 6 }}>{label}</span>
      {children}
    </label>
  );
}
