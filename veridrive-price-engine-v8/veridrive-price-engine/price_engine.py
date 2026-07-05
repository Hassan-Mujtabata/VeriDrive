"""
VeriDrive — Market Price Intelligence Engine v7
"""

import asyncio
import argparse
import json
import re
import statistics
import sys
from playwright.async_api import async_playwright

YEAR_RANGE          = 3
MAX_PAGES           = 5
MAX_COMPARABLES     = 80
MILEAGE_BAND_KM     = 60000
MIN_COMPARABLES     = 3
DEPRECIATION_RATE   = 0.15
MILEAGE_ADJ_PER_10K = 0.015


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def build_search_url(make, model, year_min, year_max, page):
    return (
        f"https://dubai.dubizzle.com/motors/used-cars/{slugify(make)}/{slugify(model)}/"
        f"?year_min={year_min}&year_max={year_max}&page={page}"
    )


def clean_num(val):
    return re.sub(r"[^\d.]", "", str(val)) if val is not None else ""


def get_name(listing):
    """Handle name field being either a string or dict {"en": "...", "ar": "..."}."""
    name = listing.get("name") or listing.get("title") or ""
    if isinstance(name, dict):
        return name.get("en") or name.get("ar") or ""
    return str(name)


def extract_price(listing):
    price = listing.get("price")
    # Flat integer or float (Algolia format)
    if isinstance(price, (int, float)):
        return float(price)
    # Nested dict
    if isinstance(price, dict):
        raw = price.get("raw") or price.get("value") or price.get("amount") or ""
        d = clean_num(raw)
        if d:
            return float(d)
    # String
    if price:
        d = clean_num(price)
        if d:
            return float(d)
    for key in ["price_aed", "asking_price", "sale_price"]:
        val = listing.get(key)
        if val:
            d = clean_num(val)
            if d:
                return float(d)
    return None


def extract_year(listing):
    # Direct field
    for key in ["year", "model_year"]:
        val = listing.get(key) or (listing.get("ad_ops") or {}).get(key)
        if val:
            try:
                y = int(str(val)[:4])
                if 1990 <= y <= 2030:
                    return y
            except Exception:
                pass

    # details_v2 (Algolia search result format)
    details_v2 = listing.get("details_v2") or {}
    if isinstance(details_v2, dict):
        val = details_v2.get("year") or details_v2.get("Year")
        if val:
            try:
                y = int(str(val)[:4])
                if 1990 <= y <= 2030:
                    return y
            except Exception:
                pass
    elif isinstance(details_v2, list):
        for item in details_v2:
            if isinstance(item, dict):
                slug = str(item.get("slug") or item.get("key") or "").lower()
                if "year" in slug:
                    try:
                        return int(str(item.get("value", ""))[:4])
                    except Exception:
                        pass

    # details array (detail page format)
    for section in ["secondary", "primary"]:
        for item in (listing.get("details") or {}).get(section, []):
            if item.get("slug") == "year":
                try:
                    return int(item["value"])
                except Exception:
                    pass

    # Last resort: extract from name
    name = get_name(listing)
    m = re.search(r'\b(20\d{2}|19\d{2})\b', name)
    if m:
        return int(m.group(1))
    return None


def extract_mileage(listing):
    # Direct fields
    for key in ["kilometers", "mileage_km", "mileage", "km", "odometer"]:
        val = listing.get(key) or (listing.get("ad_ops") or {}).get(key)
        if val:
            d = clean_num(val)
            if d:
                km = int(float(d))
                if 0 < km < 2000000:
                    return km

    # details_v2 (Algolia format) — structure: {"secondary": [{"slug": "kilometers", "value": {"en": "95000"}}]}
    details_v2 = listing.get("details_v2") or {}
    if isinstance(details_v2, dict):
        for section in ["secondary", "primary"]:
            for item in details_v2.get(section, []):
                if not isinstance(item, dict):
                    continue
                slug = str(item.get("slug", "")).lower()
                if "kilometer" in slug or slug == "km" or "mileage" in slug or "odometer" in slug:
                    val = item.get("value", "")
                    if isinstance(val, dict):
                        val = val.get("en") or val.get("ar") or ""
                    d = clean_num(val)
                    if d:
                        km = int(float(d))
                        if 0 < km < 2000000:
                            return km
        for key in ["kilometers", "mileage", "km"]:
            val = details_v2.get(key)
            if val:
                if isinstance(val, dict):
                    val = val.get("en") or val.get("ar") or ""
                d = clean_num(val)
                if d:
                    km = int(float(d))
                    if 0 < km < 2000000:
                        return km

    # details array (detail page format)
    for section in ["secondary", "primary"]:
        for item in (listing.get("details") or {}).get(section, []):
            if item.get("slug") == "kilometers":
                d = clean_num(item.get("value", ""))
                if d:
                    return int(float(d))
    return None


