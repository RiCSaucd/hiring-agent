"""Lead scoring, email verification, and CSV — emails are never invented."""

from __future__ import annotations

import csv
import io
import re
from typing import Any

DISPOSABLE = {
    "mailinator.com",
    "tempmail.com",
    "guerrillamail.com",
    "10minutemail.com",
    "yopmail.com",
    "trashmail.com",
    "getnada.com",
}

ROLE_LOCAL = {
    "info",
    "admin",
    "office",
    "support",
    "hello",
    "contact",
    "sales",
    "noreply",
    "no-reply",
    "billing",
    "webmaster",
}

TARGET_COUNTIES = {"Duval", "St. Johns", "Clay", "Nassau", "Flagler"}

ICP = re.compile(
    r"property manager|community manager|hoa|facilities|asset manager|broker|"
    r"landlord|investor|regional manager|maintenance director|portfolio|"
    r"board president|hoa president|owner-operator|build-to-rent",
    re.I,
)

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

SAMPLE_CSV = """full_name,title,company,email,phone,county,url,source
Rosa Delgado,Regional Property Manager,Tidewater Residential,rosa.delgado@tidewaterres.com,904-555-0144,Duval,,Manual
Keith Lang,HOA President,Ponte Vedra Dunes HOA,keith.lang@pvdunes.org,904-555-0188,St. Johns,,Referral
Mina Park,Facilities Director,JAXPORT Logistics Center,mina.park@jaxportlogistics.com,,Duval,https://example.com,Open Data
"""


def split_name(full_name: str) -> tuple[str, str]:
    parts = [p for p in (full_name or "").strip().split() if p]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def validate_email(email: str | None) -> str:
    value = (email or "").strip().lower()
    if not value:
        return "missing"
    if not EMAIL_RE.match(value):
        return "invalid"
    local, _, domain = value.partition("@")
    if not local or not domain:
        return "invalid"
    if domain in DISPOSABLE:
        return "disposable"
    if local in ROLE_LOCAL:
        return "role"
    if domain.count(".") < 1:
        return "invalid"
    return "valid"


def is_safe_to_email(status: str) -> bool:
    return status == "valid"


def score_lead(
    *,
    title: str = "",
    company: str = "",
    county: str = "",
    phone: str = "",
    email_status: str = "missing",
    about_summary: str = "",
    headline: str = "",
) -> dict[str, Any]:
    breakdown: list[dict[str, Any]] = [{"label": "Base", "points": 40}]

    if email_status == "valid":
        breakdown.append({"label": "Verified email", "points": 25})
    elif email_status == "role":
        breakdown.append({"label": "Role inbox", "points": 8})
    elif email_status == "catch-all":
        breakdown.append({"label": "Catch-all", "points": 6})

    digits = re.sub(r"\D", "", phone or "")
    if len(digits) >= 10:
        breakdown.append({"label": "Direct phone", "points": 10})

    if ICP.search(title or ""):
        breakdown.append({"label": "ICP title", "points": 15})

    if (company or "").strip():
        breakdown.append({"label": "Company present", "points": 5})

    county_value = (county or "").strip()
    if county_value in TARGET_COUNTIES:
        breakdown.append({"label": "First Coast county", "points": 10})

    if len((about_summary or "").strip()) > 20 or len((headline or "").strip()) > 8:
        breakdown.append({"label": "Profile depth", "points": 5})

    raw = sum(int(row["points"]) for row in breakdown)
    score = min(100, raw)
    if score >= 75:
        temperature = "Hot"
    elif score >= 55:
        temperature = "Warm"
    else:
        temperature = "Cold"
    return {"score": score, "temperature": temperature, "breakdown": breakdown}


def infer_account_type(title: str, company: str) -> str:
    blob = f"{title} {company}".lower()
    if "hoa" in blob:
        return "HOA"
    if "broker" in blob or "realty" in blob:
        return "Brokerage"
    if "capital" in blob or "asset" in blob or "investor" in blob:
        return "Investment"
    if "logistic" in blob or "industrial" in blob or "park" in blob:
        return "Commercial"
    if "apartment" in blob or "residences" in blob or "commons" in blob:
        return "Multifamily"
    return "Property management"


