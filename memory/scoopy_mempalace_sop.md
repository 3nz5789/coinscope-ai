# Scoopy MemPalace Operational Workflow — Standard Operating Procedure

**Document Type:** Practical SOP — Operational Reference
**Agent:** Scoopy (CoinScopeAI Project Coordinator)
**Memory System:** MemPalace (ChromaDB-backed, single `mempalace_drawers` collection)
**CLI Entry Point:** `python3 scoopy_cli.py`
**Revision Date:** 2026-04-09

---

## Preface

This document defines the exact, non-negotiable operational procedures by which Scoopy interacts with MemPalace in every session. It is a practical SOP, not a theoretical overview. Every command shown is directly derived from the live `scoopy_cli.py`, `manager.py`, `base_store.py`, and `config.py` source files. Scoopy must treat this document as the authoritative reference for all memory operations.

The MemPalace system uses a **single ChromaDB collection** (`mempalace_drawers`) where every stored item (a "drawer") carries `wing`, `room`, and `hall` metadata. The taxonomy is:

| Wing | Purpose | Retention |
|---|---|---|
| `wing_project` | Confirmed decisions, milestones, lessons | Permanent |
| `wing_user` | User identity, preferences, feedback | Permanent |
| `wing_agents` | Subtask outcomes, agent facts, discoveries | Permanent |
| `wing_assets` | Dashboard URLs, repos, API keys, Stripe config | Permanent |
| `wing_dev` | Architecture decisions, conventions, bug fixes | Permanent |
| `wing_agent` | Cross-agent shared context, task outcomes | 180 days |
| `wing_system` | Engine lifecycle, config changes, deployments | 180 days |
| `wing_models` | ML training runs, param changes, snapshots | 180 days |
| `wing_trading` | Trade signals, entries, exits, analysis | 90 days |
| `wing_risk` | Risk gate checks, drawdowns, kill switch | 90 days |
| `wing_scanner` | Pattern setups, performance, configs | 90 days |

Rooms that are **never pruned regardless of wing retention**: `lessons`, `architecture`, `conventions`, `knowledge`.

---

## Section 1 — Session Start Protocol

Every new session begins with a mandatory memory load sequence. Scoopy must not respond to the user's first message until this sequence is complete. The sequence loads the L0–L3 memory layers and populates Scoopy's working context.

### 1.1 Layer Architecture

MemPalace organises context into four layers:

| Layer | Name | Content | Token Budget |
|---|---|---|---|
| L0 | Identity | `identity.txt` — Scoopy's role, user, project, URLs, pricing | ~50 tokens |
| L1 | Essential Story | Most recent wake-up context from `MemoryStack` | ~120–750 tokens |
| L2 | On-demand Recall | Wing/room-filtered retrieval for specific topics | Variable |
| L3 | Deep Search | Semantic similarity search across all drawers | Variable |

### 1.2 Step-by-Step Session Start Sequence

Execute the following commands in order at the start of every session.

**Step 1 — Full wake-up (L0 + L1 context):**

```bash
python3 scoopy_cli.py wake-up
```

This loads the identity file and the essential story layer. It is the fastest way to restore baseline context (~170–800 tokens).

**Step 2 — Load active project phase and confirmed facts (L2):**

```bash
python3 scoopy_cli.py search "active project phase current status" \
  --wing wing_project --room facts --limit 5
```

**Step 3 — Load recent decisions (L2):**

```bash
python3 scoopy_cli.py search "recent decisions confirmed changes" \
  --wing wing_project --room facts --limit 5
```

**Step 4 — Load open action items and pending tasks (L2):**

```bash
python3 scoopy_cli.py search "open action items pending tasks in progress" \
  --wing wing_agent --room tasks --limit 5
```

**Step 5 — Load user preferences and communication style (L2):**

```bash
python3 scoopy_cli.py search "user preferences timezone communication style" \
  --wing wing_user --room facts --limit 3
```

**Step 6 — Load current asset inventory (L2):**

```bash
python3 scoopy_cli.py search "dashboard URLs deployment endpoints active versions" \
  --wing wing_assets --room facts --limit 5
```

**Step 7 — Check memory system health:**

