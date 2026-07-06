"""
audio_analyzer.py — VeriDrive Audio Analysis Module
=====================================================
Handles ONLY audio analysis — separate from call_veridrive.py

Features:
  - First-time setup: pick your preferred Gemini model
  - Auto-fallback: if preferred model fails, tries next automatically
  - Tracks which model failed last time and why
  - List all available recordings from Retell
  - Skip already-analyzed calls (cache)
  - Manually choose which recording to analyze

Usage:
  python audio_analyzer.py                        # interactive list + choose
  python audio_analyzer.py --latest               # analyze most recent
  python audio_analyzer.py --call_id call_xxxx    # analyze one specific call
  python audio_analyzer.py --list                 # just list, no analysis
  python audio_analyzer.py --setup                # re-run model setup

FastAPI usage:
  from audio_analyzer import analyze_call, is_already_analyzed
  if not is_already_analyzed(call_id):
      result = analyze_call(call_id)
"""

import os, io, json, time, argparse, tempfile, requests
from datetime import datetime
from pathlib import Path
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# ── Credentials ───────────────────────────────────────────────────────────────
RETELL_API_KEY = os.getenv("RETELL_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

RETELL_HEADERS = {
    "Authorization": f"Bearer {RETELL_API_KEY}",
    "Content-Type":  "application/json",
}

# Deferred — instantiated lazily in _get_gemini_client() so missing key
# raises a clear RuntimeError at call time, not silently at import time.
_gemini_client = None


def _get_gemini_client() -> genai.Client:
    """Return (and lazily create) the shared Gemini client."""
    global _gemini_client
    if _gemini_client is None:
        if not GEMINI_API_KEY:
            raise RuntimeError(
                "GEMINI_API_KEY environment variable is not set. "
                "Get a key from https://aistudio.google.com/apikey"
            )
        _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    return _gemini_client


def _get_gemini_keys() -> list:
    """All Gemini keys for auto-failover: GEMINI_API_KEY, GEMINI_API_KEY_2..10,
    then comma-separated GEMINI_API_KEYS. Blanks/dupes dropped, order kept."""
    names  = ["GEMINI_API_KEY"] + [f"GEMINI_API_KEY_{i}" for i in range(2, 11)]
    keys   = [os.getenv(n, "").strip() for n in names]
    keys  += [k.strip() for k in os.getenv("GEMINI_API_KEYS", "").split(",")]
    seen, out = set(), []
    for k in keys:
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out


_QUOTA_MARKERS = ("429", "resource_exhausted", "quota", "exceeded", "insufficient")

def _is_quota_error(error_str: str) -> bool:
    e = error_str.lower()
    return any(m in e for m in _QUOTA_MARKERS)


# ── Available Gemini Models ───────────────────────────────────────────────────
# Listed most capable first — we want accuracy, so the default (option 1) is the
# strongest model and fallbacks step down to cheaper ones.
AVAILABLE_MODELS = [
    {
        "id":          "gemini-2.5-flash",
        "name":        "Gemini 2.5 Flash",
        "description": "Most capable. Best accuracy — recommended default.",
        "tier":        "best",
    },
    {
        "id":          "gemini-2.0-flash",
        "name":        "Gemini 2.0 Flash",
        "description": "Strong and reliable. Stable availability.",
        "tier":        "standard",
    },
    {
        "id":          "gemini-2.0-flash-lite",
        "name":        "Gemini 2.0 Flash Lite",
        "description": "Lighter, cheaper fallback.",
        "tier":        "budget",
    },
    {
        "id":          "gemini-2.5-flash-lite",
        "name":        "Gemini 2.5 Flash Lite",
        "description": "Fastest and cheapest. Final fallback.",
        "tier":        "budget",
    },
]

# ── Config and Cache Files ────────────────────────────────────────────────────
MODEL_CONFIG_FILE = "model_config.json"
CACHE_FILE        = "analyzed_calls.json"


# ── Model Config Helpers ──────────────────────────────────────────────────────

def load_model_config() -> dict:
    if os.path.exists(MODEL_CONFIG_FILE):
        try:
            with open(MODEL_CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"setup_complete": False}


def save_model_config(config: dict):
    try:
        with open(MODEL_CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"   Warning: could not save model config: {e}")


def first_time_setup() -> dict:
    print("\n" + "=" * 60)
    print("  First Time Setup — Choose Your Gemini Model")
    print("=" * 60)
    print("  This only runs once. Re-run anytime with --setup\n")

    for i, model in enumerate(AVAILABLE_MODELS, 1):
        print(f"  {i}. {model['name']} [{model['tier']}]")
        print(f"     {model['description']}")
        print(f"     ID: {model['id']}\n")

    print("  Tip: Start with 1. Code auto-tries others if it fails.")
    print("  Press Enter to use default (option 1).\n")

    while True:
        choice = input("  Pick preferred model (1-4) [Enter = default 1]: ").strip()
        if choice == "":
            choice = "1"
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(AVAILABLE_MODELS):
                preferred = AVAILABLE_MODELS[idx]
                break
        except ValueError:
            pass
        print("  Invalid. Enter 1-4 or press Enter for default.")

    fallback = [m["id"] for m in AVAILABLE_MODELS if m["id"] != preferred["id"]]

    config = {
        "setup_complete":        True,
        "preferred_model":       preferred["id"],
        "preferred_model_name":  preferred["name"],
        "fallback_order":        fallback,
        "setup_date":            datetime.now().isoformat(),
        "last_successful_model": None,
        "last_failure":          None,
        "failure_history":       [],
    }

    save_model_config(config)
    print(f"\n  Saved. Preferred: {preferred['name']}")
    print(f"  Fallback order: {' -> '.join(fallback)}")
    print("=" * 60 + "\n")
    return config


def show_last_failure(config: dict):
    last    = config.get("last_failure")
    last_ok = config.get("last_successful_model")
    if last:
        print(f"  Last issue  : {last.get('model')} — {last.get('error_type')}")
        print(f"  When        : {last.get('timestamp', '')[:19]}")
        if last_ok:
            print(f"  Recovered   : fell back to {last_ok}")
    elif last_ok:
        print(f"  Last run    : {last_ok} worked fine")


def get_model_try_order(config: dict) -> list:
    preferred = config.get("preferred_model", AVAILABLE_MODELS[0]["id"])
    fallback  = config.get("fallback_order", [m["id"] for m in AVAILABLE_MODELS[1:]])
    last_ok   = config.get("last_successful_model")
    order     = [preferred]
    if last_ok and last_ok != preferred:
        order.append(last_ok)
    for m in fallback:
        if m not in order:
            order.append(m)
    return order


# ── Analysis Cache Helpers ────────────────────────────────────────────────────

def load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_to_cache(call_id: str, result: dict):
    cache = load_cache()
    cache[call_id] = {
        "analyzed_at":              datetime.now().isoformat(),
        "seller_credibility_score": result.get("seller_credibility_score"),
        "call_worth_pursuing":      result.get("call_worth_pursuing"),
        "model_used":               result.get("model_used"),
        "result":                   result,
    }
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)
        print(f"   Saved to cache: {CACHE_FILE}")
    except Exception as e:
        print(f"   Warning: could not save cache: {e}")


