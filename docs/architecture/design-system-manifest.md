# CoinScopeAI Design System — Manifest
# Version: 3 | Updated: 2026-05-09
# Authority: This manifest is a satellite of CLAUDE.md (business prompt) and index.css (dashboard)
# Any change to tokens in either source must trigger a manifest update + sync cascade

---

## Sync Trigger Rule (Mandatory)

Whenever ANY of these change → update this manifest + run §10 cascade:
1. CSS custom properties in `index.css` (colors, fonts, radii)
2. Risk thresholds in any canonical doc
3. Regime labels or hex values
4. Persona IDs / names / labels
5. Tier matrix (names, prices, structure)
6. Phase map (windows or scope)
7. Brand positioning or taglines
8. Component inventory (new UI component added/removed)

---

## 1. Brand Positioning

| Element | Value |
|---|---|
| Positioning | Institutional-grade, AI-driven quant trading for individual traders and funds |
| Guiding principle | **Capital preservation first**, profit generation second |
| Primary tagline | "Trade Smarter With AI" |
| Short tagline | "Trade Smarter" |
| B2B / formal tagline | "Your Trusted Partner in Cryptocurrency Trading" |
| Mandatory disclaimer | "Testnet only. 30-day validation phase. No real capital." |

---

## 2. Voice & Tone

**4 operating principles:**
1. **Anti-overclaim** — never say "production-ready" without PCC v2 §8 reference
2. **Explicit assumptions, phased work** — name phases (Scan → Score → Gate → Size → Arm)
3. **Risk-first** — thresholds visible when composing any position
4. **Methodical & evidence-led** — every claim links to data, model, or rule

**Registers:**
- **Product** (app, docs, API): technical, terse, declarative, data-led. No emoji. Tabular numbers.
- **Social** (X, IG, Threads): aspirational, meme-fluent. Never inside product UI.

---

## 3. Color Tokens (canonical — from `index.css` OKLCH)

### Background / Surface
| Token | CSS var | OKLCH | Use |
|---|---|---|---|
| Background | `--background` | `oklch(0.12 0.02 260)` | Page bg (dark navy) |
| Card | `--card` | `oklch(0.16 0.02 260)` | Panel / card bg |
| Popover | `--popover` | `oklch(0.18 0.025 260)` | Dropdown bg |
| Muted | `--muted` | `oklch(0.22 0.02 260)` | Subtle bg sections |
| Secondary | `--secondary` | `oklch(0.20 0.025 260)` | Secondary elements |
| Sidebar | `--sidebar` | `oklch(0.14 0.02 260)` | Sidebar bg |

### Text
| Token | CSS var | OKLCH | Use |
|---|---|---|---|
| Foreground | `--foreground` | `oklch(0.90 0.01 250)` | Primary text |
| Muted foreground | `--muted-foreground` | `oklch(0.60 0.02 250)` | Subdued text |
| Card foreground | `--card-foreground` | `oklch(0.90 0.01 250)` | Card text |

### Brand / Interactive
| Token | CSS var | OKLCH | Use |
|---|---|---|---|
| Primary (Emerald) | `--primary` | `oklch(0.70 0.17 162)` | CTAs, active states, profit |
| Accent (Cyan) | `--accent` | `oklch(0.75 0.12 200)` | Highlights, links |
| Destructive (Crimson) | `--destructive` | `oklch(0.60 0.22 25)` | Errors, losses, danger |
| Ring | `--ring` | `oklch(0.70 0.17 162)` | Focus ring |

### HUD Custom Colors
| Token | CSS var | OKLCH | Use |
|---|---|---|---|
| Navy 950 | `--color-navy-950` | `oklch(0.16 0.02 260)` | Deepest bg |
| Navy 900 | `--color-navy-900` | `oklch(0.20 0.025 260)` | Panel bg |
| Navy 800 | `--color-navy-800` | `oklch(0.25 0.03 260)` | Elevated panels |
| Emerald | `--color-emerald` | `oklch(0.70 0.17 162)` | Profit / positive |
| Emerald dim | `--color-emerald-dim` | `oklch(0.55 0.14 162)` | Subdued profit |
| Cyan accent | `--color-cyan-accent` | `oklch(0.75 0.12 200)` | Data highlights |
| Cyan dim | `--color-cyan-dim` | `oklch(0.55 0.10 200)` | Subdued highlights |
| Amber warn | `--color-amber-warn` | `oklch(0.78 0.16 75)` | Warnings, caution |
| Crimson | `--color-crimson` | `oklch(0.60 0.22 25)` | Loss / negative |
| Profit | `--color-profit` | `oklch(0.70 0.17 162)` | P&L positive |
| Loss | `--color-loss` | `oklch(0.60 0.22 25)` | P&L negative |

