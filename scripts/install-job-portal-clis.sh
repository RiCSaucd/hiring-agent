#!/usr/bin/env bash
# Linux/macOS equivalent of the PowerShell bun-install loop in
# MadsLorentzen/ai-job-search SETUP.md.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
if ! command -v bun >/dev/null 2>&1; then
  echo "bun is not on PATH. Install from https://bun.sh then re-run." >&2
  exit 1
fi
tools=(jobbank-search jobdanmark-search jobindex-search jobnet-search linkedin-search freehire-search)
for tool in "${tools[@]}"; do
  cli="$root/.agents/skills/$tool/cli"
  if [[ ! -d "$cli" ]]; then
    echo "missing $cli" >&2
    exit 1
  fi
  echo "bun install $tool"
  (cd "$cli" && bun install)
done
echo "ok"
