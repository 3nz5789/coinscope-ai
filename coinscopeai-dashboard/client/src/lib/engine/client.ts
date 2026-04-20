/**
 * Thin wrapper around the CoinScopeAI engine REST API.
 *
 * Base URL comes from `VITE_ENGINE_URL` (default: http://127.0.0.1:8001).
 * All methods return the parsed JSON body; network/HTTP errors throw
 * with the response text attached as `.body` for debugging.
 */

import axios, { type AxiosInstance } from "axios";

export const ENGINE_URL =
  (import.meta.env.VITE_ENGINE_URL as string | undefined) ??
  "http://127.0.0.1:8001";

export const engine: AxiosInstance = axios.create({
  baseURL: ENGINE_URL,
  timeout: 15_000,
  headers: { "Content-Type": "application/json" },
});

// ─── Response shapes (match engine/openapi.json at 2026-04-19) ───────────
export interface HealthResp {
  status: string;
  version: string;
  testnet: boolean;
  timestamp: number;
}

export interface ConfigResp {
  testnet_mode: boolean;
  environment: string;
  scan_pairs: string[];
  scan_interval_s: number;
  min_confluence_score: number;
  risk_per_trade_pct: number;
  max_leverage: number;
  max_open_positions: number;
  max_position_size_pct: number;
  max_total_exposure_pct: number;
  max_daily_loss_pct: number;
}

export interface PositionsResp {
  balance: number;
  position_count: number;
  total_notional: number;
  total_exposure_pct: number;
  unrealised_pnl: number;
  realised_pnl: number;
  daily_pnl: number;
  daily_loss_pct: number;
  positions: Position[];
}
export interface Position {
  symbol: string;
  side: "LONG" | "SHORT";
  qty: number;
  entry_price: number;
  mark_price?: number;
  leverage: number;
  unrealised_pnl: number;
  liquidation_price?: number;
  margin_used?: number;
  stop_loss?: number;
  take_profit?: number;
  opened_at?: string;
}

export interface ExposureResp {
  balance: number;
  position_count: number;
  total_notional: number;
  total_exposure_pct: number;
  unrealised_pnl: number;
  realised_pnl: number;
  daily_pnl: number;
  daily_loss_pct: number;
  is_over_exposed: boolean;
  max_total_exposure_pct: number;
}

export interface CircuitBreakerResp {
  state: "CLOSED" | "OPEN" | "HALF_OPEN" | "TRIPPED";
  trip_count: number;
  last_trip: string | null;
  max_daily_loss_pct: number;
  max_drawdown_pct: number;
  max_consec_losses: number;
  timestamp: number;
}

export interface Signal {
  symbol: string;
  direction: "LONG" | "SHORT" | "NEUTRAL";
  score: number;
  strength: "STRONG" | "MEDIUM" | "WEAK";
  scanners: string[];
  reasons: string[];
  actionable: boolean;
  setup?: {
    entry: number;
    stop_loss: number;
    tp1: number;
    tp2: number;
    tp3: number;
    rr_ratio: number;
    valid: boolean;
    reason: string | null;
  };
  regime?: string;
  htf_trend?: "bull" | "bear" | "neutral";
  htf_agrees?: boolean;
  anomaly?: {
    detected: boolean;
    severity?: string;
    types?: string[];
  };
  indicators?: Record<string, unknown>;
  scanned_at: number;
}
export interface SignalsResp {
  signals: Signal[];
  timestamp?: number;
  count?: number;
  actionable?: number;
  last_scan_at?: number;
  age_s?: number | null;
  loop?: {
    running: boolean;
    scans_total: number;
    scans_failed: number;
    last_scan_at: number;
    next_scan_at: number;
    seconds_to_next: number | null;
    last_duration_ms: number;
    last_signals: number;
    last_actionable: number;
    last_error: string | null;
    interval_s: number;
  };
}
export interface ScanResp {
  scanned: number;
  actionable: number;
  signals: Signal[];
  timestamp: number;
}

export interface EquityPoint {
  ts?: string;
  date?: string;
  equity: number;
  drawdown?: number;
}
export interface EquityCurveResp {
  points: EquityPoint[];
  current_equity?: number;
  initial_capital?: number;
  timestamp?: number;
}

export interface DailyPnlPoint {
  date: string;
  pnl?: number;
  pnl_pct?: number;
  trades?: number;
  win_rate?: number;
}
export interface DailyPerformanceResp {
  days: DailyPnlPoint[];
  // Engine's current shape is a single-day summary, not a history:
  date?: string;
  trades?: number;
  timestamp?: number;
}

