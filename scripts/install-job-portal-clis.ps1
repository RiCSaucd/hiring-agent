# Windows equivalent of SETUP.md bun-install for the vendored portal CLIs.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if (-not (Get-Command bun -ErrorAction SilentlyContinue)) {
  Write-Error "bun is not on PATH. Install from https://bun.sh then re-run."
}
$tools = @("jobbank-search", "jobdanmark-search", "jobindex-search", "jobnet-search", "linkedin-search", "freehire-search")
foreach ($tool in $tools) {
  Set-Location "$root\.agents\skills\$tool\cli"
  bun install
  Set-Location $root
}
Write-Host "ok"
