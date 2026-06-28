"""
Fetches accurate bridge/tunnel geometries from OpenStreetMap via the Overpass API
and saves them as data/crz_crossings_geometry.geojson.

Each crossing is stored as a GeoJSON MultiLineString containing all OSM way segments
(road lanes, decks, walkways) that share the crossing's name. This gives accurate
curved geometries rather than straight-line approximations.

Usage:
    python fetch_crossing_geometry.py

Re-run whenever you add a new crossing to CROSSING_DEFINITIONS below.
No API key required. Rate-limited to Overpass's fair-use policy.
"""

import json
import urllib.parse
import urllib.request

GEOJSON_OUT = "data/crz_crossings_geometry.geojson"

# Crossings that exist as OSM *relations* (preferred: one query returns all ways)
RELATION_NAMES = [
    ("Lincoln Tunnel",            "Lincoln Tunnel"),
    ("Holland Tunnel",            "Holland Tunnel"),
    ("Hugh L. Carey Tunnel",      "Brooklyn-Battery Tunnel"),
    ("Verrazzano-Narrows Bridge", "Verrazzano-Narrows Bridge"),
    ("Ed Koch Queensboro Bridge", "Queensboro Bridge"),
    ("Queens Midtown Tunnel",     "Queens-Midtown Tunnel"),
    ("Manhattan Bridge",          "Manhattan Bridge"),
    ("Brooklyn Bridge",           "Brooklyn Bridge"),
]

# Crossings that exist only as OSM *ways* — requires a bounding box to avoid
# pulling in unrelated places with the same name worldwide.
WAY_ONLY_NAMES = [
    ("Williamsburg Bridge", "Williamsburg Bridge", (40.68, -74.02, 40.75, -73.93)),
]

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT   = "congestion-pricing-research/1.0"


def overpass(query: str) -> list[dict]:
    data = urllib.parse.urlencode({"data": query}).encode()
    req  = urllib.request.Request(OVERPASS_URL, data=data, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read())["elements"]


def ways_to_multilinestring(elements: list[dict]) -> list[list]:
    """Extract [[lon, lat], ...] coordinate lists from way elements."""
    lines = []
    for el in elements:
        if el.get("geometry"):
            lines.append([[pt["lon"], pt["lat"]] for pt in el["geometry"]])
    return lines


def fetch_relation(osm_name: str) -> list[list]:
    """Fetch a crossing stored as an OSM relation; return way geometries."""
    query = f"""
[out:json][timeout:30];
relation["name"="{osm_name}"];
out geom;
"""
    elements = overpass(query)
    # Pick the relation with the most members (most complete)
    relations = [el for el in elements if el["type"] == "relation"]
    if not relations:
        print(f"  WARNING: no relation found for '{osm_name}'")
        return []
    best = max(relations, key=lambda r: len(r.get("members", [])))
    lines = []
    for m in best.get("members", []):
        if m["type"] == "way" and m.get("geometry"):
            lines.append([[pt["lon"], pt["lat"]] for pt in m["geometry"]])
    return lines


def fetch_ways(osm_name: str, bbox: tuple) -> list[list]:
    """Fetch a crossing stored as OSM ways within a bounding box."""
    s, w, n, e = bbox
    query = f"""
[out:json][timeout:20][bbox:{s},{w},{n},{e}];
way["name"="{osm_name}"];
out geom;
"""
    elements = overpass(query)
    return ways_to_multilinestring(elements)


def main():
    features = []

    for canonical, osm_name in RELATION_NAMES:
        print(f"Fetching relation: {canonical} ...", flush=True)
        lines = fetch_relation(osm_name)
        n_coords = sum(len(l) for l in lines)
        print(f"  {len(lines)} segments, {n_coords} coords")
        features.append({
            "type": "Feature",
            "properties": {"name": canonical},
            "geometry": {"type": "MultiLineString", "coordinates": lines},
        })

    for canonical, osm_name, bbox in WAY_ONLY_NAMES:
        print(f"Fetching ways: {canonical} ...", flush=True)
        lines = fetch_ways(osm_name, bbox)
        n_coords = sum(len(l) for l in lines)
        print(f"  {len(lines)} segments, {n_coords} coords")
        features.append({
            "type": "Feature",
            "properties": {"name": canonical},
            "geometry": {"type": "MultiLineString", "coordinates": lines},
        })

    geojson = {"type": "FeatureCollection", "features": features}
    with open(GEOJSON_OUT, "w") as f:
        json.dump(geojson, f)
    print(f"\nSaved {len(features)} crossings → {GEOJSON_OUT}")


if __name__ == "__main__":
    main()
