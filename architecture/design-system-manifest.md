# CoinScopeAI Design System — Manifest

**Version:** 2 (2026-05-02)
**Source of truth:** `~/Documents/Claude/Projects/CoinScopeAI/CLAUDE.md` (v2)
**Status:** Active — keep in sync with master prompt.

This document is a *manifest*, not the design system itself. It tells you where each element lives so the design system never drifts from the master prompt.

---

## 1. Brand positioning

| Element | Value | Canonical home |
|---|---|---|
| Positioning | Institutional-grade, AI-driven quant trading for individual traders and funds | `CLAUDE.md` (Brand positioning) |
| Guiding principle | Capital preservation first, profit generation second | `CLAUDE.md` |
| Primary tagline | "Trade Smarter With AI" | `CLAUDE.md` |
| Short tagline | "Trade Smarter" | `CLAUDE.md` |
| B2B / formal tagline | "Your Trusted Partner in Cryptocurrency Trading" | `CLAUDE.md` |

## 2. Voice & tone — 4 operating principles

1. **Anti-overclaim** — never say "production-ready" unless documented criteria are met.
2. **Explicit assumptions, phased work** — name phases (Scan → Score → Gate → Size → Arm).
3. **Risk-first** — drawdown / daily loss / leverage / heat are visible when composing a position.
4. **Methodical & evidence-led** — every claim links to data, model, or rule.

Registers:
- **Product tier** (app, coinscope.ai, docs): technical, terse, declarative, data-led. No emoji. Tabular numbers.
- **Social tier** (IG, X, Threads, FB): aspirational, meme-fluent. Never inside the product.

## 3. Risk thresholds — design tokens

| Token | Value | Notes |
|---|---|---|
| `risk.maxDrawdown` | **10%** | Account-level hard stop |
| `risk.dailyLossLimit` | **5%** | 24h rolling; halts trading |
| `risk.maxLeverage` | **10x** | Per-position. **Locked 2026-05-01 via PCC v2 §8.** Supersedes earlier 20x. |
| `risk.maxOpenPositions` | **5** | Concurrent (revised 2026-05-03 — supersedes 3) |
| `risk.positionHeatCap` | **80%** | Per position; blocks new entries |

Required disclaimer pairing: *"Testnet only. 30-day validation phase. No real capital."*

## 4. Regime palette (v3 ML labels)

| Regime | Color name | Hex | Bias |
|---|---|---|---|
| Trending | mint | `#00FFB8` | breakout / continuation |
| Mean-Reverting | neutral | `#A3ADBD` | fade / range |
| Volatile | amber | `#F5A623` | gate tightens, sizing shrinks |
| Quiet | muted | `#5B6472` | most signals suppressed |

## 5. Personas (internal only, never customer-facing)

| ID | Name | Internal label |
|---|---|---|
| P1 | Omar | The Self-Taught Methodist |
| P2 | Karim | The Engineer Trader |
| P3 | Layla | The Solo PM ($200k–$1M aggregate book) |

## 6. Tier matrix (Track B canonical, locked 2026-05-01)

| Tier | Price |
|---|---|
| Free | $0 |
| Trader | $79/mo |
| Desk Preview | $399/mo |
| Desk Full v2 | $1,199/mo + per-seat ($149 or $249) |

Annual discount: ~17% (10 months for the price of 12).
Founder cohort: ~25–30% off, time-bounded 60 days post-public-launch (per §5.3.5).

## 7. Phase map

| Phase | Window | Scope |
|---|---|---|
| P0 | May 2026 | Validation cohort capped at 40 |
| P1 | Jun–Jul 2026 | Narrow ship: CCXT 4-exchange, CoinGlass, Tradefeeds, CoinGecko, Claude minimal |
| P2 | Aug–Sep 2026 | Vendor expansion |
| P5 | Mar–May 2027 | Desk Full v2 launch |

## 8. Asset map (where the actual files live)

| Asset | Canonical location | Last verified |
|---|---|---|
| Master prompt | `CLAUDE.md` (Mac root) | 2026-05-02 |
| Master prompt (Drive copy) | `My Drive/CoinScopeAI/business-plan-v1/CLAUDE.md` | 2026-05-02 |
| v1 framework (17 sections) | `business-plan/00-framework.md` … `16-scenario-planning.md` | 2026-05-02 |
| Decision log (1,482 lines, 64+ entries) | `business-plan/_decisions/decision-log.md` | 2026-05-02 |
| Architecture v5 | Claude.ai project knowledge → `architecture.md` | 2026-05-02 |
| Brand book v3 (canonical PDF) | Drive `13 — Marketing & GTM/coin_scopeai_brand_book_v3.pdf` | 2026-05-02 |
| Engine module skills (.skill bundles) | Local `skills/` (7 files) | 2026-04-18 |
| Persona skills | Local `coinscopeai-skills/` (7 files) | 2026-04-18 |
| Drive Master Index | Drive root → `CoinScopeAI — Master Drive Index` (Google Doc) | 2026-05-02 |
| Drive START HERE | Drive root → `00 — START HERE.md` | 2026-05-02 |

## 9. Sync rule (how this manifest stays current)

**Trigger conditions** — refresh this manifest when ANY of these change:

1. Risk thresholds in `CLAUDE.md` (drawdown, daily loss, leverage, max open, heat cap)
2. Regime labels or hex values
3. Persona IDs / names / labels
4. Tier matrix (names, prices, structure)
5. Phase map (windows or scope)
6. Brand book version (currently v3)
7. Architecture doc version (currently v5)
8. Master prompt version (currently v2)

**Sync workflow:**
1. Update `CLAUDE.md` (Mac root) — single source of truth for tokens.
2. Update this manifest's affected sections.
3. Bump the **Version** stamp at top.
4. Add an entry to §10 Changelog.
5. Re-upload to Drive `02 — Architecture & Design/` (overwrite existing).
6. Re-upload to Claude.ai project knowledge (delete old, upload new).
7. Replace the `CoinScopeAI Design System.zip` in Drive `13 — Marketing & GTM/` if visual assets changed.

**Memory rule (Scoopy):** treat this manifest as a satellite of `CLAUDE.md`. Whenever a CLAUDE.md edit changes any of the trigger conditions, propose the manifest update in the same response.

## 10. Changelog

- **v2 (2026-05-02):** Created as canonical manifest. Pulls all design tokens from CLAUDE.md v2. Replaces the Apr-25 `CoinScopeAI Design System.zip` as the live source — the zip is now an Apr-25 visual snapshot, not a source of truth.
- **v1 (Apr 25, 2026):** Original `CoinScopeAI Design System.zip` (563 KB) in Drive `13 — Marketing & GTM/`. Pre-v1-framework era. Kept for visual asset reference; not authoritative on tokens.

## 11. Pre-v1 artifacts (DO NOT use for current work)

These appear in Drive search but are stale — kept for historical reference only:

- `CoinScopeAI — Design System` (Google Doc, Apr 6 2026, file id `1FbTDQHJ_pomMugt9RIm3FoDXTlQhO4odn7Iwh7t3K3E`) — in `archive-pre-v1/CoinScopeAI/`
- `design-system.md` (Apr 5 2026, file id `1pg2T-8W2ifLmvD2IwjUZuBPlFryDRLek`) — old MENA-focused vision
- Anything referencing 20x leverage, $5M ARR target, MENA-only positioning, or 5-pillar value prop

If you find one of these treated as authoritative anywhere, replace the reference with this manifest.
