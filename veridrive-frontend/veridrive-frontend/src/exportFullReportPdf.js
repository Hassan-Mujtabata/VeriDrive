// Builds a print-friendly version of the ENTIRE VeriDrive report (listing,
// trust score, sub-scores, red flags, price analysis, voice call, VIN
// report) and opens the browser's native print dialog so the user can
// "Save as PDF". Matches the app's teal brand color rather than introducing
// a new palette.

const BRAND = {
  600: '#0d9488',
  700: '#0f766e',
  50: '#f0fdfa',
}

function escapeHtml(str) {
  if (str === null || str === undefined) return ''
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

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

function rowsToTable(rows) {
  if (!rows || rows.length === 0) return '<p class="muted">No data available.</p>'
  return `<table>${rows.map(([l, v]) => `
    <tr><td class="label">${escapeHtml(l)}</td><td class="value">${escapeHtml(v)}</td></tr>
  `).join('')}</table>`
}

function severityColor(sev) {
  return sev === 'high' ? '#dc2626' : sev === 'medium' ? '#d97706' : '#2563eb'
}

function scoreColor(score) {
  if (score === null || score === undefined) return '#9ca3af'
  return score >= 75 ? '#059669' : score >= 50 ? '#d97706' : '#dc2626'
}

export function exportFullReportToPdf(report) {
  const { listing, trust_score, price_analysis, vin_report, red_flags, voice_call } = report
  const generatedAt = new Date().toLocaleString()

  const redFlagsHtml = (red_flags && red_flags.length > 0)
    ? red_flags.map((f) => `
        <div class="flag" style="border-left:4px solid ${severityColor(f.severity)}">
          <div class="flag-title">${escapeHtml(f.title)} <span class="flag-badge">${escapeHtml(f.severity.toUpperCase())}</span></div>
          <p class="flag-desc">${escapeHtml(f.description)}</p>
        </div>
      `).join('')
    : '<p class="muted">No red flags detected.</p>'

  const sources = vin_report?.sources || {}
  const vinSourcesHtml = vin_report?.available ? `
    <div class="source-block">
      <div class="source-title">NHTSA vPIC (Free, US Gov)</div>
      ${sources.nhtsa && !sources.nhtsa.error ? rowsToTable(flatten(sources.nhtsa)) : '<p class="muted">Unavailable for this VIN.</p>'}
    </div>
    <div class="source-block">
      <div class="source-title">Vehicle Databases — Decode</div>
      ${sources.vehicle_databases && !sources.vehicle_databases.error ? rowsToTable(flatten(sources.vehicle_databases.basic || sources.vehicle_databases)) : '<p class="muted">Unavailable for this VIN.</p>'}
    </div>
    <div class="source-block">
      <div class="source-title">Vehicle Databases — Title Check</div>
      ${sources.title_check && !sources.title_check.error ? rowsToTable(flatten(sources.title_check)) : '<p class="muted">Unavailable for this VIN.</p>'}
    </div>
  ` : ''

  const html = `
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>VeriDrive Report — ${escapeHtml(listing?.make)} ${escapeHtml(listing?.model)}</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, 'Segoe UI', Arial, sans-serif; color: #111827; padding: 36px; font-size: 12.5px; line-height: 1.5; }
  h1 { font-size: 22px; font-weight: 800; margin-bottom: 2px; }
  .brand { color: ${BRAND[600]}; font-weight: 700; font-size: 13px; letter-spacing: 0.02em; margin-bottom: 4px; }
  .subtitle { color: #6b7280; margin-bottom: 4px; font-size: 12px; }
  .price { font-size: 20px; font-weight: 800; color: ${BRAND[600]}; }
  section { margin: 22px 0; page-break-inside: avoid; }
  .section-title { font-size: 11px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: #6b7280; margin-bottom: 8px; border-bottom: 1px solid #e5e7eb; padding-bottom: 5px; }
  table { width: 100%; border-collapse: collapse; margin-bottom: 8px; }
  td { padding: 4px 0; border-bottom: 1px solid #f3f4f6; font-size: 12px; }
  td.label { color: #6b7280; text-transform: uppercase; font-size: 9.5px; width: 40%; }
  td.value { font-weight: 600; }
  .muted { color: #9ca3af; font-style: italic; font-size: 12px; }
  .score-row { display: flex; gap: 18px; margin-bottom: 10px; }
  .score-box { flex: 1; border: 1px solid #e5e7eb; border-radius: 8px; padding: 10px 14px; text-align: center; }
  .score-box .num { font-size: 22px; font-weight: 800; }
  .score-box .lbl { font-size: 10px; color: #6b7280; text-transform: uppercase; margin-top: 2px; }
  .composite { text-align: center; margin: 14px 0; }
  .composite .num { font-size: 46px; font-weight: 800; }
  .composite .lbl { font-size: 11px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; }
  .recommendation { background: ${BRAND[50]}; border: 1px solid #ccfbf1; border-radius: 8px; padding: 12px 16px; font-size: 12px; color: #134e4a; margin-top: 10px; }
  .flag { padding: 8px 12px; margin-bottom: 8px; background: #fafafa; border-radius: 4px; }
  .flag-title { font-weight: 700; font-size: 12px; }
  .flag-badge { font-size: 9px; font-weight: 700; color: #6b7280; margin-left: 4px; }
  .flag-desc { font-size: 11.5px; color: #4b5563; margin-top: 2px; }
  .source-block { margin-bottom: 12px; }
  .source-title { font-weight: 700; font-size: 11px; margin-bottom: 4px; color: #374151; }
  footer { margin-top: 30px; padding-top: 10px; border-top: 1px solid #e5e7eb; font-size: 10px; color: #9ca3af; display: flex; justify-content: space-between; }
  @media print { body { padding: 18px; } }
</style>
</head>
<body>

  <div class="brand">VeriDrive</div>
  <h1>${escapeHtml(listing?.year)} ${escapeHtml(listing?.make)} ${escapeHtml(listing?.model)}</h1>
  <p class="subtitle">${escapeHtml(listing?.emirate)} &middot; ${listing?.mileage_km ? Number(listing.mileage_km).toLocaleString() + ' km' : ''} ${listing?.seller_name ? '&middot; Seller: ' + escapeHtml(listing.seller_name) : ''}</p>
  <p class="price">AED ${listing?.asking_price_aed ? Number(listing.asking_price_aed).toLocaleString() : '—'}</p>

  <section>
    <div class="section-title">Composite Trust Score</div>
    <div class="composite">
      <div class="num" style="color:${scoreColor(trust_score?.composite_score)}">${trust_score?.composite_score ?? '—'}</div>
      <div class="lbl">out of 100</div>
    </div>
    <div class="score-row">
      <div class="score-box"><div class="num" style="color:${scoreColor(trust_score?.seller_credibility_subscore)}">${trust_score?.seller_credibility_subscore ?? '—'}</div><div class="lbl">Seller Credibility</div></div>
      <div class="score-box"><div class="num" style="color:${scoreColor(trust_score?.price_fairness_subscore)}">${trust_score?.price_fairness_subscore ?? '—'}</div><div class="lbl">Price Fairness</div></div>
      <div class="score-box"><div class="num" style="color:${scoreColor(trust_score?.vin_history_subscore)}">${trust_score?.vin_history_subscore ?? '—'}</div><div class="lbl">VIN History</div></div>
    </div>
    <div class="recommendation">${escapeHtml(trust_score?.recommendation)}</div>
  </section>

  <section>
    <div class="section-title">Red Flags ${red_flags ? `(${red_flags.length})` : ''}</div>
    ${redFlagsHtml}
  </section>

  <section>
    <div class="section-title">Price Analysis</div>
    ${rowsToTable([
      ['Asking Price (AED)', price_analysis?.asking_price_aed],
      ['Median Market Price (AED)', price_analysis?.median_market_price],
      ['Difference vs Market', price_analysis?.price_difference_percent != null ? price_analysis.price_difference_percent + '%' : null],
      ['Comparable Listings', price_analysis?.comparable_count],
      ['Recommended Range (AED)', price_analysis?.recommended_min_aed && price_analysis?.recommended_max_aed ? `${Number(price_analysis.recommended_min_aed).toLocaleString()} – ${Number(price_analysis.recommended_max_aed).toLocaleString()}` : null],
    ].filter(([, v]) => v !== null && v !== undefined))}
  </section>

  <section>
    <div class="section-title">Voice Call Verification</div>
    ${voice_call?.available ? rowsToTable([
      ['Call Outcome', voice_call.call_outcome],
      ['Duration', voice_call.duration_seconds ? `${voice_call.duration_seconds}s` : null],
      ['Seller Credibility Score', voice_call.seller_credibility_score],
      ['Summary', voice_call.transcript_summary],
    ].filter(([, v]) => v !== null && v !== undefined)) : '<p class="muted">Call not completed or not available.</p>'}
  </section>

  <section>
    <div class="section-title">VIN History Report</div>
    ${vin_report?.available ? rowsToTable([
      ['VIN', vin_report.vin],
      ['Data Source', vin_report.data_source],
      ['Accident Records', vin_report.accident_count === 0 ? 'None found' : `${vin_report.accident_count} found`],
      ['Ownership Count', vin_report.ownership_count ?? 'Unknown'],
      ['Title Status', vin_report.title_status],
      ['Theft Record', vin_report.theft_record ? 'Found' : 'None'],
    ]) : '<p class="muted">VIN not provided by seller — excluded from composite score.</p>'}
    ${vinSourcesHtml}
  </section>

  <footer>
    <span>VeriDrive — Vehicle Verification Report</span>
    <span>Generated ${escapeHtml(generatedAt)}</span>
  </footer>

  <script>window.onload = () => window.print();</script>
</body>
</html>`

  const printWindow = window.open('', '_blank')
  if (!printWindow) {
    alert('Please allow pop-ups for this site to export the PDF.')
    return
  }
  printWindow.document.write(html)
  printWindow.document.close()
}
