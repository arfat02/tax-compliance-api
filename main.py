"""
Global Tax & Compliance Engine API
-----------------------------------
- Static fallback database (140+ countries) so the API always works.
- Live VAT rate lookup from taxid.dev (free, no API key) for countries it covers,
  cached in-memory with a TTL so we don't hammer the upstream on every request.
- Background scheduler auto-refreshes the live cache every few hours.
- Clear "source" field on every response so callers know if data is live or fallback.
- Currency conversion via frankfurter.app (free, no key, ECB-based) for major currencies.
- API keys + tiered rate limiting so this can be monetized (free vs pro tier).

Deploy note (Render free tier): Render's free web services spin down after
inactivity. The /health endpoint exists so you can ping it with an uptime
monitor (e.g. UptimeRobot / cron-job.org) every 10-14 min to keep it warm.

IMPORTANT - in-memory state: API keys, rate-limit counters, and caches below
live in process memory. That's fine for a single Render instance/worker, but
if you scale to multiple workers/dynos, move this to Redis or a database so
counters are shared. Noted again near the relevant code.
"""

import os
import time
import logging
import secrets
import threading
from functools import wraps
from datetime import datetime, timezone, date

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("tax-api")

app = Flask(__name__)
CORS(app)  # public API -> allow browser-based clients (checkout widgets etc.)