### Border / Input
| Token | CSS var | OKLCH |
|---|---|---|
| Border | `--border` | `oklch(0.25 0.025 260)` |
| Input | `--input` | `oklch(0.22 0.025 260)` |

### Charts
| Token | CSS var | OKLCH | Maps to |
|---|---|---|---|
| Chart 1 | `--chart-1` | `oklch(0.70 0.17 162)` | Emerald — Trending |
| Chart 2 | `--chart-2` | `oklch(0.75 0.12 200)` | Cyan — Mean-Reverting |
| Chart 3 | `--chart-3` | `oklch(0.78 0.16 75)` | Amber — Volatile |
| Chart 4 | `--chart-4` | `oklch(0.65 0.20 300)` | Purple — reserved |
| Chart 5 | `--chart-5` | `oklch(0.60 0.22 25)` | Crimson — loss |

---

## 4. Typography

| Token | CSS var | Value |
|---|---|---|
| Sans | `--font-sans` | `'Inter', ui-sans-serif, system-ui, sans-serif` |
| Mono | `--font-mono` | `'JetBrains Mono', ui-monospace, monospace` |
| Data display | `.tabular-nums` | `font-variant-numeric: tabular-nums` |

---

## 5. Radii

| Token | CSS var | Value |
|---|---|---|
| Base radius | `--radius` | `0.5rem` |
| Small | `--radius-sm` | `calc(var(--radius) - 4px)` |
| Medium | `--radius-md` | `calc(var(--radius) - 2px)` |
| Large | `--radius-lg` | `var(--radius)` |
| XL | `--radius-xl` | `calc(var(--radius) + 4px)` |

---

## 6. Regime Palette (v3 ML — maps to chart colors)

| Regime | Color | CSS var | OKLCH | Trading bias |
|---|---|---|---|---|
| **Trending** | Emerald | `--chart-1` | `oklch(0.70 0.17 162)` | Breakout / continuation |
| **Mean-Reverting** | Cyan | `--chart-2` | `oklch(0.75 0.12 200)` | Fade / range trade |
| **Volatile** | Amber | `--chart-3` | `oklch(0.78 0.16 75)` | Gate tightens, size shrinks |
| **Quiet** | Muted gray | `--muted-foreground` | `oklch(0.60 0.02 250)` | Most signals suppressed |

---

## 7. Risk Tokens (LOCKED 2026-05-01 — PCC v2 §8)

| Token | Value | Env var |
|---|---|---|
| `risk.maxLeverage` | **10x** | `MAX_LEVERAGE=10` |
| `risk.maxOpenPositions` | **5** | `MAX_OPEN_POSITIONS=5` |
| `risk.maxDrawdown` | **10%** | `MAX_DRAWDOWN_PCT=10` |
| `risk.dailyLossLimit` | **5%** | `MAX_DAILY_LOSS_PCT=5` |
| `risk.positionHeatCap` | **80%** | `POSITION_HEAT_CAP_PCT=80` |

Source: v2/main commit `3d6362d` — never modify without PCC v2 §8 gate.

---

## 8. HUD Component Styles

| Class | Style | Use |
|---|---|---|
| `.hud-panel` | `bg-navy-950 border border-navy-800 rounded-lg` | Standard data panel |
| `.hud-panel-glow` | `bg-navy-950 border border-emerald/30 shadow-emerald/5` | Active / highlighted panel |
| `.hud-grid-bg` | 40px grid lines at navy-800/30 | Chart backgrounds |
| `.status-green` | `oklch(0.70 0.17 162)` | Live / healthy / profit |
| `.status-yellow` | `oklch(0.78 0.16 75)` | Warning / caution |
| `.status-red` | `oklch(0.60 0.22 25)` | Error / loss / danger |
| `.status-black` | `oklch(0.50 0 0)` | Inactive / offline |
| `.animate-pulse-dot` | 2s ease-in-out pulse | Live indicators |

---

## 9. Component Inventory

### shadcn/ui Base Components (45 — `components/ui/`)
accordion, alert, alert-dialog, aspect-ratio, avatar, badge, breadcrumb,
button, button-group, calendar, card, carousel, chart, checkbox, collapsible,
command, context-menu, dialog, drawer, dropdown-menu, empty, field, form,
hover-card, input, input-group, input-otp, item, kbd, label, menubar,
navigation-menu, pagination, popover, progress, radio-group, resizable,
scroll-area, select, separator, sheet, sidebar, skeleton, slider, sonner,
spinner, switch, table, tabs, textarea, toggle, toggle-group, tooltip

