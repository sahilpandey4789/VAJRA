"""
National case-distribution map - aggregates cases.jurisdiction into a
per-city summary (case count, risk mix, avg confidence) for the admin-only
national map view. Complements engine/exchange_board.py and
engine/syndicate.py, which aggregate the same underlying case data along
different axes (by exchange, by shared wallet cluster). This one aggregates
by *where the complaint was filed*.

Note: the (x, y) coordinates below are a hand-placed relative layout for
a bubble map, not surveyed coordinates and not tied to GeoJSON/TopoJSON
boundary data. Good enough to show relative national distribution and
hot-spots, not a GIS tool. Roadmap: swap for real district/state boundary
polygons (India district shapefiles / DataMeet's open India-maps project)
with server-side geocoding of jurisdictions.
"""

# city name (as it appears after the dash in cases.jurisdiction) -> state + stylized position
JURISDICTION_GEO = {
    "Delhi":       {"state": "Delhi (NCT)",      "x": 42, "y": 15},
    "Chandigarh":  {"state": "Chandigarh",        "x": 38, "y": 8},
    "Jaipur":      {"state": "Rajasthan",         "x": 33, "y": 22},
    "Lucknow":     {"state": "Uttar Pradesh",     "x": 52, "y": 24},
    "Ahmedabad":   {"state": "Gujarat",           "x": 22, "y": 38},
    "Mumbai":      {"state": "Maharashtra",       "x": 27, "y": 52},
    "Pune":        {"state": "Maharashtra",       "x": 30, "y": 56},
    "Kolkata":     {"state": "West Bengal",       "x": 72, "y": 42},
    "Hyderabad":   {"state": "Telangana",         "x": 48, "y": 62},
    "Bengaluru":   {"state": "Karnataka",         "x": 42, "y": 78},
    "Chennai":     {"state": "Tamil Nadu",        "x": 53, "y": 82},
    "National":    {"state": "National (I4C)",    "x": 45, "y": 42},
}

_RISK_WEIGHT = {"high": 3, "medium": 2, "low": 1}

# Publicly-known HQ city for each recognised exchange (fixtures.py's
# KNOWN_EXCHANGE_WALLETS) - used by the per-case Geographic Trail below.
# Different question than national_distribution() above: not "how many
# cases come from where" but "for THIS case, where did it start and end".
# A wallet has no inherent geography, so this doesn't try to geolocate the
# wallet - it anchors the two real endpoints: the officer's jurisdiction
# and the receiving exchange's actual HQ.
EXCHANGE_HQ = {
    "WazirX": {"city": "Mumbai", "state": "Maharashtra", "x": 27, "y": 52},
    "CoinDCX": {"city": "Bengaluru", "state": "Karnataka", "x": 42, "y": 78},
    # Binance has no single fixed India HQ - it isn't an Indian entity.
    # Represented as "international" rather than invented as a fake city.
    "Binance": {"city": None, "state": "International", "x": None, "y": None},
}


def case_geo_trail(jurisdiction, exchange_match, mixer_hit):
    """
    Builds the trail for the per-case Geographic Trail panel: where the
    complaint was filed, and - if resolved to a known exchange - that
    exchange's HQ city. Returns None fields instead of guessing:
      - exchange not in EXCHANGE_HQ, or HQ has no city (Binance) ->
        destination is None, `trail_type: "international"` says why.
      - mixer_hit, no exchange -> trail_type "mixer": no destination
        to plot, panel shows origin + "trail ends here".
      - neither -> trail_type "unresolved".
    """
    city = _city_from_jurisdiction(jurisdiction)
    origin_geo = JURISDICTION_GEO.get(city, JURISDICTION_GEO["National"])
    origin = {"city": city, "state": origin_geo["state"], "x": origin_geo["x"], "y": origin_geo["y"]}

    if exchange_match:
        exchange = exchange_match.get("exchange")
        hq = EXCHANGE_HQ.get(exchange)
        if hq and hq["city"]:
            return {
                "trail_type": "resolved", "exchange": exchange,
                "origin": origin,
                "destination": {"city": hq["city"], "state": hq["state"], "x": hq["x"], "y": hq["y"]},
            }
        return {
            "trail_type": "international", "exchange": exchange,
            "origin": origin, "destination": None,
        }
    if mixer_hit:
        return {"trail_type": "mixer", "exchange": None, "origin": origin, "destination": None}
    return {"trail_type": "unresolved", "exchange": None, "origin": origin, "destination": None}


def _city_from_jurisdiction(jurisdiction):
    # "Cyber Crime Cell - Delhi" -> "Delhi"; falls back gracefully for any
    # jurisdiction string that doesn't follow the "X - City" convention.
    if not jurisdiction:
        return "National"
    parts = jurisdiction.split(" - ")
    city = parts[-1].strip() if len(parts) > 1 else jurisdiction.strip()
    return city if city in JURISDICTION_GEO else "National"


def national_distribution(cases):
    """cases: list of sqlite Row/dict with at least jurisdiction, risk_band,
    confidence, status (sqlite3.Row and dict both support c["field"], so no
    type branching is needed). Returns one entry per city that actually has
    cases, each with a hand-placed (x, y) for plotting plus real aggregated
    counts."""
    buckets = {}
    for c in cases:
        city = _city_from_jurisdiction(c["jurisdiction"])
        b = buckets.setdefault(city, {"city": city, "cases": 0, "high": 0, "medium": 0, "low": 0,
                                       "open": 0, "confidence_sum": 0.0})
        b["cases"] += 1
        band = c["risk_band"] or "low"
        if band in b:
            b[band] += 1
        if c["status"] not in ("cleared", "closed"):
            b["open"] += 1
        b["confidence_sum"] += c["confidence"] or 0.0

    out = []
    for city, b in buckets.items():
        geo = JURISDICTION_GEO.get(city, JURISDICTION_GEO["National"])
        severity_score = (b["high"] * _RISK_WEIGHT["high"] + b["medium"] * _RISK_WEIGHT["medium"]
                           + b["low"] * _RISK_WEIGHT["low"])
        out.append({
            "city": city, "state": geo["state"], "x": geo["x"], "y": geo["y"],
            "cases": b["cases"], "open_cases": b["open"],
            "high_risk": b["high"], "medium_risk": b["medium"], "low_risk": b["low"],
            "avg_confidence": round(b["confidence_sum"] / b["cases"], 2) if b["cases"] else 0.0,
            "severity_score": severity_score,
        })
    out.sort(key=lambda r: r["cases"], reverse=True)
    return out
