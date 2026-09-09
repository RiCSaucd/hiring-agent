"""Demo desk seed — First Coast ICP, including junk/thin rows so verify is visible."""

from __future__ import annotations

from typing import Any

from lead_engine.scoring import infer_account_type, normalize_prospect

T = {
    "a": "2026-08-12T13:20:00.000Z",
    "b": "2026-08-14T10:04:00.000Z",
    "c": "2026-08-16T16:41:00.000Z",
    "d": "2026-08-18T09:12:00.000Z",
    "e": "2026-08-19T15:33:00.000Z",
    "f": "2026-08-20T11:08:00.000Z",
    "g": "2026-08-21T08:55:00.000Z",
    "h": "2026-08-21T19:02:00.000Z",
    "i": "2026-08-22T12:10:00.000Z",
}


def _lead(partial: dict[str, Any]) -> dict[str, Any]:
    n = normalize_prospect(partial)
    return {
        **n,
        "id": partial["id"],
        "status": partial["status"],
        "created_at": partial["created_at"],
        "last_enriched_at": partial.get("last_enriched_at"),
        "last_action": partial.get("last_action"),
        "notes": partial.get("notes"),
        "outreach_draft": partial.get("outreach_draft"),
        "latitude": partial.get("latitude") or n.get("latitude"),
        "longitude": partial.get("longitude") or n.get("longitude"),
        "place_id": partial.get("place_id") or partial["id"],
    }


def seed_leads() -> list[dict[str, Any]]:
    return [
        _lead(
            {
                "id": "lead_chris",
                "full_name": "Chris Carasella",
                "title": "Director of Property Management",
                "company": "Suncoast Property Management",
                "email": "",
                "phone": "(904) 517-5939",
                "county": "Duval",
                "source": "Firecrawl",
                "status": "enriched",
                "about_summary": "Florida partner for single-family and multi-family rental management; Jacksonville BTR developer.",
                "url": "https://suncoastrentals.com/",
                "created_at": T["g"],
                "last_enriched_at": T["g"],
                "last_action": "Firecrawl scrape",
                "latitude": 30.3322,
                "longitude": -81.6557,
            }
        ),
        _lead(
            {
                "id": "lead_marcus",
                "full_name": "Marcus Ellison",
                "title": "Regional Property Manager",
                "company": "Coastal Ridge Management",
                "email": "marcus.ellison@coastalridge.com",
                "phone": "904-555-0142",
                "county": "Duval",
                "status": "scored",
                "about_summary": "Oversees 1,400 garden-style units across Jacksonville’s Southside and Beaches. Signs annual exterior and turn packages.",
                "created_at": T["a"],
                "last_enriched_at": T["d"],
                "last_action": "Scored",
                "outreach_draft": (
                    "Marcus — we run recurring exterior and turn work for garden-style portfolios "
                    "on the Southside. Happy to price a 90-day pilot against your current vendor mix."
                ),
                "latitude": 30.25,
                "longitude": -81.58,
            }
        ),
        _lead(
            {
                "id": "lead_elena",
                "full_name": "Elena Vasquez",
                "title": "HOA President",
                "company": "Sawgrass Preserve HOA",
                "email": "elena.vasquez@sawgrasspreserve.org",
                "phone": "904-555-0190",
                "county": "St. Johns",
                "source": "Referral",
                "status": "scored",
                "about_summary": "Board lead for 186-home HOA. Budget season in Q4. Wants a single vendor for irrigation, pressure wash, and common-area repairs.",
                "created_at": T["b"],
                "last_enriched_at": T["e"],
                "last_action": "Scored",
                "latitude": 30.18,
                "longitude": -81.39,
            }
        ),
        _lead(
            {
                "id": "lead_harbor",
                "full_name": "James Whitaker",
                "title": "Broker-Owner",
                "company": "Harborline Realty",
                "email": "james@harborlinerealty.com",
                "phone": "904-555-0166",
                "county": "Duval",
                "status": "scored",
                "about_summary": "Broker-owner. Refers make-ready and exterior work for investor clients.",
                "created_at": T["d"],
                "last_enriched_at": T["d"],
                "last_action": "Scored",
                "latitude": 30.31,
                "longitude": -81.70,
            }
        ),
        _lead(
            {
                "id": "lead_mina",
                "full_name": "Mina Park",
                "title": "Facilities Director",
                "company": "First Coast Logistics Parks",
                "email": "mina.park@jaxportlogistics.com",
                "county": "Duval",
                "source": "Open Data",
                "status": "verified",
                "about_summary": "Facilities for logistics parks. Email present, waiting verify.",
                "created_at": T["e"],
                "last_enriched_at": T["f"],
                "last_action": "Verified",
                "latitude": 30.40,
                "longitude": -81.57,
            }
        ),
        _lead(
            {
                "id": "lead_aisha",
                "full_name": "Aisha Rahman",
                "title": "Asset Manager",
                "company": "St. Johns Build-to-Rent",
                "email": "aisha.rahman@sjbtr.com",
                "phone": "904-555-0118",
                "county": "St. Johns",
                "status": "scored",
                "about_summary": "BTR portfolio in St. Johns. Recurring exterior and turn work.",
                "created_at": T["g"],
                "last_enriched_at": T["g"],
                "last_action": "Scored",
                "latitude": 29.90,
                "longitude": -81.31,
            }
        ),
        _lead(
            {
                "id": "lead_brett",
                "full_name": "Brett Holloway",
                "title": "Regional Manager",
                "company": "Palmetto Capital",
                "email": "brett.holloway@palmettocap.com",
                "phone": "904-555-0177",
                "county": "St. Johns",
                "status": "scored",
                "about_summary": "Value-add 40–80 units. Signs annual maintenance.",
                "created_at": T["f"],
                "last_enriched_at": T["f"],
                "last_action": "Scored",
                "latitude": 29.95,
                "longitude": -81.38,
            }
        ),
        _lead(
            {
                "id": "lead_linda",
                "full_name": "Linda Cho",
                "title": "Community Manager",
                "company": "Riverside Commons",
                "email": "linda.cho@riversidecommons.com",
                "phone": "904-555-0133",
                "county": "Duval",
                "status": "delivered",
                "about_summary": "PM · Riverside Commons. Delivered in last client pack.",
                "created_at": T["c"],
                "last_enriched_at": T["c"],
                "last_action": "Delivered",
                "latitude": 30.32,
                "longitude": -81.68,
            }
        ),
        _lead(
            {
                "id": "lead_junk",
                "full_name": "Temp Drop",
                "title": "Owner",
                "company": "Pop-up LLC",
                "email": "drop@mailinator.com",
                "county": "Other",
                "status": "invalid",
                "created_at": T["b"],
                "last_action": "Email failed verify",
            }
        ),
        _lead(
            {
                "id": "lead_thin",
                "full_name": "Noah Briggs",
                "title": "Investor",
                "company": "",
                "email": "",
                "county": "Nassau",
                "source": "Manual",
                "status": "new",
                "created_at": T["i"],
                "last_action": "Queued for enrich",
                "latitude": 30.67,
                "longitude": -81.46,
            }
        ),
    ]


