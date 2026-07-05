# VeriDrive — Market Price Intelligence Engine

Scrapes live Dubizzle listings for comparable vehicles and computes
median market price, fairness score, and recommended negotiation range.

---

## Setup (already done if you set up the scraper)

```
py -3.11 -m pip install playwright
py -3.11 -m playwright install chromium
```

---

## Run

```
py -3.11 price_engine.py --make Toyota --model Corolla --year 2019 --mileage 95000 --price 28000
```

```
py -3.11 price_engine.py --make Audi --model "RS Q8" --year 2020 --mileage 110179 --price 194999
```

Put quotes around model names with spaces or special characters.

---

## Output

- comparable_count: how many matching listings found
- median_market_price_aed: median price of comparable listings
- price_difference_percent: how the asking price compares (negative = below market)
- fairness_score: 0-100 (100 = perfectly at market median)
- recommended_min_aed / recommended_max_aed: negotiation range
- verdict: plain English summary
- comparables: full list of listings used in the analysis

---

## How it works

1. Builds a Dubizzle search URL for the same make/model/year
2. Scrapes up to 5 pages of results using Playwright
3. Filters comparables to within ±40% of the target mileage
4. Computes median, mean, standard deviation
5. Scores the asking price and generates a recommended range
