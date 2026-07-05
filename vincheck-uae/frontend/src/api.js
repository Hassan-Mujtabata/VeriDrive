// Talks to your FastAPI backend (main.py). Adjust BASE_URL if your backend
// runs somewhere other than localhost:8000.

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export async function checkVehicle(vin) {
  const res = await fetch(`${BASE_URL}/api/check-vehicle/${vin}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Server error: ${res.status}`);
  }
  return res.json();
}

// Maps the FastAPI response shape into the shape the dashboard components expect.
// Keeping this in one place means if the backend response changes, only this
// function needs updating — not every page that displays a report.
//
// Real sources only, as of this version:
//   - NHTSA vPIC          → specs (make/model/year/plant/engine), free, no key
//   - Vehicle Databases   → decode, title check (salvage)
// Auction history was removed to conserve API call quota — re-add by
// restoring fetch_auction_data in main.py and the auction_history field.
export function normalizeReport(apiResponse) {
  const titleCheck = apiResponse.title_check;
  const isSalvage = Boolean(titleCheck && !titleCheck.error && titleCheck.salvage === true);
  const salvageDetails = (titleCheck && titleCheck.salvage_details) || [];

  const titleCheckAvailable = Boolean(titleCheck && !titleCheck.error);
  const titleCheckError = titleCheck?.error || (!titleCheck ? 'Vehicle Databases key not configured' : null);

  let verdict = 'warn'; // default to "review" when we simply don't have enough signal yet
  if (titleCheckAvailable) verdict = isSalvage ? 'bad' : 'good';

  let trustScore = 75; // neutral baseline when no title data is available
  if (titleCheckAvailable) trustScore = isSalvage ? 35 : 92;
  trustScore = Math.max(10, Math.min(99, trustScore));

  const vd = apiResponse.vehicledatabases_decode;
  const basic = vd?.basic || {};
  const nhtsa = apiResponse.nhtsa_decode || {};

  return {
    vin: apiResponse.vin,
    make: apiResponse.make !== 'Unknown' ? apiResponse.make : nhtsa.Make || 'Unknown',
    model: apiResponse.model !== 'Unknown' ? apiResponse.model : nhtsa.Model || 'Unknown',
    year: basic.year || nhtsa.ModelYear || '—',
    trim: basic.trim || nhtsa.Trim || null,
    verdict,
    trustScore,
    registrationStatus: 'Unknown', // populated once a local/UAE source is connected
    priceVsMarket: null,           // populated once listing comparison is connected
    vehicleDatabasesDecode: vd,
    nhtsaDecode: apiResponse.nhtsa_decode,
    titleCheck,
    titleCheckAvailable,
    titleCheckError,
    isSalvage,
    salvageDetails,
  };
}
