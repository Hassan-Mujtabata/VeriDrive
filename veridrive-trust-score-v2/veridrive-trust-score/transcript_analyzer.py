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

# Smallest to largest — same fallback order as question_generator.py
GEMINI_MODELS = [
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.5-flash",
]

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

Score credibility based on whether the seller answered directly versus deflected, whether answers were consistent with each other and with the ad description, whether they hesitated or paused unusually long, and whether they gave specific details versus vague reassurances. A seller who answers every question promptly and consistently should score 80 to 100. Noticeable hesitation or vague answers should score 50 to 70. Evasive, contradictory, or refusing to answer should score below 50."""


def _strip_markdown_fence(text: str) -> str:
    if not text.startswith("```"):
        return text
    lines = [l for l in text.split("\n") if not l.strip().startswith("```")]
    return "\n".join(lines).strip()


def analyze_transcript(transcript: str, listing_data: dict | None = None) -> dict:
    """
    Calls Gemini API to analyze a call transcript.
    Tries models from smallest to largest; falls through on any failure.

    Args:
        transcript:   raw transcript text from Retell AI
        listing_data: optional scraped listing dict for context

    Returns a dict with vin_extracted, seller_credibility_score, etc.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY environment variable is not set. "
            "Get a key from https://aistudio.google.com/apikey"
        )

    client = genai.Client(api_key=GEMINI_API_KEY)

    context = ""
    if listing_data:
        context = (
            f"\n\nFor context, the original online listing claimed: "
            f"{listing_data.get('description', 'no description available')}"
        )

    user_message = f"Here is the call transcript:\n\n{transcript}{context}"

    last_error = None

    for i, model_id in enumerate(GEMINI_MODELS):
        label = "(preferred)" if i == 0 else f"(fallback #{i})"
        try:
            print(f"[transcript] Trying {model_id} {label}...")
            response = client.models.generate_content(
                model=model_id,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                ),
                contents=user_message,
            )
            print(f"[transcript] Success with {model_id}")

            raw_text = _strip_markdown_fence(response.text.strip())

            try:
                return json.loads(raw_text)
            except json.JSONDecodeError as e:
                last_error = f"Invalid JSON from {model_id}: {e} | Raw: {raw_text[:200]}"
                print(f"[transcript] {model_id} returned bad JSON — trying next model...")
                time.sleep(1)
                continue

        except Exception as e:
            error_str  = str(e)
            last_error = error_str
            is_overload = any(x in error_str for x in [
                "503", "429", "UNAVAILABLE", "quota", "404", "NOT_FOUND"
            ])
            if is_overload and i < len(GEMINI_MODELS) - 1:
                print(f"[transcript] {model_id} unavailable — trying next...")
                time.sleep(3)
            else:
                raise RuntimeError(f"Gemini error on {model_id}: {error_str}")

    raise RuntimeError(f"All Gemini models failed. Last error: {last_error}")


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