```bash
python3 scoopy_cli.py status
```

This outputs a JSON status report showing drawer counts per wing and the async writer's pending event queue. If `pending_events` is greater than zero, the previous session may not have flushed cleanly. Note this and proceed.

### 1.3 Session Start Checklist

Before responding to the user's first message, Scoopy must confirm:

- [ ] Wake-up context loaded (L0 + L1)
- [ ] Active project phase identified
- [ ] Most recent 3–5 decisions retrieved
- [ ] Open action items retrieved
- [ ] User preferences confirmed (timezone, communication style)
- [ ] Current dashboard URLs and deployment state confirmed
- [ ] Memory system health checked

---

## Section 2 — During Conversation

Scoopy must treat every user message as a potential memory event. The following rules define when and how to write to MemPalace during an active conversation.

### 2.1 When the User Gives a New Spec or Decision

**Trigger:** The user states a confirmed product or technical decision.

**Destination:** `wing_project` → `room: facts` → `hall: hall_facts`

**Rule:** Store immediately, before responding. Do not wait until the end of the conversation.

```bash
python3 scoopy_cli.py add \
  "DECISION [2026-04-09]: Pricing model confirmed as 4-tier — Starter $19/mo, Pro $49/mo, Elite $99/mo, Team custom. Annual billing = 20% discount." \
  --wing wing_project --room facts --hall hall_facts \
  --category "pricing"
```

```bash
python3 scoopy_cli.py add \
  "DECISION [2026-04-09]: Tech stack confirmed — React + Vite (frontend), FastAPI (engine), ChromaDB (memory), Binance/Bybit/OKX (exchanges)." \
  --wing wing_project --room facts --hall hall_facts \
  --category "tech-stack"
```

**Important:** The `--hall` flag is validated against the `HALL_STRATEGY` map at write time. For `wing_project/facts`, the correct hall is always `hall_facts`. Providing the wrong hall will trigger a warning and be auto-corrected, but it is better practice to specify it correctly.

### 2.2 When the User Gives Feedback or a Preference

**Trigger:** The user expresses a preference about how they want things done, or provides feedback on a delivered task.

**Destination:** `wing_user` → `room: facts` (for durable preferences) or `room: events` (for one-time feedback)

```bash
# Durable preference
python3 scoopy_cli.py add \
  "PREFERENCE: Mohammed (3onooz) prefers Telegram daily reports at 08:00 UTC+3 via @ScoopyAI_bot." \
  --wing wing_user --room facts --hall hall_facts \
  --category "communication"

# One-time feedback
python3 scoopy_cli.py add \
  "FEEDBACK [2026-04-09]: User requested the dashboard sidebar be collapsed by default on mobile." \
  --wing wing_user --room events --hall hall_events \
  --category "ui-feedback"
```

### 2.3 When Creating a Subtask

Before delegating any work to a subtask agent, Scoopy must query MemPalace and build a context brief. This is mandatory. See Section 3 for the full protocol.

### 2.4 When a Subtask Completes

**Trigger:** A subtask agent returns a result.

**Destination:** `wing_agents` → `room: events` → `hall: hall_events`

```bash
python3 scoopy_cli.py add \
  "SUBTASK COMPLETE [2026-04-09]: Agent built Stripe checkout integration. Test mode active with sandbox keys. Webhook endpoint: /api/stripe/webhook. Key decision: used Stripe Elements for UI." \
  --wing wing_agents --room events --hall hall_events \
  --category "stripe"
```

### 2.5 When a Deployment Happens

**Trigger:** A new URL, version, or service goes live.

**Destination:** `wing_assets` → `room: facts` → `hall: hall_facts` (for the current state) AND `room: events` → `hall: hall_events` (for the deployment record)

```bash
# Update current state
python3 scoopy_cli.py add \
  "ASSET [2026-04-09]: Primary dashboard URL — coinscopedash-tltanhwx.manus.space (active). Backup — coinscopedash-cv5ce7m8.manus.space. TradingView prototype — coindash-iad7x9yd.manus.space." \
  --wing wing_assets --room facts --hall hall_facts \
  --category "dashboard-urls"

# Record the deployment event
python3 scoopy_cli.py add \
  "DEPLOYMENT [2026-04-09]: Primary dashboard redeployed to coinscopedash-tltanhwx.manus.space. Version: v1.2.0. VPS: Hetzner CPX32 Singapore." \
  --wing wing_assets --room events --hall hall_events \
  --category "deployment"
```

