"""First Coast cities and a small US hopper (no Google Maps key required)."""

from __future__ import annotations

from typing import Any

# Northeast Florida bounding box used by the desk map.
MAP_BOUNDS = {
    "min_lat": 29.35,
    "max_lat": 30.85,
    "min_lng": -82.15,
    "max_lng": -81.15,
}

COUNTY_COORDS: dict[str, tuple[float, float]] = {
    "Duval": (30.3322, -81.6557),
    "St. Johns": (29.9012, -81.3124),
    "Clay": (30.1661, -81.7065),
    "Nassau": (30.6697, -81.4626),
    "Flagler": (29.5847, -81.2078),
    "Putnam": (29.6486, -81.6379),
}

CITIES: list[dict[str, Any]] = [
    {"name": "Jacksonville", "state": "Florida", "county": "Duval", "lat": 30.3322, "lng": -81.6557},
    {"name": "Jacksonville Beach", "state": "Florida", "county": "Duval", "lat": 30.2947, "lng": -81.3931},
    {"name": "Ponte Vedra Beach", "state": "Florida", "county": "St. Johns", "lat": 30.2394, "lng": -81.3856},
    {"name": "St. Augustine", "state": "Florida", "county": "St. Johns", "lat": 29.8947, "lng": -81.3145},
    {"name": "Orange Park", "state": "Florida", "county": "Clay", "lat": 30.1661, "lng": -81.7065},
    {"name": "Fernandina Beach", "state": "Florida", "county": "Nassau", "lat": 30.6697, "lng": -81.4626},
    {"name": "Palm Coast", "state": "Florida", "county": "Flagler", "lat": 29.5847, "lng": -81.2078},
    {"name": "Yulee", "state": "Florida", "county": "Nassau", "lat": 30.6319, "lng": -81.6065},
    {"name": "Green Cove Springs", "state": "Florida", "county": "Clay", "lat": 29.9919, "lng": -81.6787},
    {"name": "Palatka", "state": "Florida", "county": "Putnam", "lat": 29.6486, "lng": -81.6379},
    {"name": "Miami", "state": "Florida", "county": "Other", "lat": 25.7617, "lng": -80.1918},
    {"name": "Tampa", "state": "Florida", "county": "Other", "lat": 27.9506, "lng": -82.4572},
    {"name": "Orlando", "state": "Florida", "county": "Other", "lat": 28.5383, "lng": -81.3792},
    {"name": "Atlanta", "state": "Georgia", "county": "Other", "lat": 33.7490, "lng": -84.3880},
    {"name": "Savannah", "state": "Georgia", "county": "Other", "lat": 32.0809, "lng": -81.0912},
]


def autocomplete(query: str, limit: int = 8) -> list[dict[str, Any]]:
    needle = (query or "").strip().lower()
    if len(needle) < 1:
        return CITIES[:limit]
    ranked: list[tuple[int, dict[str, Any]]] = []
    for city in CITIES:
        blob = f"{city['name']} {city['state']} {city['county']}".lower()
        if needle not in blob:
            continue
        rank = 0 if city["name"].lower().startswith(needle) else 1
        ranked.append((rank, city))
    ranked.sort(key=lambda item: (item[0], item[1]["name"]))
    return [city for _, city in ranked[:limit]]


def geocode(query: str) -> dict[str, Any] | None:
    hits = autocomplete(query, limit=1)
    return hits[0] if hits else None


def coords_for_county(county: str) -> tuple[float, float]:
    return COUNTY_COORDS.get(county, COUNTY_COORDS["Duval"])


def map_point(lat: float | None, lng: float | None) -> dict[str, float] | None:
    if lat is None or lng is None:
        return None
    if not (MAP_BOUNDS["min_lat"] <= lat <= MAP_BOUNDS["max_lat"]):
        return None
    if not (MAP_BOUNDS["min_lng"] <= lng <= MAP_BOUNDS["max_lng"]):
        return None
    x = (lng - MAP_BOUNDS["min_lng"]) / (MAP_BOUNDS["max_lng"] - MAP_BOUNDS["min_lng"]) * 100
    y = (MAP_BOUNDS["max_lat"] - lat) / (MAP_BOUNDS["max_lat"] - MAP_BOUNDS["min_lat"]) * 100
    return {"x": round(x, 2), "y": round(y, 2)}
