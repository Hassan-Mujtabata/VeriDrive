"""
call_veridrive.py — VeriDrive Outbound Call Module
===================================================
Handles ONLY the call pipeline:
  1. Generate questions from listing (Step 0, if listing provided)
  2. Register call with Retell (attach dynamic variables)
  3. Twilio places outbound call to seller
  4. Poll Retell until call ends
  5. Smart-wait for recording_url (learns timing, saves to veridrive_timing.json)
  6. Return combined payload dict → FastAPI stores/forwards it

Analysis is handled separately in audio_analyzer.py

Usage as module (FastAPI):
    from call_veridrive import make_verification_call
    result = make_verification_call(seller_number, listing=listing_dict)

CLI test (backwards compat):
    python call_veridrive.py +971XXXXXXXXX
"""

import os, json, time, requests, logging, sys
from datetime import datetime
from twilio.rest import Client
from dotenv import load_dotenv

log = logging.getLogger("veridrive")
if not log.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "veridrive.log"),
                encoding="utf-8"
            ),
            logging.StreamHandler(sys.stdout),
        ],
    )

load_dotenv()

# ── Credentials ───────────────────────────────────────────────────────────────
RETELL_API_KEY  = os.getenv("RETELL_API_KEY")
RETELL_AGENT_ID = os.getenv("RETELL_AGENT_ID")
TWILIO_SID      = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN    = os.getenv("TWILIO_AUTH_TOKEN")
FROM_NUMBER     = os.getenv("FROM_NUMBER")

RETELL_HEADERS = {
    "Authorization": f"Bearer {RETELL_API_KEY}",
    "Content-Type":  "application/json",
}

# ── Recording Wait Constants ──────────────────────────────────────────────────
RECORDING_DEFAULT_WAIT  = 15   # seconds fallback
RECORDING_POLL_INTERVAL = 3    # seconds between checks
RECORDING_MAX_WAIT      = 120  # give up after 2 minutes
TIMING_STATE_FILE       = "veridrive_timing.json"


# ── Timing Persistence ────────────────────────────────────────────────────────

def load_timing_state() -> dict:
    """Load saved average recording wait time from previous runs."""
    if os.path.exists(TIMING_STATE_FILE):
        try:
            with open(TIMING_STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"avg_wait_s": RECORDING_DEFAULT_WAIT, "sample_count": 0, "observations": []}


