import { useState } from 'react'

// ---------------------------------------------------------------------------
// Auction history section — fetches on demand so credits are only spent
// when the user explicitly clicks the button.
// ---------------------------------------------------------------------------
function AuctionSection({ vin }) {
  const [status, setStatus] = useState('idle') // 'idle' | 'loading' | 'done' | 'error'
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  async function loadAuction() {
    setStatus('loading')
    try {
      const res = await fetch(`http://localhost:8001/api/auction-test/${vin}`)
      if (!res.ok) throw new Error(`Server returned ${res.status}`)
      const json = await res.json()
      setData(json.auction_history)
      setStatus('done')
    } catch (err) {
      setError(err.message)
      setStatus('error')
    }
  }

  // Recursively find all image URLs anywhere in a nested object
  function findImages(obj, found = []) {
    if (!obj || typeof obj !== 'object') return found
    for (const [key, val] of Object.entries(obj)) {
      if ((key.toLowerCase().includes('image') || key.toLowerCase().includes('photo')) && typeof val === 'string' && val.startsWith('http')) {
        found.push(val)
      } else if (Array.isArray(val)) {
        val.forEach((item) => {
          if (typeof item === 'string' && item.startsWith('http')) found.push(item)
          else findImages(item, found)
        })
      } else if (typeof val === 'object') {
        findImages(val, found)
      }
    }
    return found
  }

  const records = data?.records || []
  const hasRecords = records.length > 0
  const allImages = records.flatMap((r) => findImages(r))

  return (
    <div className="border border-gray-100 rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 bg-white">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-gray-800">Auction History</span>
          <span className="text-xs px-2 py-0.5 rounded-full font-bold bg-amber-100 text-amber-700">Paid</span>
        </div>
        {status === 'idle' && (
          <button
            onClick={loadAuction}
            className="text-xs px-3 py-1.5 bg-brand-600 text-white rounded-lg font-semibold hover:bg-brand-700 transition"
          >
            Load auction history
          </button>
        )}
        {status === 'loading' && (
          <span className="text-xs text-gray-400">Loading...</span>
        )}
      </div>

      {status === 'error' && (
        <div className="px-4 py-3 bg-red-50 border-t border-red-100">
          <p className="text-xs text-red-600">{error}</p>
        </div>
      )}

      {status === 'done' && (
        <div className="px-4 py-3 bg-gray-50 border-t border-gray-100 space-y-4">
          {!hasRecords ? (
            <p className="text-xs text-gray-400 italic">No auction records found for this VIN.</p>
          ) : (
            <>
              <p className="text-xs text-gray-500">{records.length} auction record{records.length > 1 ? 's' : ''} found.</p>

              {/* Images */}
              {allImages.length > 0 ? (
                <div>
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Auction photos ({allImages.length})</p>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                    {allImages.map((url, i) => (
                      <a key={i} href={url} target="_blank" rel="noopener noreferrer">
                        <img
                          src={url}
                          alt={`Auction photo ${i + 1}`}
                          className="w-full h-32 object-cover rounded-lg border border-gray-200 hover:opacity-90 transition"
                          onError={(e) => { e.target.style.display = 'none' }}
                        />
                      </a>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="text-xs text-gray-400 italic">No photos found in auction records for this VIN.</p>
              )}

              {/* Record details */}
              {records.map((rec, i) => {
                const fields = Object.entries(rec)
                  .filter(([k, v]) => v && !k.toLowerCase().includes('image') && !k.toLowerCase().includes('photo') && typeof v !== 'object')
                  .map(([k, v]) => [k.replace(/[-_]/g, ' '), String(v)])
                return (
                  <div key={i} className="border border-gray-100 rounded-lg p-3">
                    <p className="text-xs font-semibold text-gray-500 mb-2">Record {i + 1}</p>
                    <div className="grid grid-cols-2 gap-2">
                      {fields.map(([k, v]) => (
                        <div key={k}>
                          <p className="text-[10px] uppercase text-gray-400">{k}</p>
                          <p className="text-xs font-semibold text-gray-700">{v}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )
              })}
            </>
          )}
        </div>
      )}
    </div>
  )
}

// One summary row in the top "at a glance" table — unchanged from the
// original component, this is what feeds the trust score engine's
// expected vin_report shape (accident_count, title_status, etc).
function SummaryRow({ icon, label, value, good, bad, isLast }) {
  return (
    <div
      className={`flex items-center justify-between px-4 py-3 text-sm ${
        !isLast ? 'border-b border-gray-50' : ''
      } ${bad ? 'bg-red-50' : good ? 'bg-emerald-50/50' : 'bg-white'}`}
    >
      <div className="flex items-center gap-2 text-gray-500">
        <span>{icon}</span>
        <span>{label}</span>
      </div>
      <span className={`font-semibold ${bad ? 'text-red-600' : good ? 'text-emerald-600' : 'text-gray-700'}`}>
        {value}
      </span>
    </div>
  )
}

// Expandable card for one underlying data source (NHTSA, Vehicle
// Databases decode, Title Check). Collapsed by default so the card
// doesn't overwhelm the single-page report — click to see the raw
// fields that source actually returned.
function SourceSection({ title, badge, badgeColor, available, errorMessage, children }) {
  const [open, setOpen] = useState(false)

  return (
    <div className="border border-gray-100 rounded-xl overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 bg-white hover:bg-gray-50 transition text-left"
      >
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-gray-800">{title}</span>
          <span className={`text-xs px-2 py-0.5 rounded-full font-bold ${badgeColor}`}>{badge}</span>
        </div>
        <svg
          className={`w-4 h-4 text-gray-400 transition-transform ${open ? 'rotate-180' : ''}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && (
        <div className="px-4 py-3 bg-gray-50 border-t border-gray-100">
          {!available ? (
            <p className="text-xs text-gray-400 italic">
              {errorMessage || 'Unavailable for this VIN.'}
            </p>
          ) : (
            children
          )}
        </div>
      )}
    </div>
  )
}

function FieldGrid({ fields }) {
  if (!fields || fields.length === 0) {
    return <p className="text-xs text-gray-400 italic">No fields returned.</p>
  }
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
      {fields.map(([label, value]) => (
        <div key={label}>
          <p className="text-[10px] uppercase tracking-wide text-gray-400">{label}</p>
          <p className="text-xs font-semibold text-gray-700 break-words">{value}</p>
        </div>
      ))}
    </div>
  )
}

// Flattens nested objects/arrays into readable [label, value] pairs.
function flatten(obj, prefix = '') {
  const rows = []
  for (const [key, value] of Object.entries(obj || {})) {
    if (value === null || value === undefined || value === '') continue
    if (key.toLowerCase().includes('image') || key.toLowerCase().includes('photo')) continue
    const label = prefix ? `${prefix} ${key}` : key
    if (Array.isArray(value)) {
      if (value.length === 0) continue
      if (typeof value[0] === 'object') {
        value.forEach((item, i) => rows.push(...flatten(item, `${label} ${i + 1}`)))
      } else {
        rows.push([label, value.join(', ')])
      }
    } else if (typeof value === 'object') {
      rows.push(...flatten(value, label))
    } else {
      rows.push([label.replace(/[-_]/g, ' '), String(value)])
    }
  }
  return rows
}

export default function VINReport({ vinReport }) {
  if (!vinReport || !vinReport.available) {
    return (
      <div>
        <h3 className="text-base font-bold text-gray-800 mb-3">VIN History Report</h3>
        <div className="rounded-xl border border-gray-100 bg-gray-50 p-5">
          <p className="text-sm text-gray-500">VIN was not provided by the seller during the verification call. This sub-score was excluded from the composite score.</p>
          <p className="text-xs text-gray-400 mt-2">To enable VIN verification, the seller must provide the Vehicle Identification Number during the AI call.</p>
        </div>
      </div>
    )
  }

  const {
    vin, data_source, accident_count, ownership_count, title_status, theft_record,
    sources, // optional: { nhtsa: {...}, vehicle_databases: {...}, title_check: {...} }
  } = vinReport

  const summaryRows = [
    { label: 'VIN', value: vin, icon: '🔑', neutral: true },
    {
      label: 'Data Source',
      value: data_source === 'VehicleDatabases'
        ? 'NHTSA + Vehicle Databases'
        : data_source === 'ClearVin'
          ? 'ClearVin (NMVTIS — US/Canada imports)'
          : data_source === 'CarVertical'
            ? 'CarVertical (European imports)'
            : data_source,
      icon: '🗄',
      neutral: true,
    },
    {
      label: 'Accident Records',
      value: accident_count === 0 ? 'None found' : `${accident_count} record${accident_count > 1 ? 's' : ''} found`,
      icon: accident_count === 0 ? '✅' : '⚠️',
      good: accident_count === 0,
      bad: accident_count > 0,
    },
    { label: 'Ownership Count', value: `${ownership_count} previous owner${ownership_count !== 1 ? 's' : ''}`, icon: '👤', neutral: true },
    {
      label: 'Title Status',
      value: title_status,
      icon: title_status === 'Clean' ? '✅' : '⚠️',
      good: title_status === 'Clean',
      bad: title_status !== 'Clean',
    },
    {
      label: 'Theft Record',
      value: theft_record ? 'Theft record found' : 'No theft record',
      icon: theft_record ? '🚨' : '✅',
      good: !theft_record,
      bad: theft_record,
    },
  ]

  // Per-source breakdown — only rendered if the backend actually sent
  // a `sources` object. Older/simpler responses without it just skip
  // straight to the MOI note below, so this stays backward compatible.
  const nhtsa = sources?.nhtsa
  const vdDecode = sources?.vehicle_databases
  const titleCheck = sources?.title_check

  return (
    <div>
      <h3 className="text-base font-bold text-gray-800 mb-3">VIN History Report</h3>

      {/* At-a-glance summary — unchanged, this is what the trust score engine reads */}
      <div className="bg-white rounded-xl border border-gray-100 overflow-hidden mb-4">
        {summaryRows.map((row, idx) => (
          <SummaryRow key={row.label} {...row} isLast={idx === summaryRows.length - 1} />
        ))}
      </div>

      {/* Expandable per-source breakdown */}
      {sources && (
        <div className="space-y-2 mb-4">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide px-1">Data Sources</p>

          <SourceSection
            title="NHTSA vPIC"
            badge="Free · US Gov"
            badgeColor="bg-blue-100 text-blue-700"
            available={Boolean(nhtsa && !nhtsa.error)}
            errorMessage={nhtsa?.error}
          >
            <FieldGrid fields={flatten(nhtsa)} />
          </SourceSection>

          <SourceSection
            title="Vehicle Databases · Decode"
            badge="Paid"
            badgeColor="bg-amber-100 text-amber-700"
            available={Boolean(vdDecode && !vdDecode.error)}
            errorMessage={vdDecode?.error}
          >
            <FieldGrid fields={flatten(vdDecode?.basic || vdDecode)} />
          </SourceSection>

          <SourceSection
            title="Vehicle Databases · Title Check"
            badge="Paid"
            badgeColor="bg-amber-100 text-amber-700"
            available={Boolean(titleCheck && !titleCheck.error)}
            errorMessage={titleCheck?.error}
          >
            <FieldGrid fields={flatten(titleCheck)} />
          </SourceSection>
        </div>
      )}

      {/* Auction History — on-demand, one credit per click */}
      <AuctionSection vin={vin} />

      {/* UAE MOI manual check */}
      <div className="bg-blue-50 border border-blue-100 rounded-xl p-4">
        <p className="text-xs font-semibold text-blue-800 mb-1">UAE-Registered Vehicle?</p>
        <p className="text-xs text-blue-600 mb-2">
          For vehicles registered in the UAE, accident and police records must be verified manually through the Ministry of Interior portal. No public API exists for automated access.
        </p>
        <a
          href="https://www.moi.gov.ae"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-xs bg-blue-600 text-white px-3 py-1.5 rounded-lg font-semibold hover:bg-blue-700 transition"
        >
          Check on MOI Portal →
        </a>
      </div>
    </div>
  )
}
