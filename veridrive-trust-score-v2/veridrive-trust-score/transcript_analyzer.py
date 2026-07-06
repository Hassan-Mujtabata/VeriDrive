"""
VeriDrive - Transcript Analyzer
=================================
Runs once, right after a voice call ends. Takes the raw transcript
from Retell AI and uses Gemini API to extract:

  - the VIN number, if the seller said one during the call
  - a seller credibility score (0-100) based on how consistent and
    complete their answers were
  - structured claims the seller made (accident history, ownership,
    service history, outstanding finance)
  - whether hesitation or evasiveness was detected

Usage as a module (what Hassan/FastAPI will do):
    from transcript_analyzer import analyze_transcript
    result = analyze_transcript(transcript_text, listing_data)
    vin = result["vin_extracted"]
    credibility = result["seller_credibility_score"]

CLI test:
    py -3.12 transcript_analyzer.py --demo
Requires GEMINI_API_KEY in .env
"""

import os
import json
import time
import argparse
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Largest to smallest — same order as question_generator.py.
# Try the strongest model first for the most accurate credibility scoring.
GEMINI_MODELS = [
    "gemini-2.5-flash",        # most capable — try first
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.5-flash-lite",   # cheapest — last resort
]


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


SYSTEM_PROMPT = """You are analyzing a phone call transcript between an AI verification agent and a used car seller in the UAE. Your job is to extract structured information for a buyer trust report.

Respond with ONLY valid JSON, no other text, no markdown formatting, no code fences. Use this exact structure:

{
  "vin_extracted": "<17-character VIN if mentioned, otherwise null>",
  "seller_credibility_score": <integer 0-100>,
  "credibility_reasoning": "<one sentence explaining the score>",
  "extracted_claims": {
    "accident_history": "<what the seller said about accidents, or 'not addressed'>",
    "ownership_count": <integer if mentioned, otherwise null>,
    "service_history": "<what the seller said, or 'not addressed'>",
    "outstanding_finance": "<what the seller said, or 'not addressed'>"
  },
  "hesitation_detected": <true or false>,
  "call_summary": "<2-3 sentence plain language summary of the call>"
}

Score credibility based on whether the seller answered directly versus deflected, whether answers were consistent with each other and with the specific car and claims in the listing, whether they hesitated or paused unusually long, and whether they gave specific details versus vague reassurances. Use this shared VeriDrive scoring band:
- 80-100: answers directly, consistently, with specific detail; matches the listing
- 60-79:  mostly credible, minor gaps or slight hesitation
- 40-59:  vague, deflecting, or answers that don't quite line up
- 0-39:   contradictions, refusals, or clear red flags"""


def _build_context(listing_data: dict | None, dynamic_variables: dict | None) -> str:
    """
    Build a scoring-context block appended to the transcript. Gives Gemini the
    exact car and the tailored questions Vera was asked to cover, so the score
    reflects THIS listing rather than a generic call. Never read aloud — it's
    reference only, after the fact.
    """
    if not listing_data and not dynamic_variables:
        return ""

    lines = ["\n\n--- Reference context for scoring (already happened, do not treat as dialogue) ---"]

    if listing_data:
        ident = " ".join(str(listing_data.get(k)) for k in ("year", "make", "model", "trim")
                          if listing_data.get(k))
        if ident.strip():
            lines.append(f"The listing is for a {ident.strip()}.")
        specs = listing_data.get("regional_specs")
        if specs:
            lines.append(f"Listed regional specs: {specs}.")
        mileage = listing_data.get("mileage_km")
        if mileage:
            lines.append(f"Listed mileage: {mileage} km.")
        desc = listing_data.get("description")
        if desc:
            lines.append(f"The online ad claimed: {desc}")

    if dynamic_variables:
        asked = " ".join(
            dynamic_variables.get(k, "") for k in
            ("claim_questions", "gap_questions", "suspicious_questions")
        ).strip()
        if asked:
            lines.append(
                "The buyer specifically wanted these points covered — judge how well "
                f"the seller addressed them: {asked}"
            )

    return "\n".join(lines)


def _strip_markdown_fence(text: str) -> str:
    if not text.startswith("```"):
        return text
    lines = [l for l in text.split("\n") if not l.strip().startswith("```")]
    return "\n".join(lines).strip()