export interface PerformanceResp {
  // Present once trades exist.
  total_trades?: number;
  winning_trades?: number;
  losing_trades?: number;
  win_rate?: number;
  profit_factor?: number;
  sharpe_ratio?: number;
  max_drawdown_pct?: number;
  total_return_pct?: number;
  total_return?: number;
  avg_win?: number;
  avg_loss?: number;
  largest_win?: number;
  largest_loss?: number;
  avg_hold_time_hours?: number;
  consecutive_wins?: number;
  consecutive_losses?: number;
  // Engine also returns these regardless of trade state:
  initial_capital?: number;
  equity_curve?: EquityPoint[];
  scale_profile?: {
    current?: string;
    next_profile?: string;
    account_usd?: number;
    position_pct?: number;
    next_requires?: { trades?: number; sharpe?: number };
  };
  timestamp?: number;
}

export interface JournalEntry {
  id: string | number;
  symbol: string;
  side: "LONG" | "SHORT";
  entry_price: number;
  exit_price?: number;
  size?: number;
  qty?: number;
  leverage?: number;
  pnl?: number;
  pnl_pct?: number;
  entry_time?: string;
  exit_time?: string;
  duration_hours?: number;
  strategy?: string;
  notes?: string;
  status?: string;
}
export interface JournalResp {
  entries: JournalEntry[];
  count?: number;
}

export interface PositionSizeResp {
  symbol: string;
  direction: "LONG" | "SHORT";
  qty: number;
  notional: number;
  leverage: number;
  margin_usdt: number;
  risk_usdt: number;
  risk_pct: number;
  method: string;
  valid: boolean;
  reason: string | null;
  timestamp: number;
}

// ─── Live Binance Futures Demo account ───────────────────────────────────
export interface AccountResp {
  updated_at: number;
  age_s: number | null;
  error: string | null;
  can_trade: boolean;
  fee_tier: number | null;
  total_wallet_balance: number;
  total_margin_balance: number;
  available_balance: number;
  total_unrealized_pnl: number;
  total_position_notional: number;
  total_maint_margin: number;
  position_count: number;
}
export interface AccountBalanceRow {
  asset: string;
  balance: number;
  available_balance: number;
  cross_wallet: number;
  cross_unpnl: number;
  max_withdraw: number;
}
export interface AccountBalanceResp {
  updated_at: number;
  error: string | null;
  balances: AccountBalanceRow[];
}
export interface AccountPositionRow {
  symbol: string;
  position_side: string;
  position_amt: number;
  side: "LONG" | "SHORT";
  entry_price: number;
  mark_price: number;
  liquidation_price: number;
  leverage: number;
  margin_type: string | null;
  isolated_margin: number;
  unrealized_pnl: number;
  notional: number;
  update_time: number;
}
export interface AccountPositionsResp {
  updated_at: number;
  error: string | null;
  count: number;
  positions: AccountPositionRow[];
}

export interface BillingPlan {
  tier: string;
  name: string;
  description?: string;
  price_usd: number;
  price_id?: string;
  features?: string[];
}

export interface CheckoutReq {
  tier: string;
  cycle?: "monthly" | "annual";
  success_url?: string;
  cancel_url?: string;
  customer_email?: string;
}
export interface CheckoutResp {
  url?: string;
  session_id?: string;
  detail?: string;
}

