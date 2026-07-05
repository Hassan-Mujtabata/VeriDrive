"""
VeriDrive - Dubizzle Listing Scraper
=====================================
Extracts listing data from any Dubizzle used car listing URL.

Approach:
- Dubizzle is a Next.js app. All listing data is server-side rendered
  into window.__NEXT_DATA__ as JSON. No HTML parsing needed.
- We use Playwright to load the page, extract that JSON, and parse it.
- For the seller phone number, we click the reveal button and capture
  the number that appears in the DOM.

Usage:
    python dubizzle_scraper.py <dubizzle_url>

Example:
    python dubizzle_scraper.py "https://dubai.dubizzle.com/motors/used-cars/toyota/corolla/..."
"""

import asyncio
import json
import re
import sys
from playwright.async_api import async_playwright


# ── helpers ──────────────────────────────────────────────────────────────────

def extract_field(details: list, slug: str) -> str | None:
    """Pull a value from the listing details array by its slug."""
    for item in details:
        if item.get("slug") == slug:
            return item.get("value")
    return None


def parse_mileage(value: str | None) -> int | None:
    """Convert '110,179' or '110179 km' to integer."""
    if not value:
        return None
    digits = re.sub(r"[^\d]", "", value)
    return int(digits) if digits else None


def parse_price(raw: str | None) -> float | None:
    if not raw:
        return None
    digits = re.sub(r"[^\d.]", "", raw)
    return float(digits) if digits else None


def clean_description(html: str | None) -> str:
    """Strip HTML tags and clean up the description text."""
    if not html:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()



# ── popup dismissal ───────────────────────────────────────────────────────────

CLOSE_SELECTORS = [
    "[aria-label='Close']",
    "[aria-label='close']",
    "button[aria-label='Close']",
    "[data-testid='modal-close']",
    "[data-testid='close-button']",
    ".modal-close",
    ".popup-close",
    "button.close",
    "svg[aria-label='Close']",
    "button:has(svg):near(:text('Cancel'))",
]

PATTERN_RULES = [
    # (keywords in popup text, button text to click)
    (["import", "export", "browse export"],         "Cancel"),
    (["cookie", "cookies", "privacy policy"],        "Reject"),
    (["cookie", "cookies"],                          "Accept"),
    (["sign in", "log in", "login", "register"],     "Cancel"),
    (["newsletter", "subscribe", "notification"],    "No thanks"),
    (["enable notifications", "allow notifications"],"Block"),
    (["download", "app store", "google play"],       "Cancel"),
    (["verify", "verification", "verify now"],       "Cancel"),
    (["join", "community", "get verified"],          "Cancel"),
]


async def _try_click(page, selector: str) -> bool:
    try:
        el = page.locator(selector).first
        if await el.is_visible(timeout=400):
            await el.click(timeout=800)
            await page.wait_for_timeout(500)
            return True
    except Exception:
        pass
    return False


async def _get_popup_text(page) -> str | None:
    try:
        for sel in ["[role='dialog']", ".modal", "[class*='popup']", "[class*='overlay']", "[class*='Modal']"]:
            el = page.locator(sel).first
            if await el.is_visible(timeout=400):
                return (await el.inner_text(timeout=1000)).lower()
    except Exception:
        pass
    return None


async def _gemini_dismiss(page, popup_text: str) -> bool:
    try:
        import os
        from google import genai
        from google.genai import types
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return False
        client = genai.Client(api_key=api_key)
        buttons = await page.locator("button").all_inner_texts()
        prompt = (
            f"A popup appeared on a car listing website with this text:\n\"{popup_text}\"\n\n"
            f"Available buttons: {buttons}\n\n"
            f"Which button should be clicked to close this popup WITHOUT changing any search results, "
            f"preferences, or site behaviour? Reply with ONLY the exact button text, nothing else."
        )
        response = client.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents=prompt,
        )
        btn_text = response.text.strip().strip('"')
        print(f"[scraper] Gemini says click: '{btn_text}'")
        return await _try_click(page, f"button:has-text('{btn_text}')")
    except Exception as e:
        print(f"[scraper] Gemini dismiss failed: {e}")
        return False


