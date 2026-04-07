/**
 * Equity Curve Page — Command Center HUD
 * Portfolio value over time using Recharts.
 * Design: dark navy, emerald accent, JetBrains Mono data values.
 */
import { useState, useMemo } from "react";
import { useApiData } from "@/hooks/useApiData";
import { api } from "@/lib/api";
import { formatCurrency, formatNumber } from "@/lib/format";
import HudCard from "@/components/HudCard";
import { TrendingUp } from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";

const RANGES = [
  { label: "7D", days: 7 },
  { label: "30D", days: 30 },
  { label: "90D", days: 90 },
] as const;

type RangeKey = typeof RANGES[number]["label"];

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div
      className="hud-card px-3 py-2 border border-border/50 shadow-lg"
      style={{ background: "oklch(0.16 0.02 264.05)" }}
    >
      <p className="text-[10px] text-muted-foreground mb-1">{label}</p>
      <p className="data-value text-sm font-bold text-emerald">
        ${formatNumber(payload[0].value, 0)}
      </p>
      {payload[1] && (
        <p className="data-value text-xs text-destructive/80 mt-0.5">
          DD: {payload[1].value.toFixed(2)}%
        </p>
      )}
    </div>
  );
}

export default function EquityCurve() {
  const [range, setRange] = useState<RangeKey>("30D");
  const { data: performance, loading } = useApiData(api.getPerformance, {
    refreshInterval: 30000,
  });

  const days = RANGES.find((r) => r.label === range)?.days ?? 30;

  const chartData = useMemo(() => {
    if (!performance?.equityCurve) return [];
    const sliced = performance.equityCurve.slice(-days);
    const peak = sliced.reduce((m, p) => Math.max(m, p.value), 0);
    return sliced.map((point) => ({
      date: new Date(point.timestamp).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
      }),
      value: point.value,
      drawdown: peak > 0 ? ((point.value - peak) / peak) * 100 : 0,
    }));
  }, [performance, days]);

  const currentValue = chartData.length ? chartData[chartData.length - 1].value : 0;
  const startValue = chartData.length ? chartData[0].value : 0;
  const change = currentValue - startValue;
  const changePct = startValue ? (change / startValue) * 100 : 0;
  const maxDD = chartData.length
    ? Math.min(...chartData.map((d) => d.drawdown))
    : 0;

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <TrendingUp className="w-5 h-5 text-emerald" />
        <h1 className="text-lg font-semibold text-foreground">Equity Curve</h1>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          {
            label: "Portfolio Value",
            value: `$${formatNumber(currentValue, 0)}`,
            color: "text-foreground",
          },
          {
            label: "Period P&L",
            value: formatCurrency(change),
            color: change >= 0 ? "text-emerald" : "text-destructive",
          },
          {
            label: "Period Return",
            value: `${changePct >= 0 ? "+" : ""}${changePct.toFixed(2)}%`,
            color: changePct >= 0 ? "text-emerald" : "text-destructive",
          },
          {
            label: "Max Drawdown",
            value: performance
              ? `${performance.maxDrawdownPct.toFixed(2)}%`
              : "—",
            color: "text-destructive",
          },
        ].map((card, i) => (
          <div key={i} className="hud-card px-4 py-3">
            <span className="text-[10px] uppercase tracking-widest text-muted-foreground font-medium">
              {card.label}
            </span>
            <p className={`data-value text-xl font-bold mt-1 ${card.color}`}>
              {card.value}
            </p>
          </div>
        ))}
      </div>

      {/* Chart */}
      <HudCard
        title="Portfolio Value"
        subtitle={range}
        loading={loading}
        headerRight={
          <div className="flex items-center gap-1">
            {RANGES.map((r) => (
              <button
                key={r.label}
                onClick={() => setRange(r.label)}
                className={`px-2.5 py-1 text-[10px] font-semibold rounded transition-all ${
                  range === r.label
                    ? "bg-emerald/20 text-emerald border border-emerald/40"
                    : "text-muted-foreground hover:text-foreground border border-transparent hover:border-border/40"
                }`}
              >
                {r.label}
              </button>
            ))}
          </div>
        }
      >
        <div className="h-[400px]">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart
              data={chartData}
              margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
            >
              <defs>
                <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#10b981" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="rgba(255,255,255,0.05)"
              />
              <XAxis
                dataKey="date"
                tick={{
                  fontSize: 10,
                  fill: "#6b7280",
                  fontFamily: "JetBrains Mono",
                }}
                axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                tickLine={false}
                interval="preserveStartEnd"
              />
              <YAxis
                tick={{
                  fontSize: 10,
                  fill: "#6b7280",
                  fontFamily: "JetBrains Mono",
                }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => `$${(v / 1000).toFixed(0)}K`}
                domain={["dataMin - 2000", "dataMax + 2000"]}
              />
              <Tooltip content={<CustomTooltip />} />
              {startValue > 0 && (
                <ReferenceLine
                  y={startValue}
                  stroke="rgba(255,255,255,0.15)"
                  strokeDasharray="4 4"
                />
              )}
              <Area
                type="monotone"
                dataKey="value"
                stroke="#10b981"
                strokeWidth={2}
                fill="url(#equityGradient)"
                animationDuration={600}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Drawdown stats row */}
        <div className="mt-4 pt-3 border-t border-border/30 grid grid-cols-3 gap-4">
          <div>
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground mb-1">
              Max Drawdown ({range})
            </p>
            <p className="data-value text-sm font-bold text-destructive">
              {maxDD.toFixed(2)}%
            </p>
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground mb-1">
              Sharpe Ratio
            </p>
            <p className="data-value text-sm font-bold text-emerald">
              {performance?.sharpeRatio.toFixed(2) ?? "—"}
            </p>
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground mb-1">
              Profit Factor
            </p>
            <p className="data-value text-sm font-bold text-emerald">
              {performance?.profitFactor.toFixed(2) ?? "—"}
            </p>
          </div>
        </div>
      </HudCard>
    </div>
  );
}
