/**
 * Performance Metrics Page — Command Center HUD
 * Key stats displayed as metric cards with trade distribution chart.
 * Design: dark navy, emerald accent, JetBrains Mono data values.
 */
import { useApiData } from "@/hooks/useApiData";
import { api } from "@/lib/api";
import { formatCurrency, formatPct, formatNumber } from "@/lib/format";
import HudCard from "@/components/HudCard";
import {
  Activity,
  TrendingUp,
  TrendingDown,
  Target,
  BarChart2,
  Percent,
  Award,
  AlertTriangle,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

interface MetricCardProps {
  label: string;
  value: string;
  icon: React.ComponentType<{ className?: string }>;
  color?: string;
  subtitle?: string;
}

function MetricCard({
  label,
  value,
  icon: Icon,
  color = "text-foreground",
  subtitle,
}: MetricCardProps) {
  return (
    <div className="hud-card p-4">
      <div className="flex items-start justify-between mb-2">
        <span className="text-[10px] uppercase tracking-widest text-muted-foreground font-medium">
          {label}
        </span>
        <Icon className={`w-4 h-4 ${color}`} />
      </div>
      <p className={`data-value text-2xl font-bold ${color}`}>{value}</p>
      {subtitle && (
        <p className="text-[11px] text-muted-foreground mt-1">{subtitle}</p>
      )}
    </div>
  );
}

function BarTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const v = payload[0].value as number;
  return (
    <div
      className="hud-card px-3 py-2 border border-border/50 shadow-lg text-xs"
      style={{ background: "oklch(0.16 0.02 264.05)" }}
    >
      <p className="text-muted-foreground mb-0.5">{label}</p>
      <p className={`data-value font-bold ${v >= 0 ? "text-emerald" : "text-destructive"}`}>
        {formatCurrency(v)}
      </p>
    </div>
  );
}

// Generate a mock P&L distribution for the bar chart
function buildDistribution(
  avgWin: number,
  avgLoss: number,
  winRate: number,
  total: number
): { bucket: string; count: number; pnl: number }[] {
  const buckets = [
    { bucket: "< -5%", pnl: avgLoss * 1.8, count: Math.round(total * 0.05) },
    { bucket: "-3–5%", pnl: avgLoss * 1.3, count: Math.round(total * 0.08) },
    { bucket: "-1–3%", pnl: avgLoss * 0.7, count: Math.round(total * (1 - winRate / 100) * 0.6) },
    { bucket: "0–1%", pnl: avgWin * 0.2, count: Math.round(total * 0.12) },
    { bucket: "1–3%", pnl: avgWin * 0.6, count: Math.round(total * (winRate / 100) * 0.45) },
    { bucket: "3–5%", pnl: avgWin * 1.1, count: Math.round(total * (winRate / 100) * 0.3) },
    { bucket: "> 5%", pnl: avgWin * 1.9, count: Math.round(total * (winRate / 100) * 0.15) },
  ];
  return buckets;
}

