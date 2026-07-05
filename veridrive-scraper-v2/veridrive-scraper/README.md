# VeriDrive — Dubizzle Scraper

Extracts all listing data from any Dubizzle used car listing URL.
No HTML parsing. Uses the Next.js page data (window.__NEXT_DATA__) directly.

---

## Setup (run once)

```
pip install -r requirements.txt
python -m playwright install chromium
```

---

## Run

```
python dubizzle_scraper.py "https://dubai.dubizzle.com/motors/used-cars/..."
```

Paste any Dubizzle car listing URL as the argument.

---

## Output

Returns JSON with:
- make, model, year, trim
- mileage_km, asking_price_aed
- fuel_type, body_type, regional_specs
- exterior_color, interior_color, cylinders, horsepower
- seller_type, warranty
- emirate, location, latitude, longitude
- seller_name, seller_phone (if available)
- description (cleaned, no HTML)
- photos (list of direct image URLs)

---

## How it works

Dubizzle is a Next.js app. All listing data is embedded as JSON in
window.__NEXT_DATA__ on every page load. The scraper uses Playwright
to load the page, extracts that JSON object, and parses it directly.
This is far more reliable than HTML scraping because it uses Dubizzle's
own internal data structure rather than DOM elements that change frequently.

For the seller phone number, the scraper clicks the reveal button on the
page. If that fails (e.g. Dubizzle changes the button), it falls back to
searching the description text for a UAE phone number pattern.
