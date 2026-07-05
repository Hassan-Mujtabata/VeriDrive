import { supabase } from './supabaseClient'

// Saves a completed verification report to the logged-in user's history.
// The entire report JSON is stored as one column (`report_json`) rather
// than split into many columns — VeriDrive's report is a single cohesive
// object (listing + trust_score + vin_report + red_flags + voice_call),
// and storing it whole means the History page can re-render the exact
// same ReportCard component used for a fresh check, with no separate
// "did we save every field" logic to maintain.
export async function saveReportToHistory(userId, report) {
  if (!userId) return null // not logged in — nothing to save

  const { data, error } = await supabase
    .from('report_history')
    .insert({
      user_id: userId,
      listing_url: report.listing?.listing_url || null,
      make: report.listing?.make || null,
      model: report.listing?.model || null,
      year: report.listing?.year || null,
      composite_score: report.trust_score?.composite_score ?? null,
      report_json: report,
    })
    .select()
    .single()

  if (error) {
    console.error('Failed to save report history:', error.message)
    return null
  }
  return data
}

// Loads the logged-in user's past reports, most recent first.
// Returns the lightweight list columns only (not report_json) for the
// history table view — call loadReportById() to get the full report
// when the user clicks into one.
export async function loadHistoryList(userId) {
  if (!userId) return []

  const { data, error } = await supabase
    .from('report_history')
    .select('id, listing_url, make, model, year, composite_score, checked_at')
    .eq('user_id', userId)
    .order('checked_at', { ascending: false })

  if (error) {
    console.error('Failed to load history list:', error.message)
    return []
  }
  return data
}

// Loads one full saved report by its row id, for re-displaying in ReportCard.
export async function loadReportById(id) {
  const { data, error } = await supabase
    .from('report_history')
    .select('report_json')
    .eq('id', id)
    .single()

  if (error) {
    console.error('Failed to load report:', error.message)
    return null
  }
  return data?.report_json ?? null
}
