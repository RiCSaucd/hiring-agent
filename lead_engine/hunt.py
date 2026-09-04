"""Bundled First Coast hunt cache (Firecrawl + RocketReach). Emails stay empty unless printed."""

from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from lead_engine.locations import COUNTY_COORDS, coords_for_county

HUNT_CACHE: list[dict[str, Any]] = [
    {
        "id": "hunt_chris",
        "full_name": "Chris Carasella",
        "title": "Director of Property Management",
        "company": "Suncoast Property Management",
        "phone": "(904) 517-5939",
        "email": "",
        "county": "Duval",
        "url": "https://suncoastrentals.com/",
        "about": "Florida partner for single-family and multi-family rental management; Jacksonville BTR developer.",
        "source": "Firecrawl",
        "origin": "Firecrawl",
        "latitude": 30.3322,
        "longitude": -81.6557,
    },
    {
        "id": "hunt_kelly",
        "full_name": "Kelly Treadaway",
        "title": "Director of Real Estate Operations",
        "company": "Suncoast Property Management",
        "phone": "(904) 517-5939",
        "email": "",
        "county": "Duval",
        "url": "https://suncoastrentals.com/",
        "about": "Real estate operations for Suncoast’s Jacksonville investor and BTR book.",
        "source": "Firecrawl",
        "origin": "Firecrawl",
        "latitude": 30.328,
        "longitude": -81.66,
    },
    {
        "id": "hunt_lighthouse",
        "full_name": "Lighthouse Property Management",
        "title": "Property Manager",
        "company": "Lighthouse Property Management & Realty",
        "phone": "+1-904-374-1289",
        "email": "",
        "county": "Duval",
        "url": "https://www.jaxpm.com/",
        "about": "Jacksonville PM & realty — leasing, collections, turns, and SFR/MF management.",
        "source": "Firecrawl",
        "origin": "Firecrawl",
        "latitude": 30.319,
        "longitude": -81.64,
    },
    {
        "id": "hunt_nest",
        "full_name": "Nest Finders",
        "title": "Property Manager",
        "company": "Nest Finders Property Management",
        "phone": "904-565-9040",
        "email": "",
        "county": "Duval",
        "url": "https://www.nestfinders.com/",
        "about": "Local Jacksonville and St. Augustine rental management since 2004.",
        "source": "Firecrawl",
        "origin": "Firecrawl",
        "latitude": 30.29,
        "longitude": -81.59,
    },
    {
        "id": "hunt_vesta",
        "full_name": "Vesta Property Services",
        "title": "Community Manager",
        "company": "Vesta Property Services",
        "phone": "",
        "email": "",
        "county": "Duval",
        "url": "https://vestaforyou.com",
        "about": "Jacksonville community / HOA management. RocketReach company match.",
        "source": "RocketReach",
        "origin": "RocketReach",
        "latitude": 30.35,
        "longitude": -81.67,
    },
    {
        "id": "hunt_jwb",
        "full_name": "JWB Real Estate Companies",
        "title": "Asset Manager",
        "company": "JWB Real Estate Companies",
        "phone": "",
        "email": "",
        "county": "Duval",
        "url": "https://jwbrealestatecapital.com",
        "about": "Jacksonville real estate capital and property management. RocketReach match.",
        "source": "RocketReach",
        "origin": "RocketReach",
        "latitude": 30.31,
        "longitude": -81.65,
    },
    {
        "id": "hunt_nai",
        "full_name": "NAI Hallmark",
        "title": "Broker",
        "company": "NAI Hallmark",
        "phone": "",
        "email": "",
        "county": "Duval",
        "url": "https://naihallmark.com",
        "about": "Commercial real estate, Jacksonville. RocketReach match.",
        "source": "RocketReach",
        "origin": "RocketReach",
        "latitude": 30.322,
        "longitude": -81.672,
    },
    {
        "id": "hunt_ini",
        "full_name": "INI Realty Investments",
        "title": "Investor",
        "company": "INI Realty Investments, Inc",
        "phone": "",
        "email": "",
        "county": "Duval",
        "url": "https://inirealtyinvestments.com",
        "about": "Jacksonville real estate investment firm. RocketReach match.",
        "source": "RocketReach",
        "origin": "RocketReach",
        "latitude": 30.27,
        "longitude": -81.62,
    },
    {
        "id": "hunt_rise",
        "full_name": "RISE Real Estate",
        "title": "Broker",
        "company": "RISE A Real Estate Company",
        "phone": "",
        "email": "",
        "county": "Duval",
        "url": "https://risere.com",
        "about": "Jacksonville brokerage. RocketReach match.",
        "source": "RocketReach",
        "origin": "RocketReach",
        "latitude": 30.30,
        "longitude": -81.69,
    },
    {
        "id": "hunt_greenriver",
        "full_name": "Green River Property Management",
        "title": "Property Manager",
        "company": "Green River Property Management",
        "phone": "",
        "email": "",
        "county": "Duval",
        "url": "https://www.jacksonvillespropertymanagement.com/",
        "about": "Greater Jacksonville property management. Firecrawl web hit.",
        "source": "Firecrawl",
        "origin": "Firecrawl",
        "latitude": 30.36,
        "longitude": -81.63,
    },
    {
        "id": "hunt_thirdstone",
        "full_name": "Thirdstone Properties",
        "title": "Property Manager",
        "company": "Thirdstone Properties",
        "phone": "",
        "email": "",
        "county": "St. Johns",
        "url": "https://www.thirdstoneproperties.com/",
        "about": "Jacksonville / St. Johns / Yulee residential and multifamily management.",
        "source": "Firecrawl",
        "origin": "Firecrawl",
        "latitude": 30.08,
        "longitude": -81.49,
    },
    {
        "id": "hunt_hover",
        "full_name": "Hover Girl Properties",
        "title": "Owner-Operator",
        "company": "Hover Girl Properties",
        "phone": "",
        "email": "",
        "county": "Duval",
        "url": "https://hovergirlproperties.com/",
        "about": "Jacksonville real estate and property management. Firecrawl web hit.",
        "source": "Firecrawl",
        "origin": "Firecrawl",
        "latitude": 30.34,
        "longitude": -81.61,
    },
]