// ─── Endpoint helpers ────────────────────────────────────────────────────
export const api = {
  health: () => engine.get<HealthResp>("/health").then(r => r.data),
  config: () => engine.get<ConfigResp>("/config").then(r => r.data),

  positions: () => engine.get<PositionsResp>("/positions").then(r => r.data),
  exposure:  () => engine.get<ExposureResp>("/exposure").then(r => r.data),
  circuitBreaker: () =>
    engine.get<CircuitBreakerResp>("/circuit-breaker").then(r => r.data),

  signals: () => engine.get<SignalsResp>("/signals").then(r => r.data),
  scan: (payload: { pairs?: string[]; timeframe?: string; limit?: number }) =>
    engine.post<ScanResp>("/scan", payload).then(r => r.data),

  equityCurve: () =>
    engine
      .get<any>("/performance/equity")
      .then((r): EquityCurveResp => {
        const data = r.data;
        if (Array.isArray(data)) return { points: data };
        // Engine returns { equity_curve: [...], current_equity, initial_capital }
        return {
          points: data?.equity_curve ?? data?.points ?? [],
          current_equity: data?.current_equity,
          initial_capital: data?.initial_capital,
          timestamp: data?.timestamp,
        };
      }),
  dailyPerformance: () =>
    engine
      .get<any>("/performance/daily")
      .then((r): DailyPerformanceResp => {
        const data = r.data;
        if (Array.isArray(data)) return { days: data };
        // If engine returns a single-day object, wrap into a 1-item list when it has a date
        if (data && typeof data === "object" && data.date) {
          return { days: [data as DailyPnlPoint], ...data };
        }
        return { days: data?.days ?? [], ...(data ?? {}) };
      }),
  performance: () =>
    engine.get<PerformanceResp>("/performance").then(r => r.data),

  journal: () =>
    engine
      .get<JournalResp | JournalEntry[]>("/journal")
      .then(r => (Array.isArray(r.data) ? { entries: r.data } : r.data)),

  positionSize: (params: {
    symbol: string;
    entry: number;
    stop_loss: number;
    balance: number;
    risk_pct?: number;
    leverage?: number;
  }) =>
    engine
      .get<PositionSizeResp>("/position-size", { params })
      .then(r => r.data),

  billingPlans: () =>
    engine
      .get<BillingPlan[] | { plans: BillingPlan[] }>("/billing/plans")
      .then(r => (Array.isArray(r.data) ? r.data : r.data.plans ?? [])),

  billingCheckout: (payload: CheckoutReq) =>
    engine.post<CheckoutResp>("/billing/checkout", payload).then(r => r.data),

  // Live Binance Futures Demo account (not the in-memory ExposureTracker)
  account:          () => engine.get<AccountResp>("/account").then(r => r.data),
  accountBalance:   (opts?: { only_non_zero?: boolean }) =>
    engine.get<AccountBalanceResp>("/account/balance", { params: opts }).then(r => r.data),
  accountPositions: () => engine.get<AccountPositionsResp>("/account/positions").then(r => r.data),
  accountSync:      () => engine.post("/account/sync").then(r => r.data),

  // Live WS-fed mark prices (demo-fstream markPrice@1s)
  prices:           () => engine.get<PricesResp>("/prices").then(r => r.data),

  // Decision journal (invariant #5)
  decisions:          (opts?: { symbol?: string; action?: string; limit?: number }) =>
    engine.get<{ decisions: any[]; count: number }>("/decisions", { params: opts }).then(r => r.data),
  decisionStats:      (window_s: number = 24*3600) =>
    engine.get("/decisions/stats", { params: { window_s } }).then(r => r.data),
  decisionPerSymbol:  () =>
    engine.get<{ symbols: Record<string, any> }>("/decisions/per-symbol").then(r => r.data),
  unpauseSymbol:      (symbol: string) =>
    engine.post(`/decisions/unpause/${symbol}`).then(r => r.data),

  // Historical klines store
  historicalStats:    () => engine.get("/historical/stats").then(r => r.data),
  tradeTrace:         (id: string) => engine.get(`/journal/${encodeURIComponent(id)}/trace`).then(r => r.data),
  historicalBackfill: (lookback_days = 90) =>
    engine.post("/historical/backfill", null, { params: { lookback_days } }).then(r => r.data),
  historicalRefresh:  () => engine.post("/historical/refresh").then(r => r.data),

  // Orders — Phase 3b manual placement
  placeOrder:       (payload: PlaceOrderReq) => engine.post<PlaceOrderResp>("/orders", payload).then(r => r.data),
  closePosition:    (payload: { symbol: string; qty?: number }) =>
    engine.post("/orders/close", payload).then(r => r.data),
  attachBracket:    (payload: { symbol: string; side: "BUY"|"SELL"; stop_price?: number; tp_price?: number; qty?: number }) =>
    engine.post("/orders/bracket", payload).then(r => r.data),
  openOrders:       (symbol?: string) =>
    engine.get<{ orders: any[]; count: number }>("/orders/open", { params: symbol ? { symbol } : {} }).then(r => r.data),
  cancelOrder:      (id: number, symbol: string) =>
    engine.delete(`/orders/${id}`, { params: { symbol } }).then(r => r.data),
  cancelAll:        (symbol: string) =>
    engine.delete("/orders", { params: { symbol } }).then(r => r.data),
  openAlgoOrders:   () =>
    engine.get<{ orders: any[]; count: number }>("/orders/algo/open").then(r => r.data),

  // Autotrade (Phase 3c)
  autotradeStatus:  () => engine.get<AutotradeStatus>("/autotrade/status").then(r => r.data),
  autotradeEnable:  () => engine.post("/autotrade/enable").then(r => r.data),
  autotradeDisable: () => engine.post("/autotrade/disable").then(r => r.data),
  autotradeConfig:  (payload: AutotradeConfigReq) =>
    engine.post("/autotrade/config", payload).then(r => r.data),

  // Backtest (Phase 3f)
  backtestRun:  (payload: BacktestRunReq) => engine.post<{ job_id: string; status: string }>("/backtest/run", payload).then(r => r.data),
  backtestList: () => engine.get<BacktestJobList>("/backtest/jobs").then(r => r.data),
  backtestGet:  (id: string) => engine.get<BacktestJob>(`/backtest/jobs/${id}`).then(r => r.data),
  backtestDelete: (id: string) => engine.delete(`/backtest/jobs/${id}`).then(r => r.data),
};

