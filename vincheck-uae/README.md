# VinCheck UAE

A vehicle history check tool for used car buyers. Given a VIN, it queries
multiple real data sources concurrently and returns a single consolidated
trust report — vehicle specs, salvage/title status, and a verdict score —
shown on a React dashboard with login, history, and PDF export.

---

## 1. Purpose

Used car listings rarely tell the whole story. This tool takes a VIN and
checks it against independent data sources to surface things a buyer would
otherwise have to dig for separately: confirmed vehicle specs, and whether
the title has ever been marked salvage/total-loss (commonly caused by
flood, fire, or major collision damage).

It's built as two independent pieces talking over HTTP:

- **Backend** (`backend/`) — a FastAPI service that calls the external data
  sources and returns one consolidated JSON response per VIN.
- **Frontend** (`frontend/`) — a React app (sidebar dashboard, login, history
  log, PDF export) that calls the backend and renders the result.

They're separate on purpose — the backend has no idea a React frontend
exists, it just answers HTTP requests. This means **any** frontend (a
different web app, a mobile app, another team's dashboard) can use the same
backend without changes, as long as it can make a GET request and read JSON.

---

## 2. Architecture / Algorithm

```
                         ┌─────────────────────────┐
   User enters VIN  ───► │   React Frontend         │
                         │   (port 5173)            │
                         └────────────┬─────────────┘
                                      │ GET /api/check-vehicle/{vin}
                                      ▼
                         ┌─────────────────────────┐
                         │   FastAPI Backend        │
                         │   (port 8000)            │
                         └────────────┬─────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
            ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
            │  NHTSA vPIC   │ │ Vehicle DBs   │ │ Vehicle DBs   │
            │  (free, no    │ │ VIN Decode    │ │ Title Check   │
            │   key)        │ │ (paid key)    │ │ (paid key)    │
            └───────┬───────┘ └───────┬───────┘ └───────┬───────┘
                    │                 │                 │
                    └─────────────────┼─────────────────┘
                                      ▼
                         All 3 calls run CONCURRENTLY
                         (asyncio.gather) — total wait
                         time = slowest single call,
                         not the sum of all three.
                                      │
                                      ▼
                         ┌─────────────────────────┐
                         │  Merge into one JSON     │
                         │  response, with each      │
                         │  source's own success/    │
                         │  error state preserved    │
                         └────────────┬─────────────┘
                                      ▼
                         Frontend computes a verdict
                         (good / review / high-risk)
                         and a 0-99 trust score from
                         the title check result, then
                         renders the dashboard.
```

### Step-by-step algorithm

1. User submits a VIN (17 characters, no I/O/Q) on the landing page or via
   a direct link to `/dashboard/{vin}`.
2. Frontend calls `GET /api/check-vehicle/{vin}` on the backend.
3. Backend validates the VIN format. Invalid → `400` immediately, no API
   calls wasted.
4. Backend fires three async calls **at the same time**:
   - NHTSA vPIC (always — free, no key needed)
   - Vehicle Databases VIN Decode (if a key is configured)
   - Vehicle Databases Title Check (if a key is configured)
5. `asyncio.gather(..., return_exceptions=True)` waits for all three. If one
   fails (network error, bad key, quota exceeded), it doesn't crash the
   other two — each result is captured independently.
6. Backend merges everything into one `VehicleReportResponse` JSON object
   and returns it.
7. Frontend's `normalizeReport()` (in `frontend/src/api.js`) interprets that
   JSON:
   - If Title Check succeeded and found `salvage: true` → verdict = **high risk**, trust score drops sharply.
   - If Title Check succeeded and found no salvage → verdict = **good**, high trust score.
   - If Title Check is unavailable (no key, quota exceeded, VIN not found) → verdict = **review recommended**, neutral score — we don't have enough signal to say either way.
8. Dashboard renders the verdict banner, decode details from both sources
   side by side, and (if logged in) saves the result to the user's history
   in Supabase.

---

## 3. Data sources / APIs used

| Source | What it provides | Cost | Key required |
|---|---|---|---|
| **NHTSA vPIC** | Make, model, year, body type, engine, plant location | Free, unlimited | No |
| **Vehicle Databases — VIN Decode** | Detailed specs: trim, doors, seating, drivetrain, fuel type | Paid (credit-based) | Yes |
| **Vehicle Databases — Title Check** | Salvage / total-loss flag, cause (flood, collision, etc.), date | Paid (credit-based) | Yes |

> **Note on Auction History:** an Auction History endpoint from Vehicle
> Databases was integrated and tested but removed from this version to
> conserve API credits during testing. The same pattern (a `fetch_*_data`
> async function + a field on `VehicleReportResponse`) can be used to add
> it, or any other data source, back in.

**Supabase** (not a vehicle data source) is used separately for user
accounts and check history persistence — see section 5.

---

## 4. Major functions (backend — `backend/main.py`)

| Function | Purpose |
|---|---|
| `fetch_nhtsa_data(vin)` | Calls NHTSA's free public API, normalizes its verbose response into a flat dict |
| `fetch_vehicledatabases_data(vin)` | Calls Vehicle Databases' VIN Decode endpoint |
| `fetch_title_check_data(vin)` | Calls Vehicle Databases' Title Check endpoint, returns salvage status |
| `check_vehicle_vin(vin)` | The actual `/api/check-vehicle/{vin}` endpoint — validates input, runs the three fetches concurrently, merges results |
| `VehicleReportResponse` | Pydantic model defining the exact JSON shape every response follows — this is the contract any frontend can rely on |

## 4b. Major functions (frontend — `frontend/src/`)

| File | Purpose |
|---|---|
| `api.js` | Calls the backend, and `normalizeReport()` turns the raw response into the verdict/trust-score shape the UI uses |
| `AuthContext.jsx` | Wraps Supabase auth (`signUp`, `signIn`, `signOut`) behind a `useAuth()` hook |
| `history.js` | Saves a completed check to Supabase (`saveCheckToHistory`) and loads a user's past checks (`loadHistory`) |
| `exportPdf.js` | Builds a print-friendly HTML report and triggers the browser's print-to-PDF dialog |
| `pages/Landing.jsx` | VIN input, kicks off the check, navigates to the dashboard |
| `pages/DashboardSidebar.jsx` | The report itself — sidebar tabs, verdict banner, decode details |
| `pages/History.jsx` | Lists a logged-in user's past checks from Supabase |
| `pages/Login.jsx` | Sign up / log in form |

---

## 5. Connecting a different frontend to this backend

The backend doesn't care who's calling it. Any frontend — a different React
app, a mobile app, another team's dashboard — can use it by:

1. Making a `GET` request to `http://<backend-host>:8000/api/check-vehicle/{vin}`
2. Reading the JSON response, which always follows the `VehicleReportResponse`
   shape (see section 4) regardless of which sources succeeded or failed
3. CORS is currently wide open (`allow_origins=["*"]` in `main.py`) so any
   origin can call it during development — **tighten this to your actual
   frontend's domain before deploying publicly**

No authentication is required to call the backend itself — auth is handled
entirely on the frontend side via Supabase, scoped to history/account
features, not to the vehicle-check API itself.

If this backend becomes one feature inside a bigger platform, the cleanest
approach is usually: keep `main.py` as its own service, and have the bigger
platform's frontend (or its own backend) call `/api/check-vehicle/{vin}`
like any other HTTP API.

---

## 6. Setup & running

### One-time setup

**Backend:**
```bash
cd backend
pip install -r requirements.txt
```
Create `backend/.env`:
```
VEHICLEDATABASES_API_KEY=your_key_here
```

**Frontend:**
```bash
cd frontend
npm install
```
Create `frontend/.env` (see `frontend/.env.example`):
```
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key-here
```

**Supabase database:**
In your Supabase project's SQL Editor, run the contents of
`frontend/supabase_schema.sql` once to create the `check_history` table.

### Running — single command (recommended)

From the project root:
```bash
npm install
npm run dev
```
This starts **both** the backend and frontend together in one terminal,
using `concurrently`. Backend logs appear in blue, frontend logs in green.

Open `http://localhost:5173` once both have started.

### Running — separately (if you prefer two terminals)

```bash
# Terminal 1
cd backend
py -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2
cd frontend
npm run dev
```

### Verifying it works

```bash
curl http://localhost:8000/health
```
Should return `{"status":"ok"}`. Then open `http://localhost:5173` and try
a VIN, e.g. `5YFT4MCE3MP076873`.

---

## 7. Project structure

```
vincheck-uae/
├── package.json            — root script that runs both halves together
├── backend/
│   ├── main.py              — FastAPI app, all API integrations
│   ├── requirements.txt
│   ├── .env                 — VEHICLEDATABASES_API_KEY
│   └── static/
│       └── index.html       — minimal "API is running" landing page
└── frontend/
    ├── src/
    │   ├── App.jsx           — routes
    │   ├── api.js             — talks to backend, normalizes response
    │   ├── AuthContext.jsx    — Supabase auth
    │   ├── supabaseClient.js
    │   ├── history.js         — save/load check history
    │   ├── exportPdf.js        — PDF export via browser print
    │   ├── components/
    │   └── pages/
    ├── supabase_schema.sql    — run once in Supabase SQL editor
    ├── .env                   — Supabase URL + anon key
    └── package.json
```

---

## 8. Known limitations / next steps

- **Local registry tab** (UAE-specific registration/accident data) is not
  connected to any real source yet
- **Listing comparison tab** (pricing vs similar listings) needs a scraper
  or listings API — not built
- **Seller contact tab** — not built
- **Title Check** occasionally returns `404 API not found` for some VINs —
  this may mean no title record exists for that VIN, or the endpoint path
  needs reconfirming against Vehicle Databases' current API docs
- **Auction History** was removed to conserve credits — see section 3
