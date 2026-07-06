"""
test_call.py -- End-to-end test with FAKE scraped data (no real scraper).
=========================================================================
Pretends the scraper already ran and handed us a listing, then:
  1. Gemini generates context-aware questions from that fake listing
  2. Prints exactly what Vera will say/ask (the dynamic variables)
  3. Calls YOUR number (TEST_NUMBER in .env) so you can hear it live
  4. After the call, scores the transcript like the real pipeline does

Edit FAKE_LISTING below to try different cars.

Run (PowerShell), from the project folder:
    cd "C:\\Users\\sands\\OneDrive\\Desktop\\grad proj\\retell"
    py -3.12 test_call.py

Or call a different number:
    py -3.12 test_call.py +9715XXXXXXXX
"""

import os
import sys
import json
from dotenv import load_dotenv

from question_generator import generate_questions, to_retell_dynamic_variables
from call_veridrive import make_verification_call

load_dotenv()

# --- Pretend this came out of the scraper. Change anything you like. ----------
FAKE_LISTING = {
    "make":             "Nissan",
    "model":            "Patrol",
    "trim":             "LE Platinum",
    "year":             2021,
    "mileage_km":       62000,
    "asking_price_aed": 235000,
    "exterior_color":   "White",
    "interior_color":   "Beige",
    "regional_specs":   "GCC Specs",
    "body_type":        "SUV",
    "fuel_type":        "Petrol",
    "cylinders":        8,
    "horsepower":       "400+ HP",
    "warranty":         "Yes",
    "seller_type":      "Private",
    "emirate":          "Dubai",
    "location":         "Dubai",
    "seller_name":      "Ahmed",
    "description":      ("First owner, GCC specs, full service history at Nissan, "
                         "no accidents, still under warranty. Well maintained, "
                         "non-smoker, tyres changed last year."),
}


def main():
    number = sys.argv[1] if len(sys.argv) > 1 else os.getenv("TEST_NUMBER")
    if not number:
        print("No number found. Set TEST_NUMBER in .env or pass one:")
        print("    py -3.12 test_call.py +9715XXXXXXXX")
        return

    print("=" * 60)
    print("FAKE 'SCRAPED' LISTING (what Gemini will think it received)")
    print("=" * 60)
    print(json.dumps(FAKE_LISTING, indent=2, ensure_ascii=False))

    print("\nGenerating context-aware questions with Gemini...\n")
    questions = generate_questions(FAKE_LISTING)
    dvars     = to_retell_dynamic_variables(questions, FAKE_LISTING)

    print("=" * 60)
    print("WHAT VERA WILL SAY / ASK  (dynamic variables sent to Retell)")
    print("=" * 60)
    for k, v in dvars.items():
        print(f"\n[{k}]\n  {v}")

    input(f"\n>>> Press Enter to place the call to {number} now (Ctrl+C to cancel)... ")

    result = make_verification_call(
        seller_number=number,
        seller_name=FAKE_LISTING.get("seller_name", "Test Seller"),
        dynamic_variables=dvars,      # already built -> no re-generation
        max_duration_s=240,
    )

    print("\n" + "=" * 60)
    print("CALL RESULT")
    print("=" * 60)
    for k, v in result.items():
        if k not in ("transcript", "dynamic_variables"):
            print(f"  {k}: {v}")

    transcript = result.get("transcript", "")
    print("\n  transcript (first 500 chars):")
    print("  " + (transcript[:500] if transcript else "(none)"))

    # --- Optional: score the transcript exactly like the real pipeline --------
    if transcript:
        try:
            sys.path.insert(0, os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "veridrive-trust-score-v2", "veridrive-trust-score",
            ))
            from transcript_analyzer import analyze_transcript
            print("\nScoring transcript with Gemini...")
            analysis = analyze_transcript(transcript, FAKE_LISTING, dvars)
            print(f"  seller_credibility_score: {analysis.get('seller_credibility_score')}")
            print(f"  hesitation_detected     : {analysis.get('hesitation_detected')}")
            print(f"  summary                 : {analysis.get('call_summary')}")
        except Exception as e:
            print(f"  (skipped transcript scoring: {e})")


if __name__ == "__main__":
    main()
