"""Canonical skill vocabulary and alias matching for resume/job overlap."""

from __future__ import annotations

import re
from typing import Iterable

SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    "python": ("python3", "py"),
    "javascript": ("js", "ecmascript"),
    "typescript": ("ts",),
    "react": ("reactjs", "react.js"),
    "node.js": ("nodejs", "node"),
    "fastapi": ("fast api",),
    "django": (),
    "flask": (),
    "postgresql": ("postgres", "psql"),
    "mysql": (),
    "sqlite": ("sqlite3",),
    "mongodb": ("mongo",),
    "redis": (),
    "elasticsearch": ("elastic search", "opensearch"),
    "aws": ("amazon web services",),
    "gcp": ("google cloud", "google cloud platform"),
    "azure": ("microsoft azure",),
    "docker": (),
    "kubernetes": ("k8s",),
    "terraform": (),
    "linux": ("unix",),
    "git": ("github", "gitlab"),
    "ci/cd": ("cicd", "github actions", "gitlab ci"),
    "graphql": (),
    "rest": ("rest api", "restful"),
    "grpc": (),
    "html": ("html5",),
    "css": ("css3",),
    "tailwind": ("tailwindcss",),
    "next.js": ("nextjs", "next"),
    "vue": ("vuejs", "vue.js"),
    "angular": (),
    "svelte": (),
    "java": (),
    "kotlin": (),
    "go": ("golang",),
    "rust": (),
    "c++": ("cpp", "cplusplus"),
    "c#": ("csharp", ".net", "dotnet"),
    "ruby": ("rails", "ruby on rails"),
    "php": (),
    "swift": (),
    "scala": (),
    "sql": (),
    "pandas": (),
    "numpy": (),
    "scikit-learn": ("sklearn", "scikit learn"),
    "pytorch": (),
    "tensorflow": (),
    "huggingface": ("hugging face", "transformers"),
    "langchain": (),
    "spark": ("pyspark", "apache spark"),
    "airflow": ("apache airflow",),
    "dbt": (),
    "kafka": ("apache kafka",),
    "rabbitmq": (),
    "snowflake": (),
    "bigquery": (),
    "redshift": (),
    "tableau": (),
    "power bi": ("powerbi",),
    "excel": (),
    "figma": (),
    "pytest": (),
    "jest": (),
    "playwright": (),
    "selenium": (),
    "bash": ("shell", "zsh"),
    "prometheus": (),
    "grafana": (),
    "datadog": (),
    "sentry": (),
    "oauth": ("oidc", "openid"),
    "jwt": (),
    "s3": ("aws s3",),
    "lambda": ("aws lambda",),
    "ecs": (),
    "eks": (),
    "helm": (),
    "ansible": (),
    "nginx": (),
    "webpack": (),
    "vite": (),
    "redux": (),
    "django rest framework": ("drf",),
    "celery": (),
    "llm": ("large language model", "large language models"),
    "rag": ("retrieval augmented generation",),
    "prompt engineering": (),
    "machine learning": ("ml",),
    "deep learning": (),
    "nlp": ("natural language processing",),
    "computer vision": (),
    "data engineering": (),
    "data science": (),
    "agile": ("scrum",),
    "jira": (),
    "system design": (),
    "microservices": (),
    "event-driven": ("event driven",),
    "observability": (),
    "security": ("appsec", "infosec", "cybersecurity", "cyber security"),
    "salesforce": ("salesforce crm",),
    "crm": (),
    "customer service": (
        "customer support",
        "customer experience",
        "client service",
        "client support",
        "customer-facing",
    ),
    "customer success": ("client success",),
    "client communication": ("customer communication", "client-facing"),
    "insurance": (
        "life & health",
        "life and health",
        "property & casualty",
        "property and casualty",
        "p&c",
    ),
    "comptia": ("comptia certified",),
    "network+": (
        "network plus",
        "comptia network+",
        "comptia network plus",
        "comptia network",
    ),
    "security+": (
        "security plus",
        "comptia security+",
        "comptia security plus",
        "comptia security",
    ),
    "help desk": ("helpdesk",),
    "workflow automation": ("business process automation", "ai automation"),
    "zapier": (),
    "n8n": (),
    "neon": ("neon postgres", "neon postgresql"),
    "supabase": ("super base", "supabase postgres"),
    "verbal": (),
    "compliance": ("regulatory compliance",),
    "grc": ("governance risk",),
    "pii": ("personally identifiable information", "customer data"),
    "iam": ("identity and access", "access control"),
    "soc": ("security operations", "security operations center"),
    "siem": (),
    "incident response": (),
    "vulnerability management": (),
    "security awareness": (),
    "ticketing": ("servicenow",),
    "consultative selling": ("solution selling", "consultative sales", "solution-selling"),
    "outside sales": ("field sales", "outside/field sales"),
    "inside sales": (),
    "territory management": ("sales territory",),
    "medical sales": ("pharmaceutical sales", "prescription supplies", "prescription drug supplies"),
    "contract negotiation": ("negotiating contracts",),
    "pipeline": ("sales pipeline", "pipeline forecasting", "pipeline development", "pipeline hygiene"),
    "microsoft office": ("ms office", "microsoft office suite"),
}

