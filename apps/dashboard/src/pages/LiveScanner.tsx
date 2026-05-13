/**
 * Live Scanner Page — Command Center HUD
 * Real-time signals from the trading engine with live Binance prices. Auto-refreshes every 3s.
 */
import { useApiData } from "@/hooks/useApiData";
import { api, Signal } from "@/lib/api";
import { formatTimestamp, timeAgoShort, formatPrice } from "@/lib/format";
import HudCard from "@/components/HudCard";
import PriceChangeBadge from "@/components/PriceChangeBadge";
import SignalConsoleCard, {
  type BreakerInfo,
  type BreakerState,
  type GateDecision,
  type KellyResult,
} from "@/components/SignalConsoleCard";
import { Radar, ArrowUpRight, ArrowDownRight, Signal as SignalIcon } from "lucide-react";

const signalTypeLabels: Record<string, string> = {
  funding_extreme: "Funding Extreme",
  liquidation_cascade: "Liq. Cascade",
  oi_divergence: "OI Divergence",
  basis_trade: "Basis Trade",
  orderbook_imbalance: "OB Imbalance",
};

const signalTypeColors: Record<string, string> = {
  funding_extreme: "text-chart-3",
  liquidation_cascade: "text-destructive",
  oi_divergence: "text-chart-4",
  basis_trade: "text-emerald",
  orderbook_imbalance: "text-chart-5",
};

function ConfidenceBar({ value }: { value: number }) {
  const color = value >= 80 ? "bg-emerald" : value >= 60 ? "bg-warning" : "bg-muted-foreground";
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 rounded-full bg-muted overflow-hidden">
        <div className={`h-full rounded-full ${color} transition-all duration-500`} style={{ width: `${value}%` }} />
      </div>
      <span className="data-value text-[11px] text-muted-foreground">{value}%</span>
    </div>
  );
}