---

## Section 3 — Subtask Context Injection

This is the most critical section of this SOP. Subtask agents have no persistent memory. If they are not given the right context, they will make incorrect assumptions — leading to incidents like the pricing page error described in Section 6.

### 3.1 Pre-Subtask Query Protocol

Before creating any subtask, run the following queries based on the task type. Collect the outputs and format them into a context brief.

**Universal queries (run for every subtask):**

```bash
# Confirmed project facts
python3 scoopy_cli.py search "pricing tech stack project phase" \
  --wing wing_project --room facts --limit 5

# Current asset inventory
python3 scoopy_cli.py search "dashboard URLs GitHub VPS Stripe" \
  --wing wing_assets --room facts --limit 5

# User preferences relevant to the task
python3 scoopy_cli.py search "user preferences timezone communication" \
  --wing wing_user --room facts --limit 3
```

**For UI / frontend tasks, also run:**

```bash
python3 scoopy_cli.py search "frontend conventions Tailwind component patterns" \
  --wing wing_dev --room conventions --limit 3

python3 scoopy_cli.py search "dashboard architecture design decisions" \
  --wing wing_dev --room architecture --limit 3
```

**For backend / engine tasks, also run:**

```bash
python3 scoopy_cli.py search "API endpoints FastAPI engine config" \
  --wing wing_dev --room facts --limit 3

python3 scoopy_cli.py search "backend architecture decisions" \
  --wing wing_dev --room architecture --limit 3
```

**For trading / risk tasks, also run:**

```bash
python3 scoopy_cli.py search "current market regime risk gate status" \
  --wing wing_system --room regime-changes --limit 3

python3 scoopy_cli.py search "risk parameters kill switch drawdown limits" \
  --wing wing_risk --room gate-checks --limit 3
```

**For pricing / billing tasks, also run:**

```bash
python3 scoopy_cli.py search "pricing model tiers Stripe billing" \
  --wing wing_project --room facts --limit 5
```

### 3.2 Context Brief Format

Compile the query results into the following format and prepend it to the subtask prompt. This brief must be the first thing the subtask agent reads.

```
=== SCOOPY CONTEXT BRIEF ===
Generated: [ISO timestamp]
Task: [Brief description of the subtask]

PROJECT FACTS:
- Phase: 30-day testnet validation
- Pricing: 4-tier (Starter $19/mo, Pro $49/mo, Elite $99/mo, Team custom). Annual = 20% discount.
- Tech Stack: React + Vite (frontend), FastAPI (engine), ChromaDB (memory)
- Exchanges: Binance, Bybit, OKX

ASSETS:
- Primary Dashboard: coinscopedash-tltanhwx.manus.space
- Backup Dashboard: coinscopedash-cv5ce7m8.manus.space
- TradingView Prototype: coindash-iad7x9yd.manus.space
- GitHub: 3nz5789/coinscope-ai
- VPS: Hetzner CPX32 Singapore (~$20/mo)
- Stripe: Test mode, sandbox keys active
- Telegram Bot: @ScoopyAI_bot, Chat ID: 7296767446

USER:
- Name: Mohammed (3onooz)
- Location: Amman, Jordan (UTC+3)
- Daily Report: Telegram at 08:00 UTC+3

RELEVANT DECISIONS:
- [Retrieved from wing_project/facts — paste top results here]

RELEVANT CONVENTIONS:
- [Retrieved from wing_dev/conventions — paste top results here]
=== END CONTEXT BRIEF ===
```

### 3.3 Context Brief Shell Script

For convenience, the following script generates a context brief automatically:

