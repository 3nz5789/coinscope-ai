# /archive — quarantine for historical files

**Status:** current
**Audience:** maintainers
**Related:** `docs/repo-audit.md`

Nothing in this folder is load-bearing. Files here are retained for history or future reference and can be deleted after 2026-07-01 if nobody has needed them by then.

## Contents

| Subfolder | What's in it | Why it's here |
| --- | --- | --- |
| `duplicate_engine_snapshots/` | `coinscope_trading_engine 2/`, `... 3/`, `... 4/`, plus `coinscope_trading_engine.tar.gz`, `coinscope_ai_project.zip` | Finder-duplicated snapshots from 2026-04-05. Canonical engine is `/coinscope_trading_engine/` at repo root. |
| `fixed_patches_2026-04-11/fixed/` | Older patched versions of engine modules from 2026-04-11. | Kept until someone diffs every file against the live engine and confirms the patches landed. Do that diff before deleting. |
| `legacy_scripts/` | `.command` files (macOS double-click scripts), `setup_engine.sh`, `github_setup.sh`. | Machine-specific bootstrapping. Replaced by the documented quick-start in `README.md`. |
| `skill_artifacts/` | Skill review HTML pages, `binance-futures-api.skill`, `market_scanner_skill.zip`. | Scoopy/Manus tooling artifacts. Not used by the engine. |
| `docx_exports/` | `.docx` exports of engine config, trading rules, testnet setup, weekly report template, Manus skills reference, kill-switch decision tree, staging deployment checklist. | Historical Google Drive exports. The markdown equivalents (where they exist) live in `/docs/`. |
| `doc_update_reports/` | `DOC_UPDATE_REPORT_2026-04-10.md` through `...2026-04-18.md`. | Historical pass reports, not an ongoing document. |
| `historical_reports/` | `AUDIT_REPORT.md` (old), `CODE_REVIEW_2026-04-05.md`, `HEALTH_REPORT_2026-04-04.md`, `CoinScopeAI — Week 1 Integration Report.md`, `Scoopy MemPalace Operational Workflow — SOP.md`, `CoinScopeAI Manus Workspace Setup & Workflow Guide.md`, `00_Google_Drive_Folder_Structure.md`, `NOTION_MASTER_PROMPT.md`, `CoinScopeAI Cross-Platform Audit & Sync Report.md`, `CoinScopeAI-Context.md`. | Point-in-time reports and environment-specific guides. The current state of each subject lives in `/docs/`. |
| `unrelated/` | `ps-form-1583-june-2024.pdf`. | Misfiled personal document. Keep for the author, ignore for engineering. |

## How to resurrect something

```bash
git mv archive/<path> <where it should live>
```

Nothing in `/archive` is git-ignored; history is preserved.
