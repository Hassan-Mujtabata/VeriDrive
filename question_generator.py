"""
VeriDrive - Context-Aware Question Generator
================================================
Runs BEFORE the voice call. Takes the scraped listing data and uses
Gemini API to generate verification questions tailored to that
specific car's ad, across three categories:

  1. claim_verification - probes specific claims the ad makes
  2. information_gap - asks about things the ad does not mention
  3. suspicious_pattern - flags inconsistent or statistically odd
     combinations (e.g. low price + low mileage)

Pipeline position:
    Scraper finishes
        -> THIS MODULE reads listing data, generates tailored questions
        -> questions get passed into Retell as dynamic variables
        -> Retell's agent prompt references them with {{variable_name}}
           syntax during the actual call

Usage as a module (FastAPI):
    from question_generator import generate_questions, to_retell_dynamic_variables

    questions = generate_questions(scraped_listing_dict)
    dynamic_vars = to_retell_dynamic_variables(questions)

CLI test:
    py question_generator.py --demo
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

# Model order: smallest (cheapest) to largest (most capable)
# Tries each in order; if one fails, auto-retries next until success
GEMINI_MODELS = [
    "gemini-2.5-flash-lite",   # cheapest — try first
    "gemini-2.0-flash-lite",   # next up
    "gemini-2.0-flash",        # more capable
    "gemini-2.5-flash",        # most capable — last resort
]

SYSTEM_PROMPT = """You are writing questions for Vera, a friendly AI agent who calls used car sellers in the UAE. Vera is calling on behalf of a serious buyer who knows cars well. You will be given the full listing details — make, model, year, trim, mileage, price, seller type, and description.

You must think like a knowledgeable car enthusiast who has done their research on this specific model before calling. Not a generic buyer. Someone who knows what commonly goes wrong with this car at this age and mileage, what to look out for on this trim level, and what questions actually matter for this specific vehicle.

THINK LIKE THIS before writing questions:
- What is this car's age and mileage? High mileage on an old car = ask about engine health, gearbox, suspension. Low mileage on a new car = ask about accidents, ownership, why so few km.
- What are the known issues or wear points for this specific make, model, and trim? A Toyota Land Cruiser GXR with 226,000 km needs different questions than a 2023 Nissan Patrol LE Platinum with 15,000 km.
- What did the ad claim? First owner, GCC specs, well maintained, no accidents — probe those specific claims naturally.
- What did the ad NOT mention that a serious buyer would want to know? Service history, accident history, finance status, tyre condition, battery, AC, known rattles.
- Is this a dealer or private seller? Dealers need different questions than private owners.

SPECIFICITY RULES — most important:
- Every question must only make sense for THIS specific car. If someone read the question they should know exactly which car is being discussed.
- Always use the full car name with trim. "Toyota Land Cruiser GXR" not "Land Cruiser". "Nissan Patrol LE Platinum" not "Patrol".
- Reference what the ad claimed or omitted. Don't ask generic questions that could apply to any car.
- Think about what a buyer who knows this model would actually ask — not what a form would ask.

LANGUAGE RULES:
- Simple, everyday words only. Short sentences. How a real person talks on the phone.
- No technical jargon like "chassis", "drivetrain diagnostics", "service record documentation".
- If someone with basic English would struggle, rewrite it.
- Never use "prompting", "confirm", "verify", "prove", "really", "actually".

TONE RULES:
- Warm and curious, like someone who genuinely wants the car and just wants to understand it better.
- Never accusatory, never make the seller feel tested.
- An honest seller should feel comfortable and happy to answer every question.

NUMBER RULES:
- NEVER repeat numbers from the listing — no price, no mileage, no year in any question.
- The seller must say the number themselves.
- Good: "How many kilometers has the Land Cruiser GXR done?" 
- Bad: "Is the mileage really 226,000 km?"

QUESTION STYLE RULES:
- Every question must be open-ended — seller must give a real answer, not yes or no.
- Bad: "Has the AC been checked?" — seller just says yes.
- Good: "How is the AC on the Land Cruiser GXR — still blowing cold?" — seller has to describe it.
- Questions spread across the call, not fired in a row. Each must stand alone.

Respond with ONLY valid JSON, no other text, no markdown, no code fences:

{
  "ownership_questions": ["<specific question about this car's ownership, history, or claims made in the ad>", "..."],
  "detail_questions": ["<specific question a car enthusiast would ask about this model's known wear points, missing info, or condition details>", "..."],
  "condition_questions": ["<specific question about this car's current state or reason for selling, tailored to its age and mileage>", "..."],
  "opening_line": "<one short warm sentence with full car name including trim and year — sounds genuinely interested in this specific car>",
  "car_summary": "<one line: year + full name + trim + specs + mileage + price. E.g. '2009 Toyota Land Cruiser GXR, GCC Specs, 226,000 km, AED 52,000'>",
  "end_call_summary_prompt": "<one sentence telling Vera what specific things to confirm before ending this call, based on what was claimed in THIS listing>"
}

