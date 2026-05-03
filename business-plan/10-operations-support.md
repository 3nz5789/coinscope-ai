# §10 Operations and Support Model

**Status:** v1 LOCKED. Single-pass draft synthesizing §5.2, §11.3, §13.4, §14, §16.2 with shape decisions on support SLAs, on-call model, and tooling stack.
**Last updated:** 2026-05-01
**Disclaimer:** Validation phase active. Operations posture sized for solo founder + P4 contractor support per §5.4.7. SLAs reflect what we can defensibly meet, not aspirational targets.

---

## 10.0 Assumptions and inheritance

### Locked from upstream

- **§5.2 tier matrix** — Free / Trader / Desk Preview / Desk Full v2.
- **§5.4 phase map** — solo execution P0–P3; +2 contractors at P4 per §5.4.7.
- **§5.3.1 packaging principle** — capital-preservation primitives never gated; kill switch operates regardless of tier.
- **§11.3 vendor stack** — CCXT, CoinGlass, Tradefeeds, CoinGecko, Claude minimal; ~$945/mo mid-point.
- **§13.4 risk KPIs** — vendor uptime, gate-rejection acceptance, drawdown, kill-switch activation, override attempts.
- **§14 stop-the-line** — 6 conditions + 1 §13 conditional.
- **§16.2 contingency protocols** — regulatory shock, vendor outage, founder-unavailable.
- **Project memory: Linear + Notion + GitHub** locked as core tooling per `coinscopeai-platform-sync`.
- **Email transactional only** per §6.8 — Stripe processing.

### What §10 decides (new)

- Support tier matrix with explicit SLAs.
- Engine incident-response runbook structure.
- Vendor SLA + failover playbook per P1 vendor.
- Solo-founder on-call model.
- Tooling stack additions (support, status, monitoring).

---

## 10.1 Support tier matrix and SLAs

### Channels per tier

| Tier | Primary channels | Response SLA target | Hours of support |
|---|---|---|---|
| **Free** | Email only; community FAQ | **48–72h response (best effort)** | Business hours UAE (Sun–Thu) |
| **Trader** | Email + Telegram-companion bot product issues | **24h response (weekdays); 48h weekends** | Business hours UAE; weekend coverage best-effort |
| **Desk Preview** | Email + Telegram + dedicated email thread | **12h response (weekdays); 24h weekends** | Business hours UAE + named-contact escalation path |
| **Desk Full v2** | Email + Telegram + dedicated Slack Connect channel | **4–6h response weekdays; 12h weekends** | Extended hours; PM-level founder contact |

### What "response" means

"Response" = first acknowledgment from CoinScopeAI (founder or designated support). It does *not* mean resolution — resolution time depends on issue severity and is tracked separately.

### Severity classification

| Severity | Definition | Response target | Escalation |
|---|---|---|---|
| **Sev-1** | Engine bug; gate failure; kill-switch malfunction; data loss | **1h response across all tiers** | Founder direct; §14 stop-the-line evaluation |
| **Sev-2** | Vendor outage affecting trading; billing dispute; account access loss | Tier SLA × 0.5 | Founder direct |
| **Sev-3** | Feature question; documentation gap; minor product issue | Tier SLA standard | Standard support |
| **Sev-4** | General inquiry; pricing question; partnership | Tier SLA × 1.5 | Standard support |

Sev-1 overrides tier SLAs — anyone can hit Sev-1 and get 1h response regardless of paid status. Capital-preservation primitives extend to support response.

### SLA defensibility

These SLAs are **achievable for a solo founder + P4 contractor support**. They are *not* enterprise-grade SLAs. §15 due-diligence Q&A should frame this as:

- We do not promise enterprise SLAs we can't meet.
- Solo-founder posture is honest constraint; P4 contractor scenario adds engineering capacity at the highest-load phase.
- Sev-1 priority across all tiers is non-negotiable; capital-preservation primitives apply.

---

## 10.2 Engine incident-response runbook

### Trigger conditions

Any of the following triggers immediate Sev-1 protocol:

- Gate evaluation failing (false-pass or false-fail beyond threshold).
- Position-sizer producing values outside expected math.
- Kill-switch failing to activate when daily-loss / drawdown threshold hit.
- Engine API endpoint unavailable >15 minutes.
- Cohort-level drawdown spike beyond §8 thresholds.

### Phase 1 — Detection (0–15 minutes)

- Automated monitoring alerts founder via Telegram bot.
- Founder confirms incident is real (not a monitoring false-positive).
- Founder triggers manual kill-switch override if engine kill-switch isn't activating automatically.

### Phase 2 — Containment (15–60 minutes)