export interface BacktestRunReq {
  pairs?: string[];
  timeframe?: string;
  lookback_days?: number;
  initial_balance?: number;
  risk_per_trade_pct?: number;
  min_confluence_score?: number;
  commission_pct?: number;
  slippage_pct?: number;
  atr_sl_mult?: number;
  atr_tp1_mult?: number;
  atr_tp2_mult?: number;
  atr_tp3_mult?: number;
  min_rr?: number;
  allowed_directions?: "BOTH" | "LONG_ONLY" | "SHORT_ONLY";
  mtf_filter_enabled?: boolean;
  mtf_block_neutral?:  boolean;
  mtf_htf_timeframe?: string;
}
export interface BacktestSummary {
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  avg_win_pct: number;
  avg_loss_pct: number;
  profit_factor: number;
  total_pnl_usdt: number;
  final_balance: number;
  total_return_pct: number;
  max_drawdown_pct: number;
  sharpe_ratio: number;
  avg_rr_achieved: number;
}
export interface BacktestTrade {
  symbol: string;
  direction: string;
  entry_price: number;
  stop_loss: number;
  tp1: number;
  tp2: number;
  signal_score: number;
  entry_bar: number;
  exit_bar: number;
  exit_price: number;
  exit_reason: string;
  pnl_pct: number;
  pnl_usdt: number;
  risk_usdt: number;
  rr_achieved: number;
  is_winner: boolean;
  bars_held: number;
}
export interface BacktestJob {
  job_id: string;
  status: "queued" | "running" | "done" | "error";
  created_at: number;
  started_at: number | null;
  finished_at: number | null;
  request: BacktestRunReq;
  error: string | null;
  results: null | {
    config: BacktestRunReq & { symbols: string[] };
    summary: BacktestSummary;
    equity_curve: number[];
    trades: BacktestTrade[];
  };
}
export interface BacktestJobList {
  jobs: Array<Omit<BacktestJob, "results"> & { summary: BacktestSummary | null }>;
  count: number;
}

export interface PlaceOrderReq {
  symbol: string;
  side: "BUY" | "SELL";
  type?: "MARKET" | "LIMIT";
  qty: number;
  price?: number;
  tif?: "GTC" | "IOC" | "FOK" | "GTX";
  reduce_only?: boolean;
  leverage?: number;
  client_id?: string;
}
export interface PlaceOrderResp {
  order: {
    orderId: number;
    symbol: string;
    status: string;
    clientOrderId: string;
    origQty: string;
    executedQty: string;
    avgPrice: string;
    price: string;
    side: string;
    type: string;
    updateTime: number;
  };
  client_id: string;
  leverage_change?: any;
}

export interface PriceRow {
  symbol: string;
  mark_price: number;
  index_price: number;
  funding_rate: number;
  next_funding_ts: number;
  ts: number;
  age_s: number | null;
}
export interface PricesResp {
  feed: {
    connected: boolean;
    reconnects: number;
    last_msg_at: number;
    last_msg_age_s: number | null;
    error: string | null;
  };
  prices: PriceRow[];
  count: number;
}

// ─── Autotrade (Phase 3c) ────────────────────────────────────────────────
export interface AutotradeEvent {
  ts: number;
  symbol: string;
  action: string;
  reason?: string;
  side?: string;
  qty?: number;
  score?: number;
  entry?: number;
  sl?: number;
  tp?: number;
  order_id?: number;
}
export interface AutotradeStatus {
  enabled: boolean;
  started_at: number | null;
  entries_total: number;
  entries_rejected: number;
  last_entry_at: number;
  last_reject_reason: string | null;
  recent_events: AutotradeEvent[];
  risk_per_trade_pct: number | null;
  default_leverage: number;
  attach_bracket: boolean;
  min_score: number | null;
  cooldown_s: number;
  allowed_directions: "BOTH" | "LONG_ONLY" | "SHORT_ONLY";
  mtf_filter_enabled: boolean;
  mtf_block_neutral:  boolean;
  effective_min_score: number;
  effective_risk_pct: number;
}
export interface AutotradeConfigReq {
  risk_per_trade_pct?: number;
  default_leverage?: number;
  attach_bracket?: boolean;
  min_score?: number;
  cooldown_s?: number;
  allowed_directions?: "BOTH" | "LONG_ONLY" | "SHORT_ONLY";
  mtf_filter_enabled?: boolean;
  mtf_block_neutral?:  boolean;
}
