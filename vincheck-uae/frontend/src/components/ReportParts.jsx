import { Icon } from './Icon';

const VERDICT_COPY = {
  good: { icon: 'check', text: 'No damage events recorded — clean global history.', pill: 'pill-good' },
  warn: { icon: 'alert', text: 'Review recommended — minor issues on record.', pill: 'pill-warn' },
  bad:  { icon: 'alert', text: 'High risk — major damage on record.', pill: 'pill-bad' },
};

export function VerdictBanner({ verdict }) {
  const v = VERDICT_COPY[verdict] || VERDICT_COPY.warn;
  return (
    <div
      className={`pill ${v.pill}`}
      style={{
        width: '100%',
        padding: '12px 16px',
        fontSize: 13,
        fontWeight: 500,
        textTransform: 'none',
        letterSpacing: 0,
        display: 'flex',
        alignItems: 'center',
        gap: 10,
      }}
    >
      <Icon name={v.icon} size={16} />
      {v.text}
    </div>
  );
}

export function StatCard({ label, value, color }) {
  return (
    <div style={{ border: '0.5px solid var(--border)', borderRadius: 'var(--radius-md)', padding: 12 }}>
      <p style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 4 }}>{label}</p>
      <p style={{ fontSize: 18, fontWeight: 600, color: color || 'var(--text)' }}>{value}</p>
    </div>
  );
}

export function DamageTable({ events }) {
  if (!events || events.length === 0) {
    return <p style={{ fontSize: 13, color: 'var(--green)', fontWeight: 500 }}>No damage events recorded.</p>;
  }
  return (
    <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
      <thead>
        <tr style={{ borderBottom: '0.5px solid var(--border)' }}>
          {['Date', 'Event', 'Country'].map((h) => (
            <th key={h} style={{ textAlign: 'left', padding: '0 0 10px', color: 'var(--muted)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '.05em' }}>
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {events.map((ev, i) => (
          <tr key={i} style={{ borderBottom: i < events.length - 1 ? '0.5px solid var(--border)' : 'none' }}>
            <td className="mono" style={{ padding: '10px 0', color: 'var(--muted)', fontSize: 12, whiteSpace: 'nowrap' }}>{ev.date}</td>
            <td style={{ padding: '10px 0' }}>
              {ev.type}{' '}
              <span className={`pill ${ev.severity === 'Major' ? 'pill-bad' : 'pill-warn'}`} style={{ marginLeft: 6 }}>
                {ev.severity}
              </span>
            </td>
            <td style={{ padding: '10px 0', color: 'var(--muted)', fontSize: 12 }}>{ev.country}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function scoreColor(score) {
  if (score >= 80) return 'var(--green)';
  if (score >= 65) return 'var(--yellow)';
  return 'var(--accent)';
}