def save_timing_state(state: dict, new_wait_s: float) -> float:
    """Update rolling average with new observation, save, return new average."""
    obs = state.get("observations", [])
    obs.append(round(new_wait_s, 1))
    obs = obs[-10:]  # keep last 10 only
    avg = round(sum(obs) / len(obs), 1)
    state.update({
        "observations":  obs,
        "avg_wait_s":    avg,
        "sample_count":  state.get("sample_count", 0) + 1,
        "last_updated":  datetime.now().isoformat(),
    })
    try:
        with open(TIMING_STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass
    return avg


# ── Retell Helper ─────────────────────────────────────────────────────────────

def get_call_info(call_id: str) -> dict:
    """Fetch latest call data from Retell."""
    r = requests.get(
        f"https://api.retellai.com/v2/get-call/{call_id}",
        headers=RETELL_HEADERS,
    )
    r.raise_for_status()
    return r.json()


# ── Smart Recording Wait ──────────────────────────────────────────────────────

def wait_for_recording(call_id: str, timing_state: dict) -> tuple:
    """
    Polls Retell until recording_url appears for this specific call.
    Learns from previous runs how long it usually takes.
    Returns (recording_url or None, seconds_waited).
    """
    avg_expected = timing_state.get("avg_wait_s", RECORDING_DEFAULT_WAIT)
    sample_count = timing_state.get("sample_count", 0)

    log.info(f"\n⏳ Waiting for recording to appear...")
    if sample_count > 0:
        log.info(f"   Expected ~{avg_expected}s (based on {sample_count} previous calls)")
    else:
        log.info(f"   First run — using default {RECORDING_DEFAULT_WAIT}s baseline")

    start = time.time()

    while True:
        elapsed = time.time() - start

        if elapsed > RECORDING_MAX_WAIT:
            log.warning(f"   ⚠️  Gave up after {RECORDING_MAX_WAIT}s — no recording")
            return None, elapsed

        info          = get_call_info(call_id)
        recording_url = info.get("recording_url")

        if recording_url:
            waited = round(time.time() - start, 1)
            log.info(f"   ✅ Recording available after {waited}s")
            if sample_count > 0:
                diff      = waited - avg_expected
                direction = "faster" if diff < 0 else "slower"
                log.info(f"   📊 {abs(diff):.1f}s {direction} than expected")
            return recording_url, waited

        log.info(f"   Checking... {elapsed:.0f}s elapsed (expected ~{avg_expected}s)")
        time.sleep(RECORDING_POLL_INTERVAL)


VOICEMAIL_PHRASES = [
    "leave a message", "leave your message", "not available",
    "please press", "after the tone", "after the beep",
    "voicemail", "voice mail", "record your message",
    "no one is available", "cannot take your call",
]

NO_ANSWER_MAX_DURATION = 15  # seconds — call under this = not picked up


def _is_voicemail(transcript: str) -> bool:
    if not transcript:
        return False
    t = transcript.lower()
    return any(phrase in t for phrase in VOICEMAIL_PHRASES)

def _error_payload(error_msg, seller_number, seller_name, **kwargs) -> dict:
    base = {
        "success":       False,
        "error":         error_msg,
        "seller_number": seller_number,
        "seller_name":   seller_name,
        "timestamp":     datetime.now().isoformat(),
    }
    base.update(kwargs)
    return base


# ── Main Function ─────────────────────────────────────────────────────────────

def make_verification_call(
    seller_number: str,
    seller_name: str = None,
    listing: dict = None,
    dynamic_variables: dict = None,
    max_duration_s: int = 240,
) -> dict:
    """
    Full call pipeline. Returns payload dict for FastAPI.
    Audio analysis is done separately via audio_analyzer.py

    Args:
        seller_number:     e.g. "+971501234567" from scraper
        seller_name:       optional, for logging
        listing:           scraped listing dict (if provided, generates questions)
        dynamic_variables: pre-built vars (for CLI backwards compat)

    Returns dict with:
        call_id, transcript, recording_url, recording_wait_s, duration_s, etc.
    """

    log.info("=" * 50)
    log.info("  VeriDrive — Verification Call")
    log.info("=" * 50)
    if seller_name:
        log.info(f"  Seller : {seller_name}")
    log.info(f"  Number : {seller_number}")
    log.info("=" * 50)

    timing_state = load_timing_state()

    # ── Step 0: Generate questions (if listing provided) ──────────────────────
    if listing and dynamic_variables is None:
        from question_generator import generate_questions, to_retell_dynamic_variables
        log.info("\n🤖 Step 0 — Generating context-aware questions...")
        try:
            questions = generate_questions(listing)
            # Pass the listing too so car_name / car_summary / opening_line are
            # always filled deterministically even if Gemini leaves them blank.
            dynamic_variables = to_retell_dynamic_variables(questions, listing)
            log.info(f"   ✅ Questions generated")
        except Exception as e:
            return _error_payload(
                f"Question generation failed: {str(e)}",
                seller_number, seller_name,
            )

    # ── Step 1: Register with Retell ──────────────────────────────────────────
    log.info("\n📋 Step 1 — Registering call with Retell...")

    payload = {
        "agent_id":            RETELL_AGENT_ID,
        "from_number":         FROM_NUMBER,
        "to_number":           seller_number,
        "direction":           "outbound",
        "max_duration_seconds": max_duration_s,
    }

    if dynamic_variables:
        # Retell's documented field is `retell_llm_dynamic_variables` — this is what
        # fills {{opening_line}}, {{claim_questions}}, etc. in the agent prompt.
        # (Sending the wrong key silently drops every variable → generic opener.)
        payload["retell_llm_dynamic_variables"] = dynamic_variables
        log.info(f"   ✅ Dynamic variables attached: {list(dynamic_variables.keys())}")
    else:
        log.info(f"   ⚠️  No dynamic variables — Vera uses generic questions")

    resp = requests.post(
        "https://api.retellai.com/v2/register-phone-call",
        headers=RETELL_HEADERS,
        json=payload,
    )

    if resp.status_code not in (200, 201):
        return _error_payload(
            f"Retell registration failed: {resp.status_code} — {resp.text}",
            seller_number, seller_name,
        )

    call_data = resp.json()
    call_id   = call_data.get("call_id")

    if not call_id:
        return _error_payload(
            f"No call_id returned: {call_data}",
            seller_number, seller_name,
        )

    sip_uri = f"sip:{call_id}@sip.retellai.com"
    log.info(f"   ✅ Registered — Call ID: {call_id}")
    log.info(f"   ⏳ Waiting 5s for Retell SIP to be ready...")
    time.sleep(5)

    # ── Step 2: Twilio dials seller ───────────────────────────────────────────
    RETELL_CHECK_WAIT = 30   # seconds to wait before checking if Retell saw the call
    RETRY_WAIT        = 30   # seconds to wait before retrying

    def _dial(attempt: int):
        log.info(f"\n📞 Step 2 — Calling {seller_number} (attempt {attempt})...")
        twilio_client = Client(TWILIO_SID, TWILIO_TOKEN)
        tc = twilio_client.calls.create(
            to=seller_number,
            from_=FROM_NUMBER,
            twiml=f'<Response><Dial><Sip>{sip_uri}</Sip></Dial></Response>',
            timeout=30,
        )
        log.info(f"   ✅ Twilio SID: {tc.sid}")
        return tc

    def _retell_received_call(cid: str) -> bool:
        try:
            info = get_call_info(cid)
            status = info.get("call_status", "")
            return bool(status and status != "unknown")
        except Exception:
            return False

    twilio_call = _dial(1)

    # Wait 30s then check if Retell ever saw this call
    log.info(f"   Checking if Retell received the call in {RETELL_CHECK_WAIT}s...")
    _quick = get_call_info(call_id)
    _quick_status = _quick.get("call_status", "")
    if _quick_status in {"ended", "error"}:
        log.info(f"   ⚡ Call already ended ({_quick_status}) — skipping 30s wait")
    else:
        time.sleep(RETELL_CHECK_WAIT)

    if not _retell_received_call(call_id):
        log.warning(f"   ⚠️  Retell has no record of call — Twilio/SIP failed to connect")
        log.info(f"   ⏳ Waiting {RETRY_WAIT}s before retry...")
        time.sleep(RETRY_WAIT)

        # Re-register with Retell for a fresh call_id
        log.info("\n📋 Re-registering call with Retell for retry...")
        retry_payload = {
            "agent_id":             RETELL_AGENT_ID,
            "from_number":          FROM_NUMBER,
            "to_number":            seller_number,
            "direction":            "outbound",
            "max_duration_seconds": max_duration_s,
        }
        if dynamic_variables:
            retry_payload["retell_llm_dynamic_variables"] = dynamic_variables

        retry_resp = requests.post(
            "https://api.retellai.com/v2/register-phone-call",
            headers=RETELL_HEADERS,
            json=retry_payload,
        )
        if retry_resp.status_code in (200, 201):
            retry_data = retry_resp.json()
            new_call_id = retry_data.get("call_id")
            if new_call_id:
                call_id = new_call_id
                sip_uri = f"sip:{call_id}@sip.retellai.com"
                twilio_call = _dial(2)
                log.info(f"   ✅ Retry registered — new Call ID: {call_id}")
            else:
                log.info("   ❌ Retry registration returned no call_id — skipping retry")
        else:
            log.error(f"   ❌ Retry registration failed: {retry_resp.status_code} — skipping")

    log.info(f"   Waiting for call to complete...\n")

    # ── Step 3: Poll until call ends ──────────────────────────────────────────
    log.info("📊 Step 3 — Monitoring call...")
    TERMINAL    = {"ended", "error"}
    MAX_POLL_S  = 300  # 5 min hard cap — Retell max_duration is 4 min so this is safe
    poll_start  = time.time()
    last_status = None

    while True:
        if time.time() - poll_start > MAX_POLL_S:
            log.warning(f"   ⚠️  Poll timeout after {MAX_POLL_S}s — ending monitoring")
            status = "error"
            break
        try:
            info   = get_call_info(call_id)
            status = info.get("call_status", "unknown")
        except Exception as e:
            log.warning(f"   ⚠️  get_call_info failed: {e} — retrying in 5s")
            time.sleep(5)
            continue
        if status != last_status:
            log.info(f"   Status: {status}")
            last_status = status
        if status in TERMINAL:
            break
        time.sleep(5)

    transcript = info.get("transcript", "")
    duration   = info.get("duration_ms", 0) // 1000
    log.info(f"\n\n   ✅ Call ended — Status: {status} | Duration: {duration}s")

    if status != "ended":
        call_outcome = "rejected" if duration < NO_ANSWER_MAX_DURATION else "failed"
        log.warning(f"Call {call_outcome} — Status: {status} | Duration: {duration}s")
        return {
            "success":           True,
            "call_id":           call_id,
            "twilio_sid":        twilio_call.sid,
            "seller_number":     seller_number,
            "seller_name":       seller_name,
            "call_status":       status,
            "call_outcome":      call_outcome,
            "duration_s":        duration,
            "transcript":        transcript,
            "recording_url":     None,
            "recording_wait_s":  None,
            "dynamic_variables": dynamic_variables,
            "timestamp":         datetime.now().isoformat(),
            "audio_analysis":    None,
        }

    # ── Voicemail / no-answer detection ──────────────────────────────────────
    if _is_voicemail(transcript):
        log.info(f"   📭 Voicemail detected — ending call early")
        return {
            "success":           True,
            "call_id":           call_id,
            "twilio_sid":        twilio_call.sid,
            "seller_number":     seller_number,
            "seller_name":       seller_name,
            "call_status":       "voicemail",
            "call_outcome":      "voicemail",
            "duration_s":        duration,
            "transcript":        transcript,
            "recording_url":     None,
            "recording_wait_s":  None,
            "dynamic_variables": dynamic_variables,
            "timestamp":         datetime.now().isoformat(),
            "audio_analysis":    None,
        }

    if duration < NO_ANSWER_MAX_DURATION:
        log.info(f"   📵 Call not answered — duration {duration}s under threshold")
        return {
            "success":           True,
            "call_id":           call_id,
            "twilio_sid":        twilio_call.sid,
            "seller_number":     seller_number,
            "seller_name":       seller_name,
            "call_status":       "not_answered",
            "call_outcome":      "not_answered",
            "duration_s":        duration,
            "transcript":        transcript,
            "recording_url":     None,
            "recording_wait_s":  None,
            "dynamic_variables": dynamic_variables,
            "timestamp":         datetime.now().isoformat(),
            "audio_analysis":    None,
        }

    # ── Step 4: Smart wait for recording ─────────────────────────────────────
    log.info(f"\n🎙️  Step 4 — Waiting for recording...")
    recording_url, recording_wait_s = wait_for_recording(call_id, timing_state)
    new_avg = save_timing_state(timing_state, recording_wait_s)
    log.info(f"   📊 Updated average wait: {new_avg}s saved to {TIMING_STATE_FILE}")

    # ── Return payload ────────────────────────────────────────────────────────
    log.info(f"\n✅ Call complete — returning payload to FastAPI")
    log.info(f"   Run audio_analyzer.py --call_id {call_id} to analyze recording\n")

    return {
        "success":              True,
        "call_id":              call_id,
        "twilio_sid":           twilio_call.sid,
        "seller_number":        seller_number,
        "seller_name":          seller_name,
        "agent_id":             RETELL_AGENT_ID,
        "call_status":          status,
        "duration_s":           duration,
        "transcript":           transcript,
        "recording_url":        recording_url,
        "recording_wait_s":     recording_wait_s,
        "avg_recording_wait_s": new_avg,
        "dynamic_variables":    dynamic_variables,
        "timestamp":            datetime.now().isoformat(),
        "audio_analysis":       None,  # filled in by audio_analyzer.py
    }


# ── Standalone test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from question_generator import generate_questions, to_retell_dynamic_variables

    test_number = sys.argv[1] if len(sys.argv) > 1 else os.getenv("TEST_NUMBER")

    if not test_number:
        log.info("❌ Provide a number: python call_veridrive.py +971XXXXXXXXX")
        sys.exit(1)

    demo_listing = {
        "make": "Toyota", "model": "Corolla", "year": 2019,
        "mileage_km": 95000, "asking_price_aed": 28000,
        "description": "First owner, no accidents, GCC spec.",
    }

    log.info("\n🤖 Generating context-aware questions...")
    questions    = generate_questions(demo_listing)
    dynamic_vars = to_retell_dynamic_variables(questions, demo_listing)

    result = make_verification_call(
        seller_number=test_number,
        seller_name="Test Seller",
        dynamic_variables=dynamic_vars,
    )

    log.info("\n── Result ─────────────────────────────────")
    for k, v in result.items():
        if k not in ("transcript", "dynamic_variables"):
            log.info(f"  {k}: {v}")
    log.info(f"\n  transcript: {result.get('transcript', '')[:200]}...")