async def dismiss_popups(page) -> int:
    """
    Layered popup dismissal:
      1. Try close/cross icon first (safest)
      2. Read popup text, pattern match to safe button
      3. Gemini fallback only if pattern match fails
    Returns number of popups dismissed.
    """
    dismissed = 0

    for attempt in range(3):
        # Step 1 — cross/close icon
        for sel in CLOSE_SELECTORS:
            if await _try_click(page, sel):
                print(f"[scraper] Closed popup via X button")
                dismissed += 1
                await page.wait_for_timeout(400)
                break
        else:
            # Step 2 — read popup text and pattern match
            popup_text = await _get_popup_text(page)
            if not popup_text:
                break

            print(f"[scraper] Popup detected: '{popup_text[:80].strip()}'")
            matched = False
            for keywords, btn_text in PATTERN_RULES:
                if any(kw in popup_text for kw in keywords):
                    if await _try_click(page, f"button:has-text('{btn_text}')"):
                        print(f"[scraper] Dismissed via pattern match → '{btn_text}'")
                        dismissed += 1
                        matched = True
                        break

            # Step 3 — Gemini fallback
            if not matched:
                print(f"[scraper] No pattern match — asking Gemini...")
                if await _gemini_dismiss(page, popup_text):
                    dismissed += 1
                else:
                    print(f"[scraper] Could not dismiss popup — continuing anyway")
                    break

    return dismissed