- Engine put in read-only mode; new signals blocked from arming.
- Active positions: kill-switch enforced; users notified via Telegram-companion bot.
- Dashboard banner posted: "Engine paused for incident review. Existing positions managed under kill-switch rules. Updates within 1 hour."

### Phase 3 — Diagnosis (1–4 hours)

- Founder reviews engine logs, audit trail, vendor data feeds.
- If diagnosis identifies contained bug: prepare fix; estimate resolution time.
- If diagnosis identifies vendor cause: invoke §10.3 vendor failover.
- If diagnosis is unclear after 4 hours: escalate to §14 stop-the-line — public launch holds; founder cohort notified per §16 contingency comms.

### Phase 4 — Resolution and communication

- Fix deployed and validated against test cases.
- Engine returns to active state; users notified.
- Post-mortem written within 72 hours; published to founder cohort first, then public Substack if material (>5 day outage or trust-relevant).

### Recovery and prevention

- Every Sev-1 produces an audit log entry.
- If incident exposes systemic risk: §13 risk KPI red-line updated; §14 stop-the-line conditions reviewed for additions.
- Engine documentation updated to reflect new failure modes.

### Connection to §16 contingency protocols

- Engine bug → Contingency B (vendor) or internal-only depending on cause.
- Engine kill-switch malfunction → §14 condition 5 fires.
- Cohort-wide drawdown breach → §14 condition 1 fires.

---

## 10.3 Vendor SLA + failover playbook (P1 stack)

| Vendor | Their published SLA | Our monitoring | Failover plan | Escalation contact |
|---|---|---|---|---|
| **CCXT** (4 exchanges) | Open-source library; per-exchange API SLA varies (99.5–99.9%) | Per-exchange status page + custom uptime check | If 1 exchange down: route via remaining 3. If multi-exchange: surface to user, kill-switch active positions via remaining venues | Per-exchange support; CCXT GitHub if library issue |
| **CoinGlass** | Public SLA ~99.9%; data-feed Pro tier | Per-endpoint status check every 5 min | If outage: mark regime classifier as degraded; reduce confidence scores in user-facing display; cap leverage thresholds | CoinGlass support email |
| **Tradefeeds** | Sentiment data; published SLA varies | Per-endpoint status check | If outage: sentiment input dropped from regime classifier; classifier still operates with reduced inputs | Tradefeeds support email |
| **CoinGecko** | Public SLA ~99.9%; Pro API tier | Standard | If outage: token metadata cached for ~24h; new symbol additions paused | CoinGecko support email |
| **Claude** (minimal) | Anthropic API; published SLA in API agreement | Standard | If outage: narrative-generation features degraded; engine trade-decision loop unaffected (Claude is bounded use, not in trade loop) | Anthropic support |

### Failover decision tree

Per any vendor outage:

1. **<24h outage:** Internal failover deployed; users notified via dashboard banner; affected functionality flagged. No public communication unless trust-relevant.
2. **>24h outage with no failover:** §14 stop-the-line condition 2 fires; pro-rata refund evaluated; vendor swap considered.
3. **Repeated outages (>3 in 30 days):** vendor relationship reviewed; replacement integrated if structural.

### CoinGlass dual-customer-vendor relationship (per §12)

CoinGlass is on the P1 vendor stack AND sells CoinGlass Hyper directly to our user base. §12 risk register tracks:

- API pricing changes that compress margin (>$200/mo deviation triggers §11 cost-side refresh).
- Product-feature expansion into our space (regime classifier or gate-equivalent functionality).
- Partnership opportunity if relationship reframes (their user base overlaps our ICP).

§10 acknowledges this; §12 owns the active monitoring.

---

## 10.4 On-call model (solo founder + P4 contractor support)

### Validation phase (P0, May 2026)

- Founder is sole on-call.
- Engine alerts route to Telegram bot.
- Hours: business hours UAE (Sun–Thu, 9 AM – 6 PM Gulf Standard Time) + on-call evenings/weekends.
- Sev-1 response within 1h regardless of hours.

### Soft launch (P1, June–July 2026)

- Same as P0; cohort of 40 paid users adds support volume but founder solo.
- Emergency contact protocol per §16.2 Contingency C activated.

### Public launch + stabilization (P2–P3, Aug 2026 – Dec 2026)

- Founder solo. Volume scales with cohort growth.
- Support hours extended on-demand; weekend coverage best-effort.
- If support volume exceeds founder capacity (>20 hrs/wk on tickets): support contractor evaluated outside the §5.4.7 engineering-contractor scenario.

### v2 prep + launch (P4–P5, Jan–May 2027)

- Engineering contractors (per §5.4.7) cover engineering on-call for the items they're building (multi-account dashboard, audit-grade exports).
- Founder retains overall on-call ownership and Sev-1 response.

