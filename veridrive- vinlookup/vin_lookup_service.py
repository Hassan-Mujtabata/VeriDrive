import asyncio
import logging
import os
import re

from dotenv import load_dotenv
load_dotenv()  # reads .env file in the current working directory, if present

from fastapi import FastAPI, HTTPException, Path, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
import httpx
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# ---------------------------------------------------------------------------
# 1. Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 2. Configuration
# ---------------------------------------------------------------------------

# Vehicle Databases (vehicledatabases.com) — real VIN decode, title check, auction history.
VEHICLEDATABASES_API_KEY = os.environ.get("VEHICLEDATABASES_API_KEY", "")
if not VEHICLEDATABASES_API_KEY:
    logger.warning(
        "VEHICLEDATABASES_API_KEY not set — Vehicle Databases lookups will be skipped. "
        "Set it as an environment variable to enable real data."
    )

VIN_REGEX   = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")
HTTPX_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)

# ---------------------------------------------------------------------------
# 3. Rate limiter + app
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="UAE Vehicle Intelligence Aggregator",
    description="Real-time vehicle history check via NHTSA vPIC and Vehicle Databases (decode + title check).",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten to your domain before deploying
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


# ---------------------------------------------------------------------------
# 4. Response model
# ---------------------------------------------------------------------------
class VehicleReportResponse(BaseModel):
    vin: str  = Field(..., description="The verified 17-character VIN")
    make: str = Field(default="Unknown", description="Vehicle manufacturer")
    model: str = Field(default="Unknown", description="Vehicle model")

    # Real data sources — all populated whenever the relevant key/endpoint is reachable.
    nhtsa_decode: dict | None = Field(
        default=None, description="Free, real-time VIN decode from NHTSA's vPIC API (US gov, no key required)"
    )
    vehicledatabases_decode: dict | None = Field(
        default=None, description="Real VIN decode from vehicledatabases.com"
    )
    title_check: dict | None = Field(
        default=None, description="Salvage/total-loss title check from vehicledatabases.com"
    )

    # auction_history: dict | None = Field(
    #     default=None, description="Auction sale/condition history from vehicledatabases.com, "
    #                                "normalized to always include a 'records' list"
    # )

    @field_validator("vin")
    @classmethod
    def validate_vin_structure(cls, v: str) -> str:
        clean_vin = v.strip().upper()
        if not VIN_REGEX.match(clean_vin):
            raise ValueError(
                "Invalid VIN format. Must be 17 alphanumeric characters (excluding I, O, Q)."
            )
        return clean_vin


# ---------------------------------------------------------------------------
# 6. NHTSA vPIC — free, real, no key required
# ---------------------------------------------------------------------------
# US government VIN decoder. No signup, no rate-limit key, genuinely live.
# Returns make/model/year/plant/engine and ~130 other fields for any VIN
# from model year 1981 onward. Docs: https://vpic.nhtsa.dot.gov/api/
async def fetch_nhtsa_data(vin: str) -> dict | None:
    """Calls NHTSA's free public vPIC API for real vehicle specification data."""
    url = f"https://vpic.nhtsa.dot.gov/api/vehicles/decodevin/{vin}?format=json"

    async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
        try:
            logger.info(f"Fetching NHTSA vPIC data for VIN: {vin}")
            response = await client.get(url)
            if response.status_code == 200:
                payload = response.json()
                results = payload.get("Results", [])
                if not results:
                    return {"error": "No results returned"}

                # NHTSA returns a flat list of {Variable, Value, ValueId, VariableId} dicts —
                # normalize into a simple {variable_name: value} dict, dropping empty values.
                decoded = {
                    row["Variable"]: row["Value"]
                    for row in results
                    if row.get("Value") and row["Value"] not in ("Not Applicable", "")
                }
                return decoded
            else:
                logger.error(f"NHTSA HTTP {response.status_code} for VIN {vin}")
                return {"error": f"API communication failure ({response.status_code})"}
        except httpx.RequestError as exc:
            logger.error(f"NHTSA network error: {exc}")
            return {"error": "Connection failed"}


