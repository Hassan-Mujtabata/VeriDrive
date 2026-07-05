"""
main.py — VeriDrive FastAPI Backend
====================================
Run with: python main.py
API runs at http://localhost:8000
Frontend proxies /api/* → this server (Vite strips /api prefix).

Full pipeline:
  Step 1    — scrape_listing()                                  [dubizzle_scraper.py]
  Steps 2+3 — make_verification_call() + price analysis         [parallel]
  Step 4    — analyze_transcript()                              [transcript_analyzer.py]
  Step 5    — VIN lookup via VinCheck UAE                       [vincheck-uae/backend/main.py → :8001]
  Step 6    — compute_trust_score()                             [trust_score_engine.py]
  Step 7    — build final report dict → frontend polls it
"""

import asyncio
import uuid, threading, os, sys, logging, traceback
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# ── Logger ────────────────────────────────────────────────────────────────────
_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "veridrive.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(_LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("veridrive")
log.info(f"VeriDrive started — logging to {_LOG_FILE}")

# ── Sub-project paths ─────────────────────────────────────────────────────────
_BASE = os.path.dirname(os.path.abspath(__file__))

_SCRAPER_DIR = os.path.join(_BASE, "veridrive-scraper-v2",      "veridrive-scraper")
_PRICE_DIR   = os.path.join(_BASE, "veridrive-price-engine-v8", "veridrive-price-engine")
_TRUST_DIR   = os.path.join(_BASE, "veridrive-trust-score-v2",  "veridrive-trust-score")