```bash
#!/bin/bash
# generate_context_brief.sh — Run before any subtask
echo "=== SCOOPY CONTEXT BRIEF ==="
echo "Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""
echo "--- PROJECT FACTS ---"
python3 scoopy_cli.py search "pricing tech stack project phase" \
  --wing wing_project --room facts --limit 5
echo ""
echo "--- ASSETS ---"
python3 scoopy_cli.py search "dashboard URLs GitHub VPS Stripe" \
  --wing wing_assets --room facts --limit 5
echo ""
echo "--- USER PREFERENCES ---"
python3 scoopy_cli.py search "user preferences timezone" \
  --wing wing_user --room facts --limit 3
echo ""
echo "=== END CONTEXT BRIEF ==="
```

---

## Section 4 — Post-Task Storage

After every completed task, Scoopy must file a structured storage entry. This creates an institutional record that future sessions and subtask agents can retrieve.

### 4.1 Storage Entry Template

Every post-task entry must follow this structure:

```
TASK COMPLETE [YYYY-MM-DD]
Task: [One-sentence description]
Built: [What was created or modified]
Deployed: [URL, version, or "N/A"]
Key Decisions: [Comma-separated list of important choices made]
Issues Encountered: [Any bugs, blockers, or gotchas — or "None"]
Next Steps: [What remains to be done — or "None"]
```

### 4.2 Storage Commands by Task Type

**Feature built and deployed:**

```bash
python3 scoopy_cli.py add \
  "TASK COMPLETE [2026-04-09] Task: Build pricing page. Built: React pricing component with 4-tier cards. Deployed: coinscopedash-tltanhwx.manus.space/pricing. Key Decisions: Used Tailwind grid, Stripe Checkout links per tier. Issues Encountered: None. Next Steps: Connect to Stripe webhook for subscription activation." \
  --wing wing_agents --room events --hall hall_events \
  --category "feature-pricing"
```

**Architecture decision made:**

```bash
python3 scoopy_cli.py add \
  "ADR [2026-04-09]: Chose ChromaDB over Pinecone for vector storage. Reasoning: self-hosted on Hetzner VPS, no per-query cost, integrates natively with MemPalace." \
  --wing wing_dev --room architecture --hall hall_decisions \
  --category "database"
```

**Bug fixed:**

```bash
python3 scoopy_cli.py add \
  "BUG FIX [2026-04-09]: Stripe webhook signature verification was failing due to raw body not being preserved. Fix: Added express.raw() middleware before the webhook route." \
  --wing wing_dev --room bug-fixes --hall hall_advice \
  --category "stripe-webhook"
```

**Deployment completed:**

```bash
python3 scoopy_cli.py add \
  "DEPLOYMENT [2026-04-09]: Deployed v1.3.0 to coinscopedash-tltanhwx.manus.space. Changes: Pricing page, Stripe integration. VPS: Hetzner CPX32 Singapore. Build time: 4m 12s." \
  --wing wing_assets --room events --hall hall_events \
  --category "deployment-v1.3.0"
```

---

## Section 5 — Memory Maintenance

### 5.1 Weekly Maintenance (Every Monday)

**Step 1 — Preview prunable drawers (dry run):**

```bash
python3 -c "
from memory.manager import MemoryManager
mm = MemoryManager()
result = mm.prune(dry_run=True)
import json; print(json.dumps(result, indent=2))
mm.shutdown()
"
```

**Step 2 — Review the output.** Confirm that the `pruned_by_wing` breakdown looks reasonable. Verify that permanent wings (`wing_project`, `wing_user`, `wing_assets`, `wing_dev`, `wing_agents`) show zero prunable drawers.

**Step 3 — Execute the prune (only after reviewing dry run):**

```bash
python3 -c "
from memory.manager import MemoryManager
mm = MemoryManager()
result = mm.prune(dry_run=False)
import json; print(json.dumps(result, indent=2))
mm.shutdown()
"
```

**Step 4 — Store the maintenance record:**

```bash
python3 scoopy_cli.py add \
  "MAINTENANCE [$(date +%Y-%m-%d)]: Weekly prune completed. Deleted [N] drawers from wing_trading, wing_risk, wing_scanner. Permanent wings untouched." \
  --wing wing_project --room events --hall hall_events \
  --category "maintenance"
```

### 5.2 Monthly Maintenance (First Day of Month)

**Step 1 — Generate a taxonomy overview:**

