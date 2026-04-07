/**
 * Overview Page — Command Center HUD
 * Single-screen at-a-glance dashboard combining all critical widgets.
 * Design: Military-grade HUD, information-dense, emerald accent on deep navy.
 */
import { useApiData } from "@/hooks/useApiData";
import { api } from "@/lib/api";
import { formatCurrency, formatPrice, formatPct, timeAgoShort } from "@/lib/format";
import HudCard from "@/components/HudCard";
import PriceChangeBadge from "@/components/PriceChangeBadge";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import {
  LayoutDashboard, ArrowUpRight, ArrowDownRight, Shield, ShieldAlert, ShieldX,
  TrendingUp, TrendingDown, Minus, Zap, Activity, Radar, BarChart3,
} from "lucide-react";
import { Link } from "wouter";

// ─── Mini Equity Chart ────────────────────────────────────────────────

function MiniEquityTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="hud-card px-2 py-1 border border-border/50 text-[11px]">
      <span className="data-value text-emerald">${(payload[0].value / 1000).toFixed(1)}K</span>
    </div>
  );
}

// ─── Metric Card ─────────────────────────────────────────────────────

function MetricCard({ label, value, sub, color = "text-foreground", icon: Icon }: {
  label: string; value: string; sub?: string; color?: string;
  icon?: React.ComponentType<{ className?: string }>;
}) {
  return (
    <div className="hud-card px-4 py-3">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] uppercase tracking-widest text-muted-foreground font-medium">{label}</span>
        {Icon && <Icon className={`w-3.5 h-3.5 ${color}`} />}
      </div>
      <p className={`data-value text-xl font-bold ${color}`}>{value}</p>
      {sub && <p className="text-[10px] text-muted-foreground mt-0.5 data-value">{sub}</p>}
    </div>
  );
}

// ─── Risk Status Widget ───────────────────────────────────────────────