for _p in [_SCRAPER_DIR, _PRICE_DIR, _TRUST_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(title="VeriDrive API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

reports: dict = {}

class VerifyRequest(BaseModel):
    listing_url: str

# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.post("/verify")
def verify(req: VerifyRequest):
    request_id = str(uuid.uuid4())
    reports[request_id] = {"request_id": request_id, "status": "processing"}
    threading.Thread(
        target=_run_pipeline,
        args=(request_id, req.listing_url),
        daemon=True,
    ).start()
    return {"request_id": request_id}


@app.get("/report/{request_id}")
def get_report(request_id: str):
    if request_id not in reports:
        raise HTTPException(status_code=404, detail="Report not found")
    return reports[request_id]


@app.get("/health")
def health():
    return {"status": "ok"}


# ── Pipeline ──────────────────────────────────────────────────────────────────
def _run_pipeline(request_id: str, listing_url: str):
    log.info(f"[pipeline:{request_id}] Starting — URL: {listing_url}")
    try:
        from call_veridrive      import make_verification_call
        from dubizzle_scraper    import scrape_listing
        from price_engine        import scrape_comparables, compute_analysis, MIN_COMPARABLES
        from transcript_analyzer import analyze_transcript
        from trust_score_engine  import compute_trust_score

        # ── Step 1: Scrape listing ─────────────────────────────────────────
        log.info(f"[pipeline:{request_id}] Step 1 — Scraping listing...")
        try:
            listing       = asyncio.run(scrape_listing(listing_url))
            seller_number = listing["seller_phone"]
            seller_name   = listing.get("seller_name", "Seller")
            log.info(f"[pipeline:{request_id}] Scraped: {listing.get('year')} {listing.get('make')} {listing.get('model')}")
        except Exception as e:
            log.error(f"[pipeline:{request_id}] Step 1 FAILED — Scraper crashed:\n{traceback.format_exc()}")
            _set_error(request_id, f"Scraper failed: {e}")
            return

        # ── Steps 2 & 3: Call + Price analysis (parallel) ─────────────────
        # Price engine scrapes Dubizzle (~30-60s); call takes 2-5 min.
        # Running both at once saves significant wall-clock time.
        print("[pipeline] Steps 2 & 3 — Call and price analysis running in parallel...")

        def _call():
            return make_verification_call(
                seller_number=seller_number,
                seller_name=seller_name,
                listing=listing,
                max_duration_s=240,
            )

        def _price():
            try:
                comparables = asyncio.run(scrape_comparables(
                    make=listing.get("make"),
                    model=listing.get("model"),
                    target_year=listing.get("year"),
                    target_mileage=listing.get("mileage_km"),
                ))
                if len(comparables) < MIN_COMPARABLES:
                    print("[pipeline] ⚠️  Not enough comparables found — continuing without price analysis")
                    return None
                return compute_analysis(
                    comparables=comparables,
                    asking_price=listing.get("asking_price_aed"),
                    make=listing.get("make"),
                    model=listing.get("model"),
                    target_year=listing.get("year"),
                    target_mileage=listing.get("mileage_km"),
                )
            except Exception as e:
                print(f"[pipeline] ⚠️  Price analysis failed: {e} — continuing without it")
                return None

        with ThreadPoolExecutor(max_workers=2) as executor:
            future_call  = executor.submit(_call)
            future_price = executor.submit(_price)
            call_result  = future_call.result()
            price_result = future_price.result()

        if not call_result.get("success"):
            log.error(f"[pipeline:{request_id}] Call failed: {call_result.get('error')}")
            _set_error(request_id, call_result.get("error", "Call failed"), listing)
            return

        call_outcome = call_result.get("call_outcome") or (
            "completed" if call_result.get("call_status") == "ended" else call_result.get("call_status")
        )
        log.info(f"[pipeline:{request_id}] Call outcome: {call_outcome} | duration: {call_result.get('duration_s')}s")

        # ── Voicemail / no-answer / rejected — skip analysis, surface as red flag ──
        if call_outcome in ("voicemail", "not_answered", "rejected", "failed"):
            label = {
                "not_answered": "Seller did not answer",
                "voicemail":    "Call went to voicemail",
                "rejected":     "Seller rejected the call",
                "failed":       "Call failed to connect",
            }.get(call_outcome, "Call unsuccessful")
            log.warning(f"[pipeline:{request_id}] {label} — stopping pipeline")
            reports[request_id] = {
                "request_id": request_id,
                "status":     "complete",
                "listing": {
                    "make":             listing.get("make"),
                    "model":            listing.get("model"),
                    "year":             listing.get("year"),
                    "mileage_km":       listing.get("mileage_km"),
                    "asking_price_aed": listing.get("asking_price_aed"),
                    "description":      listing.get("description"),
                    "seller_name":      seller_name,
                    "seller_phone":     seller_number,
                    "emirate":          listing.get("emirate"),
                    "listing_url":      listing_url,
                    "photos":           listing.get("photos", []),
                },
                "trust_score":    None,
                "price_analysis": None,
                "vin_report":     None,
                "red_flags":      [label],
                "voice_call": {
                    "available":                False,
                    "call_outcome":             call_outcome,
                    "duration_seconds":         call_result.get("duration_s"),
                    "seller_credibility_score": None,
                    "transcript_summary":       None,
                },
                "_raw_call": {
                    "call_id":          call_result.get("call_id"),
                    "recording_url":    None,
                    "recording_wait_s": None,
                },
            }
            print(f"[pipeline] ⚠️  {label} — report saved, pipeline stopped")
            return
        # ── Step 4: Analyze transcript ─────────────────────────────────────
        log.info(f"[pipeline:{request_id}] Step 4 — Analyzing transcript...")
        try:
            transcript = call_result.get("transcript", "")
            analysis   = analyze_transcript(transcript, listing)
        except Exception as e:
            log.error(f"[pipeline:{request_id}] Step 4 FAILED — Transcript analysis crashed:\n{traceback.format_exc()}")
            analysis = {}

        voice_data = {
            "available":                True,
            "call_outcome":             call_outcome,
            "duration_seconds":         call_result.get("duration_s"),
            "seller_credibility_score": analysis.get("seller_credibility_score"),
        }

        # ── Step 5: VIN lookup via VinCheck UAE (teammates' service) ─────
        vin_to_check = analysis.get("vin_extracted")
        vin_data     = None

        if vin_to_check:
            print(f"[pipeline] Step 5 — VIN {vin_to_check} extracted — querying VinCheck...")
            try:
                import requests as _req
                vincheck_url = os.getenv("VINCHECK_URL", "http://localhost:8001")
                r = _req.get(
                    f"{vincheck_url}/api/check-vehicle/{vin_to_check}",
                    timeout=30,
                )
                if r.status_code == 200:
                    raw = r.json()
                    title   = raw.get("title_check") or {}
                    salvage = title.get("salvage", False)
                    details = title.get("salvage_details", [])
                    cause   = details[0].get("cause", "") if details else ""

                    vin_data = {
                        "available":       True,
                        "vin":             vin_to_check,
                        "data_source":     "VinCheck / Vehicle Databases",
                        "accident_count":  1 if salvage else 0,
                        "ownership_count": None,
                        "title_status":    "Salvage" if salvage else "Clean",
                        "theft_record":    False,
                        "salvage_cause":   cause,
                        "nhtsa_decode":    raw.get("nhtsa_decode"),
                        "vd_decode":       raw.get("vehicledatabases_decode"),
                    }
                    print(f"[pipeline] ✅ VIN lookup complete — title: {vin_data['title_status']}")
                else:
                    print(f"[pipeline] ⚠️  VinCheck returned {r.status_code} — continuing without VIN data")
            except Exception as e:
                print(f"[pipeline] ⚠️  VIN lookup failed: {e} — continuing without VIN data")
        else:
            print("[pipeline] Step 5 — No VIN extracted from transcript")

        # ── Step 6: Trust score ────────────────────────────────────────────
        log.info(f"[pipeline:{request_id}] Step 6 — Computing trust score...")
        try:
            trust = compute_trust_score(
                listing_data=listing,
                price_data=price_result,
                vin_data=vin_data,
                voice_data=voice_data,
            )
        except Exception as e:
            log.error(f"[pipeline:{request_id}] Step 6 FAILED — Trust score crashed:\n{traceback.format_exc()}")
            trust = {}

        # ── Step 7: Build final report ─────────────────────────────────────
        reports[request_id] = {
            "request_id": request_id,
            "status":     "complete",
            "listing": {
                "make":             listing.get("make"),
                "model":            listing.get("model"),
                "year":             listing.get("year"),
                "mileage_km":       listing.get("mileage_km"),
                "asking_price_aed": listing.get("asking_price_aed"),
                "description":      listing.get("description"),
                "seller_name":      seller_name,
                "seller_phone":     seller_number,
                "emirate":          listing.get("emirate"),
                "listing_url":      listing_url,
                "photos":           listing.get("photos", []),
            },
            "trust_score": {
                "composite_score":             trust.get("composite_score"),
                "seller_credibility_subscore": trust.get("seller_credibility_subscore"),
                "price_fairness_subscore":     trust.get("price_fairness_subscore"),
                "vin_history_subscore":        trust.get("vin_history_subscore"),
                "recommendation":              trust.get("recommendation"),
            },
            "price_analysis": price_result and {
                "comparable_count":         price_result.get("comparable_count"),
                "median_market_price":      price_result.get("normalized_median_aed"),
                "asking_price_aed":         listing.get("asking_price_aed"),
                "price_difference_percent": price_result.get("price_difference_percent"),
                "fairness_score":           price_result.get("fairness_score"),
                "recommended_min_aed":      price_result.get("recommended_min_aed"),
                "recommended_max_aed":      price_result.get("recommended_max_aed"),
            },
            "vin_report":  vin_data,
            "red_flags":   trust.get("red_flags", []),
            "voice_call": {
                "available":                True,
                "call_outcome":             call_outcome,
                "duration_seconds":         call_result.get("duration_s"),
                "seller_credibility_score": analysis.get("seller_credibility_score"),
                "transcript_summary":       transcript[:800],
            },
            "_raw_call": {
                "call_id":          call_result.get("call_id"),
                "recording_url":    call_result.get("recording_url"),
                "recording_wait_s": call_result.get("recording_wait_s"),
            },
        }
        log.info(f"[pipeline:{request_id}] ✅ Done — composite score: {trust.get('composite_score')}")

    except Exception as e:
        log.error(f"[pipeline:{request_id}] UNHANDLED CRASH:\n{traceback.format_exc()}")
        _set_error(request_id, str(e))
    finally:
        # Safety net — if anything left the report stuck as "processing", fix it
        # so the frontend never hangs on a timeout screen
        if reports.get(request_id, {}).get("status") == "processing":
            log.error(f"[pipeline:{request_id}] Report still stuck as processing — forcing error state")
            _set_error(request_id, "Pipeline ended unexpectedly. Check veridrive.log for details.")


def _set_error(request_id: str, message: str, listing: dict = None):
    log.error(f"[pipeline:{request_id}] Error saved to report: {message}")
    reports[request_id] = {
        "request_id": request_id,
        "status":     "error",
        "error":      message,
        "listing":    listing,
    }


# ── Test Call Endpoint ────────────────────────────────────────────────────────
class TestCallRequest(BaseModel):
    phone_number: str

@app.post("/test-call")
def test_call(req: TestCallRequest):
    request_id = str(uuid.uuid4())
    reports[request_id] = {"request_id": request_id, "status": "processing"}
    threading.Thread(
        target=_run_test_call,
        args=(request_id, req.phone_number),
        daemon=True,
    ).start()
    return {"request_id": request_id}


def _run_test_call(request_id: str, phone_number: str):
    try:
        from call_veridrive import make_verification_call
        result = make_verification_call(
            seller_number=phone_number,
            seller_name="Test Seller",
            listing={
                "make": "Toyota", "model": "Corolla", "year": 2019,
                "mileage_km": 95000, "asking_price_aed": 28000,
                "description": "First owner, no accidents, GCC spec.",
            },
            max_duration_s=240,
        )
        reports[request_id] = {
            "request_id": request_id,
            "status": "complete" if result.get("success") else "error",
            **result,
        }
    except Exception as e:
        reports[request_id] = {"request_id": request_id, "status": "error", "error": str(e)}


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