```bash
python3 -c "
from memory.manager import MemoryManager
mm = MemoryManager()
import json; print(json.dumps(mm.taxonomy(), indent=2))
mm.shutdown()
"
```

**Step 2 — Query all major decisions from the past month:**

```bash
python3 scoopy_cli.py search "decisions made this month" \
  --wing wing_project --room facts --limit 20
```

**Step 3 — Store a monthly summary in the permanent lessons room:**

```bash
python3 scoopy_cli.py add \
  "MONTHLY SUMMARY [$(date +%Y-%m)]: [Paste summary of decisions, deployments, and outcomes here]" \
  --wing wing_agent --room lessons --hall hall_advice \
  --category "monthly-summary"
```

### 5.3 Retention Rules Reference

| Wing | Retention | Exempt Rooms |
|---|---|---|
| `wing_project` | Permanent | All rooms |
| `wing_user` | Permanent | All rooms |
| `wing_agents` | Permanent | All rooms |
| `wing_assets` | Permanent | All rooms |
| `wing_dev` | Permanent | All rooms |
| `wing_agent` | 180 days | `lessons`, `knowledge` |
| `wing_system` | 180 days | — |
| `wing_models` | 180 days | — |
| `wing_trading` | 90 days | — |
| `wing_risk` | 90 days | — |
| `wing_scanner` | 90 days | — |

---

## Section 6 — Error Prevention

### 6.1 The Pricing Page Incident — Root Cause and Prevention

**What happened:** A subtask agent was asked to build the pricing page. It had no context brief. It assumed a 3-tier pricing model (a common SaaS pattern) and built the page with incorrect tiers and prices. The error was not caught until Mohammed reviewed the output.

**Root cause:** No context brief was injected. The agent had no access to the confirmed pricing decision stored in `wing_project/facts`.

**How MemPalace prevents this:** If the pre-subtask query protocol from Section 3.1 had been followed, the following command would have returned the correct pricing:

```bash
python3 scoopy_cli.py search "pricing model tiers" \
  --wing wing_project --room facts --limit 3
```

Expected output:
```
DECISION [2026-04-09]: Pricing model confirmed as 4-tier — Starter $19/mo,
Pro $49/mo, Elite $99/mo, Team custom. Annual billing = 20% discount.
```

This fact, injected into the context brief, would have given the agent the exact pricing structure and prevented the error entirely.

### 6.2 Pre-Deployment Verification Checklist

Before deploying anything that references stored specifications, Scoopy must run the following checks:

| Check | Command | Expected Result |
|---|---|---|
| Pricing tiers correct | `search "pricing model tiers" --wing wing_project --room facts` | 4-tier: Starter $19, Pro $49, Elite $99, Team custom |
| Dashboard URL correct | `search "primary dashboard URL" --wing wing_assets --room facts` | `coinscopedash-tltanhwx.manus.space` |
| Tech stack correct | `search "tech stack frontend backend" --wing wing_project --room facts` | React+Vite, FastAPI, ChromaDB |
| Stripe mode correct | `search "Stripe mode keys" --wing wing_assets --room facts` | Test mode, sandbox keys |
| User timezone correct | `search "user timezone" --wing wing_user --room facts` | UTC+3 (Amman) |

If any check returns a result that contradicts the proposed deployment, **halt the deployment** and resolve the discrepancy before proceeding.

### 6.3 The Idempotency Guarantee

The `file_drawer` method in `base_store.py` generates a deterministic `drawer_id` based on a content hash (`wing + room + content_hash`). This means filing the same content twice is a safe no-op — the second write will upsert the same drawer. Scoopy can therefore re-file facts after every session start without creating duplicates.

### 6.4 Async Write Safety

All `add` commands are non-blocking. The write is enqueued to a background writer thread and returns immediately. If Scoopy needs to guarantee a write has been persisted before reading it back (e.g., before a search), it must call `flush()` explicitly:

```bash
python3 -c "
from memory.manager import MemoryManager
mm = MemoryManager()
mm.flush()
mm.shutdown()
"
```

---

## Section 7 — Soul Update Snippet

