// Builds a clean, print-friendly report and opens the browser's native
// print dialog (where the user picks "Save as PDF"). This avoids pulling in
// a heavy PDF-generation library for something the browser already does well.

function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function flattenForPrint(obj, prefix = '') {
  const rows = [];
  for (const [key, value] of Object.entries(obj || {})) {
    if (value === null || value === undefined || value === '') continue;
    if (key.toLowerCase().includes('image') || key.toLowerCase().includes('photo')) continue;
    const label = prefix ? `${prefix} ${key}` : key;

    if (Array.isArray(value)) {
      if (value.length === 0) continue;
      if (typeof value[0] === 'object') {
        value.forEach((item, i) => rows.push(...flattenForPrint(item, `${label} ${i + 1}`)));
      } else {
        rows.push([label, value.join(', ')]);
      }
    } else if (typeof value === 'object') {
      rows.push(...flattenForPrint(value, label));
    } else {
      rows.push([label, String(value)]);
    }
  }
  return rows;
}

function rowsToHtml(rows) {
  if (rows.length === 0) return '<p class="muted">No data available.</p>';
  return `
    <table>
      ${rows.map(([label, value]) => `
        <tr>
          <td class="label">${escapeHtml(label.replace(/[-_]/g, ' '))}</td>
          <td class="value">${escapeHtml(value)}</td>
        </tr>
      `).join('')}
    </table>
  `;
}

export function exportReportToPdf(report) {
  const verdictLabel = report.verdict === 'good' ? 'Looks clean' : report.verdict === 'bad' ? 'High risk' : 'Review recommended';
  const verdictColor = report.verdict === 'good' ? '#2a6b3c' : report.verdict === 'bad' ? '#c8401a' : '#b07d10';

  const titleStatusText = report.titleCheckAvailable
    ? (report.isSalvage
        ? `Salvage title — ${report.salvageDetails[0]?.cause || 'cause unspecified'}${report.salvageDetails[0]?.date ? ` (${report.salvageDetails[0].date})` : ''}`
        : 'Clean title — no salvage or total-loss record found')
    : `Title check unavailable — ${report.titleCheckError || 'unknown reason'}`;

  const vdRows = report.vehicleDatabasesDecode?.basic ? flattenForPrint(report.vehicleDatabasesDecode.basic) : [];
  const nhtsaFields = ['Make', 'Model', 'ModelYear', 'BodyClass', 'PlantCity', 'PlantCountry', 'EngineCylinders', 'FuelTypePrimary'];
  const nhtsaRows = report.nhtsaDecode && !report.nhtsaDecode.error
    ? nhtsaFields.filter((k) => report.nhtsaDecode[k]).map((k) => [k.replace(/([A-Z])/g, ' $1').trim(), report.nhtsaDecode[k]])
    : [];

  const generatedAt = new Date().toLocaleString();

  const html = `
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Vehicle Report — ${escapeHtml(report.vin)}</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, 'Segoe UI', Arial, sans-serif; color: #1a1a18; padding: 40px; font-size: 13px; line-height: 1.5; }
  h1 { font-size: 20px; font-weight: 600; margin-bottom: 2px; }
  .vin { font-family: 'Courier New', monospace; font-size: 16px; font-weight: 600; letter-spacing: 0.05em; }
  .subtitle { color: #6b6760; margin-bottom: 24px; }
  .verdict-banner { display: flex; align-items: center; gap: 16px; border: 1px solid #d8d4cc; border-radius: 8px; padding: 16px 20px; margin-bottom: 24px; }
  .score-circle { width: 56px; height: 56px; border-radius: 50%; border: 4px solid ${verdictColor}; display: flex; align-items: center; justify-content: center; font-size: 18px; font-weight: 700; flex-shrink: 0; }
  .verdict-label { font-weight: 600; color: ${verdictColor}; margin-bottom: 2px; }
  .verdict-detail { color: #6b6760; font-size: 12px; }
  section { margin-bottom: 28px; }
  .section-title { font-size: 11px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: #6b6760; margin-bottom: 10px; border-bottom: 1px solid #d8d4cc; padding-bottom: 6px; }
  table { width: 100%; border-collapse: collapse; margin-bottom: 12px; }
  td { padding: 5px 0; border-bottom: 1px solid #eee; }
  td.label { color: #6b6760; text-transform: uppercase; font-size: 10px; width: 40%; }
  td.value { font-weight: 500; }
  .muted { color: #6b6760; font-style: italic; }
  .spacer { height: 10px; }
  footer { margin-top: 40px; padding-top: 12px; border-top: 1px solid #d8d4cc; font-size: 11px; color: #b0ab9f; display: flex; justify-content: space-between; }
  @media print { body { padding: 20px; } }
</style>
</head>
<body>
  <div class="vin">${escapeHtml(report.vin)}</div>
  <h1>${escapeHtml(report.make)} ${escapeHtml(report.model)}${report.year !== '—' ? ` · ${escapeHtml(report.year)}` : ''}${report.trim ? ` · ${escapeHtml(report.trim)}` : ''}</h1>
  <p class="subtitle">Vehicle History Report</p>

  <div class="verdict-banner">
    <div class="score-circle">${report.trustScore}</div>
    <div>
      <div class="verdict-label">${escapeHtml(verdictLabel)}</div>
      <div class="verdict-detail">${escapeHtml(titleStatusText)}</div>
    </div>
  </div>

  <section>
    <div class="section-title">Vehicle Databases · Decode</div>
    ${vdRows.length > 0 ? rowsToHtml(vdRows) : '<p class="muted">Unavailable for this VIN.</p>'}
  </section>

  <section>
    <div class="section-title">NHTSA vPIC · Decode (US Government, Free)</div>
    ${nhtsaRows.length > 0 ? rowsToHtml(nhtsaRows) : '<p class="muted">Unavailable for this VIN.</p>'}
  </section>

  <footer>
    <span>VinCheck UAE — Vehicle Intelligence Report</span>
    <span>Generated ${escapeHtml(generatedAt)}</span>
  </footer>

  <script>
    window.onload = () => { window.print(); };
  </script>
</body>
</html>`;

  const printWindow = window.open('', '_blank');
  if (!printWindow) {
    alert('Please allow pop-ups for this site to export the PDF.');
    return;
  }
  printWindow.document.write(html);
  printWindow.document.close();
}