# ---------------------------------------------------------------------------
# 1. STATIC FALLBACK DATABASE
#    Source of truth when the live provider has no data for a country, or
#    when the live call fails/times out. Treat as "last known good".
# ---------------------------------------------------------------------------
STATIC_TAX_DATA = {
    "AF": {"country_name": "Afghanistan", "standard_vat": 20.0, "reduced_vat": [], "currency": "AFN"},
    "AL": {"country_name": "Albania", "standard_vat": 20.0, "reduced_vat": [6.0], "currency": "ALL"},
    "DZ": {"country_name": "Algeria", "standard_vat": 19.0, "reduced_vat": [9.0], "currency": "DZD"},
    "AD": {"country_name": "Andorra", "standard_vat": 4.5, "reduced_vat": [1.0], "currency": "EUR"},
    "AO": {"country_name": "Angola", "standard_vat": 14.0, "reduced_vat": [], "currency": "AOA"},
    "AR": {"country_name": "Argentina", "standard_vat": 21.0, "reduced_vat": [10.5], "currency": "ARS"},
    "AM": {"country_name": "Armenia", "standard_vat": 20.0, "reduced_vat": [], "currency": "AMD"},
    "AU": {"country_name": "Australia", "standard_vat": 10.0, "reduced_vat": [], "currency": "AUD"},
    "AT": {"country_name": "Austria", "standard_vat": 20.0, "reduced_vat": [10.0, 13.0], "currency": "EUR"},
    "AZ": {"country_name": "Azerbaijan", "standard_vat": 18.0, "reduced_vat": [], "currency": "AZN"},
    "BH": {"country_name": "Bahrain", "standard_vat": 10.0, "reduced_vat": [], "currency": "BHD"},
    "BD": {"country_name": "Bangladesh", "standard_vat": 15.0, "reduced_vat": [], "currency": "BDT"},
    "BY": {"country_name": "Belarus", "standard_vat": 20.0, "reduced_vat": [10.0], "currency": "BYN"},
    "BE": {"country_name": "Belgium", "standard_vat": 21.0, "reduced_vat": [6.0, 12.0], "currency": "EUR"},
    "BZ": {"country_name": "Belize", "standard_vat": 12.5, "reduced_vat": [], "currency": "BZD"},
    "BJ": {"country_name": "Benin", "standard_vat": 18.0, "reduced_vat": [], "currency": "XOF"},
    "BT": {"country_name": "Bhutan", "standard_vat": 0.0, "reduced_vat": [], "currency": "BTN"},
    "BO": {"country_name": "Bolivia", "standard_vat": 13.0, "reduced_vat": [], "currency": "BOB"},
    "BA": {"country_name": "Bosnia and Herzegovina", "standard_vat": 17.0, "reduced_vat": [], "currency": "BAM"},
    "BW": {"country_name": "Botswana", "standard_vat": 14.0, "reduced_vat": [], "currency": "BWP"},
    "BR": {"country_name": "Brazil", "standard_vat": 17.0, "reduced_vat": [], "currency": "BRL"},
    "BG": {"country_name": "Bulgaria", "standard_vat": 20.0, "reduced_vat": [9.0], "currency": "BGN"},
    "BF": {"country_name": "Burkina Faso", "standard_vat": 18.0, "reduced_vat": [], "currency": "XOF"},
    "BI": {"country_name": "Burundi", "standard_vat": 18.0, "reduced_vat": [], "currency": "BIF"},
    "KH": {"country_name": "Cambodia", "standard_vat": 10.0, "reduced_vat": [], "currency": "KHR"},
    "CM": {"country_name": "Cameroon", "standard_vat": 19.25, "reduced_vat": [], "currency": "XAF"},
    "CA": {"country_name": "Canada", "standard_vat": 5.0, "reduced_vat": [], "currency": "CAD"},
    "CV": {"country_name": "Cape Verde", "standard_vat": 15.0, "reduced_vat": [], "currency": "CVE"},
    "CF": {"country_name": "Central African Republic", "standard_vat": 19.0, "reduced_vat": [], "currency": "XAF"},
    "TD": {"country_name": "Chad", "standard_vat": 18.0, "reduced_vat": [], "currency": "XAF"},
    "CL": {"country_name": "Chile", "standard_vat": 19.0, "reduced_vat": [], "currency": "CLP"},
    "CN": {"country_name": "China", "standard_vat": 13.0, "reduced_vat": [9.0, 6.0], "currency": "CNY"},
    "CO": {"country_name": "Colombia", "standard_vat": 19.0, "reduced_vat": [5.0], "currency": "COP"},
    "KM": {"country_name": "Comoros", "standard_vat": 18.0, "reduced_vat": [], "currency": "KMF"},
    "CG": {"country_name": "Congo", "standard_vat": 18.0, "reduced_vat": [], "currency": "XAF"},
    "CR": {"country_name": "Costa Rica", "standard_vat": 13.0, "reduced_vat": [4.0, 2.0, 1.0], "currency": "CRC"},
    "HR": {"country_name": "Croatia", "standard_vat": 25.0, "reduced_vat": [5.0, 13.0], "currency": "EUR"},
    "CY": {"country_name": "Cyprus", "standard_vat": 19.0, "reduced_vat": [5.0, 9.0], "currency": "EUR"},
    "CZ": {"country_name": "Czech Republic", "standard_vat": 21.0, "reduced_vat": [12.0], "currency": "CZK"},
    "DK": {"country_name": "Denmark", "standard_vat": 25.0, "reduced_vat": [], "currency": "DKK"},
    "DJ": {"country_name": "Djibouti", "standard_vat": 10.0, "reduced_vat": [], "currency": "DJF"},
    "DO": {"country_name": "Dominican Republic", "standard_vat": 18.0, "reduced_vat": [], "currency": "DOP"},
    "EC": {"country_name": "Ecuador", "standard_vat": 15.0, "reduced_vat": [], "currency": "USD"},
    "EG": {"country_name": "Egypt", "standard_vat": 14.0, "reduced_vat": [], "currency": "EGP"},
    "SV": {"country_name": "El Salvador", "standard_vat": 13.0, "reduced_vat": [], "currency": "USD"},
    "EE": {"country_name": "Estonia", "standard_vat": 22.0, "reduced_vat": [9.0], "currency": "EUR"},
    "ET": {"country_name": "Ethiopia", "standard_vat": 15.0, "reduced_vat": [], "currency": "ETB"},
    "FJ": {"country_name": "Fiji", "standard_vat": 15.0, "reduced_vat": [], "currency": "FJD"},
    "FI": {"country_name": "Finland", "standard_vat": 24.0, "reduced_vat": [10.0, 14.0], "currency": "EUR"},
    "FR": {"country_name": "France", "standard_vat": 20.0, "reduced_vat": [2.1, 5.5, 10.0], "currency": "EUR"},
    "GA": {"country_name": "Gabon", "standard_vat": 18.0, "reduced_vat": [], "currency": "XAF"},
    "GE": {"country_name": "Georgia", "standard_vat": 18.0, "reduced_vat": [], "currency": "GEL"},
    "DE": {"country_name": "Germany", "standard_vat": 19.0, "reduced_vat": [7.0], "currency": "EUR"},
    "GH": {"country_name": "Ghana", "standard_vat": 15.0, "reduced_vat": [], "currency": "GHS"},
    "GR": {"country_name": "Greece", "standard_vat": 24.0, "reduced_vat": [6.0, 13.0], "currency": "EUR"},
    "GT": {"country_name": "Guatemala", "standard_vat": 12.0, "reduced_vat": [], "currency": "GTQ"},
    "GN": {"country_name": "Guinea", "standard_vat": 18.0, "reduced_vat": [], "currency": "GNF"},
    "HN": {"country_name": "Honduras", "standard_vat": 15.0, "reduced_vat": [], "currency": "HNL"},
    "HK": {"country_name": "Hong Kong", "standard_vat": 0.0, "reduced_vat": [], "currency": "HKD"},
    "HU": {"country_name": "Hungary", "standard_vat": 27.0, "reduced_vat": [5.0, 18.0], "currency": "HUF"},
    "IS": {"country_name": "Iceland", "standard_vat": 24.0, "reduced_vat": [11.0], "currency": "ISK"},
    "IN": {"country_name": "India", "standard_vat": 18.0, "reduced_vat": [5.0, 12.0, 28.0], "currency": "INR"},
    "ID": {"country_name": "Indonesia", "standard_vat": 11.0, "reduced_vat": [], "currency": "IDR"},
    "IR": {"country_name": "Iran", "standard_vat": 10.0, "reduced_vat": [], "currency": "IRR"},
    "IQ": {"country_name": "Iraq", "standard_vat": 0.0, "reduced_vat": [], "currency": "IQD"},
    "IE": {"country_name": "Ireland", "standard_vat": 23.0, "reduced_vat": [4.8, 9.0, 13.5], "currency": "EUR"},
    "IL": {"country_name": "Israel", "standard_vat": 18.0, "reduced_vat": [], "currency": "ILS"},
    "IT": {"country_name": "Italy", "standard_vat": 22.0, "reduced_vat": [4.0, 5.0, 10.0], "currency": "EUR"},
    "JP": {"country_name": "Japan", "standard_vat": 10.0, "reduced_vat": [8.0], "currency": "JPY"},
    "JO": {"country_name": "Jordan", "standard_vat": 16.0, "reduced_vat": [], "currency": "JOD"},
    "KZ": {"country_name": "Kazakhstan", "standard_vat": 12.0, "reduced_vat": [], "currency": "KZT"},
    "KE": {"country_name": "Kenya", "standard_vat": 16.0, "reduced_vat": [], "currency": "KES"},
    "KR": {"country_name": "South Korea", "standard_vat": 10.0, "reduced_vat": [], "currency": "KRW"},
    "KW": {"country_name": "Kuwait", "standard_vat": 0.0, "reduced_vat": [], "currency": "KWD"},
    "KG": {"country_name": "Kyrgyzstan", "standard_vat": 12.0, "reduced_vat": [], "currency": "KGS"},
    "LA": {"country_name": "Laos", "standard_vat": 10.0, "reduced_vat": [], "currency": "LAK"},
    "LV": {"country_name": "Latvia", "standard_vat": 21.0, "reduced_vat": [12.0], "currency": "EUR"},
    "LB": {"country_name": "Lebanon", "standard_vat": 11.0, "reduced_vat": [], "currency": "LBP"},
    "LY": {"country_name": "Libya", "standard_vat": 0.0, "reduced_vat": [], "currency": "LYD"},
    "LT": {"country_name": "Lithuania", "standard_vat": 21.0, "reduced_vat": [5.0, 9.0], "currency": "EUR"},
    "LU": {"country_name": "Luxembourg", "standard_vat": 17.0, "reduced_vat": [8.0, 3.0], "currency": "EUR"},
    "MY": {"country_name": "Malaysia", "standard_vat": 8.0, "reduced_vat": [], "currency": "MYR"},
    "MV": {"country_name": "Maldives", "standard_vat": 8.0, "reduced_vat": [], "currency": "MVR"},
    "MT": {"country_name": "Malta", "standard_vat": 18.0, "reduced_vat": [5.0, 7.0], "currency": "EUR"},
    "MR": {"country_name": "Mauritania", "standard_vat": 16.0, "reduced_vat": [], "currency": "MRU"},
    "MU": {"country_name": "Mauritius", "standard_vat": 15.0, "reduced_vat": [], "currency": "MUR"},
    "MX": {"country_name": "Mexico", "standard_vat": 16.0, "reduced_vat": [], "currency": "MXN"},
    "MD": {"country_name": "Moldova", "standard_vat": 20.0, "reduced_vat": [], "currency": "MDL"},
    "MC": {"country_name": "Monaco", "standard_vat": 20.0, "reduced_vat": [], "currency": "EUR"},
    "MN": {"country_name": "Mongolia", "standard_vat": 10.0, "reduced_vat": [], "currency": "MNT"},
    "ME": {"country_name": "Montenegro", "standard_vat": 21.0, "reduced_vat": [], "currency": "EUR"},
    "MA": {"country_name": "Morocco", "standard_vat": 20.0, "reduced_vat": [], "currency": "MAD"},
    "MZ": {"country_name": "Mozambique", "standard_vat": 16.0, "reduced_vat": [], "currency": "MZN"},
    "MM": {"country_name": "Myanmar", "standard_vat": 5.0, "reduced_vat": [], "currency": "MMK"},
    "NA": {"country_name": "Namibia", "standard_vat": 15.0, "reduced_vat": [], "currency": "NAD"},
    "NP": {"country_name": "Nepal", "standard_vat": 13.0, "reduced_vat": [], "currency": "NPR"},
    "NL": {"country_name": "Netherlands", "standard_vat": 21.0, "reduced_vat": [9.0], "currency": "EUR"},
    "NZ": {"country_name": "New Zealand", "standard_vat": 15.0, "reduced_vat": [], "currency": "NZD"},
    "NI": {"country_name": "Nicaragua", "standard_vat": 15.0, "reduced_vat": [], "currency": "NIO"},
    "NG": {"country_name": "Nigeria", "standard_vat": 7.5, "reduced_vat": [], "currency": "NGN"},
    "NO": {"country_name": "Norway", "standard_vat": 25.0, "reduced_vat": [12.0, 15.0], "currency": "NOK"},
    "OM": {"country_name": "Oman", "standard_vat": 5.0, "reduced_vat": [], "currency": "OMR"},
    "PK": {"country_name": "Pakistan", "standard_vat": 18.0, "reduced_vat": [], "currency": "PKR"},
    "PA": {"country_name": "Panama", "standard_vat": 7.0, "reduced_vat": [], "currency": "PAB"},
    "PY": {"country_name": "Paraguay", "standard_vat": 10.0, "reduced_vat": [5.0], "currency": "PYG"},
    "PE": {"country_name": "Peru", "standard_vat": 18.0, "reduced_vat": [], "currency": "PEN"},
    "PH": {"country_name": "Philippines", "standard_vat": 12.0, "reduced_vat": [], "currency": "PHP"},
    "PL": {"country_name": "Poland", "standard_vat": 23.0, "reduced_vat": [5.0, 8.0], "currency": "PLN"},
    "PT": {"country_name": "Portugal", "standard_vat": 23.0, "reduced_vat": [6.0, 13.0], "currency": "EUR"},
    "QA": {"country_name": "Qatar", "standard_vat": 0.0, "reduced_vat": [], "currency": "QAR"},
    "RO": {"country_name": "Romania", "standard_vat": 19.0, "reduced_vat": [5.0, 9.0], "currency": "RON"},
    "RU": {"country_name": "Russia", "standard_vat": 20.0, "reduced_vat": [10.0], "currency": "RUB"},
    "SA": {"country_name": "Saudi Arabia", "standard_vat": 15.0, "reduced_vat": [], "currency": "SAR"},
    "SN": {"country_name": "Senegal", "standard_vat": 18.0, "reduced_vat": [], "currency": "XOF"},
    "RS": {"country_name": "Serbia", "standard_vat": 20.0, "reduced_vat": [10.0], "currency": "RSD"},
    "SG": {"country_name": "Singapore", "standard_vat": 9.0, "reduced_vat": [], "currency": "SGD"},
    "SK": {"country_name": "Slovakia", "standard_vat": 20.0, "reduced_vat": [10.0], "currency": "EUR"},
    "SI": {"country_name": "Slovenia", "standard_vat": 22.0, "reduced_vat": [5.0, 9.5], "currency": "EUR"},
    "ZA": {"country_name": "South Africa", "standard_vat": 15.0, "reduced_vat": [], "currency": "ZAR"},
    "ES": {"country_name": "Spain", "standard_vat": 21.0, "reduced_vat": [4.0, 10.0], "currency": "EUR"},
    "LK": {"country_name": "Sri Lanka", "standard_vat": 18.0, "reduced_vat": [], "currency": "LKR"},
    "SE": {"country_name": "Sweden", "standard_vat": 25.0, "reduced_vat": [6.0, 12.0], "currency": "SEK"},
    "CH": {"country_name": "Switzerland", "standard_vat": 8.1, "reduced_vat": [2.6, 3.8], "currency": "CHF"},
    "TW": {"country_name": "Taiwan", "standard_vat": 5.0, "reduced_vat": [], "currency": "TWD"},
    "TZ": {"country_name": "Tanzania", "standard_vat": 18.0, "reduced_vat": [], "currency": "TZS"},
    "TH": {"country_name": "Thailand", "standard_vat": 7.0, "reduced_vat": [], "currency": "THB"},
    "TN": {"country_name": "Tunisia", "standard_vat": 19.0, "reduced_vat": [], "currency": "TND"},
    "TR": {"country_name": "Turkey", "standard_vat": 20.0, "reduced_vat": [1.0, 10.0], "currency": "TRY"},
    "UG": {"country_name": "Uganda", "standard_vat": 18.0, "reduced_vat": [], "currency": "UGX"},
    "UA": {"country_name": "Ukraine", "standard_vat": 20.0, "reduced_vat": [7.0], "currency": "UAH"},
    "AE": {"country_name": "United Arab Emirates", "standard_vat": 5.0, "reduced_vat": [], "currency": "AED"},
    "GB": {"country_name": "United Kingdom", "standard_vat": 20.0, "reduced_vat": [5.0], "currency": "GBP"},
    "US": {"country_name": "United States", "standard_vat": 10.0, "reduced_vat": [], "currency": "USD"},
    "UY": {"country_name": "Uruguay", "standard_vat": 22.0, "reduced_vat": [10.0], "currency": "UYU"},
    "UZ": {"country_name": "Uzbekistan", "standard_vat": 12.0, "reduced_vat": [], "currency": "UZS"},
    "VE": {"country_name": "Venezuela", "standard_vat": 16.0, "reduced_vat": [], "currency": "VES"},
    "VN": {"country_name": "Vietnam", "standard_vat": 10.0, "reduced_vat": [], "currency": "VND"},
    "ZM": {"country_name": "Zambia", "standard_vat": 16.0, "reduced_vat": [], "currency": "ZMW"},
    "ZW": {"country_name": "Zimbabwe", "standard_vat": 15.0, "reduced_vat": [], "currency": "ZWL"},
}

