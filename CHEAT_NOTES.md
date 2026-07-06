# VeriDrive - Code Cheat Notes (for presentation)

## 30-second pitch
VeriDrive checks whether a used-car listing (Dubizzle, UAE) is trustworthy.
You paste a listing URL and it:
1. scrapes the ad,
2. auto-calls the seller with an AI voice agent ("Vera") to verify the details,
3. checks the asking price against the market,
4. runs a VIN history check,
5. combines everything into a 0-100 Trust Score with red flags and a Proceed / Caution / Avoid recommendation.

## Tech stack (one-liner)
Python + FastAPI backend, React + Vite frontend, Retell (voice AI) + Twilio (phone), Google Gemini (question generation + analysis), Playwright (web scraping), Supabase (login + history).

---

## The pipeline - who does what
The user pastes a URL, then **main.py** runs 7 steps:

| Step | What | File |
|------|------|------|
| 1 | Scrape the listing | dubizzle_scraper.py |
| 2 + 3 | (in parallel) Call the seller  /  Price analysis | call_veridrive.py  /  price_engine.py |
| 4 | Analyze the call transcript | transcript_analyzer.py |
| 5 | VIN history check | vincheck-uae backend (separate service, port 8001) |
| 6 | Compute the trust score | trust_score_engine.py |
| 7 | Build the final report -> frontend shows it | main.py |

**Why parallel:** the phone call takes 2-5 min, price scraping ~30-60s. Running them together (ThreadPoolExecutor in main.py) saves time.

---

## Files (what / key functions / who calls it)

### main.py  -  the backend brain (FastAPI, port 8000)
- Orchestrates the whole pipeline.
- Endpoints: `POST /verify` (starts it, returns a request_id), `GET /report/{id}` (the frontend polls this), `POST /test-call`, `GET /health`.
- Runs the pipeline in a background thread so the request returns instantly; stores results in an in-memory `reports` dict.
- If the call fails (voicemail / no answer / rejected) it stops early and surfaces a red flag instead of scoring.

### call_veridrive.py  -  the phone call
- Main function: `make_verification_call(seller_number, seller_name, listing, ...)`.
- Flow: generate questions (if a listing is passed) -> register the call with Retell (sends the dynamic variables) -> Twilio dials the seller and bridges to Retell over SIP -> polls until the call ends -> waits for the recording -> returns transcript + recording URL + metadata.
- Detects voicemail / not-answered / rejected calls.
- Learns how long recordings take to appear (saved to veridrive_timing.json).
- Called by: main.py (real pipeline and /test-call) and test_call.py.

### question_generator.py  -  writes Vera's questions (runs BEFORE the call)
- `generate_questions(listing)` -> Gemini writes questions tailored to that exact car (claims to probe, info gaps, suspicious points) plus the opening line, buyer hook, etc.
- `to_retell_dynamic_variables(questions, listing)` -> flattens everything into the `{{variables}}` Retell speaks: opening_line, buyer_hook, car_name, car_short, claim_questions, gap_questions, suspicious_questions, car_summary, end_call_summary_prompt, seller_name.
- Has deterministic fallbacks so no variable is ever blank.
- 5-key Gemini auto-failover; tries the strongest model first.
- Called by: call_veridrive.py and test_call.py.

### transcript_analyzer.py  -  scores the call (this is the one in the live pipeline)
- `analyze_transcript(transcript, listing, dynamic_variables)` -> Gemini reads the transcript and returns: seller_credibility_score (0-100), any VIN the seller said, structured claims (accidents / ownership / service / finance), a hesitation flag, and a summary.
- Lives in veridrive-trust-score-v2/. Its VIN + score feed Steps 5 and 6.
- Called by: main.py Step 4.

### audio_analyzer.py  -  optional deeper analysis (NOT in the live pipeline)
- Listens to the actual audio recording (tone, hesitation), not just the text. Richer but slower.
- Manual tool: `python audio_analyzer.py --latest`.
- Uses model_config.json (which Gemini model to prefer) and analyzed_calls.json (cache).
- Q&A note: the live pipeline scores with transcript_analyzer; audio_analyzer is an optional extra pass. Both use the same 0-100 scoring bands.

