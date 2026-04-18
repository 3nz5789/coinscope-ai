---
incident_id: INC-2026-04-18-01
title: Dashboard — Redis State Drift
opened_by: Mohammed
incident_commander: Scoopy (Claude)
detected_at: 2026-04-18 (exact time TBD)
status: Investigating
severity: TBD (triaging — provisional SEV3, pending impact confirmation)
---

## Summary
Dashboard is displaying stale / frozen values that do not appear to reflect current engine state. Engine + Redis are running **local only** (localhost:8001) during the 30-day testnet validation phase (COI-41). DigitalOcean VPS not yet provisioned (COI-40 in progress).

## Provisional Impact
- Dashboard surface: TBD (single page vs multiple vs trading-critical widgets)
- Trading engine itself: no known execution impact yet — this appears to be a **view-layer** symptom, not an execution-integrity symptom
- Validation phase observability: **degraded** — stale dashboard values obscure truth about whether the engine is behaving correctly during the 30-day validation window

## Constraints (IMPORTANT)
- **No core engine changes** during validation phase
- Testnet only — no real orders
- Capital preservation first: if ANY risk-gate / kill-switch / position state is among the drifted values, this escalates to SEV2 immediately

## Timeline
| Time (UTC+3) | Event |
|--------------|-------|
| TBD | Mohammed observed stale values on dashboard |
| 2026-04-18 ~now | Incident opened, triage started |

## Leading Hypotheses (to verify)
1. **Hosted dashboard stuck in mock-data mode** — `coinscopedash-tltanhwx.manus.space` cannot reach `localhost:8001` from the public internet, so it serves static fixture values that LOOK like frozen live data. If MOCK DATA badge is visible, this is almost certainly the explanation and there is no real drift.
2. **Redis writer daemon dead or hung** — 24/7 recording daemon (EventBus) stopped writing keys; dashboard reads last-known values.
3. **Key namespace / DB mismatch** — reader and writer using different Redis logical DBs or different key prefixes after a recent change.
4. **TTL expiry with no re-write** — keys had TTLs, writer stopped, keys partially expired leaving mixed state.
5. **Dashboard frontend HTTP caching** — UI caching engine API responses longer than expected; Redis itself fine.
6. **Two Redis instances** — native redis + docker redis both running, dashboard reading one, engine writing to other.

## Actions Taken
_(none yet — awaiting diagnostic signals from Mohammed)_

## Next Steps
- Confirm whether MOCK DATA badge is visible on dashboard (single most important datum)
- Run local verification commands (see triage task)
- Determine whether this is true drift or an artifact of the hosted-dashboard-can't-reach-localhost topology

## Resolution
TBD

## Postmortem
To be completed after resolution.