# ---------------------------------------------------------------------------
# 2. LIVE VAT CACHE
# ---------------------------------------------------------------------------
LIVE_CACHE = {}
CACHE_LOCK = threading.Lock()
CACHE_TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", 6 * 60 * 60))  # 6 hours
LIVE_PROVIDER_URL = "https://www.taxid.dev/api/v1/rates/{code}"
LIVE_REQUEST_TIMEOUT = 5  # seconds - don't let a slow upstream hang our API


def fetch_live_rate(code: str):
    try:
        resp = requests.get(LIVE_PROVIDER_URL.format(code=code), timeout=LIVE_REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if "standard_rate" not in data:
            return None
        return {
            "standard_vat": float(data["standard_rate"]),
            "reduced_vat": data.get("reduced_rates", []) or [],
            "currency": data.get("currency") or STATIC_TAX_DATA.get(code, {}).get("currency"),
            "source": "live",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
    except (requests.RequestException, ValueError, TypeError) as e:
        log.warning(f"Live fetch failed for {code}: {e}")
        return None


def refresh_all_live_rates():
    log.info("Starting scheduled live-rate refresh...")
    updated = 0
    for code in STATIC_TAX_DATA:
        live = fetch_live_rate(code)
        if live:
            with CACHE_LOCK:
                LIVE_CACHE[code] = live
            updated += 1
    log.info(f"Live-rate refresh complete: {updated}/{len(STATIC_TAX_DATA)} countries updated from live source.")


def get_country_data(code: str, force_live_check: bool = False):
    code = code.upper()
    if code not in STATIC_TAX_DATA:
        return None

    with CACHE_LOCK:
        cached = LIVE_CACHE.get(code)

    if cached:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(cached["fetched_at"])).total_seconds()
        if age < CACHE_TTL_SECONDS:
            result = dict(cached)
            result["country_name"] = STATIC_TAX_DATA[code]["country_name"]
            result["country_code"] = code
            return result

    if force_live_check:
        live = fetch_live_rate(code)
        if live:
            with CACHE_LOCK:
                LIVE_CACHE[code] = live
            result = dict(live)
            result["country_name"] = STATIC_TAX_DATA[code]["country_name"]
            result["country_code"] = code
            return result

    static = STATIC_TAX_DATA[code]
    return {
        "country_code": code,
        "country_name": static["country_name"],
        "standard_vat": static["standard_vat"],
        "reduced_vat": static["reduced_vat"],
        "currency": static["currency"],
        "source": "static_fallback",
        "fetched_at": None,
    }


# ---------------------------------------------------------------------------
# 3. CURRENCY CONVERSION
#    frankfurter.app is free, no API key, backed by ECB reference rates.
#    It only covers ~30 major currencies (not exotic ones like XOF/AFN/KHR).
#    When a currency isn't supported we say so explicitly rather than
#    guessing - wrong FX math is worse than no FX math on a tax API.
# ---------------------------------------------------------------------------
FX_CACHE = {}  # {"BASE_QUOTE": {"rate": .., "fetched_at": iso}}
FX_CACHE_LOCK = threading.Lock()
FX_CACHE_TTL_SECONDS = int(os.environ.get("FX_CACHE_TTL_SECONDS", 60 * 60))  # 1 hour
FX_PROVIDER_URL = "https://api.frankfurter.app/latest"


def fetch_fx_rate(base: str, quote: str):
    """Return (rate, fetched_at_iso) or (None, None) if unavailable."""
    base, quote = base.upper(), quote.upper()
    if base == quote:
        return 1.0, datetime.now(timezone.utc).isoformat()

    cache_key = f"{base}_{quote}"
    with FX_CACHE_LOCK:
        cached = FX_CACHE.get(cache_key)
    if cached:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(cached["fetched_at"])).total_seconds()
        if age < FX_CACHE_TTL_SECONDS:
            return cached["rate"], cached["fetched_at"]

    try:
        resp = requests.get(FX_PROVIDER_URL, params={"from": base, "to": quote}, timeout=LIVE_REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return None, None
        data = resp.json()
        rate = data.get("rates", {}).get(quote)
        if rate is None:
            return None, None
        fetched_at = datetime.now(timezone.utc).isoformat()
        with FX_CACHE_LOCK:
            FX_CACHE[cache_key] = {"rate": rate, "fetched_at": fetched_at}
        return rate, fetched_at
    except (requests.RequestException, ValueError) as e:
        log.warning(f"FX fetch failed for {base}->{quote}: {e}")
        return None, None


# ---------------------------------------------------------------------------
# 4. API KEYS + TIERED RATE LIMITING (monetization layer)
#
#    In-memory store - fine for a single Render instance. If you scale past
#    one worker/dyno, swap KEY_STORE / USAGE_STORE for Redis so limits are
#    shared across processes.
#
#    Tiers:
#      - none (no key)  -> IP-based limit, low ceiling, meant for trying the API
#      - "free"          -> self-serve key via /api/v1/keys/generate
#      - "pro"           -> higher/unlimited ceiling, you create these manually
#                           (or wire up Stripe later to call issue_key("pro"))
# ---------------------------------------------------------------------------
TIER_LIMITS = {
    "anonymous": int(os.environ.get("LIMIT_ANONYMOUS", 50)),   # per day, by IP
    "free": int(os.environ.get("LIMIT_FREE", 1000)),           # per day, by key
    "pro": int(os.environ.get("LIMIT_PRO", 100000)),           # per day, by key
}

KEY_STORE = {}          # {api_key: {"tier": "free"/"pro", "created_at": iso, "label": str}}
USAGE_STORE = {}        # {identifier: {"date": "YYYY-MM-DD", "count": int}}
KEY_LOCK = threading.Lock()

# Seed a couple of admin/pro keys from env so you can hand them out manually
# to paying customers without redeploying every time (comma-separated).
for _k in os.environ.get("PRO_KEYS", "").split(","):
    _k = _k.strip()
    if _k:
        KEY_STORE[_k] = {"tier": "pro", "created_at": datetime.now(timezone.utc).isoformat(), "label": "manual-pro"}


def issue_api_key(tier: str = "free", label: str = "") -> str:
    key = "gtce_" + secrets.token_urlsafe(24)
    with KEY_LOCK:
        KEY_STORE[key] = {
            "tier": tier,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "label": label,
        }
    return key


def _usage_identifier():
    """API key if present, else client IP, so anonymous users still get a (low) limit."""
    key = request.headers.get("X-API-Key") or request.args.get("api_key")
    if key:
        return key, KEY_STORE.get(key)
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
    return f"ip:{ip}", None


def check_and_increment_usage(identifier: str, tier: str) -> tuple[bool, int, int]:
    """Returns (allowed, used_count, limit) for today, incrementing on allowed calls."""
    today = date.today().isoformat()
    limit = TIER_LIMITS.get(tier, TIER_LIMITS["anonymous"])
    with KEY_LOCK:
        entry = USAGE_STORE.get(identifier)
        if not entry or entry["date"] != today:
            entry = {"date": today, "count": 0}
        if entry["count"] >= limit:
            USAGE_STORE[identifier] = entry
            return False, entry["count"], limit
        entry["count"] += 1
        USAGE_STORE[identifier] = entry
        return True, entry["count"], limit


def require_api_key(fn):
    """
    Decorator for metered endpoints. Doesn't hard-require a key - unknown
    callers get the low 'anonymous' tier by IP - but valid keys unlock
    higher limits. Invalid (unrecognized) keys are rejected outright so
    people don't silently think they have a paid tier they don't.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        supplied_key = request.headers.get("X-API-Key") or request.args.get("api_key")
        if supplied_key and supplied_key not in KEY_STORE:
            return jsonify({"error": "Invalid API key"}), 401

        identifier, key_info = _usage_identifier()
        tier = key_info["tier"] if key_info else "anonymous"

        allowed, used, limit = check_and_increment_usage(identifier, tier)
        if not allowed:
            return jsonify({
                "error": "Rate limit exceeded",
                "tier": tier,
                "limit_per_day": limit,
                "message": (
                    "Upgrade by requesting a key at /api/v1/keys/generate, "
                    "or contact us for a 'pro' tier key."
                    if tier == "anonymous" else
                    "Daily limit reached for your tier. Try again tomorrow or upgrade to 'pro'."
                ),
            }), 429

        # expose usage info to the view via flask.g-style attribute on request
        request.rate_limit_info = {"tier": tier, "used_today": used, "limit_per_day": limit}
        return fn(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# 5. SCHEDULER - keeps the live VAT cache warm automatically
# ---------------------------------------------------------------------------
scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(refresh_all_live_rates, "interval", hours=6, id="refresh_live_rates", next_run_time=datetime.now())
scheduler.start()

# ---------------------------------------------------------------------------
# 6. ROUTES
# ---------------------------------------------------------------------------

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "Global Tax and Compliance Engine API is live!",
        "endpoints": {
            "GET /health": "service + cache health check (free, unmetered)",
            "GET /api/v1/countries": "list every supported country (metered)",
            "GET|POST /api/v1/tax-rate?code=XX": "get a country's VAT/GST rate (metered)",
            "GET|POST /api/v1/calculate?code=XX&amount=100&target_currency=USD": "calculate tax + total, optional currency conversion (metered)",
            "POST /api/v1/refresh": "manually trigger a live-rate refresh (metered)",
            "POST /api/v1/keys/generate": "get a free-tier API key",
            "GET /api/v1/keys/usage": "check your current usage/limit",
        },
        "auth": "Optional. Pass your key as header 'X-API-Key' or query param '?api_key='. "
                "No key = low anonymous limit by IP.",
        "tiers": TIER_LIMITS,
    })


@app.route("/health", methods=["GET"])
def health():
    with CACHE_LOCK:
        live_count = len(LIVE_CACHE)
    return jsonify({
        "status": "ok",
        "countries_supported": len(STATIC_TAX_DATA),
        "countries_with_live_data": live_count,
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "server_time_utc": datetime.now(timezone.utc).isoformat(),
    }), 200


@app.route("/api/v1/keys/generate", methods=["POST"])
def generate_key():
    req_data = request.get_json(silent=True) or {}
    label = (req_data.get("label") or "")[:100]
    key = issue_api_key(tier="free", label=label)
    return jsonify({
        "status": "success",
        "api_key": key,
        "tier": "free",
        "limit_per_day": TIER_LIMITS["free"],
        "usage": "Pass this as header 'X-API-Key: <key>' or query param '?api_key=<key>' on every request.",
    }), 201


@app.route("/api/v1/keys/usage", methods=["GET"])
@require_api_key
def key_usage():
    return jsonify({"status": "success", **request.rate_limit_info}), 200


@app.route("/api/v1/countries", methods=["GET"])
@require_api_key
def list_countries():
    currency_filter = request.args.get("currency")
    out = []
    for code, info in STATIC_TAX_DATA.items():
        if currency_filter and info["currency"].upper() != currency_filter.upper():
            continue
        out.append({"country_code": code, "country_name": info["country_name"], "currency": info["currency"]})
    out.sort(key=lambda x: x["country_name"])
    return jsonify({
        "status": "success", "count": len(out), "countries": out,
        "rate_limit": request.rate_limit_info,
    }), 200


@app.route("/api/v1/tax-rate", methods=["GET", "POST"])
@require_api_key
def get_tax_rate():
    try:
        code = request.args.get("code", "")
        if not code and request.method == "POST":
            req_data = request.get_json(silent=True) or {}
            code = req_data.get("code") or ""
        code = code.strip().upper()

        if not code:
            return jsonify({"error": "Missing 'code' (2-letter ISO country code)"}), 400

        data = get_country_data(code, force_live_check=True)
        if data is None:
            return jsonify({"error": f"Unsupported country code: {code}"}), 400

        return jsonify({"status": "success", **data, "rate_limit": request.rate_limit_info}), 200
    except Exception as e:
        log.exception("Error in /api/v1/tax-rate")
        return jsonify({"error": "Internal error", "detail": str(e)}), 500


@app.route("/api/v1/calculate", methods=["GET", "POST"])
@require_api_key
def calculate_tax():
    try:
        req_data = request.get_json(silent=True) or {}
        code = (req_data.get("code") or request.args.get("code", "")).strip().upper()
        amount_val = req_data.get("amount", request.args.get("amount", None))
        target_currency = (req_data.get("target_currency") or request.args.get("target_currency", "")).strip().upper()

        if not code:
            return jsonify({"error": "Missing 'code' (2-letter ISO country code)"}), 400
        if amount_val is None:
            return jsonify({"error": "Missing 'amount'"}), 400

        try:
            amount = float(amount_val)
        except (TypeError, ValueError):
            return jsonify({"error": "'amount' must be a number"}), 400
        if amount < 0:
            return jsonify({"error": "'amount' cannot be negative"}), 400

        data = get_country_data(code, force_live_check=True)
        if data is None:
            return jsonify({"error": f"Unsupported country code: {code}"}), 400

        rate = data["standard_vat"]
        tax = round(amount * rate / 100, 2)
        total = round(amount + tax, 2)

        response = {
            "status": "success",
            "country_code": data["country_code"],
            "country_name": data["country_name"],
            "currency": data["currency"],
            "standard_vat": rate,
            "reduced_vat": data.get("reduced_vat", []),
            "entered_amount": amount,
            "calculated_tax": tax,
            "total_amount": total,
            "source": data["source"],
            "rate_limit": request.rate_limit_info,
        }

        if target_currency and target_currency != data["currency"]:
            fx_rate, fetched_at = fetch_fx_rate(data["currency"], target_currency)
            if fx_rate is None:
                response["conversion"] = {
                    "requested_currency": target_currency,
                    "error": (
                        f"Conversion from {data['currency']} to {target_currency} is unavailable "
                        "(unsupported currency or FX provider unreachable). Amounts above are in "
                        f"{data['currency']} only."
                    ),
                }
            else:
                response["conversion"] = {
                    "requested_currency": target_currency,
                    "fx_rate": fx_rate,
                    "fx_source": "frankfurter.app (ECB reference rates)",
                    "fx_fetched_at": fetched_at,
                    "entered_amount_converted": round(amount * fx_rate, 2),
                    "calculated_tax_converted": round(tax * fx_rate, 2),
                    "total_amount_converted": round(total * fx_rate, 2),
                }

        return jsonify(response), 200
    except Exception as e:
        log.exception("Error in /api/v1/calculate")
        return jsonify({"error": "Internal error", "detail": str(e)}), 500


@app.route("/api/v1/refresh", methods=["POST"])
@require_api_key
def manual_refresh():
    threading.Thread(target=refresh_all_live_rates, daemon=True).start()
    return jsonify({
        "status": "success",
        "message": "Live-rate refresh started in background.",
        "rate_limit": request.rate_limit_info,
    }), 202


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