### dubizzle_scraper.py  -  gets the listing data
- `scrape_listing(url)` -> uses Playwright (a headless browser) to open the ad, dismiss popups (some with Gemini's help), and pull make / model / year / trim / mileage / price / colour / specs / seller name + phone / description / photos.
- Called by: main.py Step 1.

### price_engine.py  -  is the price fair?
- `scrape_comparables(make, model, year, mileage)` -> scrapes similar Dubizzle listings.
- `compute_analysis(...)` -> median market price, how far the asking price is off (%), a fairness score, and a recommended price range.
- `normalize_price(...)` adjusts each comparable for year/mileage differences before comparing.
- Called by: main.py Step 3 (in parallel with the call).

### trust_score_engine.py  -  the final 0-100 score
- `compute_trust_score(listing, price_data, vin_data, voice_data)` blends three subscores:
  - Seller credibility 35% (from the call)
  - Price fairness 30% (from the price engine)
  - VIN history 35% (from the VIN check)
- If a piece is missing, `redistribute_weights` re-normalizes the remaining weights.
- `detect_claim_discrepancies` cross-checks ad vs VIN vs seller (e.g. ad says "no accidents" but VIN shows salvage -> red flag).
- `generate_recommendation` -> Proceed / Caution / Avoid.
- Called by: main.py Step 6.

### vincheck-uae/backend  -  VIN history (separate FastAPI service, port 8001)
- Endpoint `/api/check-vehicle/{vin}`. Pulls an NHTSA decode, a Vehicle Databases decode, and a title/salvage check.
- Called by: main.py Step 5 over HTTP, only if the seller said a VIN during the call.

### Frontend - React + Vite (veridrive-frontend)
- User pastes the URL (URLInput.jsx), sees a loading screen, then the report: TrustScoreGauge, SubScores, PriceAnalysis, VINReport, VoiceCall (transcript + score), RedFlags, Recommendation.
- Polls `GET /report/{id}` until status = complete.
- Supabase for login + saved history; PDF export (exportFullReportPdf.js).

### Config / data files
- **.env** - all secrets + config (Retell, Twilio, 5 Gemini keys, phone numbers, agent ID). Git-ignored.
- **model_config.json** - audio_analyzer's preferred Gemini model + failure log.
- **veridrive_timing.json** - learned recording wait time.
- **analyzed_calls.json** - audio_analyzer's cache.
- **test_call.py** - end-to-end test with fake "scraped" data that calls your own number.

---

## Likely questions -> quick answers
- **How does the AI call know what to ask?** question_generator.py calls Gemini before the call with the scraped data; the questions are passed to Retell as variables Vera speaks.
- **Where does the trust score come from?** trust_score_engine.py - a weighted average of 3 subscores (call 35% / price 30% / VIN 35%).
- **What if the seller doesn't answer?** call_veridrive.py detects it; main.py stops early and flags it, no score.
- **Why two Gemini analyzers?** transcript_analyzer (text, in the pipeline) and audio_analyzer (audio, optional deeper tool).
- **What if a Gemini key runs out?** 5-key auto-failover - it tries every model on a key, then moves to the next key; stops only if all are exhausted.
- **How do the call and price run at the same time?** ThreadPoolExecutor in main.py runs them in parallel.
- **Why call the seller at all?** To verify the ad's claims live, which is the biggest signal of credibility.
- **How does the VIN check work?** The seller says the VIN on the call -> transcript_analyzer extracts it -> the vincheck service checks title / salvage / history.
- **How does Vera sound human / context-aware?** Gemini pre-writes every spoken line from the specific car's data (opener, hook, questions); Retell just delivers them. Full car name is said once, then "it" / short name.
- **Frontend <-> backend?** Frontend calls `/verify`, then polls `/report/{id}`; Vite proxies `/api/*` to the backend on port 8000.
