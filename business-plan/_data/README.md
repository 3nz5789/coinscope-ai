# `_data/` — Operational artifacts and supporting documents

This folder holds operational artifacts that the canonical 18-section v1 framework references but does not replace. The framework files (sections 1–16) are the strategic plan; `_data/` contains the working documents that operationalize it.

**Last updated:** 2026-05-01

---

## Folder structure

### `operations/` — operational documents the framework references

- **`Production_Candidate_Criteria_v2.md`** — THE §8 reference document. Defines the 4 gates (G1–G4) and the §8 Capital Cap & Phased Ramp criteria. Resolves leverage cap to 10x. Supersedes v1. Cross-referenced from §5 / §11 / §14 / §16.
- **`Vendor_Failure_Mode_Mapping_v1.md`** — Per-vendor failure scenarios + degraded-mode plans. Feeds §10.3 vendor SLA + failover playbook.
- **`Validation_Data_Analysis_Plan_v1.md`** — Validation-phase analytical methodology. Operational input to §13 KPI feedback loops + §3.7/§3.8 cohort validation.
- **`validation_analysis.py`** — Python analysis script supporting Validation_Data_Analysis_Plan.
- **`Validation_Phase_Exit_Memo_TEMPLATE.md`** — Template for the validation-phase exit decision (referenced by §14.4 P0→P1 gate).
- **`OPS_Linear_Tickets_v1.md`** — Operational Linear-ticket tracking.
- **`mvp-readiness-checklist.md`** — Operational MVP-readiness items.

### `legal/` — legal artifacts and counsel-engagement context

- **`Counsel_Brief_v2.md`** — Phase A counsel engagement brief. Reconciled to canonical Track B framework (tier prices, ICP definition, "Team tier" → Desk Full v2). Supersedes v1 (now in `archive/`).
- **`No_Investment_Advice_Memo_v0_DRAFT.md`** — Pre-counsel-review draft. Will be reviewed against the §4.5 fence + §9.6 objection table.
- **`Risk_Disclosure_v0_DRAFT.md`** — Pre-counsel-review draft. Cross-referenced from §10 incident-response runbook.

### `code-reviews/` — sequential code-review records

- **`CODE_REVIEW_2026-04-24.md`**
- **`CODE_REVIEW_2026-04-26.md`**
- **`CODE_REVIEW_2026-04-30.md`**
- **`CODE_REVIEW_2026-05-01.md`**

Date-stamped series, not duplicates. Each captures engine + dashboard review state at that date.

### `archive/` — superseded versions

Files retained for historical traceability. Each is suffixed `__SUPERSEDED.md`.

- **`Business_Plan_v1__SUPERSEDED.md`** — Earlier monolithic business-plan draft (single document, 14 workstreams). Superseded by the 18-section v1 framework in this repo. See decision-log entry "Track B canonicalization 2026-05-01."
- **`Counsel_Brief_v1__SUPERSEDED.md`** — Superseded by v2 (now in `legal/`).
- **`Production_Candidate_Criteria_v1__SUPERSEDED.md`** — Superseded by v2 (now in `operations/`).

---

## Cross-references from the canonical framework

The 18-section v1 framework references this folder at the following points:

- **§5 / §11 / §14 / §16** reference §8 Capital Cap criteria → `_data/operations/Production_Candidate_Criteria_v2.md`.
- **§10.3** vendor SLA + failover → `_data/operations/Vendor_Failure_Mode_Mapping_v1.md`.
- **§13.6** KPI feedback loops → `_data/operations/Validation_Data_Analysis_Plan_v1.md`.
- **§14.4** P0 → P1 gate → `_data/operations/Validation_Phase_Exit_Memo_TEMPLATE.md`.
- **§12** risk register → `_data/legal/` for legal-side risk inputs and `_data/operations/Vendor_Failure_Mode_Mapping_v1.md` for vendor-side risk inputs.

## Update cadence

- **Operational artifacts** refresh as engineering produces new evidence (e.g., `Validation_Data_Analysis_Plan` updates with observed cohort data; `OPS_Linear_Tickets` is live).
- **Legal artifacts** refresh on counsel engagement; `Counsel_Brief_v2` may produce a v3 once counsel returns Phase A deliverables.
- **Code reviews** are append-only; new dated reviews land in `code-reviews/`.
- **Archive** is append-only; nothing is deleted, only marked `__SUPERSEDED`.
