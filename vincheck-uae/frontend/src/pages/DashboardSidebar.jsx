import { useState, useEffect } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Icon } from '../components/Icon';
import { StatCard, scoreColor } from '../components/ReportParts';
import { REPORT_TABS } from '../mockData';
import { useAuth } from '../AuthContext';
import { checkVehicle, normalizeReport } from '../api';
import { saveCheckToHistory } from '../history';
import { exportReportToPdf } from '../exportPdf';

const FALLBACK_VIN = 'WVWZZZ3CZFE123456'; // only used the very first time, before any VIN has been checked
const LAST_VIN_KEY = 'vincheck_last_vin';

export default function DashboardSidebar() {
  const { vin: vinParam } = useParams();
  const vin = vinParam || sessionStorage.getItem(LAST_VIN_KEY) || FALLBACK_VIN;

  const [activeTab, setActiveTab] = useState('overview');
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const { user, logout } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError('');

    checkVehicle(vin)
      .then((data) => {
        if (cancelled) return;
        const normalized = normalizeReport(data);
        setReport(normalized);
        sessionStorage.setItem(LAST_VIN_KEY, vin);
        // Fire-and-forget save — don't block rendering the report on this,
        // and a failed save (e.g. not logged in) shouldn't show as an error.
        if (user?.id) saveCheckToHistory(user.id, normalized);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || 'Could not load this report.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [vin, user?.id]);

  return (
    <div style={{ minHeight: '100vh', display: 'flex' }}>
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} user={user} onLogout={async () => { await logout(); navigate('/'); }} />

      <div style={{ flex: 1, minWidth: 0, padding: '24px 32px' }}>
        {loading && <LoadingState vin={vin} />}
        {!loading && error && <ErrorState error={error} />}
        {!loading && !error && report && (
          <>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 20 }}>
              <div>
                <p className="mono" style={{ fontSize: 15, fontWeight: 500 }}>{report.vin}</p>
                <p style={{ fontSize: 13, color: 'var(--muted)', marginTop: 2 }}>
                  {report.make} {report.model}{report.year !== '—' ? ` · ${report.year}` : ''}
                  {report.trim ? ` · ${report.trim}` : ''}
                </p>
              </div>
              <button className="btn-secondary" onClick={() => exportReportToPdf(report)}>
                <Icon name="download" size={14} style={{ marginRight: 6, verticalAlign: -2 }} />
                Export PDF
              </button>
            </div>

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 16,
                background: 'var(--surface)',
                border: '0.5px solid var(--border)',
                borderRadius: 'var(--radius-md)',
                padding: '16px 20px',
                marginBottom: 20,
              }}
            >
              <ScoreRing score={report.trustScore} />
              <div>
                <p style={{ fontSize: 13, fontWeight: 600, marginBottom: 2, color: scoreColor(report.trustScore) }}>
                  {report.verdict === 'good' ? 'Looks clean' : report.verdict === 'bad' ? 'High risk' : 'Review recommended'}
                </p>
                <p style={{ fontSize: 12, color: 'var(--muted)' }}>
                  {report.titleCheckAvailable
                    ? (report.isSalvage
                        ? `Salvage title — ${report.salvageDetails[0]?.cause || 'cause unspecified'}`
                        : 'Clean title on record')
                    : `Title check unavailable — ${report.titleCheckError || 'unknown reason'}`}
                </p>
              </div>
            </div>

            <TabContent tab={activeTab} report={report} />
          </>
        )}
      </div>
    </div>
  );
}

function LoadingState({ vin }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--muted)', fontSize: 13, padding: '40px 0' }}>
      <span
        style={{
          width: 14, height: 14, borderRadius: '50%',
          border: '2px solid var(--border)', borderTopColor: 'var(--text)',
          display: 'inline-block', animation: 'spin .7s linear infinite',
        }}
      />
      Checking {vin}...
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

