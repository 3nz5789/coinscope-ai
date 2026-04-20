/**
 * React Query hooks over the engine REST client.
 *
 * All hooks set short stale times — the engine is local and data is cheap.
 * Most polling intervals match the dashboard's "live" feel: 5s for fast
 * stuff (positions, exposure, signals), 30s for heavier reports.
 */

import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "./client";

// ── Keys ────────────────────────────────────────────────────────────────
export const qk = {
  health:          ["engine", "health"] as const,
  config:          ["engine", "config"] as const,
  positions:       ["engine", "positions"] as const,
  exposure:        ["engine", "exposure"] as const,
  circuitBreaker:  ["engine", "circuit-breaker"] as const,
  signals:         ["engine", "signals"] as const,
  equityCurve:     ["engine", "performance", "equity"] as const,
  dailyPerformance:["engine", "performance", "daily"] as const,
  performance:     ["engine", "performance"] as const,
  journal:         ["engine", "journal"] as const,
  billingPlans:    ["engine", "billing", "plans"] as const,
  account:         ["engine", "account"] as const,
  accountBalance:  ["engine", "account", "balance"] as const,
  accountPositions:["engine", "account", "positions"] as const,
};

// ── Hooks (fast polling) ────────────────────────────────────────────────
export const useHealth          = () => useQuery({ queryKey: qk.health,          queryFn: api.health,          refetchInterval: 10_000 });
export const useConfig          = () => useQuery({ queryKey: qk.config,          queryFn: api.config,          staleTime: 60_000 });
export const usePositions       = () => useQuery({ queryKey: qk.positions,       queryFn: api.positions,       refetchInterval:  5_000 });
export const useExposure        = () => useQuery({ queryKey: qk.exposure,        queryFn: api.exposure,        refetchInterval:  5_000 });
export const useCircuitBreaker  = () => useQuery({ queryKey: qk.circuitBreaker,  queryFn: api.circuitBreaker,  refetchInterval: 10_000 });
export const useSignals         = () => useQuery({ queryKey: qk.signals,         queryFn: api.signals,         refetchInterval:  3_000 });

// ── Hooks (reports / heavier) ───────────────────────────────────────────
export const useEquityCurve      = () => useQuery({ queryKey: qk.equityCurve,      queryFn: api.equityCurve,      refetchInterval: 30_000 });
export const useDailyPerformance = () => useQuery({ queryKey: qk.dailyPerformance, queryFn: api.dailyPerformance, refetchInterval: 60_000 });
export const usePerformance      = () => useQuery({ queryKey: qk.performance,      queryFn: api.performance,      refetchInterval: 60_000 });
export const useJournal          = () => useQuery({ queryKey: qk.journal,          queryFn: api.journal,          refetchInterval: 30_000 });
export const useBillingPlans     = () => useQuery({ queryKey: qk.billingPlans,     queryFn: api.billingPlans,     staleTime: 5 * 60_000 });

// ── Live Binance account (pulled every 5–10s from the engine sync cache) ─
export const useAccount           = () => useQuery({ queryKey: qk.account,          queryFn: api.account,          refetchInterval:  5_000 });
export const useAccountBalance    = () => useQuery({ queryKey: qk.accountBalance,   queryFn: () => api.accountBalance({ only_non_zero: true }), refetchInterval: 10_000 });
export const useAccountPositions  = () => useQuery({ queryKey: qk.accountPositions, queryFn: api.accountPositions, refetchInterval:  5_000 });

// ── Live mark-price feed (WS-driven, polled from engine cache every 2s) ──
export const useLivePrices        = () => useQuery({ queryKey: ["engine", "prices"] as const, queryFn: api.prices,  refetchInterval: 2_000 });

// ── Mutations ───────────────────────────────────────────────────────────
export const useScan            = () => useMutation({ mutationFn: api.scan });
export const usePositionSize    = () => useMutation({ mutationFn: api.positionSize });
export const useBillingCheckout = () => useMutation({ mutationFn: api.billingCheckout });
export const useForceAccountSync = () => useMutation({ mutationFn: api.accountSync });

// ── Order placement (Phase 3b) ──────────────────────────────────────────
export const usePlaceOrder    = () => useMutation({ mutationFn: api.placeOrder });
export const useClosePosition = () => useMutation({ mutationFn: api.closePosition });
export const useAttachBracket = () => useMutation({ mutationFn: api.attachBracket });
export const useCancelOrder   = () => useMutation({ mutationFn: ({ id, symbol }: { id: number; symbol: string }) => api.cancelOrder(id, symbol) });

// Open Algo (SL/TP) orders — surfaced on the Positions page
export const useOpenAlgoOrders   = () => useQuery({ queryKey: ["engine","orders","algo","open"] as const, queryFn: api.openAlgoOrders, refetchInterval: 5_000 });

// Decision journal + per-symbol health
export const useDecisions        = (opts?: { symbol?: string; action?: string; limit?: number }) =>
  useQuery({ queryKey: ["engine","decisions",opts] as const, queryFn: () => api.decisions(opts), refetchInterval: 5_000 });
export const useDecisionStats    = (window_s = 24*3600) =>
  useQuery({ queryKey: ["engine","decisions","stats",window_s] as const, queryFn: () => api.decisionStats(window_s), refetchInterval: 15_000 });
export const useDecisionPerSymbol= () =>
  useQuery({ queryKey: ["engine","decisions","per-symbol"] as const, queryFn: api.decisionPerSymbol, refetchInterval: 5_000 });
export const useUnpauseSymbol    = () => useMutation({ mutationFn: api.unpauseSymbol });

// Per-trade provenance trace (journal entry + decisions in window + live algo orders)
export const useTradeTrace = (id: string | null) => useQuery({
  queryKey: ["engine","journal","trace", id] as const,
  queryFn:  () => api.tradeTrace(id!),
  enabled:  !!id,
  refetchInterval: 10_000,
});

// Historical klines store status
export const useHistoricalStats  = () =>
  useQuery({ queryKey: ["engine","historical","stats"] as const, queryFn: api.historicalStats, refetchInterval: 30_000 });
export const useHistoricalRefresh = () => useMutation({ mutationFn: api.historicalRefresh });

// Autotrade (Phase 3c) — polled every 3s so decisions show up fast
export const useAutotradeStatus  = () => useQuery({ queryKey: ["engine","autotrade","status"] as const, queryFn: api.autotradeStatus, refetchInterval: 3_000 });
export const useAutotradeEnable  = () => useMutation({ mutationFn: api.autotradeEnable });
export const useAutotradeDisable = () => useMutation({ mutationFn: api.autotradeDisable });
export const useAutotradeConfig  = () => useMutation({ mutationFn: api.autotradeConfig });

// Backtest (Phase 3f)
export const useBacktestList = () => useQuery({ queryKey: ["engine","backtest","jobs"] as const, queryFn: api.backtestList, refetchInterval: 3_000 });
export const useBacktestJob  = (id: string | null) => useQuery({
  queryKey: ["engine","backtest","job", id] as const,
  queryFn:  () => api.backtestGet(id!),
  enabled:  !!id,
  refetchInterval: (q: any) => {
    const status = q?.state?.data?.status;
    return status === "queued" || status === "running" ? 1_500 : false;
  },
});
export const useBacktestRun    = () => useMutation({ mutationFn: api.backtestRun });
export const useBacktestDelete = () => useMutation({ mutationFn: api.backtestDelete });