### CoinScopeAI HUD Components (10 — `components/`)
| Component | File | Purpose |
|---|---|---|
| DashboardLayout | `DashboardLayout.tsx` | Page scaffold with sidebar + topbar |
| Sidebar | `Sidebar.tsx` | Nav sidebar |
| TopBar | `TopBar.tsx` | Top navigation bar |
| MetricCard | `MetricCard.tsx` | KPI / metric display card |
| PageHeader | `PageHeader.tsx` | Page title + actions |
| StatusBadge | `StatusBadge.tsx` | Regime / engine / connection badge |
| ExecuteOrderDialog | `ExecuteOrderDialog.tsx` | Trade execution modal |
| ErrorBoundary | `ErrorBoundary.tsx` | Error containment |
| ManusDialog | `ManusDialog.tsx` | AI assistant dialog |
| Map | `Map.tsx` | Geographic display |

### Public Legal Page
- `client/public/legal.html` — dark-theme `/legal` disclosures page (COI-63, 2026-05-09)

---

## 10. Tier Matrix (LOCKED 2026-05-01)

| Tier | Price | Notes |
|---|---|---|
| Free | $0 | Signup-verified; no credit card |
| Trader | $79/mo | PLG; primary ICP |
| Desk Preview | $399/mo | PLG with founder sales-assist |
| Desk Full v2 | $1,199/mo + per-seat ($149/$249) | Sales-led |

Annual discount: ~17% (10 months for 12).
Old pricing ($19/$49/$99/$299) is superseded — never use.

---

## 11. Personas (internal only — never customer-facing)

| ID | Name | Label |
|---|---|---|
| P1 | Omar | The Self-Taught Methodist |
| P2 | Karim | The Engineer Trader |
| P3 | Layla | The Solo PM ($200k–$1M book) |

---

## 12. Phase Map

| Phase | Window | Scope |
|---|---|---|
| P0 | Apr–May 2026 | Testnet validation; cohort capped at 40 |
| P1 | Jun–Jul 2026 | Soft launch: Trader tier, Stripe, ToS, live engine |
| P1.5 | Jun–Jul 2026 | ToS gate, key vault, cost meter, audit log |
| P2 | Aug–Sep 2026 | Bybit integration, vendor expansion |
| P3 | 2026 Q4 | Multi-account, Desk tier, Arabic UI |
| P5 | Mar–May 2027 | Desk Full v2 launch |

---

## 13. Asset Map (canonical locations)

| Asset | Mac path | Drive | GitHub |
|---|---|---|---|
| Business prompt CLAUDE.md | `CLAUDE.md` (root) | `01 — Project Overview` | ✅ v2 repo |
| Design system manifest (this doc) | `docs/architecture/design-system-manifest.md` | `02 — Architecture` | ✅ v1 repo |
| CSS tokens | `coinscopeai-dashboard/client/src/index.css` | — | ✅ v1 repo |
| UI components | `coinscopeai-dashboard/client/src/components/` | — | ✅ v1 repo |
| Architecture v5 | `docs/architecture/architecture.md` | `02 — Architecture` | ✅ v1 repo |
| Decision log | `business-plan/_decisions/decision-log.md` | `08 — Session Notes` | ✅ v1 repo |
| Legal page | `coinscopeai-dashboard/client/public/legal.html` | `11 — Legal` | ✅ v1 repo |

---

## 14. Sync Cascade (run when manifest updates)

When this manifest is updated, propagate in this order:

```
1. Update this file (docs/architecture/design-system-manifest.md)
2. Bump Version stamp at top + add §15 changelog entry
3. git commit: "docs(design-system): update manifest vN — <what changed>"
4. git push to v1/main
5. Create/update in Drive My Drive root → drag to 02 — Architecture
6. Update Notion 08 Engineering & Architecture page with change summary
7. If CSS tokens changed: update index.css in same commit
8. If risk tokens changed: update .env.example + run risk_threshold_guardrail.py
9. If tier/pricing changed: update 01 Executive Dashboard in Notion
10. Run: python3 scripts/drift_detector.py
```

---

## 15. Changelog

| Version | Date | Changes |
|---|---|---|
| v3 | 2026-05-09 | Full rewrite: added complete CSS token table from index.css, HUD component styles, component inventory (45 shadcn + 10 HUD), confirmed risk tokens, added sync cascade, updated asset map |
| v2 | 2026-05-02 | Created as canonical manifest — replaced Design System zip |
| v1 | 2026-04-25 | `CoinScopeAI Design System.zip` (563 KB) — visual snapshot, not authoritative |

---

## 16. Stale Artifacts (DO NOT use)

These exist in Drive but are not authoritative:

| File | Location | Why stale |
|---|---|---|
| `CoinScopeAI — Design System` (Google Doc) | `archive-pre-v1/` | Apr 6 2026 — pre-v1 era |
| `design-system.md` | Drive archive | Apr 5 2026 — old MENA-focused |
| Any doc mentioning 20x leverage | anywhere | Superseded by 10x (2026-05-01) |
| Any doc with $19/$49/$99/$299 pricing | anywhere | Superseded (2026-05-01) |
| `CoinScopeAI Design System.zip` | `13 — Marketing & GTM` | Apr 25 snapshot — visual assets only |
