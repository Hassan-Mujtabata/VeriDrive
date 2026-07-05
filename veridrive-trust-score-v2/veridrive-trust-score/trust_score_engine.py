"""
VeriDrive - Trust Score Engine
================================
Computes the composite buyer trust score (0-100) from the outputs of
the other modules: listing scraper, price intelligence engine, VIN
report, and voice call analysis.

This is built as a set of importable functions so FastAPI can call
compute_trust_score() directly inside the request pipeline. No files,
no subprocess calls, everything happens in memory.

For testing without FastAPI, run this file directly:
    py -3.11 trust_score_engine.py --demo

Hassan / FastAPI usage:
    from trust_score_engine import compute_trust_score

    result = compute_trust_score(
        listing_data=scraped_listing_json,
        price_data=price_engine_output_json,
        vin_data=vin_report_json_or_none,
        voice_data=voice_call_json_or_none,
    )
    # result["composite_score"], result["red_flags"], etc.
"""

import argparse
import json
import re


# ── weights ───────────────────────────────────────────────────────────────────

BASE_WEIGHTS = {
    "seller_credibility": 0.35,
    "price_fairness": 0.30,
    "vin_history": 0.35,
}


def redistribute_weights(available_scores: dict) -> dict:
    """
    Takes a dict of {key: score_or_None} and returns normalized weights
    that only include the keys with an actual score, so missing data
    does not silently count as zero.
    """
    present = {k: BASE_WEIGHTS[k] for k, v in available_scores.items() if v is not None}
    if not present:
        return {}
    total = sum(present.values())
    return {k: round(v / total, 4) for k, v in present.items()}


# ── sub-score: price fairness ───────────────────────────────────────────────────

def compute_price_fairness_subscore(price_data: dict | None):
    """
    price_data is the output of the price intelligence engine.
    Returns (score_or_None, list_of_red_flags)
    """
    flags = []
    if not price_data or "fairness_score" not in price_data:
        return None, flags

    score = price_data["fairness_score"]
    diff_pct = price_data.get("price_difference_percent", 0)

    if diff_pct > 25:
        flags.append({
            "severity": "high",
            "title": "Significantly Overpriced",
            "description": f"Asking price is {diff_pct}% above the market median for comparable listings.",
            "source_module": "Price",
        })
    elif diff_pct > 10:
        flags.append({
            "severity": "medium",
            "title": "Above Market Price",
            "description": f"Asking price is {diff_pct}% above the market median. Room to negotiate.",
            "source_module": "Price",
        })
    elif diff_pct < -25:
        flags.append({
            "severity": "medium",
            "title": "Unusually Underpriced",
            "description": f"Asking price is {abs(diff_pct)}% below market median. Verify condition carefully before proceeding, large discounts can sometimes indicate undisclosed issues.",
            "source_module": "Price",
        })

    return score, flags


# ── sub-score: VIN history ───────────────────────────────────────────────────────

def compute_vin_history_subscore(vin_data: dict | None):
    """
    vin_data is the VIN report from ClearVin (NMVTIS) or CarVertical.
    Expected shape:
        {
          "available": bool,
          "data_source": "ClearVin" | "CarVertical",
          "accident_count": int,
          "ownership_count": int,
          "title_status": str,
          "theft_record": bool,
        }
    Returns (score_or_None, list_of_red_flags)
    """
    flags = []
    if not vin_data or not vin_data.get("available"):
        return None, flags

    accident_count = vin_data.get("accident_count", 0) or 0
    title_status   = (vin_data.get("title_status") or "Clean").strip()
    theft_record    = bool(vin_data.get("theft_record", False))

    score = 100

    if accident_count == 1:
        score = 70
        flags.append({
            "severity": "medium",
            "title": "One Recorded Accident",
            "description": "VIN report shows one recorded accident on this vehicle's history.",
            "source_module": "VIN",
        })
    elif accident_count == 2:
        score = 50
        flags.append({
            "severity": "high",
            "title": "Multiple Recorded Accidents",
            "description": "VIN report shows two recorded accidents on this vehicle's history.",
            "source_module": "VIN",
        })
    elif accident_count >= 3:
        score = 30
        flags.append({
            "severity": "high",
            "title": "Significant Accident History",
            "description": f"VIN report shows {accident_count} recorded accidents on this vehicle's history.",
            "source_module": "VIN",
        })

    if title_status.lower() != "clean":
        score = min(score, 40)
        flags.append({
            "severity": "high",
            "title": "Non-Clean Title Status",
            "description": f"VIN report shows title status as '{title_status}', not Clean. This may indicate salvage, rebuilt, or flood history.",
            "source_module": "VIN",
        })

    if theft_record:
        score = 5
        flags.append({
            "severity": "high",
            "title": "Theft Record Found",
            "description": "VIN report shows this vehicle has a recorded theft history. Strongly recommend an independent inspection before proceeding.",
            "source_module": "VIN",
        })

    return max(0, score), flags


