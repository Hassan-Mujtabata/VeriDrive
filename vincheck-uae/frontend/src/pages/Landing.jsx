import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Icon } from '../components/Icon';
import { checkVehicle } from '../api';

export default function Landing() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  function extractVin(input) {
    const trimmed = input.trim().toUpperCase();
    // If it looks like a bare VIN already, use it directly.
    if (/^[A-HJ-NPR-Z0-9]{17}$/.test(trimmed)) return trimmed;
    // Otherwise this is presumably a listing URL — VIN extraction from a
    // scraped listing isn't wired up yet, so ask for a VIN directly for now.
    return null;
  }

  async function handleCheck(e) {
    e.preventDefault();
    setError('');
    const vin = extractVin(query);
    if (!vin) {
      setError('Enter a 17-character VIN for now — listing URL scraping isn\u2019t wired up yet.');
      return;
    }
    setLoading(true);
    try {
      await checkVehicle(vin); // validates the VIN actually resolves before navigating
      navigate(`/dashboard/${vin}`);
    } catch (err) {
      setError(err.message || 'Could not reach the backend. Is it running?');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ minHeight: '100vh' }}>
      <nav
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '18px 32px',
          borderBottom: '0.5px solid var(--border)',
          background: 'var(--surface)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Icon name="car" size={20} />
          <span style={{ fontWeight: 600, fontSize: 15 }}>VinCheck UAE</span>
        </div>
        <div style={{ display: 'flex', gap: 24, fontSize: 13, color: 'var(--muted)' }}>
          <span>Browse listings</span>
          <span>How it works</span>
          <span>Pricing</span>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Link to="/login"><button className="btn-secondary">Log in</button></Link>
          <Link to="/login"><button className="btn-primary">Sign up</button></Link>
        </div>
      </nav>

      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          maxWidth: 1080,
          margin: '0 auto',
          padding: '64px 32px',
          gap: 48,
          alignItems: 'center',
        }}
      >
        <div style={{ flex: '1 1 380px' }}>
          <p className="eyebrow" style={{ color: 'var(--info)', marginBottom: 10 }}>
            UAE used car buyers
          </p>
          <h1 style={{ fontSize: 32, fontWeight: 600, lineHeight: 1.25, marginBottom: 14 }}>
            Stop guessing. <br />Start checking.
          </h1>
          <p style={{ color: 'var(--muted)', fontSize: 15, marginBottom: 24, maxWidth: 420 }}>
            Every used car listing hides something. We surface it before you call the seller.
          </p>

          <form onSubmit={handleCheck} style={{ display: 'flex', flexDirection: 'column', gap: 8, maxWidth: 380 }}>
            <input
              type="text"
              placeholder="Enter a 17-character VIN"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <button type="submit" className="btn-primary" style={{ padding: '12px' }} disabled={loading}>
              {loading ? 'Checking...' : 'Check this listing'}
            </button>
            {error && <p style={{ fontSize: 12, color: 'var(--accent)' }}>{error}</p>}
          </form>

          <div style={{ display: 'flex', gap: 28, marginTop: 28 }}>
            <Stat value="12,400+" label="Listings checked" />
            <Stat value="31%" label="Flagged for issues" />
            <Stat value="4.8★" label="Buyer rating" />
          </div>
        </div>

        <div style={{ flex: '1 1 320px', display: 'flex', justifyContent: 'center' }}>
          <PreviewCard />
        </div>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: 1,
          background: 'var(--border)',
          borderTop: '0.5px solid var(--border)',
          borderBottom: '0.5px solid var(--border)',
        }}
      >
        <Feature icon="world" color="var(--info)" title="Global history" desc="Damage, theft, and title records from international sources" />
        <Feature icon="pin" color="var(--green)" title="Local registry" desc="UAE registration status and local accident records" />
        <Feature icon="message" color="var(--yellow)" title="Seller comparison" desc="Listing price checked against similar offers nearby" />
      </div>

      <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--tertiary)', fontSize: 12 }}>
        Want to see it without a real VIN?{' '}
        <Link to="/dashboard/WVWZZZ3CZFE123456" style={{ textDecoration: 'underline' }}>View demo report</Link>
      </div>
    </div>
  );
}

function Stat({ value, label }) {
  return (
    <div>
      <p style={{ fontSize: 18, fontWeight: 600 }}>{value}</p>
      <p style={{ fontSize: 11, color: 'var(--tertiary)' }}>{label}</p>
    </div>
  );
}

function Feature({ icon, color, title, desc }) {
  return (
    <div style={{ background: 'var(--surface)', padding: '24px 28px' }}>
      <Icon name={icon} size={22} className="" />
      <p style={{ fontSize: 14, fontWeight: 600, margin: '12px 0 4px' }}>{title}</p>
      <p style={{ fontSize: 13, color: 'var(--muted)' }}>{desc}</p>
    </div>
  );
}

function PreviewCard() {
  return (
    <div
      style={{
        background: 'var(--surface)',
        border: '0.5px solid var(--border)',
        borderRadius: 'var(--radius-lg)',
        padding: '20px 22px',
        width: 270,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <span style={{ fontSize: 12, color: 'var(--muted)' }}>Trust score</span>
        <span style={{ fontSize: 24, fontWeight: 600, color: 'var(--green)' }}>91</span>
      </div>
      <div style={{ height: 6, background: 'var(--bg)', borderRadius: 3, overflow: 'hidden', marginBottom: 18 }}>
        <div style={{ width: '91%', height: '100%', background: 'var(--green)' }} />
      </div>
      {[
        ['Damage history', 'Clean', 'var(--green)'],
        ['Registration', 'Active', 'var(--green)'],
        ['Price vs market', '-3%', 'var(--text)'],
      ].map(([label, value, color]) => (
        <div
          key={label}
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            fontSize: 12,
            padding: '7px 0',
            borderTop: '0.5px solid var(--border)',
          }}
        >
          <span style={{ color: 'var(--muted)' }}>{label}</span>
          <span style={{ color }}>{value}</span>
        </div>
      ))}
    </div>
  );
}
