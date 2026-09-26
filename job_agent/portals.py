"""Run vendored Bun job-portal CLIs (linkedin, freehire, Danish boards)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

PORTALS = {
    "jobbank": "jobbank-search",
    "jobdanmark": "jobdanmark-search",
    "jobindex": "jobindex-search",
    "jobnet": "jobnet-search",
    "linkedin": "linkedin-search",
    "freehire": "freehire-search",
}


def cli_path(portal: str) -> Path:
    folder = PORTALS.get(portal)
    if not folder:
        known = ", ".join(sorted(PORTALS))
        raise ValueError(f"Unknown portal {portal!r}. Use one of: {known}")
    path = REPO_ROOT / ".agents" / "skills" / folder / "cli" / "src" / "cli.ts"
    if not path.is_file():
        raise FileNotFoundError(f"Missing portal CLI at {path}")
    return path


def bun_binary() -> str:
    bun = shutil.which("bun")
    if not bun:
        raise FileNotFoundError(
            "bun is not on PATH. Install https://bun.sh then run scripts/install-job-portal-clis.sh"
        )
    return bun


def run_portal(portal: str, cli_args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Invoke `bun run <cli.ts> ...`. LinkedIn is personal-use only; keep volume low."""
    cmd = [bun_binary(), "run", str(cli_path(portal)), *cli_args]
    return subprocess.run(cmd, check=check, text=True)