# ── sub-score: seller credibility ────────────────────────────────────────────────

def compute_seller_credibility_subscore(voice_data: dict | None):
    """
    voice_data is the output of the voice call module (Retell AI).
    Expected shape:
        {
          "available": bool,
          "call_outcome": "completed" | "no_answer" | "voicemail" | "declined",
          "duration_seconds": int,
          "transcript": str (optional),
          "seller_credibility_score": float or None,
        }
    If seller_credibility_score is not yet provided (Hassan's LLM call
    analysis is not built yet), this falls back to a neutral score with
    a flag noting the limitation rather than guessing.
    Returns (score_or_None, list_of_red_flags)
    """
    flags = []
    if not voice_data:
        return None, flags

    outcome = voice_data.get("call_outcome")

    if not voice_data.get("available") or outcome in ("no_answer", "voicemail", "declined"):
        flags.append({
            "severity": "medium",
            "title": "Seller Did Not Answer Verification Call",
            "description": "The AI verification call was not completed. Seller credibility could not be assessed.",
            "source_module": "Voice",
        })
        return None, flags

    score = voice_data.get("seller_credibility_score")

    if score is None:
        # Call completed but structured analysis not yet wired in
        flags.append({
            "severity": "low",
            "title": "Seller Credibility Pending Analysis",
            "description": "Call completed but a structured credibility score has not yet been computed from the transcript.",
            "source_module": "Voice",
        })
        return 50, flags

    if score < 50:
        flags.append({
            "severity": "high",
            "title": "Low Seller Credibility",
            "description": "Seller responses during the verification call showed significant inconsistency or evasiveness.",
            "source_module": "Voice",
        })
    elif score < 70:
        flags.append({
            "severity": "medium",
            "title": "Seller Hesitation Detected",
            "description": "Seller showed some hesitation or incomplete answers during the verification call.",
            "source_module": "Voice",
        })

    return score, flags


# ── claim discrepancy detection ──────────────────────────────────────────────────

NO_ACCIDENT_PHRASES   = ["no accident", "accident free", "accident-free", "zero accident"]
FIRST_OWNER_PHRASES   = ["first owner", "single owner", "one owner", "only owner"]


def detect_claim_discrepancies(listing_data: dict | None, vin_data: dict | None, voice_data: dict | None):
    """
    Cross-references claims made in the listing description (and, if
    available, the seller's voice call answers) against the independent
    VIN report. This is plain keyword matching, no LLM call needed.
    Returns a list of red flags.
    """
    flags = []
    if not listing_data:
        return flags

    description = (listing_data.get("description") or "").lower()

    claims_no_accident = any(p in description for p in NO_ACCIDENT_PHRASES)
    claims_first_owner = any(p in description for p in FIRST_OWNER_PHRASES)

    if vin_data and vin_data.get("available"):
        accident_count  = vin_data.get("accident_count", 0) or 0
        ownership_count = vin_data.get("ownership_count", 0) or 0

        if claims_no_accident and accident_count > 0:
            flags.append({
                "severity": "high",
                "title": "Accident History Discrepancy",
                "description": f"Listing description claims no accidents, but the VIN report shows {accident_count} recorded accident(s).",
                "source_module": "VIN",
            })

        if claims_first_owner and ownership_count > 1:
            flags.append({
                "severity": "high",
                "title": "Ownership Count Discrepancy",
                "description": f"Listing description claims first or single ownership, but the VIN report shows {ownership_count} previous owners.",
                "source_module": "VIN",
            })

    return flags


# ── recommendation text ──────────────────────────────────────────────────────────

def generate_recommendation(composite_score: float, red_flags: list) -> str:
    high_count = sum(1 for f in red_flags if f["severity"] == "high")

    if composite_score >= 75 and high_count == 0:
        return ("This vehicle shows strong indicators across seller credibility, price fairness, "
                "and VIN history. No major red flags were detected. Standard due diligence "
                "(in-person inspection, test drive) is still recommended before purchase.")

    if composite_score >= 50:
        flag_summary = ", ".join(f["title"] for f in red_flags[:3]) if red_flags else "minor inconsistencies"
        return (f"This vehicle shows mixed indicators. Items to address before proceeding include: "
                f"{flag_summary}. Request supporting documentation from the seller and consider an "
                f"independent inspection before finalizing the purchase.")

    return ("This vehicle shows significant red flags across one or more verification categories. "
            "We recommend requesting full documentation from the seller, arranging an independent "
            "inspection, and proceeding with caution. Consider other listings if these issues "
            "cannot be resolved satisfactorily.")