export default function Performance() {
  const { data: perf, loading } = useApiData(api.getPerformance, {
    refreshInterval: 15000,
  });

  if (!perf && loading) {
    return (
      <div className="space-y-5">
        <div className="flex items-center gap-3">
          <Activity className="w-5 h-5 text-emerald" />
          <h1 className="text-lg font-semibold text-foreground">
            Performance Metrics
          </h1>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="hud-card p-4 h-24 animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  const distribution = buildDistribution(
    perf?.avgWin || 1200,
    perf?.avgLoss || -680,
    perf?.winRate || 63,
    perf?.totalTrades || 347
  );

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Activity className="w-5 h-5 text-emerald" />
        <h1 className="text-lg font-semibold text-foreground">
          Performance Metrics
        </h1>
      </div>

      {/* Primary metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Total Return"
          value={formatCurrency(perf?.totalReturn || 0)}
          icon={TrendingUp}
          color={
            (perf?.totalReturn || 0) >= 0 ? "text-emerald" : "text-destructive"
          }
          subtitle={formatPct(perf?.totalReturnPct || 0)}
        />
        <MetricCard
          label="Sharpe Ratio"
          value={formatNumber(perf?.sharpeRatio || 0)}
          icon={Award}
          color={
            (perf?.sharpeRatio || 0) >= 2
              ? "text-emerald"
              : (perf?.sharpeRatio || 0) >= 1
              ? "text-warning"
              : "text-destructive"
          }
          subtitle={`${
            (perf?.sharpeRatio || 0) >= 2
              ? "Excellent"
              : (perf?.sharpeRatio || 0) >= 1
              ? "Good"
              : "Poor"
          }`}
        />
        <MetricCard
          label="Max Drawdown"
          value={formatPct(perf?.maxDrawdownPct || 0, false)}
          icon={TrendingDown}
          color="text-destructive"
          subtitle={formatCurrency(perf?.maxDrawdown || 0)}
        />
        <MetricCard
          label="Win Rate"
          value={`${perf?.winRate || 0}%`}
          icon={Target}
          color={
            (perf?.winRate || 0) >= 60
              ? "text-emerald"
              : (perf?.winRate || 0) >= 50
              ? "text-warning"
              : "text-destructive"
          }
        />
      </div>

      {/* Secondary metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Profit Factor"
          value={formatNumber(perf?.profitFactor || 0)}
          icon={BarChart2}
          color={(perf?.profitFactor || 0) >= 1.5 ? "text-emerald" : "text-warning"}
        />
        <MetricCard
          label="Total Trades"
          value={`${perf?.totalTrades || 0}`}
          icon={Activity}
        />
        <MetricCard
          label="Open Positions"
          value={`${perf?.openPositions || 0}`}
          icon={Percent}
          color="text-emerald"
        />
        <MetricCard
          label="Best / Worst"
          value={formatCurrency(perf?.bestTrade || 0)}
          icon={AlertTriangle}
          color="text-emerald"
          subtitle={`Worst: ${formatCurrency(perf?.worstTrade || 0)}`}
        />
      </div>

      {/* Win/Loss analysis + distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Win/Loss breakdown */}
        <HudCard title="Win / Loss Analysis">
          <div className="space-y-5">
            {/* Win vs Loss ratio bar */}
            <div>
              <div className="flex justify-between text-[11px] text-muted-foreground mb-1.5">
                <span>Win Rate</span>
                <span className="data-value text-foreground font-semibold">
                  {perf?.winRate || 0}% wins /{" "}
                  {100 - (perf?.winRate || 0)}% losses
                </span>
              </div>
              <div className="w-full h-3 rounded-full bg-muted overflow-hidden flex">
                <div
                  className="h-full bg-emerald rounded-l-full transition-all duration-700"
                  style={{ width: `${perf?.winRate || 0}%` }}
                />
                <div
                  className="h-full bg-destructive rounded-r-full transition-all duration-700"
                  style={{ width: `${100 - (perf?.winRate || 0)}%` }}
                />
              </div>
            </div>

            {/* Average win */}
            <div>
              <div className="flex justify-between mb-1.5">
                <span className="text-[11px] text-muted-foreground uppercase tracking-wider">
                  Average Win
                </span>
                <span className="data-value text-[13px] font-semibold text-emerald">
                  {formatCurrency(perf?.avgWin || 0)}
                </span>
              </div>
              <div className="w-full h-2 rounded-full bg-muted overflow-hidden">
                <div
                  className="h-full rounded-full bg-emerald transition-all duration-700"
                  style={{
                    width: `${Math.min(
                      100,
                      ((perf?.avgWin || 0) / (perf?.bestTrade || 1)) * 100
                    )}%`,
                  }}
                />
              </div>
            </div>

            {/* Average loss */}
            <div>
              <div className="flex justify-between mb-1.5">
                <span className="text-[11px] text-muted-foreground uppercase tracking-wider">
                  Average Loss
                </span>
                <span className="data-value text-[13px] font-semibold text-destructive">
                  {formatCurrency(perf?.avgLoss || 0)}
                </span>
              </div>
              <div className="w-full h-2 rounded-full bg-muted overflow-hidden">
                <div
                  className="h-full rounded-full bg-destructive transition-all duration-700"
                  style={{
                    width: `${Math.min(
                      100,
                      (Math.abs(perf?.avgLoss || 0) /
                        Math.abs(perf?.worstTrade || 1)) *
                        100
                    )}%`,
                  }}
                />
              </div>
            </div>

            {/* Expectancy */}
            <div className="pt-2 border-t border-border/30 grid grid-cols-2 gap-4">
              <div>
                <p className="text-[10px] uppercase tracking-widest text-muted-foreground mb-1">
                  Expectancy / Trade
                </p>
                <p className="data-value text-base font-bold text-emerald">
                  {formatCurrency(
                    ((perf?.winRate || 0) / 100) * (perf?.avgWin || 0) +
                      (1 - (perf?.winRate || 0) / 100) * (perf?.avgLoss || 0)
                  )}
                </p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-widest text-muted-foreground mb-1">
                  Risk / Reward
                </p>
                <p className="data-value text-base font-bold text-foreground">
                  1 :{" "}
                  {Math.abs(
                    (perf?.avgWin || 1) / (perf?.avgLoss || -1)
                  ).toFixed(2)}
                </p>
              </div>
            </div>
          </div>
        </HudCard>

        {/* P&L Distribution */}
        <HudCard title="P&L Distribution" subtitle="by trade bucket">
          <div className="h-[260px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={distribution}
                margin={{ top: 5, right: 5, left: 0, bottom: 5 }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="rgba(255,255,255,0.05)"
                />
                <XAxis
                  dataKey="bucket"
                  tick={{
                    fontSize: 9,
                    fill: "#6b7280",
                    fontFamily: "JetBrains Mono",
                  }}
                  axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                  tickLine={false}
                />
                <YAxis
                  tick={{
                    fontSize: 9,
                    fill: "#6b7280",
                    fontFamily: "JetBrains Mono",
                  }}
                  axisLine={false}
                  tickLine={false}
                  label={{
                    value: "trades",
                    angle: -90,
                    position: "insideLeft",
                    fill: "#6b7280",
                    fontSize: 9,
                  }}
                />
                <Tooltip content={<BarTooltip />} />
                <Bar dataKey="count" radius={[3, 3, 0, 0]}>
                  {distribution.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={entry.pnl >= 0 ? "#10b981" : "#ef4444"}
                      fillOpacity={0.8}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-3 pt-3 border-t border-border/30 flex items-center gap-4 text-[10px] text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-sm bg-emerald inline-block" />
              Profitable trades
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-sm bg-destructive inline-block" />
              Loss trades
            </span>
          </div>
        </HudCard>
      </div>
    </div>
  );
}
