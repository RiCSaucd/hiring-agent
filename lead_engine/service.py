"""Nexus desk orchestration: hunt, enrich, pipeline, deliver."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lead_engine.hunt import filter_hunt, scrape_url
from lead_engine.locations import autocomplete, geocode, map_point
from lead_engine.pipeline import PIPELINE_STAGES, apply_gates, draft_outreach, pipeline_counts
from lead_engine.scoring import infer_account_type, leads_to_csv, parse_prospect_csv
from lead_engine.store import LeadStore, uid

DEFAULT_DB = Path("var/nexus_leads.db")


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class NexusDesk:
    def __init__(self, db_path: str | Path = DEFAULT_DB, seed: bool = True):
        self.store = LeadStore(db_path, seed=seed)

    def close(self) -> None:
        self.store.close()

    def status(self) -> dict[str, Any]:
        leads = self.store.list_leads()
        hot = [lead for lead in leads if lead.get("lead_temperature") == "Hot" and lead.get("status") != "invalid"]
        safe = [lead for lead in leads if lead.get("is_safe_to_email")]
        return {
            "leads": len(leads),
            "hot": len(hot),
            "safe_to_email": len(safe),
            "accounts": len(self.store.list_accounts()),
            "batches": len(self.store.list_batches()),
            "captures": len(self.store.list_captures()),
            "stages": PIPELINE_STAGES,
            "pipeline": pipeline_counts(leads),
            "rule": "Emails are never invented. Only status=valid is safe to email.",
        }

    def list_leads(self, temperature: str | None = None, county: str | None = None) -> list[dict[str, Any]]:
        leads = self.store.list_leads()
        if temperature:
            leads = [lead for lead in leads if lead.get("lead_temperature") == temperature]
        if county:
            leads = [lead for lead in leads if lead.get("county") == county]
        return [self._with_map(lead) for lead in leads]

    def hunt(self, query: str = "", title: str = "Property Manager", location: str = "Jacksonville") -> dict[str, Any]:
        hits = [self._with_map(hit) for hit in filter_hunt(query, title, location)]
        self.store.add_activity(
            {
                "kind": "hunt",
                "title": "Hunt run",
                "detail": f"{len(hits)} targets · {title} · {location}",
            }
        )
        return {
            "count": len(hits),
            "hits": hits,
            "query": query,
            "title": title,
            "location": location,
            "live": False,
            "note": "Cached First Coast Firecrawl + RocketReach set. Live Maps/RocketReach keys are optional.",
        }

    def import_hits(self, hit_ids: list[str] | None = None, hits: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        catalog = {hit["id"]: hit for hit in filter_hunt()}
        rows = hits or []
        if hit_ids:
            rows = [catalog[hit_id] for hit_id in hit_ids if hit_id in catalog]
        return self.add_prospects(rows)

    def add_prospects(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        created = 0
        updated = 0
        for raw in rows:
            payload = {
                "full_name": raw.get("full_name") or raw.get("fullName"),
                "title": raw.get("title"),
                "company": raw.get("company"),
                "email": raw.get("email") or "",
                "phone": raw.get("phone"),
                "county": raw.get("county"),
                "url": raw.get("url") or raw.get("website"),
                "source": raw.get("source") or "Manual",
                "about_summary": raw.get("about") or raw.get("about_summary") or raw.get("aboutSummary"),
                "latitude": raw.get("latitude"),
                "longitude": raw.get("longitude"),
                "place_id": raw.get("place_id") or raw.get("id"),
                "address": raw.get("address"),
            }
            existing = self.store.find_duplicate(
                email=payload.get("email") or "",
                full_name=payload.get("full_name") or "",
                company=payload.get("company") or "",
                place_id=payload.get("place_id") or "",
            )
            gated = apply_gates(existing or {"status": "new", "created_at": iso_now()}, payload)
            if existing:
                gated["id"] = existing["id"]
                gated["created_at"] = existing.get("created_at")
                gated["last_action"] = "Updated from intake"
                updated += 1
            else:
                gated["id"] = uid("lead")
                gated["created_at"] = iso_now()
                gated["status"] = "new" if gated.get("status") != "invalid" else gated["status"]
                gated["last_action"] = "Created"
                created += 1
            gated["last_enriched_at"] = iso_now()
            self.store.upsert_lead(gated)
            self._upsert_account_for(gated)
        self.store.add_activity(
            {
                "kind": "hunt",
                "title": "Prospects in",
                "detail": f"{created} created · {updated} merged",
            }
        )
        return {
            "created": created,
            "updated": updated,
            "invalid": 0,
            "hot_ids": self._hot_ids(),
            "leads": self.list_leads(),
        }

    def import_csv(self, text: str) -> dict[str, Any]:
        rows = parse_prospect_csv(text)
        if not rows:
            raise ValueError("No prospect rows in CSV")
        return self.add_prospects(rows)

    def run_pipeline(self, lead_ids: list[str] | None = None) -> dict[str, Any]:
        updated = 0
        invalid = 0
        targets = set(lead_ids or [])
        for lead in self.store.list_leads():
            if targets and lead["id"] not in targets:
                continue
            if lead.get("status") in {"delivered", "nurture"}:
                continue
            extra: dict[str, Any] = {}
            url = lead.get("url") or lead.get("website")
            if url and not lead.get("email"):
                try:
                    scraped = scrape_url(str(url))
                    extra["email"] = scraped.get("email") or ""
                    extra["phone"] = scraped.get("phones")[0] if scraped.get("phones") else lead.get("phone")
                    extra["social_profiles"] = scraped.get("socials") or {}
                    extra["about_summary"] = lead.get("about_summary") or scraped.get("text", "")[:280]
                except ValueError:
                    extra = {}
            next_lead = apply_gates(lead, extra)
            next_lead["last_enriched_at"] = iso_now()
            if not next_lead.get("outreach_draft") and next_lead.get("is_safe_to_email"):
                next_lead["outreach_draft"] = draft_outreach(next_lead)
            if next_lead["status"] == "invalid":
                invalid += 1
            else:
                updated += 1
            self.store.upsert_lead(next_lead)
            self._upsert_account_for(next_lead)
        self.store.add_activity(
            {
                "kind": "system",
                "title": "Pipeline run",
                "detail": f"{updated} scored · {invalid} dropped",
            }
        )
        return {
            "created": 0,
            "updated": updated,
            "invalid": invalid,
            "hot_ids": self._hot_ids(),
            "leads": self.list_leads(),
            "status": self.status(),
        }

    def enrich_url(self, url: str) -> dict[str, Any]:
        scraped = scrape_url(url)
        prospect = {
            "full_name": scraped.get("url", "").split("//")[-1].split("/")[0],
            "title": "Property Manager",
            "company": scraped.get("url", ""),
            "email": scraped.get("email") or "",
            "phone": (scraped.get("phones") or [""])[0],
            "county": "Duval",
            "url": scraped["url"],
            "source": "Firecrawl" if scraped else "Manual",
            "about_summary": scraped.get("text", "")[:280],
            "social_profiles": scraped.get("socials") or {},
        }
        return {"scrape": scraped, "prospect": prospect}

    def update_lead(self, lead_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        lead = self.store.get_lead(lead_id)
        allowed = {
            "full_name",
            "title",
            "company",
            "email",
            "phone",
            "county",
            "url",
            "notes",
            "outreach_draft",
            "status",
        }
        extra = {key: patch[key] for key in allowed if key in patch}
        next_lead = apply_gates(lead, extra)
        next_lead["id"] = lead_id
        self.store.upsert_lead(next_lead)
        return self._with_map(next_lead)

    def delete_lead(self, lead_id: str) -> None:
        self.store.delete_lead(lead_id)

    def deliver(self, lead_ids: list[str], client_name: str, notes: str = "") -> dict[str, Any]:
        if not lead_ids:
            raise ValueError("Select at least one lead to deliver")
        if not (client_name or "").strip():
            raise ValueError("Client name is required")
        batch = {
            "id": uid("batch"),
            "client_name": client_name.strip(),
            "created_at": iso_now(),
            "lead_ids": lead_ids,
            "notes": notes,
        }
        self.store.upsert_batch(batch)
        for lead_id in lead_ids:
            try:
                lead = self.store.get_lead(lead_id)
            except KeyError:
                continue
            lead["status"] = "delivered"
            lead["last_action"] = "Delivered"
            self.store.upsert_lead(lead)
        self.store.add_activity(
            {
                "kind": "lead",
                "title": "Batch delivered",
                "detail": f"{client_name} · {len(lead_ids)} leads",
            }
        )
        return {"batch": batch, "leads": self.list_leads()}

    def export_csv(self, lead_ids: list[str] | None = None, safe_only: bool = False) -> str:
        leads = self.list_leads()
        if lead_ids:
            wanted = set(lead_ids)
            leads = [lead for lead in leads if lead["id"] in wanted]
        if safe_only:
            leads = [lead for lead in leads if lead.get("is_safe_to_email")]
        return leads_to_csv(leads)

    def add_capture(self, payload: dict[str, Any]) -> dict[str, Any]:
        capture = {
            "id": uid("cap"),
            "name": (payload.get("name") or "").strip() or "Unknown",
            "email": (payload.get("email") or "").strip().lower(),
            "kind": payload.get("kind") or "property",
            "service": payload.get("service") or "",
            "message": payload.get("message") or "",
            "urgency": int(payload.get("urgency") or 5),
            "value_score": int(payload.get("value_score") or payload.get("valueScore") or 5),
            "next_step": payload.get("next_step") or payload.get("nextStep") or "Call same day. Confirm scope.",
            "response_draft": payload.get("response_draft")
            or payload.get("responseDraft")
            or self._capture_draft(payload),
            "labels": payload.get("labels") or ["property"],
            "status": payload.get("status") or "new",
            "created_at": iso_now(),
        }
        self.store.upsert_capture(capture)
        self.store.add_activity({"kind": "capture", "title": "Property inquiry", "detail": capture["name"]})
        return capture

    def list_captures(self) -> list[dict[str, Any]]:
        return self.store.list_captures()

    def list_batches(self) -> list[dict[str, Any]]:
        return self.store.list_batches()

    def activity(self) -> list[dict[str, Any]]:
        return self.store.list_activity()

    def reset_demo(self) -> dict[str, Any]:
        self.store.reset_demo()
        return self.status()

    def suggest_locations(self, query: str) -> list[dict[str, Any]]:
        return autocomplete(query)

    def geocode_location(self, query: str) -> dict[str, Any] | None:
        return geocode(query)

    def snapshot(self) -> dict[str, Any]:
        return {
            "status": self.status(),
            "leads": self.list_leads(),
            "accounts": self.store.list_accounts(),
            "batches": self.list_batches(),
            "captures": self.list_captures(),
            "activity": self.activity(),
        }

    def _upsert_account_for(self, lead: dict[str, Any]) -> str:
        name = (lead.get("company") or "").strip()
        if not name:
            return ""
        existing = self.store.find_account(name)
        if existing:
            lead["account_id"] = existing["id"]
            self.store.upsert_lead(lead)
            return existing["id"]
        account = {
            "id": uid("acct"),
            "name": name,
            "account_type": infer_account_type(lead.get("title") or "", name),
            "primary_county": lead.get("county") or "Other",
            "website": lead.get("url") or "",
            "created_at": iso_now(),
        }
        self.store.upsert_account(account)
        lead["account_id"] = account["id"]
        self.store.upsert_lead(lead)
        return account["id"]

    def _hot_ids(self) -> list[str]:
        return [
            lead["id"]
            for lead in self.store.list_leads()
            if lead.get("lead_temperature") == "Hot" and lead.get("status") != "invalid"
        ]

    def _with_map(self, lead: dict[str, Any]) -> dict[str, Any]:
        point = map_point(lead.get("latitude"), lead.get("longitude"))
        return {**lead, "map": point}

    def _capture_draft(self, payload: dict[str, Any]) -> str:
        name = (payload.get("name") or "there").split()[0]
        service = payload.get("service") or "the work"
        return (
            f"{name} — we can walk the site this week and put a written bid for {service} "
            "in your hands the same day. Recurring First Coast coverage if you want it on one invoice."
        )
