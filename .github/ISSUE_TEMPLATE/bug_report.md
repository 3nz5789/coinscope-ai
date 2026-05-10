---
name: Bug Report
about: Something is broken or behaving unexpectedly
title: "[BUG] <short description>"
labels: "type: bug"
assignees: ""
---

## Summary

<!-- One sentence: what is broken? -->

## Environment

| Field | Value |
|---|---|
| Component | <!-- engine / scanner / risk-gate / regime / executor / journal / dashboard / telegram / billing / VPS / local --> |
| Mode | <!-- testnet / local dev --> |
| Commit / version | <!-- git rev-parse --short HEAD --> |
| OS / Python | <!-- e.g. Ubuntu 22.04 / Python 3.11.9 --> |

## Steps to reproduce

1.
2.
3.

## Expected behaviour

## Actual behaviour

## Logs / output

```
# For engine: docker compose logs engine --tail=50
# For risk gate: curl http://localhost:8001/risk-gate | python3 -m json.tool
# For journal: curl http://localhost:8001/journal | python3 -m json.tool
```

## Impact assessment

- [ ] **SLO: No Data Loss** — trade or journal data at risk
- [ ] **Capital at risk** — incorrect sizing, gate bypass, or order error possible
- [ ] **Silent failure** — bug occurs with no error surfaced
- [ ] **Engine unavailable** — health/ready endpoints failing
- [ ] **Cosmetic / low impact** — UI, logging, or non-critical path

## Possible cause

## Related

<!-- Linear issue (COI-NNN), ADR, or PR -->
