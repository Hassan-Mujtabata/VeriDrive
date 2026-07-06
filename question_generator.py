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

# Model order: largest (most capable) to smallest (cheapest).
# We want the best content quality — Gemini does the heavy lifting here, so try
# the strongest model first and only fall back to cheaper ones if it's down.
GEMINI_MODELS = [
    "gemini-2.5-flash",        # most capable — try first (quality over cost)
    "gemini-2.0-flash",        # next
    "gemini-2.0-flash-lite",   # cheaper fallback
    "gemini-2.5-flash-lite",   # cheapest — last resort
]


def _get_gemini_keys() -> list:
    """
    Collect every Gemini API key for auto-failover, in priority order:
      GEMINI_API_KEY, GEMINI_API_KEY_2 ... GEMINI_API_KEY_10,
      then any comma-separated keys in GEMINI_API_KEYS.
    Blanks and duplicates are dropped, order preserved. When one key is out of
    quota the caller rotates to the next so the pipeline never drops.
    """
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


SYSTEM_PROMPT = """You are writing questions for Vera, a friendly AI agent who calls used car sellers in the UAE. Vera is calling on behalf of a serious buyer who knows cars well. You will be given the full listing details — make, model, year, trim, mileage, price, seller type, and description.

You must think like a knowledgeable car enthusiast who has done their research on this specific model before calling. Not a generic buyer. Someone who knows what commonly goes wrong with this car at this age and mileage, what to look out for on this trim level, and what questions actually matter for this specific vehicle.

THINK LIKE THIS before writing questions:
- What is this car's age and mileage? High mileage on an old car = ask about engine health, gearbox, suspension. Low mileage on a new car = ask about accidents, ownership, why so few km.
- What are the known issues or wear points for this specific make, model, and trim? A Toyota Land Cruiser GXR with 226,000 km needs different questions than a 2023 Nissan Patrol LE Platinum with 15,000 km.
- What did the ad claim? First owner, GCC specs, well maintained, no accidents — probe those specific claims naturally.
- What did the ad NOT mention that a serious buyer would want to know? Service history, accident history, finance status, tyre condition, battery, AC, known rattles.
- Is this a dealer or private seller? Dealers need different questions than private owners.

SPECIFICITY RULES — most important:
- Every question must be tailored to THIS car — but the specificity comes from the SUBSTANCE (its known weak points, its trim's features, what matters at its age and mileage), NOT from repeating the car's name.
- Do NOT put the car's name in your questions. On a real call, hearing "the 2021 Nissan Patrol LE Platinum" in every question is exhausting and robotic. Say "it" or "the car" almost always. At most once across all the questions you may use the short model name (e.g. "the Patrol") — never the full year + make + model + trim.
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
- Good: "How many kilometers has it done now?"
- Bad: "Is the mileage really 226,000 km?"

QUESTION STYLE RULES:
- Every question must be open-ended — seller must give a real answer, not yes or no.
- Bad: "Has the AC been checked?" — seller just says yes.
- Good: "How's the AC holding up — still blowing cold?" — seller has to describe it, and no car name is crammed in.
- Questions spread across the call, not fired in a row. Each must stand alone.

OPENING LINE RULES — the opening_line is only the FIRST short turn, NOT the whole pitch. It has one job: get the seller to say "yeah?" back to you. Keep it to one short sentence you can say in a single breath, ending on a light question so they respond immediately. Do NOT monologue — cramming the car, the buyer and the ask into one breath sounds exactly like a robocall and gives them nothing to answer. Earn a "yeah" first; the serious-buyer hook and the tiny ask come AFTER, as your reply, inside the conversation.
The opening_line must do just two things:
  - a small humble/disarming touch ("sorry to call out of the blue", "quick one")
  - name the car IN FULL here — year + make + model + trim (e.g. "the 2021 Nissan Patrol LE Platinum"), phrased as a question — "is this the 2021 Nissan Patrol LE Platinum?". This opener is the ONE time in the whole call the full name is spoken; every mention after this is "it" or the short model. You may add a concrete detail like the colour if it still flows naturally.
Rules:
- ONE short sentence. No buyer hook, no ask, no questions about the car yet — those all come after the seller answers.
- Do NOT say the seller's name — being named by a stranger who cold-called them feels invasive and makes people hang up.
- No price, no mileage numbers, no corporate words ("verification", "platform", "regarding your vehicle").
- Warm, casual, a little imperfect — a real person, not a polished script.
- Good: "Hey, sorry to call out of the blue — is this the 2009 Toyota Land Cruiser GXR that's up for sale?"
- Good: "Hi, quick one — is this the 2019 Toyota Corolla you've got listed?"
- Bad (robotic, no car): "Hello, I am calling regarding your car listing."
- Bad (too long / monologue): "Hi, is this the Corolla? I've got a buyer who's really keen and wants to come see it and just had a couple things he wanted me to ask first." — the buyer part must wait until AFTER they answer.

BUYER HOOK RULES — the buyer_hook is the SECOND turn, said right after the seller responds to the opener. This is the line that actually makes them stay, so write it as a ready-to-speak line (the agent delivers it as-is, it will NOT improvise):
- Mention a genuine, serious buyer who is keen and wants to come see it — a real ready buyer is the one thing a seller wants.
- Refer to the car by its SHORT name (e.g. "the Patrol") or just "it" — NOT the full year + make + model + trim. It was already named in the opener; repeating the whole name here sounds robotic.
- Add the tiny ask: he just wants a couple of quick things checked first, framed as the buyer's diligence, not an interrogation.
- End by asking if now's a good moment.
- 1-2 short sentences, warm and casual. No price, no mileage, no corporate words.
- Good: "So I've got a buyer who's really into it — he wants to come see the Patrol, just asked me to check a couple of quick things first. You got a minute?"

Respond with ONLY valid JSON, no other text, no markdown, no code fences:

{
  "ownership_questions": ["<specific question about this car's ownership, history, or claims made in the ad>", "..."],
  "detail_questions": ["<specific question a car enthusiast would ask about this model's known wear points, missing info, or condition details>", "..."],
  "condition_questions": ["<specific question about this car's current state or reason for selling, tailored to its age and mileage>", "..."],
  "opening_line": "<ONE short first-turn line: a small disarm + the car's FULL name (year+make+model+trim, the only full mention in the call), ending on a question that gets a 'yeah'. NO buyer hook and NO ask here — see OPENING LINE RULES>",
  "buyer_hook": "<the SECOND turn, said after the seller responds: serious ready buyer + a tiny couple-of-questions ask + 'is now a good time?'. Refer to the car as 'it' or the short model name, not the full name. Ready to speak as-is — see BUYER HOOK RULES>",
  "car_short": "<the short, natural way to say the car mid-call — usually just the model, e.g. 'Patrol', 'Corolla', 'Land Cruiser'. Vera uses this (or 'it') instead of repeating the full name.>",
  "car_name": "<short natural name Vera can drop into the conversation: year + make + model + trim. E.g. '2009 Toyota Land Cruiser GXR'. No specs, no mileage, no price.>",
  "car_summary": "<one line: year + full name + trim + specs + mileage + price. E.g. '2009 Toyota Land Cruiser GXR, GCC Specs, 226,000 km, AED 52,000'>",
  "end_call_summary_prompt": "<a short SPEAKABLE readback of the main claims from THIS ad, to slot straight into a confirmation sentence — just the clause, no preamble like 'confirm that'. E.g. 'you're the first owner, it's never been in an accident, and it's got full service history'>"
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
    keys = _get_gemini_keys()
    if not keys:
        raise RuntimeError(
            "No Gemini API key found. Add GEMINI_API_KEY (and optionally "
            "GEMINI_API_KEY_2, GEMINI_API_KEY_3, ... for auto-failover) to .env. "
            "Get keys from https://aistudio.google.com/apikey"
        )

    # ── Guard: reject incomplete listing data before calling Gemini ──────────
    REQUIRED_FIELDS = ["make", "model", "year"]
    missing = [f for f in REQUIRED_FIELDS if not listing_data.get(f)]
    if missing:
        raise ValueError(
            f"[questions] Listing data is incomplete — missing: {missing}. "
            "Scraper likely failed. Aborting to prevent Vera calling with wrong car details."
        )

    SOFT_FIELDS = ["mileage_km", "asking_price_aed", "description"]
    soft_missing = [f for f in SOFT_FIELDS if not listing_data.get(f)]
    if soft_missing:
        print(f"[questions] ⚠️  Soft fields missing (weaker questions): {soft_missing}")

    listing_summary = (
        f"Make: {listing_data.get('make')}\n"
        f"Model: {listing_data.get('model')}\n"
        f"Trim: {listing_data.get('trim', 'not specified')}\n"
        f"Year: {listing_data.get('year')}\n"
        f"Mileage: {listing_data.get('mileage_km')} km\n"
        f"Asking price: AED {listing_data.get('asking_price_aed')}\n"
        f"Body type: {listing_data.get('body_type', 'not specified')}\n"
        f"Fuel type: {listing_data.get('fuel_type', 'not specified')}\n"
        f"Cylinders: {listing_data.get('cylinders', 'not specified')}\n"
        f"Horsepower: {listing_data.get('horsepower', 'not specified')}\n"
        f"Exterior colour: {listing_data.get('exterior_color', 'not specified')}\n"
        f"Interior colour: {listing_data.get('interior_color', 'not specified')}\n"
        f"Warranty: {listing_data.get('warranty', 'not specified')}\n"
        f"Seller type: {listing_data.get('seller_type', 'unknown')}\n"
        f"Regional specs: {listing_data.get('regional_specs', 'not specified')}\n"
        f"Location: {listing_data.get('location') or listing_data.get('emirate', 'not specified')}\n"
        f"Description: {listing_data.get('description', 'no description provided')}"
    )

    last_error = None

    # Outer loop = API keys (rotate on quota), inner loop = models (best first).
    for key_idx, api_key in enumerate(keys, 1):
        client = genai.Client(api_key=api_key)

        for i, model_id in enumerate(GEMINI_MODELS):
            label = "(preferred)" if i == 0 else f"(fallback #{i})"
            try:
                print(f"[questions] Key {key_idx}/{len(keys)} · {model_id} {label}...")
                response = client.models.generate_content(
                    model=model_id,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                    ),
                    contents=f"Here is the listing:\n\n{listing_summary}",
                )

                raw_text = _strip_markdown_fence(response.text.strip())
                try:
                    result = json.loads(raw_text)
                    print(f"[questions] Success with {model_id} (key {key_idx})")
                    return result
                except json.JSONDecodeError as e:
                    last_error = f"Invalid JSON from {model_id}: {e} | Raw: {raw_text[:200]}"
                    print(f"[questions] {model_id} returned bad JSON — trying next...")
                    time.sleep(1)
                    continue

            except Exception as e:
                error_str  = str(e)
                last_error = error_str

                if _is_quota_error(error_str):
                    # This key is rate-limited / out of quota on this model. Try the
                    # next model; once all models are exhausted the outer loop moves
                    # to the next API key automatically.
                    print(f"[questions] Key {key_idx} quota/limit on {model_id} — rotating...")
                    time.sleep(1)
                    continue

                if any(x in error_str for x in ["503", "500", "UNAVAILABLE", "404", "NOT_FOUND"]):
                    print(f"[questions] {model_id} unavailable — trying next...")
                    time.sleep(2)
                    continue

                # Unexpected error — don't hard-fail the whole pipeline; try next combo.
                print(f"[questions] Error on {model_id}: {error_str[:140]} — trying next...")
                time.sleep(1)
                continue

    raise RuntimeError(f"All Gemini keys/models exhausted. Last error: {last_error}")


# ── Deterministic fallbacks (so Vera always knows the car) ────────────────────
# Gemini fills these fields, but if it leaves any blank we rebuild them straight
# from the scraped listing so the seller never hears a generic "your car".

_EMPTY_VALUES = {None, "", "not specified", "unknown", "none", "n/a"}


def _clean(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in _EMPTY_VALUES else text


def build_car_name(listing: dict) -> str:
    """'2019 Toyota Corolla SE' from the listing (year make model trim)."""
    parts = [
        _clean(listing.get("year")),
        _clean(listing.get("make")),
        _clean(listing.get("model")),
        _clean(listing.get("trim")),
    ]
    return " ".join(p for p in parts if p).strip()


def build_car_short(listing: dict) -> str:
    """Short natural mid-call reference — usually just the model ('Patrol')."""
    model = _clean(listing.get("model"))
    if model:
        return model
    make = _clean(listing.get("make"))
    return make or "car"


def build_car_summary(listing: dict) -> str:
    """One spec line: '2019 Toyota Corolla SE, GCC Specs, 95,000 km, AED 28,000'."""
    bits = [build_car_name(listing)]
    specs = _clean(listing.get("regional_specs"))
    if specs:
        bits.append(specs)
    mileage = listing.get("mileage_km")
    if mileage:
        try:
            bits.append(f"{int(mileage):,} km")
        except (TypeError, ValueError):
            pass
    price = listing.get("asking_price_aed")
    if price:
        try:
            bits.append(f"AED {int(price):,}")
        except (TypeError, ValueError):
            pass
    return ", ".join(b for b in bits if b)


# Words that mean the "seller_name" is really a dealership, not a person — we
# must NOT greet a business by a fake first name ("Hi, is that Al Futtaim?").
_DEALER_MARKERS = (
    "motor", "cars", "car ", "auto", "trading", "llc", "gallery", "used",
    "rent", "showroom", "garage", "group", "company", "co.", "est",
    "establishment", "dealer", "export", "import", "gcc", "premium",
)


def build_seller_first_name(listing: dict) -> str:
    """
    Best-effort first name for a warm greeting. Returns "" when the listing name
    is missing, looks like a dealership, or isn't a clean single name — in which
    case Vera just greets without a name (better than guessing wrong).
    """
    raw = _clean(listing.get("seller_name"))
    if not raw:
        return ""
    low = raw.lower()
    if any(m in low for m in _DEALER_MARKERS) or any(c.isdigit() for c in raw):
        return ""
    first = raw.split()[0]
    if not first.isalpha() or not (2 <= len(first) <= 15):
        return ""
    return first[:1].upper() + first[1:].lower()


def build_opening_line(listing: dict) -> str:
    """
    Deterministic opener used when Gemini leaves opening_line blank. Just the
    short first turn — a small disarm + the specific car as a question, ending so
    the seller replies "yeah?". The buyer hook and the ask are delivered after
    they respond (handled by the Retell prompt flow), not crammed in here.
    """
    full = build_car_name(listing) or "car"   # full name — said once, in the opener only
    return f"Hey, sorry to call out of the blue — is this the {full} that's up for sale?"


def build_buyer_hook(listing: dict) -> str:
    """
    Deterministic second turn (delivered after the seller answers the opener)
    used when Gemini leaves buyer_hook blank. The retention line: a real ready
    buyer for this exact car + a tiny ask + 'is now a good time?'.
    """
    short = build_car_short(listing) or "car"
    return (
        f"So I've got a buyer who's really keen on it and wants to come see the "
        f"{short} — he just asked me to check a couple of quick things first. "
        f"Have you got a quick minute?"
    )


def to_retell_dynamic_variables(questions: dict, listing: dict = None) -> dict:
    """
    Flattens question categories into the flat string variables Retell expects
    under `retell_llm_dynamic_variables`.

    Variable names match {{variable_name}} syntax in Vera's Retell prompt:
      {{opening_line}}            -> opening_line (first turn — get a "yeah")
      {{buyer_hook}}              -> buyer_hook (second turn — the retention pitch)
      {{car_name}}                -> car_name (full name — use ONCE, e.g. the recap)
      {{car_short}}               -> car_short (short model — occasional mid-call use)
      {{car_summary}}             -> car_summary (spec line for the closing recap)
      {{claim_questions}}         -> claim_questions
      {{gap_questions}}           -> gap_questions
      {{suspicious_questions}}    -> suspicious_questions
      {{end_call_summary_prompt}} -> end_call_summary_prompt

    If `listing` is passed, any car field Gemini left blank is rebuilt from the
    scraped data — so {{opening_line}}/{{car_name}}/{{car_summary}} are never
    empty and Vera always names the real car.

    Retell requires every value to be a string.
    """
    listing = listing or {}

    def _prefer(gen_value: str, builder) -> str:
        val = _clean(gen_value)
        if val:
            return val
        return builder(listing) if listing else ""

    return {
        "opening_line":             _prefer(questions.get("opening_line"), build_opening_line),
        "buyer_hook":               _prefer(questions.get("buyer_hook"),   build_buyer_hook),
        "seller_name":              build_seller_first_name(listing) if listing else "",
        "car_name":                 _prefer(questions.get("car_name"),     build_car_name),
        "car_short":                _prefer(questions.get("car_short"),    build_car_short),
        "car_summary":              _prefer(questions.get("car_summary"),  build_car_summary),
        "claim_questions":          " ".join(questions.get("ownership_questions", [])),
        "gap_questions":            " ".join(questions.get("detail_questions", [])),
        "suspicious_questions":     " ".join(questions.get("condition_questions", [])),
        "end_call_summary_prompt":  _clean(questions.get("end_call_summary_prompt"))
                                    or "everything's as described in the listing",
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