def analyze_transcript(
    transcript: str,
    listing_data: dict | None = None,
    dynamic_variables: dict | None = None,
) -> dict:
    """
    Calls Gemini API to analyze a call transcript.
    Tries models from smallest to largest; falls through on any failure.

    Args:
        transcript:        raw transcript text from Retell AI
        listing_data:      optional scraped listing dict for context
        dynamic_variables: optional Retell variables that were injected into the
                           call (opening_line, claim/gap/suspicious_questions...).
                           Passing these lets the score reflect how well the
                           seller answered the exact tailored questions.

    Returns a dict with vin_extracted, seller_credibility_score, etc.
    """
    keys = _get_gemini_keys()
    if not keys:
        raise RuntimeError(
            "No Gemini API key found. Add GEMINI_API_KEY (and optionally "
            "GEMINI_API_KEY_2, GEMINI_API_KEY_3, ... for auto-failover) to .env."
        )

    context      = _build_context(listing_data, dynamic_variables)
    user_message = f"Here is the call transcript:\n\n{transcript}{context}"

    last_error = None

    # Outer loop = API keys (rotate on quota), inner loop = models (best first).
    for key_idx, api_key in enumerate(keys, 1):
        client = genai.Client(api_key=api_key)

        for i, model_id in enumerate(GEMINI_MODELS):
            label = "(preferred)" if i == 0 else f"(fallback #{i})"
            try:
                print(f"[transcript] Key {key_idx}/{len(keys)} · {model_id} {label}...")
                response = client.models.generate_content(
                    model=model_id,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                    ),
                    contents=user_message,
                )

                raw_text = _strip_markdown_fence(response.text.strip())
                try:
                    result = json.loads(raw_text)
                    print(f"[transcript] Success with {model_id} (key {key_idx})")
                    return result
                except json.JSONDecodeError as e:
                    last_error = f"Invalid JSON from {model_id}: {e} | Raw: {raw_text[:200]}"
                    print(f"[transcript] {model_id} returned bad JSON — trying next...")
                    time.sleep(1)
                    continue

            except Exception as e:
                error_str  = str(e)
                last_error = error_str

                if _is_quota_error(error_str):
                    print(f"[transcript] Key {key_idx} quota/limit on {model_id} — rotating...")
                    time.sleep(1)
                    continue

                if any(x in error_str for x in ["503", "500", "UNAVAILABLE", "404", "NOT_FOUND"]):
                    print(f"[transcript] {model_id} unavailable — trying next...")
                    time.sleep(2)
                    continue

                print(f"[transcript] Error on {model_id}: {error_str[:140]} — trying next...")
                time.sleep(1)
                continue

    raise RuntimeError(f"All Gemini keys/models exhausted. Last error: {last_error}")


# ── demo ──────────────────────────────────────────────────────────────────────

DEMO_TRANSCRIPT = """Agent: Hi, I am calling about your Toyota Corolla listed on Dubizzle. Do you have a moment to answer a few questions?
Seller: Yeah sure, go ahead.
Agent: The ad mentions you are the first owner. Can you confirm that?
Seller: Um, yes, well, I bought it from my cousin actually, but he barely drove it. So basically first owner.
Agent: I see. Has the car been in any accidents?
Seller: No, no accidents. It is in perfect condition.
Agent: Do you have service records from a Toyota dealer?
Seller: I have some of them, not all, I think. I can send what I have.
Agent: Is there any outstanding finance on the vehicle?
Seller: No, it is fully paid off.
Agent: Can you provide the VIN number?
Seller: Sure, it's J T D B L four zero E four nine nine zero one two three four five.
Agent: Thank you, that's all my questions.
"""

DEMO_LISTING = {"description": "First owner, no accidents, GCC spec Toyota Corolla, full service history."}


def main():
    parser = argparse.ArgumentParser(description="VeriDrive Transcript Analyzer")
    parser.add_argument("--demo", action="store_true", help="Run with a built-in sample transcript")
    parser.add_argument("--file", help="Path to a transcript text file")
    args = parser.parse_args()

    if args.demo:
        transcript   = DEMO_TRANSCRIPT
        listing_data = DEMO_LISTING
        print("[transcript] Using built-in demo transcript.\n")
    elif args.file:
        with open(args.file, encoding="utf-8") as f:
            transcript = f.read()
        listing_data = None
    else:
        print("Use --demo to test with a sample transcript, or --file <path> for a real one.")
        return

    print("[transcript] Calling Gemini API to analyze the call...\n")
    try:
        result = analyze_transcript(transcript, listing_data)
    except RuntimeError as e:
        print(f"[transcript] ERROR: {e}")
        return

    print("=" * 60)
    print("TRANSCRIPT ANALYSIS RESULT")
    print("=" * 60)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()