### Post-validation: support tooling

If support load exceeds founder capacity at any phase, evaluate:

- Part-time support contractor (~$1.5–3k/mo, lower-cost region).
- Documentation-led self-service expansion (FAQ, methodology docs per §5.3.4).
- Tier-specific delegation (Free tier → community + docs; paid tiers → founder).

### Outside business hours

- Telegram-companion bot delivers automated alerts.
- Engine kill-switch and risk-gate operate autonomously per locked rules.
- Sev-1 alerts page founder via Telegram + SMS backup.
- Sev-2/3/4 wait until next business day.

---

## 10.5 Tooling stack

### Locked from project memory (no §10 decision)

- **Linear** — project + issue management.
- **Notion** — documentation, runbooks, internal knowledge base.
- **GitHub** — code repository, version control.
- **Stripe** — billing, subscription management (per §6.8).

### §10 additions (new locks)

- **Help Scout** (or equivalent: Front, Intercom-light) — support ticketing inbox. ~$25–50/mo. Light setup; integrates with email + Stripe customer data.
- **BetterStack** (or self-hosted alternative: Statping, Cabin) — uptime + status page for engine API + dashboard. ~$30–50/mo.
- **Per-vendor status monitoring** — CCXT exchanges, CoinGlass, Tradefeeds, CoinGecko, Claude — pulled into a custom dashboard. v1 lightweight; v2 if needed.
- **PagerDuty-light** — for now, simple Telegram alerts via existing bot; PagerDuty proper deferred to post-v2 if support load justifies.

### Total v1 ops tooling cost

- Help Scout: ~$40/mo
- BetterStack: ~$40/mo
- Total: **~$80/mo** (within §11.3 "Other operational" budget; no model refresh needed)

### Notion structure for ops runbooks

- `/Ops/Incident-Runbooks/` — engine incident response (this section's protocol)
- `/Ops/Vendor-Failover/` — per-vendor failover details
- `/Ops/Support-Templates/` — per-tier response templates, refund policy reference, escalation paths
- `/Ops/Stop-the-Line/` — §14 condition response protocols
- `/Ops/Contingency/` — §16.2 protocols (regulatory, vendor, founder-unavailable)

---

## 10.6 Anti-overclaim audit on §10

Audit performed against §10.0 through §10.5 on 2026-05-01. Five flags considered.

### Flags applied

**Flag 1 — SLAs are defensible, not aspirational.**

Trader 24h, Desk Preview 12h, Desk Full v2 4–6h. These are *achievable for solo founder + P4 contractor*. We don't promise enterprise-grade 99.99% SLAs.

*Mitigation:* Public SLA copy uses "target" and "best-effort" language, never "guaranteed." Sev-1 priority is the only firm commitment ("1h response across all tiers"); even Sev-1 is "response" not "resolution."

**Flag 2 — Solo founder posture honestly framed.**

§16.2 Contingency C is real risk. §10.4 on-call model surfaces this in the V2-prep contractor scenario.

*Mitigation:* §15 deck Slide 9 + §1 exec summary already disclose. §10 inherits.

**Flag 3 — Vendor SLAs reflect vendor commitments, not our wishes.**

CCXT 99.5–99.9% per-exchange. CoinGlass ~99.9% Pro tier. We do not over-state vendor reliability.

*Mitigation:* §10.3 vendor table cites *their* published SLAs. Failover decision tree is *our* response, not a vendor commitment.

**Flag 4 — CoinGlass dual relationship flagged but not over-discussed.**

§12 owns the active monitoring; §10 references but doesn't elaborate.

*Mitigation:* §10.3 includes the dual-relationship paragraph as cross-reference, not as risk-register narrative.

**Flag 5 — Support contractor optionality flagged in §10.4.**

If support load exceeds founder capacity, contractor option is mentioned. This is honest about scaling constraint.

*Mitigation:* Trigger criteria explicit (>20 hrs/wk on tickets); doesn't promise contractor will be hired automatically.

### What §10 audited clean

- Tier SLAs traceable to §5.2 tier matrix structure.
- Incident-response runbook traceable to §14 stop-the-line conditions.
- Vendor SLA table traceable to §11.3 vendor stack and §16.2 Contingency B.
- On-call model honest about solo-founder constraint.
- Tooling cost (~$80/mo) within §11.3 "Other operational" budget — no model refresh required.
- Notion runbook structure aligns with `coinscopeai-platform-sync` locked rules.

### §10 v1 LOCKED

§10.0 through §10.6 all committed. Soft launch (P1, June 1, 2026) operationally ready when ops runbooks live in Notion per §10.5 structure.
