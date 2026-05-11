#!/usr/bin/env python3
"""
setup_github_labels.py
Sets up GitHub repo labels to match the Linear label taxonomy.

Usage:
    export GH_TOKEN=ghp_your_token_here
    python3 scripts/setup_github_labels.py
"""

import os
import json
import urllib.request
import urllib.error
import urllib.parse

REPO = "3nz5789/coinscope-ai"
API_BASE = "https://api.github.com/repos/{}/labels".format(REPO)
TOKEN = os.environ.get("GH_TOKEN", "")

if not TOKEN:
    print("ERROR: Set GH_TOKEN environment variable first.")
    print("  export GH_TOKEN=ghp_your_personal_access_token")
    raise SystemExit(1)

HEADERS = {
    "Authorization": "Bearer {}".format(TOKEN),
    "Content-Type": "application/json",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

LABELS = [
    # Types
    ("type: bug",       "d73a4a", "Something is broken"),
    ("type: feature",   "0075ca", "New capability"),
    ("type: infra",     "e4e669", "Infrastructure / DevOps"),
    ("type: docs",      "cfd3d7", "Documentation"),
    ("type: research",  "bfd4f2", "Investigation / spike"),
    ("type: refactor",  "fef2c0", "Code cleanup, no behaviour change"),
    ("type: test",      "c2e0c6", "Test coverage"),
    ("type: config",    "f9d0c4", "Configuration / env change"),
    # Domains
    ("dom: scanner",      "0e8a16", "Signal scoring / scanner"),
    ("dom: risk",         "b60205", "Risk gate / kill switch / sizing"),
    ("dom: exchange-api", "ff6b35", "Exchange integration (Binance, CCXT)"),
    ("dom: regime",       "6f42c1", "HMM regime classifier"),
    ("dom: alerts",       "0052cc", "Telegram / Notion alerts"),
    ("dom: monitoring",   "e11d48", "Observability / metrics"),
    ("dom: signals",      "1d76db", "Signal model / ML"),
    ("dom: execution",    "5319e7", "Order management / execution"),
    ("dom: ui",           "84b6eb", "Dashboard / frontend"),
    # Priority
    ("P0 - urgent",  "b60205", "Blocking, requires immediate action"),
    ("P1 - high",    "e4e669", "High priority"),
    ("P2 - medium",  "fef2c0", "Medium priority"),
    ("P3 - low",     "cfd3d7", "Low priority, nice to have"),
    # SLOs
    ("SLO: No Data Loss", "b60205", "Data integrity SLO"),
    ("SLO: Code Quality", "1d76db", "Code quality SLO"),
    # Status
    ("status: tech-debt",          "fef2c0", "Accumulated technical debt"),
    ("status: needs-decision",     "f9d0c4", "Blocked on a design decision"),
    ("status: validation-freeze",  "b60205", "Blocked until validation phase ends"),
]

DEFAULT_LABELS = [
    "bug", "documentation", "duplicate", "enhancement",
    "good first issue", "help wanted", "invalid", "question", "wontfix",
]


def api_call(method, url, data=None):
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read()
            return (json.loads(raw) if raw else {}), r.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        return (json.loads(raw) if raw else {}), e.code


print("Setting up labels for {}".format(REPO))
print("")

print("Removing default GitHub labels...")
for name in DEFAULT_LABELS:
    encoded = urllib.parse.quote(name)
    _, status = api_call("DELETE", "{}/{}".format(API_BASE, encoded))
    if status == 204:
        print("  Deleted: {}".format(name))
    else:
        print("  Skipped (not found): {}".format(name))

print("")
print("Creating labels...")
for name, color, description in LABELS:
    data = {"name": name, "color": color, "description": description}
    result, status = api_call("POST", API_BASE, data)
    if status == 201:
        print("  Created: {}".format(name))
    elif status == 422:
        encoded = urllib.parse.quote(name)
        result, status = api_call("PATCH", "{}/{}".format(API_BASE, encoded), {
            "color": color,
            "description": description,
        })
        if status == 200:
            print("  Updated: {}".format(name))
        else:
            print("  ERROR on {}: {}".format(name, result))
    else:
        print("  ERROR on {}: status {}".format(name, status))

print("")
print("Done. Labels configured for {}".format(REPO))
