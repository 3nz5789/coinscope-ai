# Drive vs Git — Architecture Rule

**Status:** Locked 2026-05-04
**Owner:** Mohammed (founder), Scoopy (AI agent)
**Why:** A 6-hour disaster on 2026-05-03/04 wiped 4 unpushed commits when Google Drive Desktop sync raced with `.git/`. Recovery succeeded; the structural lesson is permanent: **git working trees do not belong inside Google Drive Desktop sync paths.**

---

## The rule

Each tool gets one specialty. Do not blur the boundaries.

| Concern | Tool | Local path |
|---|---|---|
| Code, configs, technical markdown, runbooks | **Git + GitHub** | `~/Code/CoinScopeAI/` |
| Collaborative live docs (multi-author, comments) | **Google Docs / Sheets / Slides** in curated Drive tree | not local — stream mode |
| Task / issue tracking | **Linear** | n/a |
| Wiki / cross-linked structured content | **Notion** | n/a |
| Binary assets (PDFs, designs, brand) for sharing | **Drive curated tree** | not local — stream mode |

---

## What goes in git (`~/Code/CoinScopeAI/`)

Engineering source of truth. Versioned, branchable, PR-reviewable.

- `coinscope_trading_engine/` — engine source
- `coinscopeai-dashboard/` — dashboard source
- `business-plan/` — 17-section framework as markdown
- `architecture/`, `legal/`, `research/`, `strategy/` — internal markdown docs
- `docs/runbooks/` — operational runbooks (this file)
- `scripts/` — utility scripts (drift detector, mirror, daily status, guardrails)
- `skills_src/` — Claude skill definitions
- `incidents/` — incident reports
- `archive/code-reviews/`, `archive/doc_update_reports/`, `archive/superseded/` — paper trail
- `.env.example`, `requirements.txt`, `pyproject.toml`, `.github/workflows/` — engineering config

---

## What goes in Drive curated tree (`1-rhyCJaycpf4GAGM45rxNZcH6MeSzkB8`)

Polished, collaborative, shareable. **Native Google formats only.** Do not duplicate repo markdown here.

- **01 — Project Overview:** master prompt as Google Doc, vision/mission Google Doc, link to GitHub repo
- **02 — Architecture & Design:** architecture exported as Google Doc when collaborator-facing; design-system-manifest as Google Doc
- **03 — Roadmap & Planning:** phase map (P0→P5) as Google Doc, validation cohort tracker as Google Sheet
- **05 — Risk Management:** risk register Google Sheet, drawdown / heat tracking Google Sheet
- **13 — Marketing & GTM:** website copy drafts as Google Docs, brand asset PDFs
- **14 — Admin & Entity:** EIN, mailing form, banking docs as PDFs
- **business-plan-v1/:** collaborative review version of the framework as Google Docs (export when needed for non-engineer review)

---

## What goes in Linear

- Engineering tickets (COI- prefix)
- OPS tickets
- Sprint planning, cycles, status

---

## What goes in Notion

- MemPalace memory (Scoopy session memory)
- Cross-linked wiki pages
- Knowledge base for non-engineering topics

---

## Hard rules

1. **No `.git/` inside any Drive Desktop synced path.** Confirmed-bad locations: `~/Documents/`, `~/Desktop/`, `~/Downloads/` — all currently inside Drive sync.
2. **No code under `~/Documents/Claude/Projects/`.** That path is retired. The retired folder there has `xattr com.google.drivefs.ignore` applied. New repos go to `~/Code/`.
3. **No bidirectional sync of repo content to Drive.** When repo markdown needs to be in Drive (collaborator review), export manually to a Google Doc in the curated tree. Never auto-mirror.
4. **No mirror mode for any folder containing a repo.** Drive Desktop stays in stream mode. Mirror is only for non-code shared assets, and even then with caution.
5. **Never delete `.git/` from drive.google.com.** A cloud-side `.git` deletion will propagate to local and wipe the repo. The `com.google.drivefs.ignore` xattr blocks push only, not pull. If you ever see `.git` in cloud Drive: do not touch it from the cloud. Remove local first, the cloud copy follows safely.

---

## Decision matrix — "Where does this go?"

- Is it code, config, or technical reference engineers consume? → **Git**
- Does it need real-time multi-author editing or comments? → **Google Doc** in Drive
- Is it tabular tracking with formulas? → **Google Sheet** in Drive (or Linear if task-shaped)
- Is it a presentation? → **Google Slides** in Drive
- Is it a task / issue with status, owner, deadline? → **Linear**
- Is it cross-linked wiki content? → **Notion**
- Is it a binary asset (PDF, image, design) for sharing? → **Drive curated tree**
- Is it a runbook? → **Git** (`docs/runbooks/`)
- Is it a scratch note? → local terminal or Notion, never Drive sync

---

## Recovery — what to do if Drive sync corrupts a repo again

If you observe any of these symptoms on a repo that should be outside Drive:
- Stale `.git/index.lock` reappearing after `rm`
- `EPERM` errors on `.git/` operations
- `tmp_obj_*` files in `.git/objects/`
- Filenames with ` (1)`, ` (2)`, or `-conflict-` patterns inside `.git/`

Do this immediately:

1. **Pause Drive Desktop.** Menubar icon → gear → Pause syncing. Confirm the icon shows the pause overlay.
2. Do not run any git commands until pause is confirmed.
3. Run `find .git -name "*.lock" -type f` and `find .git -name "* (*)*"` to scope the damage.
4. If the working tree is intact: clone fresh from GitHub to `~/Code/<repo>`, then `rsync -av --exclude=.git <broken-path>/ ~/Code/<repo>/` to copy working tree changes. Replay any unpushed commits manually.
5. If `.git` is too damaged to read: re-clone, accept loss of unpushed commits, replay from working tree content.
6. Document the incident in `incidents/digest-YYYY-MM-DD.md`.
7. Verify the new location is outside any Drive sync path before continuing work.

---

## Reference incident — 2026-05-03/04

A 6-hour debugging session corrupted the local `.git` of `coinscope-ai` after I deleted cloud `.git` from drive.google.com, expecting the `com.google.drivefs.ignore` xattr to prevent local propagation. The xattr only blocks push; cloud-side deletions still propagate. Drive wiped the local `.git` directory entirely. "Restore from cloud Trash" returned a stale April-3 snapshot, not the live one. 4 unpushed commits lost.

Recovery: working tree was intact, so we cloned fresh to `~/Code/CoinScopeAI/`, rsync'd the working tree, replayed the 4 commits with corrected `Scoopy (Claude) <scoopy@coinscope.ai>` author identity (also caught a typo in the previous email which used `coinscopeai.com` — wrong domain), and pushed. All work recovered structurally; SHAs differ but content is identical.

The repo lived inside `~/Documents/Claude/Projects/CoinScopeAI/` which Drive Desktop was mirroring. That path is now retired. New canonical home: `~/Code/CoinScopeAI/`.

See also:
- `incidents/digest-2026-05-03.md`
- Memory: `feedback_drive_git_incompatibility.md`
- Memory: `project_repo_relocation_2026-05-04.md`

---

## Authority

This runbook is **locked** — changes require explicit founder sign-off.

Backups happen via:
- **GitHub** — primary. Commits, branches, tags. Push frequently.
- **Drive curated tree** — Google-native files only. Manual maintenance.
- **macOS Time Machine** — currently NOT configured (verified 2026-05-04). Setting it up is recommended; would have been a 100% recovery path tonight.

Locked 2026-05-04 by Scoopy (Claude) under founder direction.