# ---------------------------------------------------------------------------
# 6b. Vehicle Databases — real VIN Decode (confirmed live)
# ---------------------------------------------------------------------------
# Confirmed response shape from a real test call against VIN 5YFT4MCE3MP076873:
#
# {
#   "status": "success",
#   "data": {
#     "intro": {"vin": "..."},
#     "basic": {"make": "...", "model": "...", "year": "...", "trim": "...", ...},
#     "engine": {...}, "manufacturer": {...}, "transmission": {...},
#     "restraint": {...}, "dimensions": {...}, "drivetrain": {...}, "fuel": {...}
#   }
# }
async def fetch_vehicledatabases_data(vin: str) -> dict | None:
    """
    Calls Vehicle Databases' VIN Decoder API for real vehicle specs.
    Returns None (not an error dict) if no key is configured, so callers
    can distinguish "not configured" from "configured but failed".
    """
    if not VEHICLEDATABASES_API_KEY:
        return None

    url = f"https://api.vehicledatabases.com/vin-decode/{vin}"
    headers = {"x-AuthKey": VEHICLEDATABASES_API_KEY}

    async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
        try:
            logger.info(f"Fetching Vehicle Databases VIN decode for VIN: {vin}")
            response = await client.get(url, headers=headers)

            if response.status_code == 200:
                payload = response.json()
                if payload.get("status") == "success":
                    return payload.get("data", {})
                logger.warning(f"Vehicle Databases returned non-success status for VIN {vin}")
                return {"error": "Decode unsuccessful"}
            else:
                logger.error(f"Vehicle Databases HTTP {response.status_code} for VIN {vin}: {response.text[:500]}")
                return {"error": f"API communication failure ({response.status_code})"}

        except httpx.RequestError as exc:
            logger.error(f"Vehicle Databases network error: {exc}")
            return {"error": "Connection failed"}


# ---------------------------------------------------------------------------
# 6c. Vehicle Databases — Title Check (real, confirmed live)
# ---------------------------------------------------------------------------
# Confirmed endpoint from official docs: GET /title-check/{vin}
# (earlier version of this code incorrectly used /vin-title-check/{vin},
# which 404'd — fixed after confirming the real path in their API docs)
#
# Confirmed response shape from a real test call:
# {
#   "status": "success",
#   "data": {
#     "salvage": true,
#     "salvage_details": [
#       {"cause": "Water/flood", "date": "11-03-2021"}
#     ]
#   }
# }
async def fetch_title_check_data(vin: str) -> dict | None:
    """Calls Vehicle Databases' Title Check API for salvage/total-loss history."""
    if not VEHICLEDATABASES_API_KEY:
        return None

    url = f"https://api.vehicledatabases.com/title-check/{vin}"
    headers = {"x-AuthKey": VEHICLEDATABASES_API_KEY}

    async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
        try:
            logger.info(f"Fetching Title Check data for VIN: {vin}")
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                payload = response.json()
                if payload.get("status") == "success":
                    return payload.get("data", {})
                return {"error": "Title check unsuccessful"}
            else:
                logger.error(f"Title Check HTTP {response.status_code} for VIN {vin}: {response.text[:500]}")
                return {"error": f"API communication failure ({response.status_code})"}
        except httpx.RequestError as exc:
            logger.error(f"Title Check network error: {exc}")
            return {"error": "Connection failed"}


# ---------------------------------------------------------------------------
# 6d. Vehicle Databases — Auction History (built & tested, currently disabled
#     to conserve API credits — uncomment to re-enable)
# ---------------------------------------------------------------------------
# Confirmed real response when no auction records exist for a VIN:
#   "No records found for this vehicle" — this is a legitimate empty result,
#   not every car passes through auction, so absence of data is expected.
#
# async def fetch_auction_data(vin: str) -> dict | None:
#     """
#     Calls Vehicle Databases' Auction History API for prior sale/condition records.
#     Always returns a normalized dict shape: {"records": [...]} on success,
#     {"records": [], "note": "..."} when nothing was found, or {"error": "..."}.
#     The underlying API itself is inconsistent — sometimes "data" is a dict,
#     sometimes a list of sale records directly — so we normalize here rather
#     than push that inconsistency up into the response model.
#     """
#     if not VEHICLEDATABASES_API_KEY:
#         return None
#
#     url = f"https://api.vehicledatabases.com/auction/{vin}"
#     headers = {"x-AuthKey": VEHICLEDATABASES_API_KEY}
#
#     async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
#         try:
#             logger.info(f"Fetching Auction History data for VIN: {vin}")
#             response = await client.get(url, headers=headers)
#             if response.status_code == 200:
#                 payload = response.json()
#                 if payload.get("status") == "success":
#                     data = payload.get("data", [])
#                     if isinstance(data, list):
#                         return {"records": data}
#                     if isinstance(data, dict):
#                         return {"records": data.get("records", [data] if data else [])}
#                     return {"records": []}
#                 return {"records": [], "note": payload.get("message", "No records found")}
#             else:
#                 logger.error(f"Auction HTTP {response.status_code} for VIN {vin}: {response.text[:500]}")
#                 return {"error": f"API communication failure ({response.status_code})"}
#         except httpx.RequestError as exc:
#             logger.error(f"Auction network error: {exc}")
#             return {"error": "Connection failed"}


# ---------------------------------------------------------------------------
# 7. Routes
# ---------------------------------------------------------------------------
@app.get("/", include_in_schema=False)
async def serve_frontend():
    return FileResponse("static/index.html")


@app.get("/health", tags=["Meta"])
async def health_check():
    return {"status": "ok"}


