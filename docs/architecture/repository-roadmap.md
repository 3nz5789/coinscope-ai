# Repository Roadmap

This doc captures the **delta** between the present-state repository structure described in [`../../README.md#repository-structure`](../../README.md#repository-structure) and the intended end-state. The README is present state only; this is the only place where "planned" lives.

## Why this split exists

A repository-structure section that mixes present and aspirational forces every reader to decode which is which. After enough drift, the aspirational becomes wishful thinking that nobody can verify. Splitting them lets the [`invariant_matrix_check.py`](../../scripts/invariant_matrix_check.py) CI job catch broken citations in the present-state structure, while leaving room here to document direction without polluting the front-door doc.

If you find yourself wanting to write "planned" in `README.md`, write it here instead.

## Planned migrations

### `services/trading-engine/` — consolidate

The directory exists but its responsibilities overlap with `engine/` (live execution side) and `services/paper_trading/` (paper side). Plan: fold into both rather than maintain a third location. Timeline not locked; tracked alongside the post-P0 restructure. Until then it is intentionally omitted from the README's structure block.

### Dashboard at `apps/dashboard/`

Older docs and runbooks reference `coinscopeai-dashboard/` at the repo root. The canonical present-state location is [`apps/dashboard/`](../../apps/dashboard/). External references should update incrementally; no symlink or alias is planned.

## Naming clarifications (not migrations)

External docs sometimes cite these `risk_management/` filenames. The present-state files are listed on the right. **No rename is planned** — update external citations rather than the source.

| External citation | Present-state file |
|---|---|
| `risk_management/kelly_sizer.py` | `risk_management/kelly_position_sizer.py` |
| `risk_management/circuit_breakers.py` | `services/paper_trading/safety.py` |
| `risk_management/kill_switch.py` | `services/paper_trading/safety.py` + `services/paper_trading/kill.py` |

## Cited-but-not-yet-present paths

Some past `README.md` callouts and matrix rows reference files that have not yet landed on `main`. Each is tracked here until it does. The [`invariant-matrix`](../validation/invariant-matrix.md) flags any that are load-bearing for an invariant.

| Cited path | Where it should land | Tracking |
|---|---|---|
| `docs/decisions/adr-0001-fastapi-and-uvicorn.md` | `docs/decisions/` | open |
| `docs/decisions/adr-0002-redis-celery-for-workers.md` | `docs/decisions/` | open |
| `docs/decisions/adr-0003-llm-off-hot-path.md` | `docs/decisions/` | invariant-matrix I13 (🟡) |
| `CLAUDE.md` | repo root | open |
| `scripts/drift_detector.py` | `scripts/` | open — partial coverage in `scripts/risk_threshold_guardrail.py` |
| `tests/test_risk_gate.py` | `tests/` | open — coverage in `tests/unit/paper_trading/test_safety.py` |
| `docs/ml/regime-detection.md` | `docs/ml/` | open |
| `docs/architecture/architecture.md` | `docs/architecture/` | open — present dir holds `confidence-scoring.md` + `design-system-manifest.md` |
| `docs/runbooks/daily-ops.md` | `docs/runbooks/` | open |
| `docs/runbooks/local-development.md` | `docs/runbooks/` | open |
| `docs/runbooks/digitalocean-deployment.md` | `docs/runbooks/` | open |
| `docs/runbooks/troubleshooting.md` | `docs/runbooks/` | open |
| `docs/runbooks/release-checklist.md` | `docs/runbooks/` | open |
| `configs/logging.yaml` | `configs/` | open — structured-log config is currently inline |
| Root-level `docker-compose.yml` | repo root | open — present compose files live under `infra/docker/` |

## Closure protocol

When a tracked gap closes:

1. Remove the row from this doc.
2. If the new path belongs in the README structure block, add it there in the same PR.
3. If it is cited by [`../validation/invariant-matrix.md`](../validation/invariant-matrix.md), flip the matrix row colour and update the Notes column. The `invariant-matrix` CI job will fail until the citation resolves — that is the intended behaviour.
4. Add a CHANGELOG entry under `## Unreleased` if it is user-visible.

The README structure block, this roadmap, and the matrix are the three faces of the same architectural truth. They drift independently in practice; this protocol is what keeps them in sync.
