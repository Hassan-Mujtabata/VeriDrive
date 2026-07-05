import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Icon } from '../components/Icon';
import { useAuth } from '../AuthContext';
import { loadHistory } from '../history';

export default function History() {
  const [search, setSearch] = useState('');
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!user?.id) {
      setRecords([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    loadHistory(user.id).then((data) => {
      setRecords(data);
      setLoading(false);
    });
  }, [user?.id]);

  const filtered = records.filter(
    (r) =>
      r.vin.toLowerCase().includes(search.toLowerCase()) ||
      `${r.make} ${r.model}`.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div style={{ minHeight: '100vh' }}>
      <nav
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '14px 32px',
          borderBottom: '0.5px solid var(--border)',
          background: 'var(--surface)',
        }}
      >
        <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Icon name="car" size={18} />
          <span style={{ fontWeight: 600, fontSize: 14 }}>VinCheck UAE</span>
        </Link>
        <div style={{ display: 'flex', gap: 20, fontSize: 13 }}>
          <Link to="/dashboard" style={{ color: 'var(--muted)' }}>Report</Link>
          <Link to="/history" style={{ color: 'var(--info)', fontWeight: 500 }}>History</Link>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 13, color: 'var(--muted)' }}>{user?.email || 'guest'}</span>
          <button className="btn-ghost" onClick={async () => { await logout(); navigate('/'); }}>
            <Icon name="logout" size={15} />
          </button>
        </div>
      </nav>

      <div style={{ maxWidth: 880, margin: '0 auto', padding: '32px 24px' }}>
        <div
          style={{
            background: 'var(--surface)',
            border: '0.5px solid var(--border)',
            borderRadius: 'var(--radius-lg)',
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              padding: '18px 24px',
              borderBottom: '0.5px solid var(--border)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 16,
            }}
          >
            <p style={{ fontSize: 15, fontWeight: 600 }}>Your check history</p>
            <div style={{ position: 'relative', width: 220 }}>
              <Icon name="search" size={14} style={{ position: 'absolute', left: 10, top: 10, color: 'var(--tertiary)' }} />
              <input
                type="text"
                placeholder="Search by VIN or model"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={{ paddingLeft: 32, fontSize: 13 }}
              />
            </div>
          </div>

          {!user?.id ? (
            <p style={{ padding: 32, textAlign: 'center', color: 'var(--tertiary)', fontSize: 13, fontStyle: 'italic' }}>
              Log in to see your check history.
            </p>
          ) : loading ? (
            <p style={{ padding: 32, textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>
              Loading...
            </p>
          ) : filtered.length === 0 ? (
            <p style={{ padding: 32, textAlign: 'center', color: 'var(--tertiary)', fontSize: 13, fontStyle: 'italic' }}>
              {records.length === 0 ? 'No checks yet — run a VIN check to see it here.' : 'No checks match your search.'}
            </p>
          ) : (
            <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '0.5px solid var(--border)' }}>
                  {['Vehicle', 'VIN', 'Checked', 'Trust score', ''].map((h) => (
                    <th
                      key={h}
                      style={{
                        textAlign: h === '' ? 'right' : 'left',
                        padding: h === '' ? '10px 24px' : '10px 0',
                        color: 'var(--muted)',
                        fontWeight: 500,
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((r) => (
                  <tr
                    key={r.id}
                    onClick={() => navigate(`/dashboard/${r.vin}`)}
                    style={{ borderBottom: '0.5px solid var(--border)', cursor: 'pointer' }}
                  >
                    <td style={{ padding: '12px 24px 12px 0' }}>{r.make} {r.model}{r.year ? ` ${r.year}` : ''}</td>
                    <td className="mono" style={{ padding: '12px 0', color: 'var(--muted)' }}>
                      {r.vin.slice(0, 8)}...{r.vin.slice(-5)}
                    </td>
                    <td style={{ padding: '12px 0', color: 'var(--muted)' }}>{relativeTime(r.checked_at)}</td>
                    <td style={{ padding: '12px 0' }}>
                      <span
                        className={`pill ${r.trust_score >= 80 ? 'pill-good' : r.trust_score >= 65 ? 'pill-warn' : 'pill-bad'}`}
                      >
                        {r.trust_score}
                      </span>
                    </td>
                    <td style={{ padding: '12px 24px', textAlign: 'right' }}>
                      <Icon name="chevronRight" size={16} style={{ color: 'var(--tertiary)' }} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

function relativeTime(isoDate) {
  if (!isoDate) return '—';
  const diffMs = Date.now() - new Date(isoDate).getTime();
  const days = Math.floor(diffMs / 86400000);
  if (days <= 0) return 'Today';
  if (days === 1) return 'Yesterday';
  if (days < 7) return `${days} days ago`;
  return `${Math.floor(days / 7)} week${days >= 14 ? 's' : ''} ago`;
}