# ── main orchestrator ────────────────────────────────────────────────────────────

def compute_trust_score(
    listing_data: dict | None = None,
    price_data: dict | None = None,
    vin_data: dict | None = None,
    voice_data: dict | None = None,
) -> dict:
    """
    Main entry point. Call this from FastAPI with whatever data is
    available at the time. Any module's data can be None if that step
    has not run yet or failed (e.g. seller never answered the call).
    """
    seller_score, seller_flags = compute_seller_credibility_subscore(voice_data)
    price_score,  price_flags  = compute_price_fairness_subscore(price_data)
    vin_score,    vin_flags    = compute_vin_history_subscore(vin_data)
    discrepancy_flags          = detect_claim_discrepancies(listing_data, vin_data, voice_data)

    raw_scores = {
        "seller_credibility": seller_score,
        "price_fairness": price_score,
        "vin_history": vin_score,
    }

    weights = redistribute_weights(raw_scores)

    if not weights:
        composite_score = 50
    else:
        composite_score = round(sum(raw_scores[k] * w for k, w in weights.items()))

    all_flags = seller_flags + price_flags + vin_flags + discrepancy_flags

    recommendation = generate_recommendation(composite_score, all_flags)

    return {
        "composite_score": composite_score,
        "seller_credibility_subscore": (round(seller_score) if seller_score is not None else None),
        "price_fairness_subscore": (round(price_score) if price_score is not None else None),
        "vin_history_subscore": (round(vin_score) if vin_score is not None else None),
        "weights_applied": weights,
        "recommendation": recommendation,
        "red_flags": all_flags,
    }


# ── demo / CLI testing ───────────────────────────────────────────────────────────

def build_demo_inputs():
    """Realistic sample inputs with a deliberate discrepancy, so the
    discrepancy detector and red flag generation are visibly exercised."""

    listing_data = {
        "make": "Toyota",
        "model": "Corolla",
        "year": 2019,
        "mileage_km": 95000,
        "asking_price_aed": 28000,
        "description": (
            "First owner, no accidents, full service history at Toyota dealer. "
            "GCC spec, well maintained. Single owner since new."
        ),
    }

    price_data = {
        "fairness_score": 80,
        "price_difference_percent": -10.1,
        "median_market_price_aed": 31158,
        "comparable_count": 100,
    }

    vin_data = {
        "available": True,
        "data_source": "ClearVin",
        "accident_count": 1,
        "ownership_count": 2,
        "title_status": "Clean",
        "theft_record": False,
    }

    voice_data = {
        "available": True,
        "call_outcome": "completed",
        "duration_seconds": 187,
        "seller_credibility_score": 55,
    }

    return listing_data, price_data, vin_data, voice_data


def main():
    parser = argparse.ArgumentParser(description="VeriDrive Trust Score Engine")
    parser.add_argument("--demo", action="store_true", help="Run with built-in sample data")
    parser.add_argument("--listing", help="Path to scraper output JSON file")
    parser.add_argument("--price",   help="Path to price engine output JSON file")
    parser.add_argument("--vin",     help="Path to VIN report JSON file (optional)")
    parser.add_argument("--voice",   help="Path to voice call JSON file (optional)")
    args = parser.parse_args()

    if args.demo or not (args.listing and args.price):
        print("[trust] No file inputs given (or --demo used), running with built-in sample data.\n")
        listing_data, price_data, vin_data, voice_data = build_demo_inputs()
    else:
        with open(args.listing) as f:
            listing_data = json.load(f)
        with open(args.price) as f:
            price_data = json.load(f)
        vin_data = None
        if args.vin:
            with open(args.vin) as f:
                vin_data = json.load(f)
        voice_data = None
        if args.voice:
            with open(args.voice) as f:
                voice_data = json.load(f)

    result = compute_trust_score(
        listing_data=listing_data,
        price_data=price_data,
        vin_data=vin_data,
        voice_data=voice_data,
    )

    print("=" * 60)
    print("TRUST SCORE RESULT")
    print("=" * 60)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