_TOKEN_RE = re.compile(r"[a-z0-9+#./]+", re.IGNORECASE)


def _alias_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    for canonical, aliases in SKILL_ALIASES.items():
        lookup[canonical.lower()] = canonical
        for alias in aliases:
            lookup[alias.lower()] = canonical
    return lookup


_LOOKUP = _alias_lookup()

# Holding a more specific cert or product should also satisfy broader job tags.
SKILL_IMPLIES: dict[str, tuple[str, ...]] = {
    "network+": ("comptia",),
    "security+": ("comptia", "security"),
    "salesforce": ("crm",),
    "customer success": ("customer service", "client communication"),
    "consultative selling": ("client communication",),
}


def normalize_skill(raw: str) -> str | None:
    """Map a free-text token to a canonical skill, if known."""
    if not raw:
        return None
    key = re.sub(r"\s+", " ", raw.strip().lower())
    return _LOOKUP.get(key)


def _phrase_in_text(haystack: str, phrase: str) -> bool:
    """Match multi-word phrases loosely; require token boundaries for short words."""
    if not phrase:
        return False
    if any(sep in phrase for sep in (" ", "/", ".")):
        return phrase in haystack
    return (
        re.search(rf"(?<![a-z0-9+#]){re.escape(phrase)}(?![a-z0-9+#])", haystack)
        is not None
    )


def extract_skills(text: str) -> list[str]:
    """Return canonical skills mentioned in unstructured text, preserving order."""
    if not text:
        return []
    lowered = text.lower()
    found: list[str] = []
    seen: set[str] = set()
    phrases = sorted(_LOOKUP.keys(), key=len, reverse=True)
    for phrase in phrases:
        if _phrase_in_text(lowered, phrase):
            canonical = _LOOKUP[phrase]
            if canonical not in seen:
                seen.add(canonical)
                found.append(canonical)
    for skill in list(found):
        for implied in SKILL_IMPLIES.get(skill, ()):
            if implied not in seen:
                seen.add(implied)
                found.append(implied)
    return found


def tokenize(text: str) -> set[str]:
    """Lowercased alphanumeric tokens, dropping very short noise."""
    if not text:
        return set()
    return {m.group(0).lower() for m in _TOKEN_RE.finditer(text) if len(m.group(0)) > 2}


def skill_overlap(
    resume_skills: Iterable[str], job_skills: Iterable[str]
) -> tuple[list[str], list[str]]:
    """Return (matched, missing) canonical skills."""
    have = {s.lower() for s in resume_skills}
    matched: list[str] = []
    missing: list[str] = []
    for skill in job_skills:
        key = skill.lower()
        canonical = _LOOKUP.get(key, skill.lower())
        if canonical in have or key in have:
            if canonical not in matched:
                matched.append(canonical)
        elif canonical not in missing:
            missing.append(canonical)
    return matched, missing