function ErrorState({ error }) {
  return (
    <div
      style={{
        display: 'flex', alignItems: 'center', gap: 10,
        background: 'var(--accent-bg)', color: 'var(--accent)',
        padding: '14px 18px', borderRadius: 'var(--radius-md)', fontSize: 13,
      }}
    >
      <Icon name="alert" size={16} />
      {error}
      <span style={{ color: 'var(--muted)', marginLeft: 6 }}>— is the backend running on localhost:8000?</span>
    </div>
  );
}

function TabContent({ tab, report }) {
  if (tab === 'overview') {
    return (
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 10 }}>
        <StatCard
          label="Title status"
          value={report.titleCheckAvailable ? (report.isSalvage ? 'Salvage' : 'Clean') : '—'}
          color={report.titleCheckAvailable ? (report.isSalvage ? 'var(--accent)' : 'var(--green)') : undefined}
        />
        <StatCard label="Registration" value={report.registrationStatus} />
        <StatCard label="Decode source" value={report.vehicleDatabasesDecode ? 'Vehicle Databases' : report.nhtsaDecode ? 'NHTSA' : '—'} />
      </div>
    );
  }
  if (tab === 'global') {
    return (
      <div style={{ background: 'var(--surface)', border: '0.5px solid var(--border)', borderRadius: 'var(--radius-md)', padding: 20 }}>
        {report.isSalvage && (
          <div
            style={{
              display: 'flex', alignItems: 'center', gap: 10,
              background: 'var(--accent-bg)', color: 'var(--accent)',
              padding: '12px 16px', borderRadius: 'var(--radius-md)', marginBottom: 16, fontSize: 13,
            }}
          >
            <Icon name="alert" size={16} />
            Salvage title — {report.salvageDetails[0]?.cause || 'cause unspecified'}
            {report.salvageDetails[0]?.date ? ` (${report.salvageDetails[0].date})` : ''}
          </div>
        )}
        {report.titleCheckAvailable && !report.isSalvage && (
          <div
            style={{
              display: 'flex', alignItems: 'center', gap: 10,
              background: 'var(--green-bg)', color: 'var(--green)',
              padding: '12px 16px', borderRadius: 'var(--radius-md)', marginBottom: 16, fontSize: 13,
            }}
          >
            <Icon name="check" size={16} />
            No salvage or total-loss title found.
          </div>
        )}

        {report.vehicleDatabasesDecode?.basic ? (
          <div style={{ marginBottom: 16 }}>
            <p className="eyebrow" style={{ marginBottom: 12 }}>Vehicle Databases · Real decode</p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
              {Object.entries(report.vehicleDatabasesDecode.basic)
                .filter(([, v]) => v)
                .map(([k, v]) => (
                  <div key={k}>
                    <p style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase' }}>{k.replace(/_/g, ' ')}</p>
                    <p style={{ fontSize: 13, fontWeight: 500 }}>{v}</p>
                  </div>
                ))}
            </div>
          </div>
        ) : (
          <div style={{ marginBottom: 16, paddingBottom: 16, borderBottom: '0.5px solid var(--border)' }}>
            <p className="eyebrow" style={{ marginBottom: 6 }}>Vehicle Databases · Real decode</p>
            <p style={{ fontSize: 13, color: 'var(--muted)', fontStyle: 'italic' }}>
              {report.vehicleDatabasesDecode?.error
                ? `Unavailable — ${report.vehicleDatabasesDecode.error}`
                : 'Unavailable — no response from Vehicle Databases for this VIN.'}
            </p>
          </div>
        )}

        {report.nhtsaDecode && !report.nhtsaDecode.error && (
          <div style={{ paddingTop: 16, borderTop: report.vehicleDatabasesDecode ? '0.5px solid var(--border)' : 'none' }}>
            <p className="eyebrow" style={{ marginBottom: 12 }}>NHTSA vPIC · Real decode (US gov, free)</p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
              {['Make', 'Model', 'ModelYear', 'BodyClass', 'PlantCity', 'PlantCountry', 'EngineCylinders', 'FuelTypePrimary']
                .filter((k) => report.nhtsaDecode[k])
                .map((k) => (
                  <div key={k}>
                    <p style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase' }}>{k.replace(/([A-Z])/g, ' $1').trim()}</p>
                    <p style={{ fontSize: 13, fontWeight: 500 }}>{report.nhtsaDecode[k]}</p>
                  </div>
                ))}
            </div>
          </div>
        )}

      </div>
    );
  }
  if (tab === 'local') {
    return (
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10 }}>
        <StatCard label="UAE accidents" value="Not connected yet" />
        <StatCard label="Registration status" value="Not connected yet" />
      </div>
    );
  }
  if (tab === 'listing') {
    return <p style={{ fontSize: 13, color: 'var(--tertiary)', fontStyle: 'italic' }}>Coming soon — listing comparison not yet connected.</p>;
  }
  return <p style={{ fontSize: 13, color: 'var(--tertiary)', fontStyle: 'italic' }}>Coming soon — seller contact integration not yet connected.</p>;
}

