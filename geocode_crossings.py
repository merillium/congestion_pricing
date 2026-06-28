"""
Geocodes bridge/tunnel crossing endpoints using the Nominatim API (OpenStreetMap).

For each crossing, two search queries are provided — one for each side of the
crossing (e.g. NJ portal vs. Manhattan portal). Nominatim returns a bounding box
for each result; this script picks the most geographically distinct result for
each side and uses its center as the endpoint coordinate.

The output is printed as a Python literal ready to paste into crz_crossings.py.

Usage:
    python geocode_crossings.py

No API key required. Nominatim's terms of service require a descriptive User-Agent
and max 1 request/second, which this script enforces.
"""

import json
import time
import urllib.parse
import urllib.request

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "congestion-pricing-research/1.0"
RATE_LIMIT_S = 1.1  # seconds between requests


def geocode(query: str) -> list[dict]:
    """Return up to 3 Nominatim results for the query."""
    params = urllib.parse.urlencode({
        "q": query,
        "format": "json",
        "limit": 3,
        "addressdetails": 0,
    })
    req = urllib.request.Request(
        f"{NOMINATIM_URL}?{params}",
        headers={"User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def best_result(results: list[dict]) -> tuple[float, float] | None:
    """Return (lat, lon) of the first result, or None if empty."""
    if not results:
        return None
    r = results[0]
    return float(r["lat"]), float(r["lon"])


# ---------------------------------------------------------------------------
# Crossing definitions: each entry has a name, toll rates, and two search
# queries — one for each end of the bridge or tunnel.
#
# Tips for query strings:
#   - Include the borough/state on each side to disambiguate
#   - For tunnels, "Manhattan entrance" / "New Jersey entrance" works well
#   - For bridges, "<Bridge name> <Borough>" is usually enough
# ---------------------------------------------------------------------------
CROSSING_QUERIES = [
    {
        "name": "Lincoln Tunnel",
        "query1": "Lincoln Tunnel Manhattan",
        "query2": "Lincoln Tunnel Weehawken New Jersey",
        "ezpass": "$22.06",
        "plate": "$27.31",
    },
    {
        "name": "Holland Tunnel",
        "query1": "Holland Tunnel Manhattan",
        "query2": "Holland Tunnel Jersey City New Jersey",
        "ezpass": "$22.06",
        "plate": "$27.31",
    },
    {
        "name": "Hugh L. Carey Tunnel",
        "query1": "Brooklyn Battery Tunnel Manhattan",
        "query2": "Brooklyn Battery Tunnel Brooklyn",
        "ezpass": "$12.94",
        "plate": "$20.19",
    },
    {
        "name": "Verrazzano-Narrows Bridge",
        "query1": "Verrazzano-Narrows Bridge Staten Island",
        "query2": "Verrazzano-Narrows Bridge Brooklyn",
        "ezpass": "$15.94",
        "plate": "$20.19",
    },
    {
        "name": "Ed Koch Queensboro Bridge",
        "query1": "Queensboro Bridge Queens Long Island City",
        "query2": "Queensboro Bridge Manhattan",
        "ezpass": "$9.00",
        "plate": "$13.50",
    },
    {
        "name": "Queens Midtown Tunnel",
        "query1": "Queens Midtown Tunnel Long Island City",
        "query2": "Queens Midtown Tunnel Manhattan",
        "ezpass": "$12.94",
        "plate": "$20.19",
    },
    {
        "name": "Williamsburg Bridge",
        "query1": "Williamsburg Bridge Brooklyn",
        "query2": "Williamsburg Bridge Manhattan",
        "ezpass": "$9.00",
        "plate": "$13.50",
    },
    {
        "name": "Manhattan Bridge",
        "query1": "Manhattan Bridge Brooklyn",
        "query2": "Manhattan Bridge Manhattan",
        "ezpass": "$9.00",
        "plate": "$13.50",
    },
    {
        "name": "Brooklyn Bridge",
        "query1": "Brooklyn Bridge Brooklyn",
        "query2": "Brooklyn Bridge Manhattan",
        "ezpass": "$9.00",
        "plate": "$13.50",
    },
]


def main():
    results = []
    for c in CROSSING_QUERIES:
        print(f"Geocoding: {c['name']} ...", flush=True)

        r1 = geocode(c["query1"])
        time.sleep(RATE_LIMIT_S)
        r2 = geocode(c["query2"])
        time.sleep(RATE_LIMIT_S)

        end1 = best_result(r1)
        end2 = best_result(r2)

        if end1 is None or end2 is None:
            print(f"  WARNING: could not geocode both ends of {c['name']}")
            print(f"    query1 ({c['query1']}): {r1}")
            print(f"    query2 ({c['query2']}): {r2}")

        results.append({**c, "end1": end1, "end2": end2})

    # Print as Python literal ready to paste into crz_crossings.py
    print("\n\n# ---- paste into crz_crossings.py ----")
    print("CROSSINGS = [")
    for c in results:
        print(f"    {{")
        print(f'        "name": "{c["name"]}",')
        print(f'        "end1": {c["end1"]},  # {c["query1"]}')
        print(f'        "end2": {c["end2"]},  # {c["query2"]}')
        print(f'        "ezpass": "{c["ezpass"]}",')
        print(f'        "plate": "{c["plate"]}",')
        print(f"    }},")
    print("]")
    print()
    print("for c in CROSSINGS:")
    print("    c['lat'] = (c['end1'][0] + c['end2'][0]) / 2")
    print("    c['lon'] = (c['end1'][1] + c['end2'][1]) / 2")


if __name__ == "__main__":
    main()
