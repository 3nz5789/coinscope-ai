# CoinScopeAI Dashboard

Production-quality frontend trading terminal for the CoinScopeAI crypto futures trading agent.

## Stack

- React 19 + TypeScript + Vite 7
- Tailwind CSS 4 dark trading-terminal design system
- Recharts for equity curve and P&L distribution charts
- shadcn/ui component primitives, Wouter routing, JetBrains Mono

## Pages

-  Overview
-  Live Scanner (3s refresh)
-  Positions (5s refresh)
-  Equity Curve with 7D/30D/90D selector
-  Performance Metrics + P&L distribution chart
-  Alpha Signals (5 generators)
-  Regime State
-  Trade Journal
-  Risk Gate
-  Recording Daemon

## API

Set  to connect to the live engine.
Set  in  to disable mock data.
Live prices always fetched from Binance public API.

## Dev