function ScoreRing({ score }) {
  const radius = 24;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const color = scoreColor(score);

  return (
    <div style={{ position: 'relative', width: 56, height: 56, flexShrink: 0 }}>
      <svg viewBox="0 0 56 56" style={{ width: 56, height: 56, transform: 'rotate(-90deg)' }}>
        <circle cx="28" cy="28" r={radius} fill="none" stroke="var(--border)" strokeWidth="6" />
        <circle
          cx="28" cy="28" r={radius} fill="none"
          stroke={color} strokeWidth="6"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
        />
      </svg>
      <span style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 15, fontWeight: 600 }}>
        {score}
      </span>
    </div>
  );
}

function Sidebar({ activeTab, setActiveTab, user, onLogout }) {
  return (
    <div style={{ width: 200, borderRight: '0.5px solid var(--border)', background: 'var(--surface)', padding: '20px 0', flexShrink: 0, display: 'flex', flexDirection: 'column' }}>
      <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0 20px', marginBottom: 24 }}>
        <Icon name="car" size={18} />
        <span style={{ fontWeight: 600, fontSize: 14 }}>VinCheck UAE</span>
      </Link>

      <p className="eyebrow" style={{ padding: '0 20px', marginBottom: 8 }}>Report sections</p>
      {REPORT_TABS.map((tab) => (
        <SidebarItem key={tab.key} icon={tab.icon} active={activeTab === tab.key} onClick={() => setActiveTab(tab.key)}>
          {tab.label}
        </SidebarItem>
      ))}

      <p className="eyebrow" style={{ padding: '16px 20px 8px' }}>Account</p>
      <SidebarItem icon="history" linkTo="/history">Check history</SidebarItem>
      <SidebarItem icon="settings">Settings</SidebarItem>

      <div style={{ marginTop: 'auto', padding: '16px 20px 0', borderTop: '0.5px solid var(--border)' }}>
        <p style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 8 }}>{user?.email || 'Not logged in'}</p>
        <button className="btn-ghost" onClick={onLogout} style={{ padding: '4px 0' }}>
          <Icon name="logout" size={14} style={{ marginRight: 6, verticalAlign: -2 }} />
          Log out
        </button>
      </div>
    </div>
  );
}

function SidebarItem({ icon, active, onClick, children, linkTo }) {
  const content = (
    <div
      onClick={onClick}
      style={{
        padding: '9px 20px',
        fontSize: 13,
        fontWeight: active ? 500 : 400,
        color: active ? 'var(--info)' : 'var(--muted)',
        background: active ? 'var(--info-bg)' : 'transparent',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        gap: 8,
      }}
    >
      <Icon name={icon} size={15} />
      {children}
    </div>
  );
  return linkTo ? <Link to={linkTo}>{content}</Link> : content;
}
