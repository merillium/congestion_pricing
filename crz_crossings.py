"""
Coordinates for the 9 NYC Congestion Relief Zone entry crossings.

Endpoints are derived from Nominatim (OpenStreetMap) geocoding results:
- For tunnels: center coordinates of the Manhattan-side and NJ/Brooklyn/Queens-side
  Nominatim results are used as the two portal locations.
- For bridges: bounding box extremes of the bridge way object are used.
- Verrazzano and Queensboro: two distinct Nominatim results with clear borough separation.

Source: https://nominatim.openstreetmap.org (OpenStreetMap data)
"""

CROSSINGS = [
    {
        "name": "Lincoln Tunnel",
        # Manhattan result center vs. Weehawken NJ result center
        "end1": (40.7598, -74.0035),   # Manhattan portal (38th–40th St)
        "end2": (40.7674, -74.0213),   # Weehawken, NJ portal
        "ezpass": "$22.06",
        "plate": "$27.31",
    },
    {
        "name": "Holland Tunnel",
        # Manhattan result center vs. Jersey City NJ result center
        "end1": (40.7264, -74.0142),   # Manhattan portal (Canal St)
        "end2": (40.7287, -74.0290),   # Jersey City, NJ portal
        "ezpass": "$22.06",
        "plate": "$27.31",
    },
    {
        "name": "Hugh L. Carey Tunnel",
        # Single Nominatim result with large N-S bounding box [40.682, 40.705, -74.016, -74.006]
        # Tunnel runs N (Manhattan/Battery Park) to S (Red Hook, Brooklyn)
        "end1": (40.7052, -74.0055),   # Manhattan portal (Battery Park)
        "end2": (40.6819, -74.0156),   # Brooklyn portal (Red Hook)
        "ezpass": "$12.94",
        "plate": "$20.19",
    },
    {
        "name": "Verrazzano-Narrows Bridge",
        # Two distinct Nominatim results with clear borough separation
        "end1": (40.6060, -74.0468),   # Staten Island anchorage
        "end2": (40.6103, -74.0335),   # Brooklyn anchorage
        "ezpass": "$15.94",
        "plate": "$20.19",
    },
    {
        "name": "Ed Koch Queensboro Bridge",
        # Two distinct Nominatim results
        "end1": (40.7530, -73.9454),   # Queens (Long Island City)
        "end2": (40.7557, -73.9519),   # Manhattan (East 59th St)
        "ezpass": "$9.00",
        "plate": "$13.50",
    },
    {
        "name": "Queens Midtown Tunnel",
        # Nominatim bbox [40.742, 40.748, -73.971, -73.954] — runs E-W
        "end1": (40.7419, -73.9576),   # Queens portal (Hunters Point, LIC)
        "end2": (40.7462, -73.9719),   # Manhattan portal (2nd Ave & 34th St)
        "ezpass": "$12.94",
        "plate": "$20.19",
    },
    {
        "name": "Williamsburg Bridge",
        # Nominatim bbox [40.711, 40.716, -73.979, -73.965] — runs roughly E-W
        "end1": (40.7136, -73.9788),   # Manhattan portal (Delancey/Clinton St)
        "end2": (40.7109, -73.9636),   # Brooklyn portal (Bedford Ave)
        "ezpass": "$9.00",
        "plate": "$13.50",
    },
    {
        "name": "Manhattan Bridge",
        # Nominatim bbox [40.699, 40.715, -73.995, -73.986] — runs roughly NW-SE
        "end1": (40.7070, -73.9950),   # Manhattan portal (Canal St/Bowery)
        "end2": (40.6993, -73.9863),   # Brooklyn portal (Flatbush Ave Ext)
        "ezpass": "$9.00",
        "plate": "$13.50",
    },
    {
        "name": "Brooklyn Bridge",
        # Nominatim bbox [40.702, 40.709, -74.001, -73.992] — runs roughly NW-SE
        "end1": (40.7061, -74.0008),   # Manhattan portal (Park Row)
        "end2": (40.7022, -73.9919),   # Brooklyn portal (Adams/Tillary St)
        "ezpass": "$9.00",
        "plate": "$13.50",
    },
]

# Midpoint of each crossing (for map labels and hover tooltips)
for c in CROSSINGS:
    c["lat"] = (c["end1"][0] + c["end2"][0]) / 2
    c["lon"] = (c["end1"][1] + c["end2"][1]) / 2