function RiskWidget({ risk }: { risk: any }) {
  if (!risk) return null;
  const RiskIcon = risk.status === "critical" ? ShieldX : risk.status === "warning" ? ShieldAlert : Shield;
  const riskColor = risk.status === "critical" ? "text-destructive" : risk.status === "warning" ? "text-warning" : "text-emerald";
  const riskBg = risk.status === "critical" ? "border-destructive/30 bg-destructive/5" : risk.status === "warning" ? "border-warning/30 bg-warning/5" : "border-emerald/30 bg-emerald/5";

  const gauges = [
    { label: "Daily Loss", value: risk.dailyLossPct, limit: risk.dailyLossLimit },
    { label: "Drawdown", value: risk.drawdownPct, limit: risk.drawdownLimit },
    { label: "Position Heat", value: risk.positionHeat, limit: risk.positionHeatLimit },
    { label: "Leverage", value: risk.currentLeverage, limit: risk.maxLeverage },
  ];

  return (
    <div className={`hud-card p-4 border ${riskBg}`}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-[10px] uppercase tracking-widest text-muted-foreground font-medium">Risk Gate</span>
        <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-semibold data-value ${riskColor}`}>
          <RiskIcon className="w-3.5 h-3.5" />
          {risk.status.toUpperCase()}
        </span>
      </div>
      <div className="space-y-2">
        {gauges.map((g) => {
          const ratio = Math.min(g.value / g.limit, 1);
          const barColor = ratio > 0.7 ? "bg-destructive" : ratio > 0.4 ? "bg-warning" : "bg-emerald";
          return (
            <div key={g.label}>
              <div className="flex justify-between text-[10px] mb-0.5">
                <span className="text-muted-foreground">{g.label}</span>
                <span className="data-value text-foreground">{g.value.toFixed(1)}<span className="text-muted-foreground">/{g.limit}</span></span>
              </div>
              <div className="w-full h-1 rounded-full bg-muted overflow-hidden">
                <div className={`h-full rounded-full transition-all duration-500 ${barColor}`} style={{ width: `${ratio * 100}%` }} />
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-3 pt-2 border-t border-border/30 flex items-center justify-between">
        <span className="text-[10px] text-muted-foreground">Kill Switch</span>
        <span className={`text-[11px] font-semibold data-value ${risk.killSwitch ? "text-destructive" : "text-emerald"}`}>
          {risk.killSwitch ? "ARMED" : "DISARMED"}
        </span>
      </div>
    </div>
  );
}

// ─── Signal Row (compact) ─────────────────────────────────────────────

function SignalRowCompact({ signal }: { signal: any }) {
  const isLong = signal.direction === "LONG";
  return (
    <div className="flex items-center justify-between py-2 border-b border-border/20 last:border-0">
      <div className="flex items-center gap-2 min-w-0">
        <span className={`inline-flex items-center gap-0.5 text-[11px] font-semibold shrink-0 ${isLong ? "text-emerald" : "text-destructive"}`}>
          {isLong ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
          {signal.direction}
        </span>
        <span className="data-value text-[12px] text-foreground font-medium truncate">{signal.symbol}</span>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <span className="text-[10px] text-muted-foreground capitalize hidden sm:block">{signal.type.replace(/_/g, " ")}</span>
        <div className="flex items-center gap-1">
          <div className="w-10 h-1 rounded-full bg-muted overflow-hidden">
            <div
              className={`h-full rounded-full ${signal.confidence >= 80 ? "bg-emerald" : signal.confidence >= 60 ? "bg-warning" : "bg-muted-foreground"}`}
              style={{ width: `${signal.confidence}%` }}
            />
          </div>
          <span className="data-value text-[10px] text-muted-foreground w-7 text-right">{signal.confidence}%</span>
        </div>
      </div>
    </div>
  );
}

// ─── Position Row (compact) ───────────────────────────────────────────

function PositionRowCompact({ pos }: { pos: any }) {
  const isProfit = pos.unrealizedPnl >= 0;
  const isLong = pos.direction === "LONG";
  return (
    <div className="flex items-center justify-between py-2 border-b border-border/20 last:border-0">
      <div className="flex items-center gap-2">
        <span className={`text-[10px] font-semibold px-1 py-0.5 rounded ${isLong ? "bg-emerald/10 text-emerald" : "bg-destructive/10 text-destructive"}`}>
          {pos.direction}
        </span>
        <span className="data-value text-[12px] font-medium text-foreground">{pos.symbol}</span>
        <span className="text-[10px] text-warning data-value">{pos.leverage}x</span>
      </div>
      <div className="flex items-center gap-3">
        <span className="data-value text-[11px] text-muted-foreground hidden sm:block">{formatPrice(pos.currentPrice)}</span>
        <span className={`data-value text-[12px] font-semibold ${isProfit ? "text-emerald" : "text-destructive"}`}>
          {formatCurrency(pos.unrealizedPnl)}
        </span>
      </div>
    </div>
  );
}

// ─── Ticker Row ───────────────────────────────────────────────────────

function TickerRow({ symbol, price, ticker }: { symbol: string; price: number; ticker?: any }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-border/20 last:border-0">
      <span className="data-value text-[12px] font-medium text-foreground">{symbol}</span>
      <div className="flex items-center gap-2">
        <span className="data-value text-[12px] text-foreground">{formatPrice(price)}</span>
        {ticker ? (
          <PriceChangeBadge pct={ticker.priceChangePercent} size="sm" showIcon={false} />
        ) : (
          <span className="text-[10px] text-muted-foreground">—</span>
        )}
      </div>
    </div>
  );
}

// ─── Regime Badge (compact) ───────────────────────────────────────────

const regimeConfig: Record<string, { label: string; color: string; icon: React.ComponentType<{ className?: string }> }> = {
  trending_up: { label: "Trending ↑", color: "text-emerald", icon: TrendingUp },
  trending_down: { label: "Trending ↓", color: "text-destructive", icon: TrendingDown },
  ranging: { label: "Ranging", color: "text-blue-400", icon: Minus },
  volatile: { label: "Volatile", color: "text-warning", icon: Zap },
};

// ─── Main Overview Page ───────────────────────────────────────────────

export default function Overview() {
  const { data: perf, loading: perfLoading } = useApiData(api.getPerformance, { refreshInterval: 30000 });
  const { data: positions, loading: posLoading } = useApiData(api.getPositions, { refreshInterval: 5000 });
  const { data: signals, loading: sigLoading } = useApiData(api.getSignals, { refreshInterval: 3000 });
  const { data: risk } = useApiData(api.getRiskGate, { refreshInterval: 10000 });
  const { data: regimes } = useApiData(api.getRegimes, { refreshInterval: 10000 });
  const { data: tickers } = useApiData(api.getTicker24h, { refreshInterval: 30000 });
  const { data: prices } = useApiData(api.getLivePrices, { refreshInterval: 3000 });

  // Equity chart data (last 30 days for mini chart)
  const chartData = perf?.equityCurve
    .slice(-30)
    .map(p => ({
      date: new Date(p.timestamp).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
      value: p.value,
    })) || [];

  const currentValue = chartData.length ? chartData[chartData.length - 1].value : 0;
  const startValue = chartData.length ? chartData[0].value : 0;
  const changePct = startValue ? ((currentValue - startValue) / startValue) * 100 : 0;

  const totalPnl = positions?.reduce((a, p) => a + p.unrealizedPnl, 0) || 0;
  const topSignals = signals?.slice(0, 6) || [];
  const topPositions = positions?.slice(0, 5) || [];

  const DISPLAY_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT", "AVAXUSDT", "ADAUSDT"];

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <LayoutDashboard className="w-5 h-5 text-emerald" />
          <h1 className="text-lg font-semibold text-foreground">Overview</h1>
          <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-emerald/10 border border-emerald/20">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald pulse-live" />
            <span className="text-[10px] font-medium text-emerald data-value">LIVE</span>
          </span>
        </div>
        <span className="text-[11px] text-muted-foreground data-value">
          {new Date().toLocaleString("en-US", { weekday: "short", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false })} UTC
        </span>
      </div>

      {/* Top KPI Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <MetricCard
          label="Portfolio Value"
          value={`$${(currentValue / 1000).toFixed(1)}K`}
          sub={`${changePct >= 0 ? "+" : ""}${changePct.toFixed(2)}% (30d)`}
          color={changePct >= 0 ? "text-emerald" : "text-destructive"}
          icon={TrendingUp}
        />
        <MetricCard
          label="Unrealized P&L"
          value={formatCurrency(totalPnl)}
          sub={`${positions?.length || 0} open positions`}
          color={totalPnl >= 0 ? "text-emerald" : "text-destructive"}
          icon={BarChart3}
        />
        <MetricCard
          label="Total Return"
          value={perf ? `${perf.totalReturnPct >= 0 ? "+" : ""}${perf.totalReturnPct.toFixed(2)}%` : "—"}
          sub={perf ? formatCurrency(perf.totalReturn) : ""}
          color={perf && perf.totalReturnPct >= 0 ? "text-emerald" : "text-destructive"}
          icon={Activity}
        />
        <MetricCard
          label="Win Rate"
          value={perf ? `${perf.winRate.toFixed(1)}%` : "—"}
          sub={perf ? `${perf.totalTrades} trades · Sharpe ${perf.sharpeRatio}` : ""}
          color="text-foreground"
          icon={Radar}
        />
      </div>

      {/* Main Grid: Equity + Signals + Positions + Risk + Prices */}
      <div className="grid grid-cols-12 gap-3">

        {/* Equity Curve (spans 7 cols) */}
        <div className="col-span-12 lg:col-span-7">
          <HudCard
            title="Equity Curve"
            subtitle="30-Day"
            loading={perfLoading}
            headerRight={
              <Link href="/equity" className="text-[10px] text-emerald hover:text-emerald/80 transition-colors">
                Full Chart →
              </Link>
            }
          >
            <div className="h-[200px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 5, right: 5, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="overviewEquityGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#10b981" stopOpacity={0.25} />
                      <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 9, fill: "#6b7280", fontFamily: "JetBrains Mono" }}
                    axisLine={false}
                    tickLine={false}
                    interval="preserveStartEnd"
                  />
                  <YAxis
                    tick={{ fontSize: 9, fill: "#6b7280", fontFamily: "JetBrains Mono" }}
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={(v) => `$${(v / 1000).toFixed(0)}K`}
                    domain={["dataMin - 1000", "dataMax + 1000"]}
                    width={42}
                  />
                  <Tooltip content={<MiniEquityTooltip />} />
                  <Area
                    type="monotone"
                    dataKey="value"
                    stroke="#10b981"
                    strokeWidth={1.5}
                    fill="url(#overviewEquityGrad)"
                    animationDuration={600}
                    dot={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </HudCard>
        </div>

        {/* Risk Gate (spans 5 cols) */}
        <div className="col-span-12 lg:col-span-5">
          <RiskWidget risk={risk} />
        </div>

        {/* Live Signals (spans 5 cols) */}
        <div className="col-span-12 lg:col-span-5">
          <HudCard
            title="Top Signals"
            loading={sigLoading}
            headerRight={
              <Link href="/scanner" className="text-[10px] text-emerald hover:text-emerald/80 transition-colors">
                All Signals →
              </Link>
            }
          >
            <div className="space-y-0">
              {topSignals.map(s => <SignalRowCompact key={s.id} signal={s} />)}
              {!topSignals.length && !sigLoading && (
                <p className="text-sm text-muted-foreground text-center py-4">No signals</p>
              )}
            </div>
          </HudCard>
        </div>

        {/* Open Positions (spans 4 cols) */}
        <div className="col-span-12 lg:col-span-4">
          <HudCard
            title="Open Positions"
            loading={posLoading}
            headerRight={
              <Link href="/positions" className="text-[10px] text-emerald hover:text-emerald/80 transition-colors">
                All Positions →
              </Link>
            }
          >
            <div className="space-y-0">
              {topPositions.map(p => <PositionRowCompact key={p.id} pos={p} />)}
              {!topPositions.length && !posLoading && (
                <p className="text-sm text-muted-foreground text-center py-4">No open positions</p>
              )}
            </div>
          </HudCard>
        </div>

        {/* Market Prices + 24h Change (spans 3 cols) */}
        <div className="col-span-12 lg:col-span-3">
          <HudCard
            title="Market Prices"
            subtitle="24h Change"
          >
            <div className="space-y-0">
              {DISPLAY_SYMBOLS.map(sym => (
                <TickerRow
                  key={sym}
                  symbol={sym}
                  price={prices?.[sym] || 0}
                  ticker={tickers?.[sym]}
                />
              ))}
            </div>
          </HudCard>
        </div>

        {/* Regime Summary (spans 12 cols, compact row) */}
        <div className="col-span-12">
          <HudCard
            title="Market Regime"
            headerRight={
              <Link href="/regime" className="text-[10px] text-emerald hover:text-emerald/80 transition-colors">
                Full View →
              </Link>
            }
          >
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2">
              {regimes?.map(r => {
                const cfg = regimeConfig[r.regime] || regimeConfig.ranging;
                const Icon = cfg.icon;
                return (
                  <div key={r.symbol} className="flex flex-col gap-1 px-2 py-2 rounded bg-muted/30 border border-border/30">
                    <span className="data-value text-[11px] font-semibold text-foreground">{r.symbol}</span>
                    <span className={`inline-flex items-center gap-1 text-[10px] font-medium ${cfg.color}`}>
                      <Icon className="w-3 h-3" />
                      {cfg.label}
                    </span>
                    <span className="text-[10px] text-muted-foreground data-value">{r.confidence}% conf.</span>
                  </div>
                );
              })}
            </div>
          </HudCard>
        </div>

      </div>
    </div>
  );
}