def is_already_analyzed(call_id: str) -> bool:
    return call_id in load_cache()


def get_cached_result(call_id: str) -> dict | None:
    return load_cache().get(call_id)


# ── Retell Helpers ────────────────────────────────────────────────────────────

def get_single_call(call_id: str) -> dict:
    r = requests.get(
        f"https://api.retellai.com/v2/get-call/{call_id}",
        headers=RETELL_HEADERS,
    )
    r.raise_for_status()
    return r.json()


def list_all_calls() -> list:
    # v3 list endpoint supports pagination_key; v2 get-call used for single fetch
    url            = "https://api.retellai.com/v3/list-calls"
    all_calls      = []
    pagination_key = None
    while True:
        body = {"limit": 100}
        if pagination_key:
            body["pagination_key"] = pagination_key
        r = requests.post(url, headers=RETELL_HEADERS, json=body)
        r.raise_for_status()
        data = r.json()
        all_calls.extend(data.get("items", []))
        if not data.get("has_more"):
            break
        pagination_key = data.get("pagination_key")
        if not pagination_key:
            break
    return all_calls


def list_available_recordings() -> list:
    print("Fetching calls from Retell...")
    all_calls  = list_all_calls()
    recordings = [c for c in all_calls if c.get("recording_url")]
    recordings.sort(key=lambda c: c.get("start_timestamp", 0), reverse=True)
    print(f"   Found {len(recordings)} recordings (out of {len(all_calls)} total)")
    return recordings


