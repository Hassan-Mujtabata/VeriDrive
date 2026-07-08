# VeriDrive

**AI-powered trust verification for used-car listings.** Paste a Dubizzle listing URL and VeriDrive scrapes the ad, places an autonomous AI voice call to the seller to verify the details, checks the asking price against the live market, runs a VIN history check, and combines everything into a single **0–100 Trust Score** with red flags and a Proceed / Caution / Avoid recommendation.

> **Course:** BCS 410 · **Region:** UAE (Dubizzle) · **Voice agent:** "Vera"

---

## Table of Contents
- [What it does](#what-it-does)
- [Architecture & pipeline](#architecture--pipeline)
- [Tech stack](#tech-stack)
- [Modules](#modules)
- [Vera — the Retell voice agent](#vera--the-retell-voice-agent)
- [Trust score methodology](#trust-score-methodology)
- [Getting started](#getting-started)
- [Environment variables](#environment-variables)
- [Team](#team)

---

## What it does

Buying a used car online means trusting an anonymous listing. VeriDrive automates the due diligence a careful buyer would do:

1. **Reads the ad** — scrapes the full listing (make, model, year, trim, mileage, price, specs, seller contact).
2. **Calls the seller** — an AI agent ("Vera") phones the seller and naturally verifies the ad's claims, asking questions tailored to that exact car.
3. **Checks the price** — compares the asking price against real comparable listings on the market.
4. **Checks the VIN** — if the seller states a VIN on the call, runs a title/salvage/history lookup.
5. **Scores it** — blends all signals into a composite Trust Score and surfaces red flags.

---

## Architecture & pipeline

The FastAPI backend (`main.py`) orchestrates a 7-step pipeline. The **voice call and price analysis run in parallel** to save wall-clock time (the call takes 2–5 min, price scraping ~30–60 s).

```
 User pastes listing URL
          │
          ▼
 ┌─────────────────────────────────────────────────────────────┐
 │  main.py  (FastAPI · port 8000)                              │
 │                                                              │
 │  1. Scrape listing ............ dubizzle_scraper.py          │
 │           │                                                  │
 │     ┌─────┴─────┐  (parallel — ThreadPoolExecutor)           │
 │     ▼           ▼                                            │
 │  2. Call     3. Price                                        │
 │  seller      analysis                                        │
 │  call_       price_engine.py                                 │
 │  veridrive.py                                                │
 │     │ (Retell + Twilio)                                      │
 │     ▼                                                        │
 │  4. Analyse transcript ........ transcript_analyzer.py       │
 │     ▼                                                        │
 │  5. VIN history check ......... vincheck-uae/ (port 8001)    │
 │     ▼                                                        │
 │  6. Trust score ............... trust_score_engine.py        │
 │     ▼                                                        │
 │  7. Build report → frontend polls GET /report/{id}          │
 └─────────────────────────────────────────────────────────────┘
          │
          ▼
 React + Vite frontend (npm run dev)
```

**API endpoints (`main.py`):**
| Method | Route | Purpose |
|--------|-------|---------|
| `POST` | `/verify` | Start a verification; returns a `request_id` |
| `GET`  | `/report/{request_id}` | Frontend polls this until `status = complete` |
| `POST` | `/test-call` | Place a standalone test call |
| `GET`  | `/health` | Health check |

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python **3.12**, FastAPI, Uvicorn |
| **Voice AI** | [Retell AI](https://retellai.com) (conversation-flow agent "Vera") |
| **Telephony** | Twilio (outbound call bridged to Retell over SIP) |
| **LLM** | Google **Gemini** — question generation, transcript & audio analysis, scraper pop-up handling |
| **Scraping** | Playwright (headless Chromium) |
| **Frontend** | React + **Vite**, Recharts, Supabase (auth + history), Tailwind |
| **VIN data** | NHTSA + Vehicle Databases APIs (separate FastAPI service) |

---

## Modules

| File | Role |
|------|------|
| `main.py` | FastAPI backend; orchestrates the 7-step pipeline in a background thread. |
| `call_veridrive.py` | Places the verification call: registers the call with Retell (injecting dynamic variables), dials the seller via Twilio over SIP, polls until the call ends, waits for the recording, returns the transcript. Detects voicemail / no-answer / rejected. |
| `question_generator.py` | Runs **before** the call. Uses Gemini to generate car-specific questions and Vera's spoken lines, then flattens them into Retell dynamic variables. Includes deterministic fallbacks and **5-key Gemini auto-failover**. |
| `transcript_analyzer.py` | Uses Gemini to score the call transcript → seller credibility (0–100), extracted VIN, claims, hesitation. This is the score the pipeline uses. |
| `audio_analyzer.py` | Optional deeper tool — analyses the actual audio recording (tone, hesitation), not just the text. Shares the same scoring bands. |
| `dubizzle_scraper.py` | Playwright scraper for the listing; dismisses pop-ups (some via Gemini). |
| `price_engine.py` | Scrapes comparable listings and computes market median, price gap %, fairness score, and a recommended price range. |
| `trust_score_engine.py` | Combines the sub-scores into the composite Trust Score, redistributes weights when data is missing, and detects claim discrepancies. |
| `vincheck-uae/` | Separate FastAPI service (port 8001) for VIN title/salvage/history lookups. |
| `veridrive-frontend/` | React + Vite single-page app that submits the URL and renders the report. |
| `test_call.py` | Standalone end-to-end test with fake "scraped" data (no scraper needed). |

---

## Vera — the Retell Voice Agent

Vera is a Retell conversation-flow agent. All of her *spoken* content is generated per-listing by `question_generator.py` and injected at call time via Retell's `retell_llm_dynamic_variables`. The agent prompt itself only *delivers* those variables — this keeps the rigid agent reliable and the phrasing fresh every call.

**Dynamic variables injected into the agent:**

`opening_line` · `buyer_hook` · `car_name` · `car_short` · `car_summary` · `seller_name` · `claim_questions` · `gap_questions` · `suspicious_questions` · `end_call_summary_prompt`

The call flows in three phases (three prompt "parts" in Retell):

<details>
<summary><b>Part 1 — Opener</b></summary>

```
Speak ONLY the lines in "quotes" below (with their {{variables}}). Every other line is guidance — never read it aloud.

You are Vera, a real person calling a used-car seller for a buyer. Warm, casual, natural. Never say you're an AI. Never open with the seller's name. Name the car once at the start, then just say "it" or "the car" — never keep repeating the full name.

Turn 1 — say only this, then stop and listen:
"{{opening_line}}"

Turn 2 — after they answer, say only this, then stop and listen:
"{{buyer_hook}}"

If they're happy to talk, go to the questions.

If they're busy, say:
"No worries at all — when's a better time to reach you?"
Then thank them and end.

If they ask who you are or how you got their number, say:
"A buyer saw your {{car_short}} listed and asked me to check a couple of quick things before he comes to see it."

If it's not the seller, say:
"Ah — could I reach whoever's selling the {{car_short}}? Or I can call back another time."

Never say: "verification", "platform", "VeriDrive", "regarding your vehicle", "I saw your listing".
```
</details>

<details>
<summary><b>Part 2 — Verification questions</b></summary>

```
Speak ONLY the lines in "quotes" and the questions inside {{claim_questions}}, {{gap_questions}}, {{suspicious_questions}}. Every other line is guidance — never read it aloud.

You're having a quick, friendly chat about the car for the buyer. Only gathering honest details — never selling, never pushy. Refer to it as "it" or "the car" almost always; only once in a while "the {{car_short}}". Never repeat the full name.

Ask these one at a time, in a natural order, never as a list. React warmly to each answer before the next. Skip anything they already answered.

What the ad claims:
{{claim_questions}}

What the ad didn't mention:
{{gap_questions}}

Anything worth a closer look:
{{suspicious_questions}}

Now and then, tie an answer back to the buyer so it feels like a real sale, not a survey — say:
"He'll be really glad to hear that."

If an answer isn't clear, ask once more, simply. If they still don't know, say "no problem" and move on. Keep each question short. Never ask the same thing more than twice.

If they get hesitant, ease off — say:
"Totally fine — he just likes to know what he's coming to see."
If they still want to stop, thank them and wrap up.
```
</details>

<details>
<summary><b>Part 3 — Recap & close</b></summary>

```
Speak ONLY the lines in "quotes" below (with their {{variables}}). Every other line is guidance — never read it aloud.

When the questions are done, wrap up warmly — don't drag it out.

To confirm, say (this is the one place you say the full details):
"Perfect — so just to make sure I've got it right: this is the {{car_summary}}, and {{end_call_summary_prompt}}. Does that all sound right?"

If they correct something, fix only that one detail and say it back once. Don't repeat the whole recap.

To close, say:
"Great — that's everything he needed. He'll likely reach out directly to come and see it. Really appreciate your time!"

Vary the exact closing words each call. You may use their first name once here if you have it: {{seller_name}}. After the final thank-you, pause briefly, then end the call.
```
</details>

---

## Trust score methodology

The composite Trust Score (0–100) is a weighted blend of three sub-scores (`trust_score_engine.py`). If a signal is unavailable, its weight is redistributed across the rest.

| Sub-score | Weight | Source |
|-----------|--------|--------|
| Seller credibility | **35%** | The AI call (`transcript_analyzer.py`) |
| Price fairness | **30%** | Market comparables (`price_engine.py`) |
| VIN history | **35%** | VIN lookup (`vincheck-uae/`) |

The engine also cross-checks claims across sources (e.g. ad says "no accidents" but the VIN shows a salvage title → red flag).

---

## Getting started

### Prerequisites
- **Python 3.12**
- **Node.js** (for the frontend)
- Accounts / keys for Retell, Twilio, and Google Gemini

### 1. Backend (Python 3.12)

```bash
# from the project root
py -3.12 -m pip install fastapi uvicorn twilio requests python-dotenv google-genai playwright anthropic
py -3.12 -m playwright install chromium      # for the scraper

# configure secrets (see below)
cp .env.example .env      # then fill in your keys

# run the API (port 8000)
py -3.12 main.py
```

### 2. VIN service (Python 3.12, separate terminal)

```bash
cd vincheck-uae/backend
py -3.12 main.py          # runs on port 8001
```

### 3. Frontend (Vite)

```bash
cd veridrive-frontend/veridrive-frontend
npm install
npm run dev               # Vite dev server (proxies /api/* → backend on :8000)
```

Open the frontend, paste a Dubizzle listing URL, and watch the report build.

### Quick test without the scraper

```bash
py -3.12 test_call.py                 # calls TEST_NUMBER with fake listing data
py -3.12 test_call.py +9715XXXXXXXX   # or a specific number
```

---

## Environment variables

Create a `.env` in the project root (git-ignored). Never commit real keys.

| Variable | Purpose |
|----------|---------|
| `RETELL_API_KEY` | Retell API key |
| `RETELL_AGENT_ID` | The "Vera" agent ID |
| `RETELL_PUBLIC_KEY`, `RETELL_CF_ID` | Retell public key / conversation-flow ID |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` | Twilio credentials |
| `FROM_NUMBER` | Twilio phone number to call from |
| `GEMINI_API_KEY` | Primary Gemini key |
| `GEMINI_API_KEY_2` … `GEMINI_API_KEY_5` | Extra Gemini keys — used automatically on quota exhaustion (auto-failover) |
| `VINCHECK_URL` | Base URL of the VIN service (default `http://localhost:8001`) |
| `TEST_NUMBER` | Number used by `test_call.py` |

---

## Team

_To be added._

---

<sub>Built for BCS 410. VeriDrive is a student project; the voice agent calls only listings/numbers the user submits.</sub>
