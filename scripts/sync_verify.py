#!/usr/bin/env python3
"""
sync_verify.py — CoinScopeAI Cross-Platform Sync Verifier
Run: python3 scripts/sync_verify.py
"""

import os, subprocess, sys, urllib.request, json

G="\033[92m"; R="\033[91m"; E="\033[0m"; B="\033[1m"
results = []

def check(name, passed, detail=""):
    results.append((name, passed, detail))
    print(f"  {G+'✅'+E if passed else R+'❌'+E}  {name}" + (f" — {detail}" if detail else ""))

def section(title):
    print(f"\n{B}{'─'*50}{E}\n{B}  {title}{E}\n{B}{'─'*50}{E}")

section("Mac / Cowork")
BASE = "/Users/mac/Documents/Claude/Projects/CoinScopeAI"
for d in ["01-project-overview","03-roadmap","08-sessions","09-research","11-legal","14-admin","99-archive","docs","scripts","skills","coinscope_trading_engine","coinscopeai-dashboard"]:
    check(f"dir: {d}/", os.path.isdir(os.path.join(BASE, d)))
for f in ["CLAUDE.md","CONTEXT_PRIMER.md","README.md","CONTRIBUTING.md","SECURITY.md","canonical-structure-spec.md",".env.example"]:
    check(f"file: {f}", os.path.isfile(os.path.join(BASE, f)))
for item in ["Business_Plan_v1.md","Counsel_Brief_v2.md","billing_server.py","validation_analysis.py","admin","architecture","legal","incidents","ml","research","strategy","skills_src"]:
    p = os.path.join(BASE, item); exists = os.path.exists(p)
    check(f"root clean: no {item}", not exists, "still exists — move to canonical folder" if exists else "")

section("GitHub")
REPO = os.path.expanduser("~/Projects/coinscope-ai")
if os.path.isdir(REPO):
    r = subprocess.run(["git","remote","get-url","origin"], capture_output=True, text=True, cwd=REPO)
    remote = r.stdout.strip()
    check("remote URL → CoinScopeAI", "CoinScopeAI" in remote, remote)
    r = subprocess.run(["git","status","--porcelain"], capture_output=True, text=True, cwd=REPO)
    uncommitted = r.stdout.strip()
    check("no uncommitted changes", not uncommitted, f"{len(uncommitted.splitlines())} files" if uncommitted else "")
else:
    check("repo dir exists", False, f"{REPO} not found")

section("Environment")
env = os.path.join(BASE, ".env.example")
if os.path.isfile(env):
    c = open(env).read()
    check("MAX_OPEN_POSITIONS=5", "MAX_OPEN_POSITIONS=5" in c, "shows =3" if "MAX_OPEN_POSITIONS=3" in c else "not found")
    check("MAX_LEVERAGE=10", "MAX_LEVERAGE=10" in c, "shows =20" if "MAX_LEVERAGE=20" in c else "not found")
    check("no old repo name", "coinscope-ai" not in c)
else:
    check(".env.example exists", False)

section("Engine API (local)")
try:
    data = json.loads(urllib.request.urlopen("http://localhost:8001/config", timeout=3).read())
    check("engine reachable", True)
    check("max_open_positions = 5", data.get("max_open_positions") == 5, f"got: {data.get('max_open_positions')}")
    check("max_leverage = 10", data.get("max_leverage") == 10, f"got: {data.get('max_leverage')}")
except:
    check("engine reachable", False, "not running — VPS restart pending (COI-68)")

print(f"\n{B}{'═'*50}{E}")
passed = sum(1 for _,p,_ in results if p); failed = len(results)-passed
print(f"{B}  {G if not failed else R}Result: {passed}/{len(results)} checks passed{E}")
if failed:
    print(f"\n  {R}Failed:{E}")
    [print(f"    ❌ {n}" + (f" — {d}" if d else "")) for n,p,d in results if not p]
print(f"{B}{'═'*50}{E}\n")
sys.exit(0 if not failed else 1)