ICP_TITLE = re.compile(
    r"property|community|hoa|facilities|asset|broker|landlord|investor|regional|director",
    re.I,
)

EMAIL_FIND = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)
PHONE_FIND = re.compile(r"(?:\+1[\s\-.]?)?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}")
SOCIAL_FIND = {
    "linkedin": re.compile(r"https?://(?:www\.)?linkedin\.com/(?:company|in)/[^\s\"'<>]+", re.I),
    "facebook": re.compile(r"https?://(?:www\.)?facebook\.com/[^\s\"'<>]+", re.I),
    "instagram": re.compile(r"https?://(?:www\.)?instagram\.com/[^\s\"'<>]+", re.I),
}

SKIP_EMAIL_HOSTS = {
    "example.com",
    "sentry.io",
    "wixpress.com",
    "cloudflare.com",
    "schema.org",
    "godaddy.com",
}


def filter_hunt(query: str = "", title: str = "", location: str = "") -> list[dict[str, Any]]:
    needle = (query or "").lower()
    role = (title or "").lower()
    loc = (location or "").lower()
    hits: list[dict[str, Any]] = []
    for hit in HUNT_CACHE:
        blob = f"{hit['full_name']} {hit['title']} {hit['company']} {hit['about']} {hit['county']}".lower()
        if needle and needle not in blob and needle not in hit["county"].lower():
            continue
        if role and role not in hit["title"].lower() and role not in blob:
            if not ICP_TITLE.search(role) or not ICP_TITLE.search(hit["title"]):
                continue
        if loc and loc not in blob and loc not in {"first coast", "jacksonville", "florida", "fl"}:
            if not any(token in blob for token in ("duval", "jacksonville", "st. johns", "florida")):
                continue
        row = dict(hit)
        if row.get("latitude") is None:
            row["latitude"], row["longitude"] = coords_for_county(row["county"])
        hits.append(row)
    return hits


def extract_printed_contacts(html: str) -> dict[str, Any]:
    """Pull only addresses that appear in the page. Never synthesize an email."""
    emails: list[str] = []
    for match in EMAIL_FIND.findall(html or ""):
        value = match.strip(".,;:)(").lower()
        local, _, host = value.partition("@")
        if host in SKIP_EMAIL_HOSTS:
            continue
        if local.endswith((".png", ".jpg", ".gif", ".svg", ".webp")):
            continue
        if value.endswith((".png", ".jpg", ".gif", ".svg", ".webp")):
            continue
        if value not in emails:
            emails.append(value)
    phones: list[str] = []
    for match in PHONE_FIND.findall(html or ""):
        if match not in phones:
            phones.append(match)
    socials: dict[str, str] = {}
    for network, pattern in SOCIAL_FIND.items():
        found = pattern.search(html or "")
        if found:
            socials[network] = found.group(0).rstrip(").,")
    return {"emails": emails, "phones": phones, "socials": socials}


def scrape_url(url: str, timeout: int = 8) -> dict[str, Any]:
    url = (url or "").strip()
    if not url:
        raise ValueError("URL is required")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    html = _fetch_html(url, timeout=timeout)
    contacts = extract_printed_contacts(html)
    text = _strip_tags(html)[:4000]
    return {
        "ok": True,
        "url": url,
        "text": text,
        "emails": contacts["emails"],
        "phones": contacts["phones"],
        "socials": contacts["socials"],
        "email": contacts["emails"][0] if contacts["emails"] else "",
        "invented": False,
        "note": "Only printed emails are kept. Empty means none was on the page.",
    }


def _fetch_html(url: str, timeout: int) -> str:
    key = os.environ.get("FIRECRAWL_API_KEY", "").strip()
    if key:
        try:
            payload = json.dumps({"url": url, "formats": ["html", "markdown"]}).encode("utf-8")
            request = Request(
                "https://api.firecrawl.dev/v1/scrape",
                data=payload,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urlopen(request, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8", errors="replace"))
            inner = data.get("data") or {}
            return str(inner.get("html") or inner.get("markdown") or "")
        except (URLError, TimeoutError, json.JSONDecodeError, OSError):
            pass
    request = Request(
        url,
        headers={"User-Agent": "NexusLeadEngine/0.1 (+https://github.com/hatcheric950/nexus-lead-desk)"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(400_000)
        return raw.decode("utf-8", errors="replace")
    except (URLError, TimeoutError, OSError) as exc:
        raise ValueError(f"Could not fetch {url}: {exc}") from exc


def _strip_tags(html: str) -> str:
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def county_anchor(county: str) -> tuple[float, float]:
    return COUNTY_COORDS.get(county, COUNTY_COORDS["Duval"])