def seed_accounts(leads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    accounts: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    for lead in leads:
        name = (lead.get("company") or "").strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            lead["account_id"] = seen[key]
            continue
        account_id = f"acct_{lead['id'].replace('lead_', '')}"
        seen[key] = account_id
        lead["account_id"] = account_id
        accounts.append(
            {
                "id": account_id,
                "name": name,
                "account_type": infer_account_type(lead.get("title") or "", name),
                "primary_county": lead.get("county") or "Other",
                "website": lead.get("url") or "",
                "created_at": lead.get("created_at"),
            }
        )
    return accounts


def seed_captures() -> list[dict[str, Any]]:
    return [
        {
            "id": "cap_roof",
            "name": "Derek Colton",
            "email": "derek@springfieldtwelve.com",
            "kind": "property",
            "service": "Emergency roof + dry-in, 12-unit",
            "message": "Wind-driven leak on building B, Springfield. Tenants on second floor. Need a crew this week and a bid for full slope repair.",
            "urgency": 9,
            "value_score": 8,
            "next_step": "Same-day call. Site walk. Recurring roof-inspection package after dry-in.",
            "response_draft": (
                "Derek — we can dry-in this week and put a written slope bid in your hands after the walk. "
                "If the other eleven units are due, we will price a quarterly inspection so this does not become a night call again."
            ),
            "labels": ["emergency", "multifamily", "Duval"],
            "status": "drafted",
            "created_at": T["h"],
        },
        {
            "id": "cap_hoa_bid",
            "name": "Elena Vasquez",
            "email": "elena.vasquez@sawgrasspreserve.org",
            "kind": "property",
            "service": "HOA common-area package",
            "message": "Need a 12-month common-area maintenance quote before the October board.",
            "urgency": 6,
            "value_score": 9,
            "next_step": "Send one-pager + site walk date. Attach recurring package tiers.",
            "response_draft": (
                "Elena — we will have a 12-month common-area package in front of the board before October. "
                "Irrigation, pressure wash, and work-order response on one invoice. Two walk times this week are open."
            ),
            "labels": ["HOA", "St. Johns", "recurring"],
            "status": "drafted",
            "created_at": T["f"],
        },
    ]


def seed_batches() -> list[dict[str, Any]]:
    return [
        {
            "id": "batch_1",
            "client_name": "Harborline desk pack",
            "created_at": T["c"],
            "lead_ids": ["lead_linda"],
            "notes": "First Coast scored Hot, safe to email.",
        }
    ]


def seed_activity() -> list[dict[str, Any]]:
    return [
        {"id": "act_1", "at": T["i"], "kind": "hunt", "title": "Firecrawl hunt", "detail": "Suncoast · Chris Carasella · public phone only"},
        {"id": "act_2", "at": T["h"], "kind": "capture", "title": "Emergency property lead", "detail": "Springfield 12-unit roof leak — urgency 9"},
        {"id": "act_3", "at": T["g"], "kind": "hunt", "title": "RocketReach companies", "detail": "Vesta, JWB, NAI Hallmark — Jacksonville"},
        {"id": "act_4", "at": T["g"], "kind": "lead", "title": "New prospect", "detail": "Aisha Rahman · St. Johns Build-to-Rent"},
        {"id": "act_5", "at": T["f"], "kind": "lead", "title": "Scored Hot", "detail": "Brett Holloway · Palmetto Capital"},
        {"id": "act_6", "at": T["e"], "kind": "system", "title": "Whop listing", "detail": "Nexus Lead Engine · Starter $97/mo"},
        {"id": "act_7", "at": T["d"], "kind": "system", "title": "Pipeline run", "detail": "Scored and dropped junk on the desk"},
    ]
