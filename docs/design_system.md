# CoinScopeAI Design System

**Author:** Manus AI
**Date:** April 6, 2026

This document outlines the design system for the CoinScopeAI web dashboard. It defines the visual language, typography, color palette, and UI/UX principles to ensure a consistent and professional user experience.

## 1. Design Philosophy

The CoinScopeAI dashboard is designed for professional traders and quantitative analysts. The interface must be clean, data-dense, and highly responsive. The primary goal is to present complex trading data, risk metrics, and AI insights in a clear, actionable format without overwhelming the user.

*   **Data-Driven:** The UI prioritizes the display of real-time market data, performance charts, and risk indicators.
*   **Dark Mode First:** Given the nature of trading environments, the default theme is a sophisticated dark mode to reduce eye strain during extended use.
*   **Clarity over Clutter:** Complex information is organized into logical sections (Dashboard, Trading, Risk, Journal) with clear visual hierarchy.
*   **Actionable Insights:** AI-driven recommendations (e.g., regime changes, position sizing) are highlighted prominently to facilitate quick decision-making.

## 2. Color Palette

The color palette is designed to convey trust, precision, and the dynamic nature of cryptocurrency markets.

| Color Name | Hex Code | Usage |
| :--- | :--- | :--- |
| **Primary Background** | `#0F172A` (Slate 900) | Main application background, providing deep contrast for data visualization. |
| **Secondary Background** | `#1E293B` (Slate 800) | Card backgrounds, sidebar, and modal overlays. |
| **Accent Primary** | `#3B82F6` (Blue 500) | Primary buttons, active states, and key data highlights. |
| **Accent Secondary** | `#8B5CF6` (Violet 500) | AI insights, regime indicators, and secondary actions. |
| **Success (Long/Profit)** | `#10B981` (Emerald 500) | Positive PnL, "Long" signals, successful risk checks. |
| **Danger (Short/Loss)** | `#EF4444` (Red 500) | Negative PnL, "Short" signals, risk warnings, stop-loss indicators. |
| **Warning** | `#F59E0B` (Amber 500) | Cautionary alerts, approaching risk limits, neutral market regimes. |
| **Text Primary** | `#F8FAFC` (Slate 50) | Main body text, headings, and primary data points. |
| **Text Secondary** | `#94A3B8` (Slate 400) | Subtitles, labels, disabled states, and secondary information. |
| **Border/Divider** | `#334155` (Slate 700) | Separators between sections, table borders, and input outlines. |

## 3. Typography

The typography system uses a clean, modern sans-serif font optimized for readability on digital screens, particularly for numerical data.

*   **Primary Font Family:** Inter (or similar modern sans-serif like Roboto or SF Pro).
*   **Monospace Font:** JetBrains Mono (or Fira Code) for displaying code snippets, API keys, and precise numerical data (e.g., prices, percentages).

### 3.1 Font Sizes and Weights

| Element | Size | Weight | Usage |
| :--- | :--- | :--- | :--- |
| **Heading 1 (H1)** | 2.25rem (36px) | Bold (700) | Page titles (e.g., "Dashboard", "Risk Management"). |
| **Heading 2 (H2)** | 1.875rem (30px) | Semi-Bold (600) | Section headers within pages. |
| **Heading 3 (H3)** | 1.5rem (24px) | Medium (500) | Card titles, widget headers. |
| **Body Large** | 1.125rem (18px) | Regular (400) | Introductory text, prominent data labels. |
| **Body Default** | 1rem (16px) | Regular (400) | Standard paragraph text, table data. |
| **Body Small** | 0.875rem (14px) | Regular (400) | Secondary labels, timestamps, minor annotations. |
| **Data Highlight** | 2rem (32px) | Bold (700) | Key metrics (e.g., Total PnL, Win Rate) displayed in widgets. |

## 4. UI Components

The dashboard relies on a set of reusable UI components to maintain consistency.

*   **Cards:** Used to group related information (e.g., a specific trading signal, a performance metric). Cards have a subtle border (`#334155`) and a slightly lighter background (`#1E293B`) than the main canvas.
*   **Buttons:** Primary actions use the Accent Primary color (`#3B82F6`). Secondary actions use a transparent background with a border. Destructive actions use the Danger color (`#EF4444`).
*   **Badges/Tags:** Small, rounded indicators used for status (e.g., "Open", "Closed"), signal direction ("Long", "Short"), or market regime ("Trending Up"). They utilize the Success, Danger, or Warning colors with a low-opacity background.
*   **Tables:** Data-heavy views (e.g., Trade Journal, Signal List) use clean tables with alternating row colors (zebra striping) for readability. Headers are sticky, and columns are sortable.
*   **Charts:** Interactive charts (using libraries like Recharts or TradingView Lightweight Charts) are central to the experience. They must support zooming, panning, and tooltips. Colors within charts align with the Success/Danger palette for price action and Accent colors for indicators.

## 5. Dashboard Layout Wireframe

The layout is designed for a desktop-first experience, maximizing screen real estate for data visualization.

### 5.1 Global Structure

*   **Sidebar (Left, Fixed):** Contains navigation links to main sections: Dashboard, Trading Signals, Trade Journal, Performance Analytics, Risk Management, and Settings. It also displays a minimized summary of the current account balance and overall risk status.
*   **Top Bar (Fixed):** Displays the current system status (e.g., "Engine Running", "API Connected"), a global search bar (for symbols or trade IDs), and user profile/notification icons.
*   **Main Content Area:** The dynamic area where the selected page content is rendered.

### 5.2 Key Screens

#### 5.2.1 Main Dashboard
The central hub providing a high-level overview of the system's health and performance.
*   **Top Row (Widgets):** Key metrics: Total PnL (24h/All-time), Win Rate, Current Drawdown, and Active Risk Level.
*   **Middle Section (Charts):** A prominent Equity Curve chart showing account growth over time, alongside a smaller chart displaying recent PnL distribution.
*   **Bottom Section (Split View):**
    *   *Left:* "Active Signals" table, showing the top 5 highest-scoring current trading opportunities.
    *   *Right:* "Recent Trades" list, summarizing the outcomes of the last 5 closed positions.

#### 5.2.2 Trading Signals View
A detailed view of all current market opportunities identified by the AI engine.
*   **Filters:** Options to filter signals by symbol, direction (Long/Short), minimum score, and timeframe.
*   **Signal Table:** A comprehensive list of signals, including Symbol, Score, Direction, Current Price, Key Indicators (RSI, MACD), and the AI-detected Market Regime.
*   **Detail Panel (On Click):** Clicking a row opens a side panel with a detailed chart for that symbol, the specific rationale for the signal, and a pre-calculated position sizing recommendation based on current risk settings.

#### 5.2.3 Risk Management Console
The control center for monitoring and adjusting the system's risk parameters.
*   **Risk Gate Status:** A prominent visual indicator (e.g., a traffic light system) showing whether trading is currently allowed, blocked, or restricted based on drawdown limits.
*   **Portfolio Heatmap:** A visual representation of current exposure across different assets, highlighting any over-concentration.
*   **Drawdown Monitor:** A chart tracking current drawdown against predefined limits (daily, weekly, maximum).
*   **Parameter Controls:** Input fields to adjust risk tolerance (e.g., "Risk per Trade %", "Max Daily Drawdown %"), requiring confirmation before applying changes to the engine.