@app.get("/api/check-vehicle/{vin}", response_model=VehicleReportResponse, tags=["Vehicle"])
@limiter.limit("20/minute")
async def check_vehicle_vin(
    request: Request,
    vin: str = Path(..., description="17-character VIN"),
):
    sanitized_vin = vin.strip().upper()
    if not VIN_REGEX.match(sanitized_vin):
        raise HTTPException(status_code=400, detail="Malformed VIN string.")

    logger.info(f"Processing VIN: {sanitized_vin}")

    nhtsa_result, vd_result, title_result = await asyncio.gather(
        fetch_nhtsa_data(sanitized_vin),
        fetch_vehicledatabases_data(sanitized_vin),
        fetch_title_check_data(sanitized_vin),
        return_exceptions=True,
    )
    # To re-enable Auction History: uncomment fetch_auction_data above, add it
    # as a 4th argument to gather() here, unpack it into `auction_result`,
    # and pass `auction_history=auction_result` into VehicleReportResponse below.

    if isinstance(nhtsa_result, Exception):
        logger.error(f"NHTSA task raised: {nhtsa_result}")
        nhtsa_result = {"error": "Internal error during NHTSA decode"}

    if isinstance(vd_result, Exception):
        logger.error(f"Vehicle Databases task raised: {vd_result}")
        vd_result = {"error": "Internal error during decode"}

    if isinstance(title_result, Exception):
        logger.error(f"Title Check task raised: {title_result}")
        title_result = {"error": "Internal error during title check"}

    # Prefer Vehicle Databases for make/model if available, fall back to NHTSA.
    vd_basic = (vd_result or {}).get("basic", {}) if isinstance(vd_result, dict) else {}
    nhtsa_safe = nhtsa_result if isinstance(nhtsa_result, dict) else {}

    report = VehicleReportResponse(
        vin=sanitized_vin,
        make=vd_basic.get("make") or nhtsa_safe.get("Make", "Unknown"),
        model=vd_basic.get("model") or nhtsa_safe.get("Model", "Unknown"),
        nhtsa_decode=nhtsa_result,
        vehicledatabases_decode=vd_result,
        title_check=title_result,
    )

    logger.info(f"Report compiled for VIN: {sanitized_vin}")
    return report


# ---------------------------------------------------------------------------
# 8. Dev entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    # Defaults to 8001, not 8000 — this VIN lookup service runs alongside
    # the main VeriDrive pipeline backend (which typically uses 8000), so
    # a distinct port avoids a collision when both run on the same machine.
    # Override with: VIN_SERVICE_PORT=8002 python main.py
    port = int(os.environ.get("VIN_SERVICE_PORT", 8001))
    uvicorn.run("main:app", host="127.0.0.1", port=port, reload=True)


# ===========================================================================
# 9. PENDING INTEGRATIONS — not yet built, awaiting API approval
# ===========================================================================
# The two stubs below are placeholders only. Neither ClearVIN nor VinAudit
# access has been approved yet (see README.md "Future Improvements" for
# context). Once a key is issued, fill in the real endpoint, headers, and
# response-parsing logic following the same pattern as fetch_title_check_data
# above, then wire it into check_vehicle_vin() the same way.
#
# CLEARVIN_API_KEY = os.environ.get("CLEARVIN_API_KEY", "")
#
# async def fetch_clearvin_data(vin: str) -> dict | None:
#     """
#     Calls ClearVIN's API — likely NMVTIS title records, theft check, and/or
#     recalls depending on which product tier is approved. Confirm the real
#     endpoint URL, auth header name, and response shape from ClearVIN's
#     documentation before filling this in; the values below are placeholders.
#     """
#     if not CLEARVIN_API_KEY:
#         return None
#
#     url = f"https://api.clearvin.com/REPLACE_WITH_REAL_ENDPOINT/{vin}"
#     headers = {"Authorization": f"Bearer {CLEARVIN_API_KEY}"}
#
#     async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
#         try:
#             response = await client.get(url, headers=headers)
#             if response.status_code == 200:
#                 return response.json()
#             return {"error": f"API communication failure ({response.status_code})"}
#         except httpx.RequestError as exc:
#             return {"error": "Connection failed"}
#
#
# VINAUDIT_API_KEY = os.environ.get("VINAUDIT_API_KEY", "")
#
# async def fetch_vinaudit_data(vin: str) -> dict | None:
#     """
#     Calls VinAudit's API — independent title/salvage cross-check, still
#     pending their internal review as of this version. Confirm the real
#     endpoint URL, auth method, and response shape once approved; the values
#     below are placeholders.
#     """
#     if not VINAUDIT_API_KEY:
#         return None
#
#     url = f"https://api.vinaudit.com/REPLACE_WITH_REAL_ENDPOINT/{vin}"
#     headers = {"Authorization": f"Bearer {VINAUDIT_API_KEY}"}
#
#     async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
#         try:
#             response = await client.get(url, headers=headers)
#             if response.status_code == 200:
#                 return response.json()
#             return {"error": f"API communication failure ({response.status_code})"}
#         except httpx.RequestError as exc:
#             return {"error": "Connection failed"}
