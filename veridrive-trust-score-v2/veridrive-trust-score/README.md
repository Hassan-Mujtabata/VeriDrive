# VeriDrive - Trust Score Engine and Transcript Analyzer

Two modules. `trust_score_engine.py` is pure math, no AI calls, takes
structured data and produces a score. `transcript_analyzer.py` is the
one AI call in this pair, it turns a raw phone call transcript into
the structured data the trust score engine needs.

---

## Setup

```
py -3.11 -m pip install -r requirements.txt
```

For the transcript analyzer, set your Claude API key first:
```
set ANTHROPIC_API_KEY=your-key-here
```
(Windows Command Prompt, this only lasts for the current terminal session)

---

## For Hassan: Using These in FastAPI

```python
from transcript_analyzer import analyze_transcript
from trust_score_engine import compute_trust_score

# Step 1: right after the Retell AI webhook delivers the transcript
analysis = analyze_transcript(transcript_text, listing_data)

voice_data = {
    "available": True,
    "call_outcome": "completed",
    "duration_seconds": call_duration,
    "seller_credibility_score": analysis["seller_credibility_score"],
}
vin_to_check = analysis["vin_extracted"]   # feed this into the VIN router

# Step 2: once price engine and VIN lookup have also run
result = compute_trust_score(
    listing_data=scraped_listing_dict,
    price_data=price_engine_output_dict,
    vin_data=vin_report_dict_or_None,
    voice_data=voice_data,
)
```

No files, no subprocess calls anywhere. Both are plain function calls.

---

## Testing Without FastAPI

Trust score engine, built-in sample data:
```
py -3.11 trust_score_engine.py --demo
```

Transcript analyzer, built-in sample transcript (requires ANTHROPIC_API_KEY):
```
py -3.11 transcript_analyzer.py --demo
```

---

## What Each One Does

**transcript_analyzer.py** sends the call transcript to Claude API
with instructions to extract: the VIN number if the seller said one,
a credibility score (0-100) based on how consistent and direct their
answers were, and structured claims about accident history, ownership,
service records, and finance. This is the only step in this pair that
costs API tokens and takes a few seconds.

**trust_score_engine.py** takes whatever structured data exists
(listing, price analysis, VIN report, voice analysis) and computes:
- A VIN history subscore: starts at 100, deducts points for each
  accident, non-clean title, or theft record found.
- A price fairness subscore: copied directly from the price engine's
  own fairness_score.
- A seller credibility subscore: copied directly from the transcript
  analyzer's score, or defaults to a neutral 50 with a flag if that
  data is not available yet.
- A discrepancy check: compares the listing's own description text
  against the VIN report, flagging contradictions like "no accidents"
  claimed but accidents found.
- A composite score: weighted average of the three subscores (35%
  seller credibility, 30% price fairness, 35% VIN history). If any
  subscore is missing, its weight is redistributed to the other two
  rather than counting as zero.
- A plain language recommendation based on the final score and flags.

This function never calls any AI model itself. Every number it
produces is deterministic and traceable to a specific rule.

---

## Output Shape

This matches the `Trust_Score` entity in your ERD and the React
frontend's expected report card shape directly.