def display_recordings_list(recordings: list):
    cache = load_cache()
    print("\n" + "=" * 65)
    print("  Available Recordings")
    print("=" * 65)
    if not recordings:
        print("  No recordings found.")
        return
    for i, call in enumerate(recordings, 1):
        call_id  = call.get("call_id", "unknown")
        duration = round(call.get("duration_ms", 0) / 1000)
        ts       = call.get("start_timestamp", 0)
        try:
            dt_str = datetime.fromtimestamp(ts / 1000).strftime("%b %d %I:%M%p")
        except Exception:
            dt_str = "unknown date"
        if call_id in cache:
            score      = cache[call_id].get("seller_credibility_score", "?")
            model_used = cache[call_id].get("model_used", "?")
            status_tag = f"Done — Score: {score}/100 via {model_used}"
        else:
            status_tag = "Not analyzed"
        mins = duration // 60
        secs = duration % 60
        print(f"  {i:2}. [{dt_str}] {mins}:{secs:02d} | {call_id[:35]}... | {status_tag}")
    print("=" * 65)


# ── Audio Download ────────────────────────────────────────────────────────────

def download_recording(recording_url: str, call_id: str) -> str:
    tmp_path = os.path.join(tempfile.gettempdir(), f"{call_id}.wav")
    response = requests.get(recording_url, stream=True, timeout=60)
    response.raise_for_status()
    with open(tmp_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    size_kb = os.path.getsize(tmp_path) / 1024
    print(f"   Downloaded: {size_kb:.1f} KB")
    return tmp_path


# ── Gemini Prompt ─────────────────────────────────────────────────────────────

ANALYSIS_PROMPT = """
You are analyzing a car seller phone call for VeriDrive, a platform that verifies used car listings.

Listen carefully to the audio and return ONLY a valid JSON object — no explanation, no markdown, no extra text.

Return this exact structure:
{
  "seller_credibility_score": <integer 0-100>,
  "vin_mentioned": <string if VIN was spoken, otherwise null>,
  "accident_claim": <string summarizing accident info, or null>,
  "ownership_claim": <string summarizing ownership info, or null>,
  "confidence_level": <"high", "medium", or "low">,
  "hesitation_detected": <true or false>,
  "tone_assessment": <one sentence on seller overall tone>,
  "red_flags": [<list of concerns, empty if none>],
  "call_worth_pursuing": <true or false>,
  "summary": <2-3 sentence plain English summary>
}

Shared VeriDrive scoring band (same as the transcript analyzer, so scores are comparable):
- 80-100: answers directly, consistently, with specific detail; matches the listing
- 60-79:  mostly credible, minor gaps or slight hesitation
- 40-59:  vague, deflecting, or answers that don't quite line up
- 0-39:   contradictions, refusals, or clear red flags
"""


# ── Gemini Analysis with Fallback ─────────────────────────────────────────────

def _build_car_context(car_context: dict | None) -> str:
    """Turn a listing/variables dict into a short reference block for scoring."""
    if not car_context:
        return ""
    lines = ["\n\nReference context (the call was about this car — do not read aloud):"]
    ident = " ".join(str(car_context.get(k)) for k in ("year", "make", "model", "trim")
                      if car_context.get(k))
    if ident.strip():
        lines.append(f"Listing: {ident.strip()}.")
    elif car_context.get("car_summary"):
        lines.append(f"Listing: {car_context.get('car_summary')}.")
    if car_context.get("description"):
        lines.append(f"The ad claimed: {car_context.get('description')}")
    asked = " ".join(
        car_context.get(k, "") for k in
        ("claim_questions", "gap_questions", "suspicious_questions")
    ).strip()
    if asked:
        lines.append(f"The buyer wanted these points covered: {asked}")
    return "\n".join(lines)


def analyze_audio_with_gemini(
    audio_path: str,
    transcript: str = "",
    car_context: dict | None = None,
) -> tuple:
    """
    Rotate over every Gemini API key (out-of-quota keys fall through to the next)
    and, within each key, try each model in order. The audio is re-uploaded per
    key since Gemini files are scoped to the key's project.
    Optionally accepts a car_context dict (listing fields and/or the Retell
    dynamic variables) so the score is grounded in the specific listing.
    Returns (analysis_dict, model_id_used).
    """
    keys = _get_gemini_keys()
    if not keys:
        raise RuntimeError(
            "No Gemini API key found. Add GEMINI_API_KEY (and optionally "
            "GEMINI_API_KEY_2, GEMINI_API_KEY_3, ... for auto-failover) to .env."
        )

    config    = load_model_config()
    try_order = get_model_try_order(config)

    # Read the audio bytes once; each key gets its own upload from these bytes.
    with open(audio_path, "rb") as f:
        audio_raw = f.read()
    audio_name = Path(audio_path).name

    last_error = None

    for key_idx, api_key in enumerate(keys, 1):
        client = genai.Client(api_key=api_key)

        # ── Upload audio to THIS key's project ────────────────────────────────
        print(f"   Uploading audio to Gemini (key {key_idx}/{len(keys)})...")
        try:
            audio_bytes = io.BytesIO(audio_raw)
            audio_bytes.name = audio_name
            uploaded = client.files.upload(
                file=audio_bytes,
                config=types.UploadFileConfig(mime_type="audio/wav"),
            )
            while uploaded.state.name == "PROCESSING":
                time.sleep(2)
                uploaded = client.files.get(name=uploaded.name)
            if uploaded.state.name != "ACTIVE":
                raise RuntimeError(f"upload state {uploaded.state.name}")
        except Exception as e:
            error_str  = str(e)
            last_error = error_str
            if _is_quota_error(error_str):
                print(f"   Key {key_idx} quota/limit on upload — trying next key...")
            else:
                print(f"   Upload failed on key {key_idx}: {error_str[:120]} — trying next key...")
            continue

        contents = [uploaded]
        if transcript:
            contents.append(f"\n\nTranscript for reference:\n{transcript}\n")
        car_block = _build_car_context(car_context)
        if car_block:
            contents.append(car_block)
        contents.append(ANALYSIS_PROMPT)

        try:
            for i, model_id in enumerate(try_order):
                label = "(preferred)" if i == 0 else f"(fallback #{i})"
                print(f"   Key {key_idx} · {model_id} {label}...")

                try:
                    response = client.models.generate_content(
                        model=model_id,
                        contents=contents,
                    )

                    raw = response.text.strip()
                    if raw.startswith("```"):
                        lines = [l for l in raw.split("\n") if not l.strip().startswith("```")]
                        raw   = "\n".join(lines).strip()

                    try:
                        result = json.loads(raw)
                    except json.JSONDecodeError as e:
                        result = {"parse_error": str(e), "raw_response": raw, "seller_credibility_score": None}

                    config["last_successful_model"] = model_id
                    config["last_failure"] = None
                    save_model_config(config)

                    print(f"   Success with {model_id} (key {key_idx})")
                    return result, model_id

                except Exception as e:
                    error_str  = str(e)
                    last_error = error_str

                    if "503" in error_str:
                        error_type = "503 high demand"
                    elif _is_quota_error(error_str):
                        error_type = "429 quota / rate limit"
                    elif "404" in error_str or "NOT_FOUND" in error_str:
                        error_type = "404 model not found"
                    else:
                        error_type = "unknown error"

                    failure_entry = {
                        "model":      model_id,
                        "key_index":  key_idx,
                        "error_type": error_type,
                        "error":      error_str[:300],
                        "timestamp":  datetime.now().isoformat(),
                    }
                    config["last_failure"] = failure_entry
                    history = config.get("failure_history", [])
                    history.append(failure_entry)
                    config["failure_history"] = history[-20:]
                    save_model_config(config)

                    print(f"   {model_id} failed ({error_type}) — trying next...")
                    time.sleep(2)
                    continue

        finally:
            # Always clean up this key's uploaded file before moving on.
            try:
                client.files.delete(name=uploaded.name)
            except Exception:
                pass

    raise RuntimeError(f"All Gemini keys/models exhausted. Last error: {last_error}")


# ── Main Analyze Function ─────────────────────────────────────────────────────

def analyze_call(call_id: str, force: bool = False, car_context: dict | None = None) -> dict:
    if not force and is_already_analyzed(call_id):
        cached = get_cached_result(call_id)
        score  = cached.get("seller_credibility_score", "?")
        print(f"\n Already analyzed (Score: {score}/100) — returning cache.")
        return cached.get("result", cached)

    print(f"\nAnalyzing call: {call_id}")
    print(f"   Fetching from Retell...")

    try:
        call = get_single_call(call_id)
    except Exception as e:
        return {"success": False, "error": str(e), "call_id": call_id}

    recording_url = call.get("recording_url")
    transcript    = call.get("transcript", "")
    duration_ms   = call.get("duration_ms", 0)

    # If no context passed, fall back to the variables Retell stored for the call
    # so a standalone re-analysis still knows which car it was about.
    if car_context is None:
        car_context = call.get("retell_llm_dynamic_variables") or \
                      call.get("collected_dynamic_variables")

    if not recording_url:
        print(f"   No recording available yet for {call_id}")
        return {"success": False, "call_id": call_id, "error": "no recording", "available": False}

    audio_path = None
    try:
        print(f"   Downloading recording...")
        audio_path           = download_recording(recording_url, call_id)
        analysis, model_used = analyze_audio_with_gemini(audio_path, transcript, car_context)
        score                = analysis.get("seller_credibility_score", "N/A")
        print(f"   Done — Score: {score}/100 | Model: {model_used}")

        result = {
            "success":                    True,
            "call_id":                    call_id,
            "available":                  True,
            "duration_s":                 round(duration_ms / 1000),
            "transcript":                 transcript,
            "recording_url":              recording_url,
            "analyzed_at":                datetime.now().isoformat(),
            "model_used":                 model_used,
            "seller_credibility_score":   analysis.get("seller_credibility_score"),
            "vin_mentioned":              analysis.get("vin_mentioned"),
            "accident_claim":             analysis.get("accident_claim"),
            "ownership_claim":            analysis.get("ownership_claim"),
            "confidence_level":           analysis.get("confidence_level"),
            "hesitation_detected":        analysis.get("hesitation_detected"),
            "tone_assessment":            analysis.get("tone_assessment"),
            "red_flags":                  analysis.get("red_flags", []),
            "call_worth_pursuing":        analysis.get("call_worth_pursuing"),
            "summary":                    analysis.get("summary"),
            "raw_analysis":               analysis,
        }

        save_to_cache(call_id, result)
        return result

    except Exception as e:
        print(f"   Error: {e}")
        return {"success": False, "call_id": call_id, "error": str(e)}

    finally:
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)