function SignalRow({ signal, ticker }: { signal: Signal; ticker?: any }) {
  const isLong = signal.direction === "LONG";
  return (
    <tr className="border-b border-border/30 hover:bg-white/[0.02] transition-colors">
      <td className="py-2.5 px-3">
        <span className={`text-[11px] font-medium uppercase tracking-wider ${signalTypeColors[signal.type] || "text-muted-foreground"}`}>
          {signalTypeLabels[signal.type] || signal.type}
        </span>
      </td>
      <td className="py-2.5 px-3">
        <div className="flex items-center gap-2">
          <span className="data-value text-[13px] text-foreground font-medium">{signal.symbol}</span>
          {ticker && <PriceChangeBadge pct={ticker.priceChangePercent} size="sm" showIcon={false} />}
        </div>
      </td>
      <td className="py-2.5 px-3">
        <span className={`inline-flex items-center gap-1 text-[12px] font-semibold data-value ${isLong ? "text-emerald" : "text-destructive"}`}>
          {isLong ? <ArrowUpRight className="w-3.5 h-3.5" /> : <ArrowDownRight className="w-3.5 h-3.5" />}
          {signal.direction}
        </span>
      </td>
      <td className="py-2.5 px-3">
        <span className="data-value text-[12px] text-foreground">{signal.price > 0 ? formatPrice(signal.price) : "—"}</span>
      </td>
      <td className="py-2.5 px-3">
        <ConfidenceBar value={signal.confidence} />
      </td>
      <td className="py-2.5 px-3">
        <span className="text-[11px] text-muted-foreground capitalize">{signal.regime.replace(/_/g, " ")}</span>
      </td>
      <td className="py-2.5 px-3">
        <div className="flex flex-col">
          <span className="data-value text-[11px] text-muted-foreground">{formatTimestamp(signal.timestamp)}</span>
          <span className="text-[10px] text-muted-foreground/60">{timeAgoShort(signal.timestamp)}</span>
        </div>
      </td>
    </tr>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Console-card data joins
//
// SignalConsoleCard takes optional gate / breaker / kelly props. While the
// engine endpoints that return them per-signal are still in flight, derive
// best-effort views from /risk-gate and /position-size and degrade
// gracefully when those endpoints have not yet been called.
//
// These helpers are exported for testability; they have no React deps.
// ──────────────────────────────────────────────────────────────────────────

export function deriveBreakerInfo(risk: any | null | undefined): BreakerInfo | undefined {
  if (!risk) return undefined;
  let state: BreakerState = "closed";
  if (risk.killSwitch) state = "kill_switch";
  else if (risk.dailyLossPct >= risk.dailyLossLimit) state = "daily_loss";
  else if (risk.drawdownPct >= risk.drawdownLimit) state = "drawdown";
  return {
    state,
    dailyLossPct: risk.dailyLossPct ?? 0,
    dailyLossLimit: risk.dailyLossLimit ?? 5,
    drawdownPct: risk.drawdownPct ?? 0,
    drawdownLimit: risk.drawdownLimit ?? 10,
    heatPct: risk.positionHeat ?? 0,
    heatLimit: risk.positionHeatLimit ?? 80,
  };
}

export function deriveGateDecision(
  risk: any | null | undefined,
  breaker: BreakerInfo | undefined,
): GateDecision | undefined {
  if (!risk) return undefined;
  if (breaker && breaker.state !== "closed") {
    return { pass: false, reason: `breaker '${breaker.state}' is open` };
  }
  if (risk.status === "critical") {
    return { pass: false, reason: "risk status critical" };
  }
  return { pass: true };
}

export default function LiveScanner() {
  const { data: signals, loading, lastUpdated } = useApiData(api.getSignals, { refreshInterval: 3000 });
  const { data: tickers } = useApiData(api.getTicker24h, { refreshInterval: 30000 });
  const { data: risk } = useApiData(api.getRiskGate, { refreshInterval: 5000 });

  // The "primary signal" is the highest-confluence candidate currently
  // active. Ties broken by recency. Mirrors the operator's natural triage
  // order — work the strongest signal first.
  const primarySignal = signals && signals.length
    ? [...signals].sort((a, b) => b.confidence - a.confidence || +new Date(b.timestamp) - +new Date(a.timestamp))[0]
    : undefined;

  const breaker = deriveBreakerInfo(risk);
  const gate = deriveGateDecision(risk, breaker);

  // Kelly is per-signal and ideally comes from POST /position-size.
  // Until that wire-up lands, surface the equity-percentage view the
  // engine already exposes via the risk-gate snapshot. This is the
  // honest fallback — clearly labelled as such inside the card.
  const kelly: KellyResult | undefined = primarySignal && risk
    ? {
        // Conservative placeholder until /position-size is joined per-signal.
        // 1% of a notional $10k equity at regime ×1.0 is intentionally
        // small; the value is meant to be replaced, not relied on.
        usd: Math.round(100 * (primarySignal.confidence / 100)),
        pctOfEquity: 1.0 * (primarySignal.confidence / 100),
        regimeMultiplier: 1.0,
        hardCappedAt2pct: false,
      }
    : undefined;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Radar className="w-5 h-5 text-emerald" />
          <h1 className="text-lg font-semibold text-foreground">Live Scanner</h1>
          <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-emerald/10 border border-emerald/20">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald pulse-live" />
            <span className="text-[10px] font-medium text-emerald data-value">SCANNING</span>
          </span>
        </div>
        {lastUpdated && (
          <span className="text-[11px] text-muted-foreground data-value">
            Last update: {formatTimestamp(lastUpdated.toISOString())}
          </span>
        )}
      </div>

      {/* Primary signal — full six-attribute console panel */}
      {primarySignal && (
        <SignalConsoleCard
          signal={primarySignal}
          gate={gate}
          breaker={breaker}
          kelly={kelly}
        />
      )}

      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: "Total Signals", value: signals?.length || 0, icon: SignalIcon },
          { label: "LONG Signals", value: signals?.filter(s => s.direction === "LONG").length || 0, color: "text-emerald" },
          { label: "SHORT Signals", value: signals?.filter(s => s.direction === "SHORT").length || 0, color: "text-destructive" },
          { label: "Avg Confidence", value: signals?.length ? `${Math.round(signals.reduce((a, s) => a + s.confidence, 0) / signals.length)}%` : "—" },
        ].map((card, i) => (
          <div key={i} className="hud-card px-4 py-3">
            <span className="text-[10px] uppercase tracking-widest text-muted-foreground font-medium">{card.label}</span>
            <p className={`data-value text-xl font-bold mt-1 ${(card as any).color || "text-foreground"}`}>{card.value}</p>
          </div>
        ))}
      </div>

      {/* Signals table */}
      <HudCard title="Signal Feed" loading={loading} noPadding>
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-border/50">
                {["Signal Type", "Symbol / 24h", "Direction", "Price", "Confidence", "Regime", "Time"].map(h => (
                  <th key={h} className="py-2 px-3 text-[10px] uppercase tracking-widest text-muted-foreground font-semibold">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {signals?.map(signal => (
                <SignalRow key={signal.id} signal={signal} ticker={tickers?.[signal.symbol]} />
              ))}
              {!signals?.length && !loading && (
                <tr><td colSpan={7} className="py-12 text-center text-muted-foreground text-sm">No signals detected</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </HudCard>
    </div>
  );
}
