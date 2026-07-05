import { useState, useEffect } from 'react'
import { useAuth } from '../AuthContext'
import { loadHistoryList, loadReportById } from '../history'

function scoreColor(score) {
  if (score === null || score === undefined) return 'text-gray-400 bg-gray-50'
  if (score >= 75) return 'text-emerald-700 bg-emerald-50'
  if (score >= 50) return 'text-amber-700 bg-amber-50'
  return 'text-red-700 bg-red-50'
}

function relativeTime(isoDate) {
  if (!isoDate) return '—'
  const days = Math.floor((Date.now() - new Date(isoDate).getTime()) / 86400000)
  if (days <= 0) return 'Today'
  if (days === 1) return 'Yesterday'
  if (days < 7) return `${days} days ago`
  return `${Math.floor(days / 7)} week${days >= 14 ? 's' : ''} ago`
}

export default function HistoryScreen({ onBack, onOpenReport }) {
  const { user, logout } = useAuth()
  const [records, setRecords] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [openingId, setOpeningId] = useState(null)

  useEffect(() => {
    if (!user?.id) { setRecords([]); setLoading(false); return }
    setLoading(true)
    loadHistoryList(user.id).then((data) => { setRecords(data); setLoading(false) })
  }, [user?.id])

  async function handleOpen(id) {
    setOpeningId(id)
    const report = await loadReportById(id)
    setOpeningId(null)
    if (report) onOpenReport(report)
  }

  const filtered = records.filter((r) =>
    `${r.make} ${r.model}`.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-100 px-6 py-4">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <button onClick={onBack} className="flex items-center gap-3">
            <div className="w-8 h-8 bg-brand-600 rounded-lg flex items-center justify-center">
              <svg viewBox="0 0 24 24" fill="white" className="w-5 h-5">
                <path d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
            </div>
            <span className="text-lg font-bold text-gray-900">VeriDrive</span>
          </button>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-500">{user?.email}</span>
            <button onClick={async () => { await logout(); onBack() }} className="text-sm text-gray-400 hover:text-gray-600">
              Log out
            </button>
          </div>
        </div>
      </nav>

      <div className="max-w-3xl mx-auto px-4 pt-8 pb-16">
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
            <h2 className="text-base font-bold text-gray-800">Your verification history</h2>
            <input
              type="text"
              placeholder="Search by make or model"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="px-3 py-2 rounded-lg border border-gray-200 text-sm w-56 focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>

          {!user?.id ? (
            <p className="text-center text-gray-400 text-sm py-12">Log in to see your verification history.</p>
          ) : loading ? (
            <p className="text-center text-gray-400 text-sm py-12">Loading...</p>
          ) : filtered.length === 0 ? (
            <p className="text-center text-gray-400 text-sm py-12">
              {records.length === 0 ? 'No reports yet — verify a listing to see it here.' : 'No reports match your search.'}
            </p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 text-left text-gray-400 text-xs uppercase">
                  <th className="px-6 py-3 font-medium">Vehicle</th>
                  <th className="py-3 font-medium">Checked</th>
                  <th className="py-3 font-medium">Trust score</th>
                  <th className="px-6 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((r) => (
                  <tr
                    key={r.id}
                    onClick={() => handleOpen(r.id)}
                    className="border-b border-gray-50 last:border-0 hover:bg-gray-50 cursor-pointer transition"
                  >
                    <td className="px-6 py-4">{r.year} {r.make} {r.model}</td>
                    <td className="py-4 text-gray-500">{relativeTime(r.checked_at)}</td>
                    <td className="py-4">
                      <span className={`px-2.5 py-1 rounded-full text-xs font-bold ${scoreColor(r.composite_score)}`}>
                        {r.composite_score ?? '—'}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right text-gray-300">
                      {openingId === r.id ? '...' : '→'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