def analyze_latest() -> dict:
    recordings = list_available_recordings()
    if not recordings:
        print("No recordings found.")
        return {"success": False, "error": "no recordings found"}

    latest  = recordings[0]
    call_id = latest.get("call_id")
    print(f"\nLatest: {call_id}")

    if is_already_analyzed(call_id):
        cached = get_cached_result(call_id)
        score  = cached.get("seller_credibility_score", "?")
        print(f"Already analyzed (Score: {score}/100)")
        print(f"To re-analyze, run interactively and select it.")
        return cached.get("result", cached)

    return analyze_call(call_id, force=False)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="VeriDrive Audio Analyzer")
    parser.add_argument("--call_id", type=str, help="Analyze one specific call ID")
    parser.add_argument("--latest",  action="store_true", help="Analyze most recent recording")
    parser.add_argument("--list",    action="store_true", help="List recordings, no analysis")
    parser.add_argument("--force",   action="store_true", help="Re-analyze even if cached")
    parser.add_argument("--setup",   action="store_true", help="Re-run model selection setup")
    args = parser.parse_args()

    config = load_model_config()

    if args.setup or not config.get("setup_complete"):
        config = first_time_setup()
    else:
        preferred = config.get("preferred_model_name", config.get("preferred_model"))
        print(f"\nPreferred model: {preferred}")
        show_last_failure(config)
        print()

    if args.list:
        recordings = list_available_recordings()
        display_recordings_list(recordings)
        return

    if args.latest:
        result = analyze_latest()
        print("\n── Result ─────────────────────────────────────")
        print(json.dumps({k: v for k, v in result.items()
                          if k not in ("transcript", "raw_analysis", "recording_url")}, indent=2))
        return

    if args.call_id:
        result = analyze_call(args.call_id, force=args.force)
        print("\n── Result ─────────────────────────────────────")
        print(json.dumps({k: v for k, v in result.items()
                          if k not in ("transcript", "raw_analysis", "recording_url")}, indent=2))
        return

    recordings = list_available_recordings()
    display_recordings_list(recordings)

    if not recordings:
        return

    print("\nOptions:")
    print("  Enter a number to analyze that recording")
    print("  Type 'latest' for most recent")
    print("  Type 'q' to quit")
    choice = input("\nYour choice: ").strip().lower()

    if choice == "q":
        return

    if choice == "latest":
        call_id = recordings[0].get("call_id")
    else:
        try:
            idx     = int(choice) - 1
            call_id = recordings[idx].get("call_id")
        except (ValueError, IndexError):
            print("Invalid choice.")
            return

    force = False
    if is_already_analyzed(call_id):
        cached = get_cached_result(call_id)
        score  = cached.get("seller_credibility_score", "?")
        print(f"\nAlready analyzed (Score: {score}/100).")
        redo = input("Re-analyze? (y/n): ").strip().lower()
        if redo == "y":
            force = True
        else:
            result = cached.get("result", cached)
            print("\n── Cached Result ───────────────────────────────")
            print(json.dumps({k: v for k, v in result.items()
                              if k not in ("transcript", "raw_analysis", "recording_url")}, indent=2))
            return

    result = analyze_call(call_id, force=force)
    print("\n── Result ─────────────────────────────────────")
    print(json.dumps({k: v for k, v in result.items()
                      if k not in ("transcript", "raw_analysis", "recording_url")}, indent=2))


if __name__ == "__main__":
    main()
