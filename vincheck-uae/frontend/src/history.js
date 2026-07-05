import { supabase } from './supabaseClient';

// Saves a completed VIN check to the logged-in user's history.
// Call this after a successful checkVehicle() + normalizeReport() in the
// dashboard, once you have a `report` object and a `userId`.
export async function saveCheckToHistory(userId, report) {
  if (!userId) return null; // not logged in — nothing to save

  const { data, error } = await supabase
    .from('check_history')
    .insert({
      user_id: userId,
      vin: report.vin,
      make: report.make,
      model: report.model,
      year: report.year,
      trust_score: report.trustScore,
      verdict: report.verdict,
      is_salvage: report.isSalvage,
    })
    .select()
    .single();

  if (error) {
    console.error('Failed to save check history:', error.message);
    return null;
  }
  return data;
}

// Loads the logged-in user's past checks, most recent first.
export async function loadHistory(userId) {
  if (!userId) return [];

  const { data, error } = await supabase
    .from('check_history')
    .select('*')
    .eq('user_id', userId)
    .order('checked_at', { ascending: false });

  if (error) {
    console.error('Failed to load history:', error.message);
    return [];
  }
  return data;
}