Write 2 to 3 questions per category. Make every single question specific to this exact car and listing. Think like a car person, not a form."""


def _strip_markdown_fence(text: str) -> str:
    """Remove ```json / ``` fences from model output if present."""
    if not text.startswith("```"):
        return text
    lines = [l for l in text.split("\n") if not l.strip().startswith("```")]
    return "\n".join(lines).strip()


def generate_questions(listing_data: dict) -> dict:
    """
    Calls Gemini API to generate tailored verification questions for
    a specific car listing. Tries models from smallest to largest;
    if one fails, auto-retries the next until success.

    Args:
        listing_data: the scraped listing dict (make, model, year,
                      mileage_km, asking_price_aed, description, etc.)

    Returns a dict with claim_verification, information_gap,
    suspicious_pattern (each a list of question strings) and an
    opening_line string.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY environment variable is not set. "
            "Get a key from https://aistudio.google.com/apikey"
        )

    client = genai.Client(api_key=GEMINI_API_KEY)

    listing_summary = (
        f"Make: {listing_data.get('make')}\n"
        f"Model: {listing_data.get('model')}\n"
        f"Trim: {listing_data.get('trim', 'not specified')}\n"
        f"Year: {listing_data.get('year')}\n"
        f"Mileage: {listing_data.get('mileage_km')} km\n"
        f"Asking price: AED {listing_data.get('asking_price_aed')}\n"
        f"Seller type: {listing_data.get('seller_type', 'unknown')}\n"
        f"Regional specs: {listing_data.get('regional_specs', 'not specified')}\n"
        f"Description: {listing_data.get('description', 'no description provided')}"
    )

    last_error = None

    for i, model_id in enumerate(GEMINI_MODELS):
        label = "(preferred)" if i == 0 else f"(fallback #{i})"
        try:
            print(f"[questions] Trying {model_id} {label}...")
            response = client.models.generate_content(
                model=model_id,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                ),
                contents=f"Here is the listing:\n\n{listing_summary}",
            )
            print(f"[questions] Success with {model_id}")

            raw_text = _strip_markdown_fence(response.text.strip())

            try:
                return json.loads(raw_text)
            except json.JSONDecodeError as e:
                last_error = f"Invalid JSON from {model_id}: {e} | Raw: {raw_text[:200]}"
                print(f"[questions] {model_id} returned bad JSON — trying next model...")
                time.sleep(1)
                continue

        except Exception as e:
            error_str   = str(e)
            last_error  = error_str
            is_overload = any(x in error_str for x in [
                "503", "429", "UNAVAILABLE", "quota", "404", "NOT_FOUND"
            ])

            if is_overload and i < len(GEMINI_MODELS) - 1:
                print(f"[questions] {model_id} unavailable — trying next...")
                time.sleep(3)
            else:
                raise RuntimeError(f"Gemini error on {model_id}: {error_str}")

    # Unreachable in normal flow — last iteration always raises above
    raise RuntimeError(f"All Gemini models failed. Last error: {last_error}")


def to_retell_dynamic_variables(questions: dict) -> dict:
    """
    Flattens question categories into flat string variables
    Retell's dynamic_variables system expects.

    Variable names match {{variable_name}} syntax in Vera's Retell prompt:
      {{opening_line}}         -> opening_line
      {{claim_questions}}      -> claim_questions
      {{gap_questions}}        -> gap_questions
      {{suspicious_questions}} -> suspicious_questions
    """
    return {
        "opening_line":             questions.get("opening_line", ""),
        "claim_questions":          " ".join(questions.get("ownership_questions", [])),
        "gap_questions":            " ".join(questions.get("detail_questions", [])),
        "suspicious_questions":     " ".join(questions.get("condition_questions", [])),
        "car_summary":              questions.get("car_summary", ""),
        "end_call_summary_prompt":  questions.get("end_call_summary_prompt", ""),
    }


# ── Demo listing ──────────────────────────────────────────────────────────────

DEMO_LISTING = {
    "make":             "Toyota",
    "model":            "Corolla",
    "year":             2019,
    "mileage_km":       95000,
    "asking_price_aed": 28000,
    "description":      "First owner, no accidents, GCC spec, well maintained, regularly serviced."
}


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="VeriDrive Context-Aware Question Generator")
    parser.add_argument("--demo", action="store_true", help="Run with built-in sample listing")
    parser.add_argument("--file", help="Path to a scraped listing JSON file")
    args = parser.parse_args()

    if args.demo:
        listing_data = DEMO_LISTING
        print("[questions] Using built-in demo listing (2019 Toyota Corolla).\n")
    elif args.file:
        with open(args.file, encoding="utf-8") as f:
            listing_data = json.load(f)
    else:
        print("Use --demo to test with a sample listing, or --file <path> for a real one.")
        return

    print("[questions] Calling Gemini API to generate tailored questions...\n")
    try:
        questions = generate_questions(listing_data)
    except RuntimeError as e:
        print(f"[questions] ERROR: {e}")
        return

    print("=" * 60)
    print("GENERATED QUESTIONS")
    print("=" * 60)
    print(json.dumps(questions, indent=2, ensure_ascii=False))

    print("\n" + "=" * 60)
    print("RETELL DYNAMIC VARIABLES (what gets passed to the call)")
    print("=" * 60)
    print(json.dumps(to_retell_dynamic_variables(questions), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
