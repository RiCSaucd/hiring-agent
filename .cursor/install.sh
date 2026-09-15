#!/usr/bin/env bash
# Idempotent bootstrap for the Hiring Agent repo.
#
# The job-seeker "Application Desk" (job_agent) runs on the Python standard
# library plus `requests` and `Jinja2`, which ship in Cursor's base image, so
# the desk works even with no network access.
#
# The optional recruiter pipeline (score.py) needs heavier packages
# (PyMuPDF, ollama, pydantic, pymupdf4llm, google-generativeai, python-dotenv).
# We try to install everything in requirements.txt, but treat a blocked PyPI as
# a soft failure so setup still completes and the desk stays usable.
set -uo pipefail

cd "$(dirname "$0")/.."

echo "== Python =="
python3 --version

echo "== Best-effort dependency install (requirements.txt) =="
if timeout 240 python3 -m pip install --user -r requirements.txt; then
  echo "All requirements installed (recruiter pipeline available)."
else
  echo "WARN: Could not install every dependency (PyPI likely blocked by egress)."
  echo "      The job-seeker desk still runs on the pre-installed stdlib + requests + Jinja2."
  echo "      To enable the optional LLM recruiter pipeline (score.py), allow pypi.org"
  echo "      egress and re-run this install."
fi

echo "== Verify Application Desk dependencies =="
python3 - <<'PY'
import importlib, sys
missing = []
for mod in ("requests", "jinja2"):
    try:
        importlib.import_module(mod)
    except Exception:
        missing.append(mod)
if missing:
    print("ERROR: required desk modules missing:", ", ".join(missing))
    sys.exit(1)
print("Application Desk dependencies present: requests, jinja2")
PY

echo "== Smoke check: import job_agent service =="
python3 -c "from job_agent.service import HiringDesk; print('job_agent import OK')"

echo "Install complete."