Add the following block to Scoopy's `soul.md` file. It must be placed in a prominent section, ideally immediately after the identity declaration.

```markdown
## MemPalace Memory Discipline — Non-Negotiable Habits

I am Scoopy. I do not operate from assumptions. I operate from memory.

### Session Start (Mandatory — Before First Response)
Every session begins with a memory load sequence. I run `wake-up` first,
then query `wing_project/facts`, `wing_agent/tasks`, `wing_user/facts`,
and `wing_assets/facts` to establish full context. I do not respond to
the user's first message until this sequence is complete.

### Active Listening (Real-Time Storage)
When Mohammed gives me a decision, I store it in `wing_project/facts`
immediately — before I respond. When he gives me a preference, I store
it in `wing_user/facts`. I never let a confirmed fact exist only in the
conversation window.

### Subtask Context Injection (Mandatory — Before Every Delegation)
I never create a subtask without a context brief. Before delegating any
work, I query the relevant wings, compile the results into a structured
brief, and prepend it to the subtask prompt. Subtask agents have no
memory. I am their memory.

### Post-Task Documentation (Mandatory — After Every Completed Task)
After every task, I file a structured record: what was built, where it
is deployed, what decisions were made, and what issues were encountered.
I store this in `wing_agents/events` and, for architectural decisions,
in `wing_dev/architecture`.

### Pre-Deployment Verification (Mandatory — Before Every Deploy)
Before any deployment, I query MemPalace to verify that the pricing
model, dashboard URLs, tech stack, and Stripe mode are correct. If any
stored fact contradicts the proposed deployment, I halt and resolve the
discrepancy. The pricing page incident will not happen again.

### Memory Maintenance
Every Monday I run a dry-run prune and review the output. On the first
day of each month I generate a taxonomy overview and store a monthly
summary in `wing_agent/lessons`.

### The Core Principle
A fact that is not in MemPalace does not exist for future sessions or
subtask agents. My job is to ensure that every important fact, decision,
and outcome is stored, retrievable, and injected where it is needed.
```

---

## Quick Reference Card

| Situation | Command |
|---|---|
| Session start (full context) | `python3 scoopy_cli.py wake-up` |
| Load project facts | `python3 scoopy_cli.py search "..." --wing wing_project --room facts --limit 5` |
| Load open tasks | `python3 scoopy_cli.py search "..." --wing wing_agent --room tasks --limit 5` |
| Load user preferences | `python3 scoopy_cli.py search "..." --wing wing_user --room facts --limit 3` |
| Load asset URLs | `python3 scoopy_cli.py search "..." --wing wing_assets --room facts --limit 5` |
| Store a decision | `python3 scoopy_cli.py add "DECISION [date]: ..." --wing wing_project --room facts --hall hall_facts` |
| Store a preference | `python3 scoopy_cli.py add "PREFERENCE: ..." --wing wing_user --room facts --hall hall_facts` |
| Store a subtask outcome | `python3 scoopy_cli.py add "SUBTASK COMPLETE [date]: ..." --wing wing_agents --room events --hall hall_events` |
| Store a deployment | `python3 scoopy_cli.py add "DEPLOYMENT [date]: ..." --wing wing_assets --room events --hall hall_events` |
| Store an architecture decision | `python3 scoopy_cli.py add "ADR [date]: ..." --wing wing_dev --room architecture --hall hall_decisions` |
| Store a bug fix | `python3 scoopy_cli.py add "BUG FIX [date]: ..." --wing wing_dev --room bug-fixes --hall hall_advice` |
| Check memory health | `python3 scoopy_cli.py status` |
| Weekly prune (dry run) | `python3 -c "from memory.manager import MemoryManager; mm = MemoryManager(); print(mm.prune(dry_run=True)); mm.shutdown()"` |
| Weekly prune (execute) | `python3 -c "from memory.manager import MemoryManager; mm = MemoryManager(); print(mm.prune(dry_run=False)); mm.shutdown()"` |
| Force flush pending writes | `python3 -c "from memory.manager import MemoryManager; mm = MemoryManager(); mm.flush(); mm.shutdown()"` |

---

*End of SOP — Scoopy MemPalace Operational Workflow*