async def scrape_listing(url: str) -> dict:
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,  # Run with visible browser to avoid bot detection
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ]
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            viewport={"width": 1280, "height": 800},
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )

        # Remove webdriver property to avoid bot detection
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        page = await context.new_page()

        print(f"[scraper] Loading: {url}")
        await page.goto(url, wait_until="networkidle", timeout=45000)
        await page.wait_for_timeout(3000)

        # Dismiss any popups that appeared on load
        popped = await dismiss_popups(page)
        if popped:
            await page.wait_for_timeout(800)

        # Debug: print page title so we know what loaded
        title = await page.title()
        print(f"[scraper] Page title: {title}")

        # ── Step 1: Extract __NEXT_DATA__ ────────────────────────────────────
        next_data_raw = await page.evaluate("() => JSON.stringify(window.__NEXT_DATA__)")

        # If data missing, try dismissing popups and retry once
        if not next_data_raw or next_data_raw == "null":
            print("[scraper] No __NEXT_DATA__ found — checking for blocking popups...")
            popped = await dismiss_popups(page)
            if popped:
                await page.wait_for_timeout(1000)
                next_data_raw = await page.evaluate("() => JSON.stringify(window.__NEXT_DATA__)")

        if not next_data_raw or next_data_raw == "null":
            raise ValueError("Could not find __NEXT_DATA__ on this page. Is it a valid Dubizzle listing?")

        next_data = json.loads(next_data_raw)

        # Navigate to the listing payload
        actions = next_data["props"]["pageProps"]["reduxWrapperActionsGIPP"]
        listing_payload = None
        for action in actions:
            if action.get("type") == "listings/detailRequest/fulfilled":
                listing_payload = action["payload"]
                break

        if not listing_payload:
            raise ValueError("Could not find listing data in __NEXT_DATA__.")

        listing    = listing_payload["listing"]
        ad_ops     = listing_payload.get("ad_ops", {})
        lister     = listing_payload.get("lister", {})

        # ── Step 2: Parse core fields ─────────────────────────────────────────
        details_secondary = listing.get("details", {}).get("secondary", [])
        details_primary   = listing.get("details", {}).get("primary",   [])
        all_details       = details_secondary + details_primary

        make        = ad_ops.get("auto_make_name") or extract_field(all_details, "make")
        model       = ad_ops.get("auto_model_name") or extract_field(all_details, "model")
        year_str    = ad_ops.get("year") or extract_field(all_details, "year")
        year        = int(year_str) if year_str and year_str.isdigit() else None

        mileage_raw = extract_field(all_details, "kilometers")
        mileage_km  = parse_mileage(mileage_raw)

        price_raw   = listing.get("price", {}).get("raw")
        price_aed   = parse_price(price_raw)

        fuel_type   = extract_field(all_details, "fuel_type") or ad_ops.get("fuel")
        body_type   = extract_field(all_details, "body_type")
        specs       = extract_field(all_details, "regional_specs")
        ext_color   = extract_field(all_details, "exterior_color")
        int_color   = extract_field(all_details, "interior_color")
        seller_type = extract_field(all_details, "seller_type")
        cylinders   = extract_field(all_details, "no_of_cylinders")
        doors       = extract_field(all_details, "doors")
        horsepower  = extract_field(all_details, "horsepower")
        trim        = extract_field(all_details, "motors_trim")
        warranty    = extract_field(all_details, "warranty")

        location_name = listing.get("location", {}).get("name", "")
        coords        = listing.get("location", {}).get("coordinates", {})

        photos = listing.get("photos", [])

        description_raw = listing.get("description", "")
        description     = clean_description(description_raw)

        listing_title = listing.get("name", "")
        listing_uuid  = listing.get("uuid", "")
        listing_id    = listing.get("listing_id")
        short_url     = listing.get("short_url", "")

        seller_name = lister.get("name", "")
        seller_id   = lister.get("legacy_id")
        phone_available = listing_payload.get("leads", {}).get("is_phone_number_available", False)

        # ── Step 3: Attempt phone number reveal ───────────────────────────────
        seller_phone = None
        if phone_available:
            try:
                print("[scraper] Attempting to reveal seller phone number...")
                await dismiss_popups(page)
                # Click the call/phone button
                call_btn = page.locator(
                    "button:has-text('Call'), "
                    "button:has-text('Show number'), "
                    "button:has-text('Phone'), "
                    "[data-testid='call-button'], "
                    "[data-testid='show-phone']"
                ).first
                await call_btn.click(timeout=5000)
                await page.wait_for_timeout(1500)

                # Try to find the revealed phone number in the DOM
                phone_el = page.locator(
                    "a[href^='tel:'], "
                    "[data-testid='phone-number'], "
                    ".phone-number"
                ).first
                phone_text = await phone_el.inner_text(timeout=3000)
                seller_phone = re.sub(r"[^\d+]", "", phone_text).strip() or None
                if seller_phone:
                    print(f"[scraper] Phone number found: {seller_phone}")
            except Exception as e:
                print(f"[scraper] Could not reveal phone number: {e}")
                # Try extracting from description as fallback
                phone_match = re.search(r"(\+971[\s\-]?\d{2}[\s\-]?\d{3}[\s\-]?\d{4}|\b05\d[\s\-]?\d{3}[\s\-]?\d{4})", description)
                if phone_match:
                    seller_phone = re.sub(r"[\s\-]", "", phone_match.group(1))
                    print(f"[scraper] Phone extracted from description: {seller_phone}")

        await browser.close()

        # ── Step 4: Assemble output ───────────────────────────────────────────
        result = {
            "listing_url": url,
            "listing_id": listing_id,
            "listing_uuid": listing_uuid,
            "listing_title": listing_title,
            "short_url": short_url,

            # Core vehicle data
            "make": make,
            "model": model,
            "year": year,
            "trim": trim,
            "mileage_km": mileage_km,
            "asking_price_aed": price_aed,

            # Specs
            "fuel_type": fuel_type,
            "body_type": body_type,
            "regional_specs": specs,
            "exterior_color": ext_color,
            "interior_color": int_color,
            "cylinders": cylinders,
            "doors": doors,
            "horsepower": horsepower,
            "warranty": warranty,
            "seller_type": seller_type,

            # Location
            "emirate": ad_ops.get("emirate", "").title(),
            "location": location_name,
            "latitude": float(coords.get("lat", 0)) if coords.get("lat") else None,
            "longitude": float(coords.get("lng", 0)) if coords.get("lng") else None,

            # Seller
            "seller_name": seller_name,
            "seller_id": seller_id,
            "seller_phone": seller_phone,

            # Content
            "description": description,
            "photos": photos,
            "photo_count": len(photos),
        }

        return result


# ── entry point ───────────────────────────────────────────────────────────────

async def main():
    if len(sys.argv) < 2:
        print("Usage: python dubizzle_scraper.py <dubizzle_url>")
        sys.exit(1)

    url = sys.argv[1]
    result = await scrape_listing(url)
    print("\n" + "="*60)
    print("SCRAPED LISTING DATA")
    print("="*60)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


if __name__ == "__main__":
    asyncio.run(main())