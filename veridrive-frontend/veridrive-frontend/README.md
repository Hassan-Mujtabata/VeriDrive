# VeriDrive Frontend

React 18 + TailwindCSS + Recharts buyer report card.

---

## Setup

```bash
npm install
npm run dev
```

App runs at http://localhost:3000

### Login & report history (Supabase)

1. Create a free project at [supabase.com](https://supabase.com)
2. Copy `.env.example` to `.env`, fill in your Project URL and anon key from Settings → API
3. In Supabase's SQL Editor, run the contents of `supabase_schema.sql` once — this creates the `report_history` table with row-level security
4. Restart `npm run dev`

Without a `.env` file, the app still works exactly as before — login/history features just won't function (a console warning will note this), everything else (URL input, demo report, verification flow) is unaffected.

### Email OTP verification (instead of confirmation links)

By default, Supabase sends a confirmation **link**. This app expects a 6-digit **code** instead, entered directly in the UI. Set this up in Supabase:

1. Dashboard → Authentication → Email Templates → "Confirm signup"
2. Make sure the template includes `{{ .Token }}` (the 6-digit code) — Supabase's default template already does, but if it was customized to only show a link, add the token back in
3. That's it — `supabase.auth.signUp()` already triggers this email automatically, and `AuthContext.jsx`'s `verifyOtp()` function handles the code entry

To test without waiting for real email confirmation during development: Supabase dashboard → Authentication → Providers → Email → turn off "Confirm email" entirely (skips the whole OTP step, signup logs straight in). Turn it back on before any real demo.

### CAPTCHA (Cloudflare Turnstile)

1. Get a free site key + secret key at [Cloudflare Turnstile](https://dash.cloudflare.com/?to=/:account/turnstile) (no credit card required)
2. Add the **site key** to `.env`:
   ```
   VITE_TURNSTILE_SITE_KEY=your-site-key-here
   ```
3. Add the **secret key** in Supabase dashboard → Authentication → Settings → "Bot and Abuse Protection" → enable CAPTCHA protection → select Turnstile → paste the secret key

Without a `VITE_TURNSTILE_SITE_KEY` set, the widget still renders using Cloudflare's public "always passes" test key — useful for local dev, but it isn't real bot protection. Set a real key before any real demo or deployment, and make sure the matching secret key is configured in Supabase, or the token Supabase receives won't actually be verified server-side.

---

## Testing Without the Backend

Click **View Demo Report** on the home screen. This loads a pre-built sample report (no backend required). Use this to test the full UI.

---

## Connecting to the FastAPI Backend

When Hassan's FastAPI backend is running (default: http://localhost:8000), the frontend proxies all `/api` requests to it automatically via Vite's proxy config.

The backend must expose these two endpoints:

**POST /verify**
```json
Request:  { "listing_url": "https://dubai.dubizzle.com/..." }
Response: { "request_id": "uuid-here" }
```

**GET /report/{request_id}**
```json
Response:
{
  "request_id": "...",
  "status": "complete",
  "listing": {
    "make": "Toyota",
    "model": "Corolla",
    "year": 2019,
    "mileage_km": 95000,
    "asking_price_aed": 28000,
    "description": "...",
    "seller_name": "...",
    "seller_phone": "...",
    "emirate": "Dubai",
    "listing_url": "...",
    "photos": ["url1", "url2"]
  },
  "trust_score": {
    "composite_score": 72,
    "seller_credibility_subscore": 65,
    "price_fairness_subscore": 88,
    "vin_history_subscore": 60,
    "recommendation": "Plain language summary..."
  },
  "price_analysis": {
    "comparable_count": 23,
    "median_market_price": 31500,
    "asking_price_aed": 28000,
    "price_difference_percent": -11.1,
    "fairness_score": 88,
    "recommended_min_aed": 25000,
    "recommended_max_aed": 28500
  },
  "vin_report": {
    "available": true,
    "vin": "...",
    "data_source": "ClearVin",
    "accident_count": 1,
    "ownership_count": 2,
    "title_status": "Clean",
    "theft_record": false
  },
  "red_flags": [
    {
      "severity": "high",
      "title": "...",
      "description": "...",
      "source_module": "VIN"
    }
  ],
  "voice_call": {
    "available": true,
    "seller_credibility_score": 65,
    "call_outcome": "completed",
    "duration_seconds": 187,
    "transcript_summary": "..."
  }
}
```

Status can be `"processing"` while the pipeline is running. The frontend polls every 5 seconds until it sees `"complete"` or `"error"`.

---

## File Structure

```
src/
  App.jsx                  Main state: input / loading / report / error / login / history / pricecheck
  AuthContext.jsx          Supabase auth (signUp / signIn / signOut / verifyOtp / resendOtp), CAPTCHA-aware
  supabaseClient.js        Supabase client setup, reads .env
  history.js               Save/load full reports to/from Supabase
  exportFullReportPdf.js   Whole-report PDF export via browser print
  sampleData.js            Demo data (no backend required)
  components/
    URLInput.jsx           Landing screen with Dubizzle URL input + login/history/price-check nav
    LoadingState.jsx       Animated pipeline progress screen
    LoginScreen.jsx        Login / signup form with Turnstile CAPTCHA + email OTP code step
    PriceCheckScreen.jsx   Standalone make/model/year/mileage price estimate form (not saved to history)
    HistoryScreen.jsx      List of past reports, click to reopen
    ReportCard.jsx         Sidebar-tab report layout (Overview/Red flags/Price/Voice/VIN) + Export PDF button
    VehicleHeader.jsx      Car photo carousel + basic info
    TrustScoreGauge.jsx    SVG circular gauge (0-100)
    SubScores.jsx          Three sub-score cards
    RedFlags.jsx           Red flags with severity colours
    PriceAnalysis.jsx      Recharts bar chart + stats
    VoiceCall.jsx          AI call summary
    VINReport.jsx          VIN summary + expandable per-source breakdown + MOI link
    Recommendation.jsx     Final verdict banner
```

---

## Tech Stack

- React 18
- Vite 5
- TailwindCSS 3
- Recharts 2