def normalize_prospect(raw: dict[str, Any]) -> dict[str, Any]:
    full_name = (raw.get("full_name") or raw.get("fullName") or "").strip()
    if not full_name:
        full_name = f"{raw.get('first_name') or raw.get('firstName') or ''} {raw.get('last_name') or raw.get('lastName') or ''}".strip()
    first_name, last_name = split_name(full_name)
    email = (raw.get("email") or "").strip().lower()
    email_status = validate_email(email)
    title = (raw.get("title") or "").strip()
    company = (raw.get("company") or "").strip()
    phone = (raw.get("phone") or "").strip()
    county = (raw.get("county") or "Other").strip() or "Other"
    about = (raw.get("about_summary") or raw.get("aboutSummary") or raw.get("about") or "").strip()
    headline = (raw.get("headline") or "").strip()
    scored = score_lead(
        title=title,
        company=company,
        county=county,
        phone=phone,
        email_status=email_status,
        about_summary=about,
        headline=headline,
    )
    source = raw.get("source") or "Manual"
    url = (raw.get("url") or "").strip()
    return {
        "first_name": first_name,
        "last_name": last_name,
        "full_name": full_name or "Unknown",
        "title": title,
        "company": company,
        "email": email,
        "phone": phone,
        "email_status": email_status,
        "is_safe_to_email": is_safe_to_email(email_status),
        "lead_score": scored["score"],
        "lead_temperature": scored["temperature"],
        "about_summary": about,
        "headline": headline or (f"{title} · {company}".strip(" ·") if title or company else ""),
        "county": county,
        "source": source,
        "url": url,
        "latitude": _optional_float(raw.get("latitude") or raw.get("lat")),
        "longitude": _optional_float(raw.get("longitude") or raw.get("lng")),
        "score_breakdown": scored["breakdown"],
        "social_profiles": raw.get("social_profiles") or {},
        "place_id": (raw.get("place_id") or raw.get("placeId") or "").strip(),
        "address": (raw.get("address") or "").strip(),
        "website": (raw.get("website") or url).strip(),
    }


def parse_prospect_csv(text: str) -> list[dict[str, Any]]:
    if not (text or "").strip():
        return []
    reader = csv.reader(io.StringIO(text.strip()))
    rows = list(reader)
    if not rows:
        return []
    header = [h.strip().lower().replace(" ", "_") for h in rows[0]]
    looks_header = any(
        h in {"full_name", "name", "email", "company", "title", "linkedin_url", "url"}
        for h in header
    )
    keys = (
        header
        if looks_header
        else ["full_name", "title", "company", "email", "phone", "county", "url", "source"]
    )
    body = rows[1:] if looks_header else rows

    def get(cols: list[str], *aliases: str) -> str:
        for alias in aliases:
            if alias in keys:
                idx = keys.index(alias)
                if idx < len(cols) and cols[idx]:
                    return cols[idx].strip()
        return ""

    out: list[dict[str, Any]] = []
    for cols in body:
        if not any(c.strip() for c in cols):
            continue
        out.append(
            {
                "full_name": get(cols, "full_name", "name"),
                "title": get(cols, "title"),
                "company": get(cols, "company"),
                "email": get(cols, "email"),
                "phone": get(cols, "phone"),
                "county": get(cols, "county", "location"),
                "url": get(cols, "url", "linkedin_url"),
                "source": get(cols, "source") or "Manual",
            }
        )
    return out


def leads_to_csv(leads: list[dict[str, Any]]) -> str:
    header = [
        "full_name",
        "title",
        "company",
        "email",
        "phone",
        "email_status",
        "is_safe_to_email",
        "lead_score",
        "lead_temperature",
        "about_summary",
        "headline",
        "county",
        "source",
        "status",
        "last_action",
        "last_enriched_at",
        "is_safe_to_email_note",
    ]
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    for lead in leads:
        writer.writerow(
            [
                lead.get("full_name", ""),
                lead.get("title", ""),
                lead.get("company", ""),
                lead.get("email", ""),
                lead.get("phone", ""),
                lead.get("email_status", ""),
                lead.get("is_safe_to_email", False),
                lead.get("lead_score", 0),
                lead.get("lead_temperature", ""),
                lead.get("about_summary", ""),
                lead.get("headline", ""),
                lead.get("county", ""),
                lead.get("source", ""),
                lead.get("status", ""),
                lead.get("last_action") or "",
                lead.get("last_enriched_at") or "",
                "safe to email" if lead.get("is_safe_to_email") else "do not email — not verified valid",
            ]
        )
    return buf.getvalue()


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