def parse_listings_from_next_data(data):
    listings = []
    try:
        page_props = data.get("props", {}).get("pageProps") or data.get("pageProps", {})
        actions = page_props.get("reduxWrapperActionsGIPP", [])
        for action in actions:
            if action.get("type") == "listings/fetchListingDataForQuery/fulfilled":
                payload = action.get("payload", {})
                hits = payload.get("hits", [])
                if hits:
                    listings.extend(hits)
                cotw = payload.get("cotwListings", [])
                if cotw:
                    listings.extend(cotw)
    except Exception as e:
        print(f"[debug] parse error: {e}")
    return listings


def normalize_price(price, comp_year, comp_mileage, target_year, target_mileage):
    p = price
    if comp_year:
        p *= (1 + DEPRECIATION_RATE) ** (target_year - comp_year)
    if comp_mileage and target_mileage:
        p *= 1 + ((comp_mileage - target_mileage) / 10000) * MILEAGE_ADJ_PER_10K
    return p


async def scrape_comparables(make, model, target_year, target_mileage):
    year_min   = target_year - YEAR_RANGE
    year_max   = target_year + YEAR_RANGE
    all_raw    = []
    debug_done = False

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            viewport={"width": 1280, "height": 800},
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = await context.new_page()

        for page_num in range(1, MAX_PAGES + 1):
            url = build_search_url(make, model, year_min, year_max, page_num)
            print(f"[price] Page {page_num}: {url}")

            try:
                await page.goto(url, wait_until="networkidle", timeout=50000)
                await page.wait_for_timeout(2000)
                print(f"[price] Title: {await page.title()}")
            except Exception:
                # Timeout on networkidle — the page may still have loaded
                print(f"[price] Page {page_num} slow to load, trying anyway...")
                await page.wait_for_timeout(3000)

            try:
                raw = await page.evaluate("() => JSON.stringify(window.__NEXT_DATA__)")
                if not raw:
                    print(f"[price] No __NEXT_DATA__ on page {page_num}, stopping.")
                    break

                listings = parse_listings_from_next_data(json.loads(raw))
                if not listings:
                    print(f"[price] No listings on page {page_num}, stopping.")
                    break

                print(f"[price] Found {len(listings)} listings on page {page_num}")

                # Print details_v2 of first listing once
                if not debug_done and listings:
                    debug_done = True
                    first = listings[0]
                    dv2 = first.get("details_v2")
                    print(f"\n[debug] details_v2 type: {type(dv2).__name__}")
                    print(f"[debug] details_v2 content: {str(dv2)[:500]}")
                    print(f"[debug] name field: {str(first.get('name'))[:100]}")
                    print()

                all_raw.extend(listings)

                if len(all_raw) >= MAX_COMPARABLES:
                    break

            except Exception as e:
                print(f"[price] Error extracting data on page {page_num}: {e}")
                break

        await browser.close()

    seen, unique = set(), []
    for l in all_raw:
        key = str(l.get("objectID") or l.get("uuid") or l.get("id") or id(l))
        if key not in seen:
            seen.add(key)
            unique.append(l)

    print(f"[price] {len(unique)} unique listings before mileage filter")

    comparables = []
    for l in unique:
        price   = extract_price(l)
        year    = extract_year(l)
        mileage = extract_mileage(l)

        if not price or price <= 0:
            continue
        if year and abs(year - target_year) > YEAR_RANGE:
            continue
        if mileage and target_mileage and abs(mileage - target_mileage) > MILEAGE_BAND_KM:
            continue

        name = get_name(l)
        loc  = l.get("location_list") or l.get("places") or ""
        if isinstance(loc, list) and loc:
            loc = loc[0] if isinstance(loc[0], str) else str(loc[0])

        comparables.append({
            "source": "Dubizzle",
            "url": l.get("absolute_url") or l.get("permalink", ""),
            "name": name,
            "price_aed": price,
            "year": year,
            "mileage_km": mileage,
            "location": loc,
        })

    return comparables


