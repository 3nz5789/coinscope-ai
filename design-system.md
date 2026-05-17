# CoinScopeAI Design System

**Version:** 1.0 — May 2026  
**Scope:** Dashboard application (`apps/dashboard/`)  
**Stack:** React 18 · TypeScript · Tailwind CSS v4 · shadcn/ui · Radix UI

---

## Table of Contents

1. [Design Tokens](#1-design-tokens)
2. [Typography](#2-typography)
3. [Color System](#3-color-system)
4. [Spacing & Layout](#4-spacing--layout)
5. [Border & Radius](#5-border--radius)
6. [Animation & Motion](#6-animation--motion)
7. [Custom CSS Utilities](#7-custom-css-utilities)
8. [Core Components](#8-core-components)
9. [Domain Components](#9-domain-components)
10. [Page-Embedded Components](#10-page-embedded-components)
11. [shadcn/ui Primitive Inventory](#11-shadcnui-primitive-inventory)
12. [UI Patterns](#12-ui-patterns)
13. [Accessibility](#13-accessibility)
14. [Data Refresh Intervals](#14-data-refresh-intervals)

---

## 1. Design Tokens

All tokens are defined in `apps/dashboard/src/index.css` using two layers:

- `@theme inline { }` — Registers tokens with Tailwind v4 as class-generating CSS variables
- `:root { }` — Defines the actual computed values (dark theme only; no light variant)

The project uses **OKLCH** (`oklch(L C H)`) throughout for perceptually uniform, wide-gamut color.

---

## 2. Typography

### Font Families

| Role | Family | CSS Variable | Tailwind Class |
|------|---------|-------------|----------------|
| UI / Body | Inter | `--font-sans` | `font-sans` |
| Data / Numbers | JetBrains Mono | `--font-mono` | `font-mono` |

### Font Usage Rules

- **All numeric data** (prices, percentages, confidence scores, timestamps, P&L values) must use `font-mono` via the `.data-value` utility class.
- **`font-variant-numeric: tabular-nums`** is applied globally to `.data-value` — ensures digits align in tables and time-series displays.
- UI text, labels, headings: `font-sans` (Inter).
- `-webkit-font-smoothing: antialiased` applied to `body`.

### Type Scale (Used in Practice)

| Size | Usage |
|------|-------|
| `text-xl` (`1.25rem`) | Regime distribution count numbers |
| `text-2xl` (`1.5rem`) | Risk gauge primary values |
| `text-lg` (`1.125rem`) | Page headings |
| `text-[15px]` | Symbol names in cards |
| `text-[13px]` | HudCard titles; status labels |
| `text-[12px]` | Regime confidence values; secondary data |
| `text-[11px]` | Gauge labels; metric identifiers |
| `text-[10px]` | Duration text; 24h stats; micro-labels |

---

## 3. Color System

### Semantic Color Tokens (`:root`)

| Token | OKLCH | Role |
|-------|-------|------|
| `--background` | `oklch(0.145 0.028 264.05)` | Page background — deepest navy |
| `--foreground` | `oklch(0.925 0.006 264.53)` | Primary text |
| `--card` | `oklch(0.185 0.02 264.05)` | Card / panel background |
| `--card-foreground` | `oklch(0.925 0.006 264.53)` | Card text |
| `--popover` | `oklch(0.185 0.02 264.05)` | Popover background |
| `--popover-foreground` | `oklch(0.925 0.006 264.53)` | Popover text |
| `--primary` | `oklch(0.696 0.17 162.48)` | Primary action / emerald brand |
| `--primary-foreground` | `oklch(0.145 0.028 264.05)` | Text on primary bg |
| `--secondary` | `oklch(0.22 0.02 264.05)` | Secondary element bg |
| `--secondary-foreground` | `oklch(0.75 0.01 264.05)` | Secondary text |
| `--muted` | `oklch(0.25 0.015 264.05)` | Muted backgrounds, gauge tracks |
| `--muted-foreground` | `oklch(0.556 0.02 264.05)` | Secondary / helper text |
| `--accent` | `oklch(0.22 0.02 264.05)` | Accent hover states |
| `--accent-foreground` | `oklch(0.925 0.006 264.53)` | Accent text |
| `--destructive` | `oklch(0.637 0.237 25.331)` | Error / danger / negative P&L |
| `--destructive-foreground` | `oklch(0.985 0 0)` | Text on destructive bg |
| `--border` | `oklch(0.3 0.015 264.05)` | Default borders |
| `--input` | `oklch(0.25 0.015 264.05)` | Input backgrounds |
| `--ring` | `oklch(0.696 0.17 162.48)` | Focus ring (emerald) |
| `--sidebar` | `oklch(0.12 0.025 264.05)` | Sidebar background — darkest |
| `--sidebar-foreground` | `oklch(0.75 0.01 264.05)` | Sidebar text |
| `--sidebar-primary` | `oklch(0.696 0.17 162.48)` | Sidebar active accent |
| `--sidebar-border` | `oklch(0.25 0.015 264.05)` | Sidebar borders |

### CoinScopeAI Custom Colors (`@theme inline`)

| Token | OKLCH | Tailwind Class | Hex Approx | Usage |
|-------|-------|----------------|-----------|-------|
| `--color-emerald` | `oklch(0.696 0.17 162.48)` | `emerald` | `#00C896` | Positive, brand, active states |
| `--color-danger` | `oklch(0.637 0.237 25.331)` | `danger` | `#E34D26` | Errors (alias of `--destructive`) |
| `--color-warning` | `oklch(0.795 0.184 86.047)` | `warning` | `#F5A623` | Caution, volatile regime, partial risk |
| `--color-navy-deep` | `oklch(0.145 0.028 264.05)` | `navy-deep` | `#0C0E18` | Background base |
| `--color-navy-card` | `oklch(0.185 0.02 264.05)` | `navy-card` | `#111420` | Card surface |
| `--color-navy-surface` | `oklch(0.22 0.02 264.05)` | `navy-surface` | `#161926` | Elevated surface |

### Chart Color Tokens

| Token | OKLCH | Assignment |
|-------|-------|-----------|
| `--chart-1` | `oklch(0.696 0.17 162.48)` | Emerald (primary series) |
| `--chart-2` | `oklch(0.637 0.237 25.331)` | Red / destructive |
| `--chart-3` | `oklch(0.795 0.184 86.047)` | Amber / warning |
| `--chart-4` | `oklch(0.623 0.214 259.815)` | Blue (ranging state) |
| `--chart-5` | `oklch(0.7 0.15 300)` | Purple (extended palette) |

### Regime Color Assignments (v3 ML)

| Regime | Color Token | Tailwind Classes |
|--------|------------|-----------------|
| `trending_up` | Emerald | `text-emerald bg-emerald/10 border-emerald/20` |
| `trending_down` | Destructive | `text-destructive bg-destructive/10 border-destructive/20` |
| `ranging` | Blue-400 | `text-blue-400 bg-blue-400/10 border-blue-400/20` |
| `volatile` | Warning | `text-warning bg-warning/10 border-warning/20` |

### Risk Threshold Color Mapping

Ratio = `value / limit`. Applied to `RiskGauge` and similar components.

| Ratio Range | Label | Text Color | Background | Border |
|------------|-------|-----------|------------|--------|
| `< 0.5` | NOMINAL | `text-emerald` | `bg-emerald` | `bg-emerald/10 text-emerald` |
| `0.5 – 0.8` | WARNING | `text-warning` | `bg-warning` | `bg-warning/10 text-warning` |
| `≥ 0.8` | CRITICAL | `text-destructive` | `bg-destructive` | `bg-destructive/10 text-destructive` |

---

## 4. Spacing & Layout

### Grid System

- **Application shell**: Sidebar (220px or 68px collapsed) + main content area (flex-1)
- **Content padding**: `p-5` or `p-6` on page containers; `p-4` on HudCard content
- **Card gaps**: `gap-3` (summary row), `gap-4` (main grids)
- **Grid backgrounds**: `40px × 40px` repeating grid via `.grid-bg`

### Responsive Grid Columns (Regime / Signal Grids)

```
grid-cols-1                 → mobile
md:grid-cols-2              → tablet
lg:grid-cols-3              → desktop
xl:grid-cols-4              → wide desktop
```

### Key Spacing Values

| Use | Value |
|-----|-------|
| Section spacing | `space-y-5` |
| Card header padding | `px-4 py-3` |
| Card content padding | `p-4` |
| Card header bottom border | `border-b border-border/50` |
| Status bar height | `h-10` |
| Sidebar expanded width | `220px` |
| Sidebar collapsed width | `68px` |
| Left accent bar width | `3px` (`.border-l-[3px]`) |

---

## 5. Border & Radius

| Token | Value |
|-------|-------|
| `--radius` | `0.5rem` (8px) |
| `--radius-sm` | `calc(0.5rem - 4px)` = 4px |
| `--radius-md` | `calc(0.5rem - 2px)` = 6px |
| `--radius-lg` | `0.5rem` = 8px |
| `--radius-xl` | `calc(0.5rem + 4px)` = 12px |
| HudCard radius | `border-radius: 0.375rem` (6px, custom) |
| Badge radius | `rounded-md` |
| Progress bars | `rounded-full` |
| Focus ring | `outline-ring/50` global default |

---

## 6. Animation & Motion

### Sidebar Transition
```css
transition-all duration-200 ease-out
```
Applied to sidebar width changes (expand/collapse).

### HudCard Hover
```css
transition: border-color 0.2s ease, box-shadow 0.2s ease;
/* hover state: */
border-color: oklch(0.696 0.17 162.48 / 0.4);  /* emerald/40 */
box-shadow: 0 0 20px oklch(0.696 0.17 162.48 / 0.06);
```

### `.pulse-live` — Status Indicator
```css
animation: pulse-glow 2s ease-in-out infinite;

@keyframes pulse-glow {
  0%, 100% { opacity: 1; box-shadow: 0 0 4px currentColor; }
  50%       { opacity: 0.6; box-shadow: 0 0 12px currentColor; }
}
```
Used on live status dot in StatusBar and KillSwitch ACTIVATED state.

### Progress Bar Fill
```css
transition-all duration-500
```
Applied to confidence bars, risk gauges.

---

## 7. Custom CSS Utilities

Defined in `@layer components` within `index.css`.

### `.hud-card`

The primary card container for all dashboard panels.

```css
.hud-card {
  position: relative;
  background: oklch(0.185 0.02 264.05);      /* --card */
  border: 1px solid oklch(0.3 0.015 264.05); /* --border */
  border-radius: 0.375rem;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}
.hud-card:hover {
  border-color: oklch(0.696 0.17 162.48 / 0.4);
  box-shadow: 0 0 20px oklch(0.696 0.17 162.48 / 0.06);
}
```

### `.data-value`

Applied to all numeric/data text throughout the dashboard.

```css
.data-value {
  font-family: "JetBrains Mono", ui-monospace, monospace;
  font-variant-numeric: tabular-nums;
}
```

### `.pulse-live`

Animated glow pulse for live status indicators.

```css
.pulse-live {
  animation: pulse-glow 2s ease-in-out infinite;
}
```

### `.scanline-overlay`

CRT scan-line aesthetic overlay (pointer-events: none).

```css
.scanline-overlay {
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    oklch(0.696 0.17 162.48 / 0.015) 2px,
    oklch(0.696 0.17 162.48 / 0.015) 4px
  );
  pointer-events: none;
}
```

### `.grid-bg`

40px grid background for dashboard backdrops.

```css
.grid-bg {
  background-image:
    linear-gradient(oklch(0.3 0.015 264.05 / 0.3) 1px, transparent 1px),
    linear-gradient(90deg, oklch(0.3 0.015 264.05 / 0.3) 1px, transparent 1px);
  background-size: 40px 40px;
}
```

---

## 8. Core Components

### HudCard

**File:** `src/components/HudCard.tsx`  
**Role:** Primary container panel for all dashboard sections.

#### Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `title` | `string` | — | Card header title (rendered uppercase, tracked) |
| `subtitle` | `string` | — | Optional subtitle below title |
| `children` | `ReactNode` | — | Card body content |
| `className` | `string` | — | Additional classes on wrapper |
| `headerRight` | `ReactNode` | — | Content pinned to header right side |
| `loading` | `boolean` | `false` | Shows spinning RefreshCw icon in header when true |
| `noPadding` | `boolean` | `false` | Removes `p-4` from content wrapper |

#### Visual Spec

- **Wrapper**: `.hud-card` + `overflow-hidden`
- **Header** (when `title` present):
  - Layout: `px-4 py-3 flex items-center justify-between border-b border-border/50`
  - Title: `text-[13px] font-semibold uppercase tracking-wider text-muted-foreground`
  - Loading icon: `RefreshCw` 14px, `animate-spin`, `text-muted-foreground`
- **Content**: `p-4` (or `p-0` when `noPadding`)

#### States

| State | Visual |
|-------|--------|
| Default | Navy card bg, subtle border |
| Hover | Emerald border glow (from `.hud-card:hover`) |
| Loading | Spin icon in header right |
| No data | Children render empty / null |

#### Usage

```tsx
<HudCard title="Daily Loss" loading={isFetching}>
  <RiskGauge label="Daily P&L Loss" value={risk.dailyLossPct} limit={risk.dailyLossLimit} />
</HudCard>

<HudCard title="Scanner" headerRight={<Badge>LIVE</Badge>} noPadding>
  <SignalTable data={signals} />
</HudCard>
```

---

### Sidebar

**File:** `src/components/Sidebar.tsx`  
**Role:** Primary navigation. Collapsible.

#### Dimensions

| State | Width |
|-------|-------|
| Expanded | `220px` |
| Collapsed | `68px` |

Transition: `transition-all duration-200 ease-out`

#### Visual Spec

- **Background**: `oklch(0.12 0.025 264.05)` (`--sidebar`) — darkest navy in the system
- **Top**: 60px logo area — 32×32px image + wordmark when expanded
  - Wordmark: `CoinScope` in foreground + `AI` in `text-emerald font-bold`
- **Bottom**: Collapse toggle button with ChevronLeft/Right icon
- **Border right**: `border-r border-border/30`

#### Navigation Routes (10)

| Route | Icon | Path |
|-------|------|------|
| Overview | `LayoutDashboard` | `/` |
| Live Scanner | `Scan` | `/scanner` |
| Positions | `Target` | `/positions` |
| Equity Curve | `TrendingUp` | `/equity` |
| Performance | `Activity` | `/performance` |
| Alpha Signals | `Zap` | `/signals` |
| Regime State | `Gauge` | `/regime` |
| Trade Journal | `BookOpen` | `/journal` |
| Risk Gate | `ShieldAlert` | `/risk` |
| Recording Daemon | `Mic` | `/recording` |

#### Item States

| State | Classes |
|-------|---------|
| Active | `bg-emerald/10 text-emerald font-medium` + `absolute left-0 w-[3px] h-5 bg-emerald rounded-r-full` accent bar |
| Inactive | `text-muted-foreground hover:text-foreground hover:bg-white/[0.04]` |
| All items | `rounded-md` container, `gap-3` icon+label, `text-[13px]` label |

---

### StatusBar

**File:** `src/components/StatusBar.tsx`  
**Role:** Application-wide status strip across the top of the main content area.

#### Visual Spec

- **Height**: `h-10`
- **Background**: Sidebar color (`--sidebar`)
- **Border**: `border-b border-border/50`
- **Layout**: Flex, space-between, `px-4`

#### Left Section — Live Indicator

```
● LIVE  [wifi icon]  [UTC Clock]
```

- Pulse dot: `w-2 h-2 rounded-full bg-emerald` + `.pulse-live`
- "LIVE" text: `text-[11px] font-bold text-emerald tracking-widest`
- Wifi icon: `w-3.5 h-3.5 text-emerald`
- Clock: `.data-value text-[12px] text-muted-foreground` — updates every second

#### Right Section — Performance & Risk

```
[Total Return %]  [Risk Badge]
```

- **Total Return**: `.data-value text-[13px] font-bold` — `text-emerald` if ≥ 0, `text-destructive` if < 0
- **Risk Badge**: Shield icon + status text
  - `nominal`: `ShieldCheck` + `text-emerald bg-emerald/10 border-emerald/20`
  - `warning`: `AlertTriangle` + `text-warning bg-warning/10 border-warning/20`
  - `critical`: `ShieldX` + `text-destructive bg-destructive/10 border-destructive/20`

---

### PriceChangeBadge

**File:** `src/components/PriceChangeBadge.tsx`  
**Role:** Inline 24h price percentage change indicator.

#### Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `pct` | `number` | required | Percentage value (positive or negative) |
| `size` | `"sm" \| "md"` | `"sm"` | Badge size |
| `showIcon` | `boolean` | `true` | Whether to show trend icon |

#### Size Scale

| Size | Text | Icon |
|------|------|------|
| `sm` | `text-[10px]` | `w-3 h-3` |
| `md` | `text-[12px]` | `w-3.5 h-3.5` |

#### States

| Condition | Color Scheme | Icon |
|-----------|-------------|------|
| `pct >= 0` | `text-emerald bg-emerald/10 border-emerald/20` | `TrendingUp` |
| `pct < 0` | `text-destructive bg-destructive/10 border-destructive/20` | `TrendingDown` |

#### Format

- Positive: `+{pct.toFixed(2)}%`
- Negative: `{pct.toFixed(2)}%` (toFixed handles the `-` sign)
- All numbers use `.data-value` for monospace rendering

---

## 9. Domain Components

### SignalConsoleCard

**File:** `src/components/SignalConsoleCard.tsx`  
**Role:** Displays individual trading signal entries in the Live Scanner and Alpha Signals pages.

Key characteristics (from usage patterns):
- Renders signal direction (LONG/SHORT), symbol, entry price, confidence score
- Integrates regime label and gate status
- Uses `.data-value` for all numeric fields
- Color-coded by signal direction: emerald (LONG), destructive (SHORT)

---

## 10. Page-Embedded Components

These components are defined inline within page files rather than as shared components.

### RegimeCard

**File:** `src/pages/RegimeState.tsx`  
**Role:** Displays regime state for a single trading symbol.

#### Props

| Prop | Type | Description |
|------|------|-------------|
| `regime` | `RegimeType` | Regime data object from `/regime/{symbol}` |
| `ticker` | `any` | 24h ticker data (optional) |
| `price` | `number` | Current live price (optional) |

#### Visual Spec

- **Container**: `.hud-card p-4 border-l-[3px] {regime-border-color}`
- **Left border**: 3px solid line colored by regime (see regime color table)
- **Header row**: Symbol name (15px bold) + `PriceChangeBadge` + regime badge (right-aligned)
- **Regime badge**: `inline-flex items-center gap-1.5 px-2 py-1 rounded border text-[11px] font-semibold`
- **Price**: 12px muted-foreground, `formatPrice()` output
- **Confidence label**: `text-[10px] uppercase tracking-widest text-muted-foreground`
- **Confidence value**: `.data-value text-[12px] font-semibold {regime-color}`
- **Confidence bar**: `w-full h-1.5 rounded-full bg-muted` track + colored fill at `regime.confidence%` width
- **Duration / timestamp**: `text-[10px] text-muted-foreground`, flex row, `pt-1`
- **24h Stats** (when ticker available): `pt-2 border-t border-border/20 grid grid-cols-2 gap-x-4`
  - 24h High: `text-emerald`
  - 24h Low: `text-destructive`
  - Volume: formatted as `$XB` or `$XM` (≥1B threshold)

#### Regime Badge Config

```typescript
const regimeConfig = {
  trending_up:   { label: "Trending Up",   color: "text-emerald",    bg: "bg-emerald/10 border-emerald/20",       icon: TrendingUp  },
  trending_down: { label: "Trending Down", color: "text-destructive", bg: "bg-destructive/10 border-destructive/20", icon: TrendingDown },
  ranging:       { label: "Ranging",       color: "text-blue-400",   bg: "bg-blue-400/10 border-blue-400/20",     icon: Minus       },
  volatile:      { label: "Volatile",      color: "text-warning",    bg: "bg-warning/10 border-warning/20",       icon: Zap         },
}
```

---

### RiskGauge

**File:** `src/pages/RiskGate.tsx`  
**Role:** Displays a single risk metric with progress bar and threshold status.

#### Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `label` | `string` | required | Metric label |
| `value` | `number` | required | Current value |
| `limit` | `number` | required | Maximum threshold |
| `unit` | `string` | `"%"` | Unit suffix (`"%"` or `"x"`) |

#### Threshold Logic

```typescript
const ratio = value / limit;
// ratio >= 0.8 → CRITICAL (destructive)
// ratio >= 0.5 → WARNING (warning)
// else         → NOMINAL (emerald)
```

#### Visual Spec

- **Label**: `text-[11px] uppercase tracking-wider font-medium text-muted-foreground`
- **Status pill**: `text-[10px] font-semibold px-1.5 py-0.5 rounded` with appropriate bg/text
- **Value**: `.data-value text-2xl font-bold {color}` + `{unit}` suffix
- **Limit**: `text-[11px] text-muted-foreground mb-1` — `/ {limit}{unit}`
- **Track**: `w-full h-2 rounded-full bg-muted overflow-hidden`
- **Fill**: `h-full rounded-full transition-all duration-500 {bgColor}` at `min(100, ratio * 100)%`

---

### KillSwitchIndicator

**File:** `src/pages/RiskGate.tsx`  
**Role:** Displays the emergency kill switch status.

#### Props

| Prop | Type | Description |
|------|------|-------------|
| `active` | `boolean` | Whether kill switch is engaged |

#### Visual Spec

- **Container**: `.hud-card p-4 border-l-[3px]`
  - Active: `border-l-destructive`
  - Inactive: `border-l-emerald`
- **Icon**: `Power` 24×24px
  - Active: `text-destructive`
  - Inactive: `text-emerald`
- **Label**: `text-[13px] font-semibold text-foreground` — "Kill Switch"
- **Subtitle**: `text-[11px] text-muted-foreground` — "Emergency position liquidation"
- **Status badge**:
  - Active: `bg-destructive/10 text-destructive border-destructive/20` + `.pulse-live` dot + "ACTIVATED"
  - Inactive: `bg-emerald/10 text-emerald border-emerald/20` + static dot + "DISARMED"
- **Status badge text**: `text-[12px] font-bold data-value`

---

### RegimeDistributionRow (Inline)

**File:** `src/pages/RegimeState.tsx`  
**Role:** Summary bar showing count of symbols per regime.

- **Layout**: `grid grid-cols-4 gap-3`
- **Each card**: `.hud-card px-4 py-3`
- **Icon**: `w-4 h-4 {regime-color}`
- **Label**: `text-[10px] uppercase tracking-widest text-muted-foreground font-medium`
- **Count**: `.data-value text-xl font-bold {regime-color}`

---

## 11. shadcn/ui Primitive Inventory

All primitives live in `src/components/ui/`. Built with `cva` + Radix UI.

| Component | File | Notes |
|-----------|------|-------|
| `Badge` | `badge.tsx` | 4 CVA variants: `default`, `secondary`, `destructive`, `outline` |
| `Button` | `button.tsx` | Standard shadcn button with size/variant system |
| `Card` | `card.tsx` | Base card primitives (not the domain HudCard) |
| `Dialog` | `dialog.tsx` | Radix Dialog — used in ManusDialog |
| `Dropdown Menu` | `dropdown-menu.tsx` | Radix DropdownMenu |
| `Input` | `input.tsx` | Form input |
| `Label` | `label.tsx` | Form label |
| `Select` | `select.tsx` | Radix Select |
| `Separator` | `separator.tsx` | Divider |
| `Sheet` | `sheet.tsx` | Slide-over panel |
| `Skeleton` | `skeleton.tsx` | Loading placeholder |
| `Slider` | `slider.tsx` | Range slider |
| `Switch` | `switch.tsx` | Toggle switch |
| `Table` | `table.tsx` | HTML table wrappers |
| `Tabs` | `tabs.tsx` | Radix Tabs |
| `Textarea` | `textarea.tsx` | Multi-line input |
| `Toast` / `Toaster` | `toast.tsx`, `toaster.tsx` | Notification system |
| `Tooltip` | `tooltip.tsx` | Radix Tooltip |
| `Progress` | `progress.tsx` | Progress bar primitive |
| `Avatar` | `avatar.tsx` | Radix Avatar |
| `Collapsible` | `collapsible.tsx` | Radix Collapsible (used in Sidebar) |
| `Command` | `command.tsx` | cmdk command palette |
| `Popover` | `popover.tsx` | Radix Popover |
| `Calendar` | `calendar.tsx` | Date picker calendar |
| `Form` | `form.tsx` | react-hook-form integration |

### Badge Variants (Full Spec)

```typescript
// badgeVariants from badge.tsx
{
  default:     "border-transparent bg-primary text-primary-foreground",
  secondary:   "border-transparent bg-secondary text-secondary-foreground",
  destructive: "border-transparent bg-destructive text-white",
  outline:     "text-foreground",
}
```

Base: `inline-flex items-center justify-center rounded-md border px-2 py-0.5 text-xs font-medium`

---

## 12. UI Patterns

### Data Display Pattern

All numeric data follows this pattern:

1. Label: `text-[10–11px] uppercase tracking-wider text-muted-foreground`
2. Value: `.data-value {size} font-bold {color}`
3. Unit / context: `text-[10–11px] text-muted-foreground`

```tsx
<div className="flex justify-between">
  <span className="text-[10px] text-muted-foreground">24h High</span>
  <span className="data-value text-[10px] text-emerald">{formatPrice(ticker.highPrice)}</span>
</div>
```

### Status Indicator Pattern

Three-tier status using consistent color semantics:

```
NOMINAL → text-emerald + bg-emerald/10 + border-emerald/20 + ShieldCheck icon
WARNING → text-warning + bg-warning/10 + border-warning/20 + AlertTriangle icon
CRITICAL → text-destructive + bg-destructive/10 + border-destructive/20 + ShieldX icon
```

### Left-Accent Card Pattern

Used for cards that need regime or status color identity:

```tsx
<div className={`hud-card p-4 border-l-[3px] border-l-${color}`}>
  {/* content */}
</div>
```

### Confidence / Progress Bar Pattern

```tsx
{/* Track */}
<div className="w-full h-1.5 rounded-full bg-muted overflow-hidden">
  {/* Fill */}
  <div
    className={`h-full rounded-full transition-all duration-500 ${bgColor}`}
    style={{ width: `${pct}%` }}
  />
</div>
```

Heights: `h-1.5` (confidence bars), `h-2` (risk gauges)

### Volume Formatting

```typescript
ticker.quoteVolume >= 1e9
  ? `$${(ticker.quoteVolume / 1e9).toFixed(2)}B`
  : `$${(ticker.quoteVolume / 1e6).toFixed(1)}M`
```

### Live Badge

```tsx
<span className="flex items-center gap-1">
  <span className="w-2 h-2 rounded-full bg-emerald pulse-live" />
  <span className="text-[11px] font-bold text-emerald tracking-widest">LIVE</span>
</span>
```

---

## 13. Accessibility

### Current Implementation Notes

| Concern | Status | Detail |
|---------|--------|--------|
| Focus rings | Implemented | `outline-ring/50` global default; Radix components handle focus management |
| Color contrast | Partial | Emerald on navy-deep is primary palette — verify WCAG AA at production |
| ARIA on icons | Radix-managed | Lucide icons used as decorative (no explicit `aria-hidden` in all cases) |
| Keyboard navigation | Radix-handled | Dialog, Dropdown, Select, Tabs all use Radix keyboard patterns |
| Screen reader labels | Gap | Status badges and regime labels should have `aria-label` on icon-only states |
| Animation `prefers-reduced-motion` | Not implemented | `.pulse-live` and transitions do not check `prefers-reduced-motion` |

### Recommended Additions

```css
@media (prefers-reduced-motion: reduce) {
  .pulse-live { animation: none; }
  * { transition-duration: 0.01ms !important; }
}
```

```tsx
{/* Icon-only status badge */}
<ShieldCheck className="w-4 h-4 text-emerald" aria-label="Risk status: Nominal" />
```

---

## 14. Data Refresh Intervals

| Data Type | Hook | Interval |
|-----------|------|----------|
| Live prices | `api.getLivePrices` | 3,000ms |
| Risk gate | `api.getRiskGate` | 5,000ms |
| Regime states | `api.getRegimes` | 10,000ms |
| 24h ticker | `api.getTicker24h` | 30,000ms |

### `useApiData` Hook

```typescript
// Usage pattern
const { data, loading } = useApiData(api.getRegimes, { refreshInterval: 10000 });
```

Returns `{ data: T | null, loading: boolean }`. Polling via `refreshInterval` in milliseconds. Pass `loading` to `HudCard` for spinner display.

---

## Appendix A — Scrollbar Styles

```css
::-webkit-scrollbar        { width: 6px; height: 6px; }
::-webkit-scrollbar-track  { background: oklch(0.145 0.028 264.05); }
::-webkit-scrollbar-thumb  { background: oklch(0.3 0.015 264.05); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: oklch(0.4 0.015 264.05); }
```

---

## Appendix B — Icon Library

All icons from `lucide-react`. Consistent sizing conventions:

| Context | Size |
|---------|------|
| Page heading icons | `w-5 h-5` |
| Card header icons | `w-4 h-4` |
| Regime/signal icons | `w-3.5 h-3.5` (badge), `w-4 h-4` (summary) |
| Inline badge icons | `w-3 h-3` (sm), `w-3.5 h-3.5` (md) |
| Kill switch | `w-6 h-6` |
| Status bar | `w-3.5 h-3.5` |

---

## Appendix C — Engine API Quick Reference

**Base URL:** `http://localhost:8001`

| Endpoint | Component Consumer | Refresh |
|----------|-------------------|---------|
| `GET /regime/{symbol}` | RegimeState page | 10s |
| `GET /risk-gate` | RiskGate page | 5s |
| `GET /scan` | LiveScanner page | — |
| `GET /performance` | Performance page | — |
| `GET /journal` | TradeJournal page | — |
| `GET /position-size` | Positions page | — |

---

*This document reflects the dashboard codebase as of May 2026. Update when new components are promoted from page-embedded to shared status, or when tokens change in `index.css`.*