def compute_analysis(comparables, asking_price, make, model, target_year, target_mileage):
    normalized = [
        normalize_price(c["price_aed"], c.get("year"), c.get("mileage_km"), target_year, target_mileage)
        for c in comparables
    ]
    n            = len(normalized)
    median_price = statistics.median(normalized)
    if n >= 4:
        q1 = statistics.quantiles(normalized, n=4)[0]
        q3 = statistics.quantiles(normalized, n=4)[2]
        iqr = q3 - q1
        clean = [p for p in normalized if (q1 - 1.5*iqr) <= p <= (q3 + 1.5*iqr)]
    else:
        clean = normalized
    mean_price   = statistics.mean(clean) if clean else statistics.mean(normalized)
    std_dev      = statistics.stdev(clean) if len(clean) >= 2 else 0.0
    diff_pct     = ((asking_price - median_price) / median_price) * 100
    abs_diff     = abs(diff_pct)

    if abs_diff <= 5:      fairness = round(100 - abs_diff)
    elif abs_diff <= 15:   fairness = round(90 - (abs_diff - 5) * 2)
    elif abs_diff <= 30:   fairness = round(70 - (abs_diff - 15) * 2)
    else:                  fairness = max(10, round(40 - (abs_diff - 30)))

    if diff_pct < -15:     verdict = "Significantly below market — investigate before buying"
    elif diff_pct < -5:    verdict = "Below market value — good deal if condition checks out"
    elif diff_pct <= 5:    verdict = "Fairly priced relative to current market"
    elif diff_pct <= 15:   verdict = "Slightly above market — negotiate before buying"
    else:                  verdict = "Overpriced relative to comparable listings"

    has_year    = sum(1 for c in comparables if c.get("year"))
    has_mileage = sum(1 for c in comparables if c.get("mileage_km"))

    return {
        "vehicle": f"{target_year} {make} {model}",
        "asking_price_aed": asking_price,
        "comparable_count": n,
        "comparables_with_year": has_year,
        "comparables_with_mileage": has_mileage,
        "normalization": "applied" if (has_year or has_mileage) else "NOT APPLIED",
        "normalized_median_aed": round(median_price),
        "normalized_mean_aed": round(mean_price),
        "std_deviation_aed": round(std_dev),
        "price_difference_aed": round(asking_price - median_price),
        "price_difference_percent": round(diff_pct, 1),
        "fairness_score": fairness,
        "recommended_min_aed": round(median_price * 0.90 / 500) * 500,
        "recommended_max_aed": round(median_price / 500) * 500,
        "verdict": verdict,
        "comparables": comparables,
    }


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--make",    required=True)
    parser.add_argument("--model",   required=True)
    parser.add_argument("--year",    required=True, type=int)
    parser.add_argument("--mileage", required=True, type=int)
    parser.add_argument("--price",   required=True, type=float)
    args = parser.parse_args()

    print(f"\n[price] {args.year} {args.make} {args.model} | {args.mileage:,} km | AED {args.price:,.0f}")
    comparables = await scrape_comparables(args.make, args.model, args.year, args.mileage)
    print(f"\n[price] {len(comparables)} comparables after filtering\n")

    if len(comparables) < MIN_COMPARABLES:
        print("[price] Not enough comparables found.")
        sys.exit(1)

    result = compute_analysis(comparables, args.price, args.make, args.model, args.year, args.mileage)

    print("="*60)
    print("PRICE ANALYSIS")
    print("="*60)
    print(json.dumps({k: v for k, v in result.items() if k != "comparables"}, indent=2))

    print(f"\nSample comparables:")
    for i, c in enumerate(comparables[:5], 1):
        yr   = str(c.get("year") or "N/A")
        km   = f"{c['mileage_km']:,} km" if c.get("mileage_km") else "N/A"
        name = str(c.get("name") or "")[:50]
        print(f"  {i}. {yr} | AED {c['price_aed']:,.0f} | {km} | {name}")
    if len(comparables) > 5:
        print(f"  ... and {len(comparables)-5} more")


if __name__ == "__main__":
    asyncio.run(main())
