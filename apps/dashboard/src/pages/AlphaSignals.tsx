/**
 * Alpha Signals Page — Command Center HUD
 * Shows the 5 alpha generators with strength indicators.
 */
import { useApiData } from "@/hooks/useApiData";
import { api, AlphaSignal } from "@/lib/api";
import { timeAgoShort } from "@/lib/format";
import HudCard from "@/components/HudCard";
import { Zap, ArrowUpRight, ArrowDownRight, Minus } from "lucide-react";

const typeIcons: Record<string, string> = {
  funding_extreme: "F",
  liquidation_cascade: "L",
  oi_divergence: "O",
  basis_trade: "B",
  orderbook_imbalance: "I",
};

const typeColors: Record<string, string> = {
  funding_extreme: "from-amber-500/20 to-amber-500/5 border-amber-500/30",
  liquidation_cascade: "from-red-500/20 to-red-500/5 border-red-500/30",
  oi_divergence: "from-blue-500/20 to-blue-500/5 border-blue-500/30",
  basis_trade: "from-emerald/20 to-emerald/5 border-emerald/30",
  orderbook_imbalance: "from-purple-500/20 to-purple-500/5 border-purple-500/30",
};

const typeAccentColors: Record<string, string> = {
  funding_extreme: "text-amber-400",
  liquidation_cascade: "text-red-400",
  oi_divergence: "text-blue-400",
  basis_trade: "text-emerald",
  orderbook_imbalance: "text-purple-400",
};

function StrengthMeter({ value, color }: { value: number; color: string }) {
  const bars = 10;
  const filled = Math.round((value / 100) * bars);
  return (
    <div className="flex items-center gap-1">
      <div className="flex gap-[2px]">
        {Array.from({ length: bars }).map((_, i) => (
          <div
            key={i}
            className={`w-2 h-5 rounded-[1px] transition-all duration-300 ${
              i < filled
                ? value >= 80 ? "bg-emerald" : value >= 50 ? "bg-warning" : "bg-muted-foreground"
                : "bg-muted"
            }`}
            style={{ height: `${12 + (i * 1.2)}px` }}
          />
        ))}
      </div>
      <span className={`data-value text-[13px] font-bold ml-2 ${color}`}>{value}</span>
    </div>
  );
}

function DirectionBadge({ direction }: { direction: AlphaSignal["direction"] }) {
  if (direction === "NEUTRAL") {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-muted-foreground">
        <Minus className="w-3 h-3" /> NEUTRAL
      </span>
    );
  }
  const isLong = direction === "LONG";
  return (
    <span className={`inline-flex items-center gap-1 text-[11px] font-semibold ${isLong ? "text-emerald" : "text-destructive"}`}>
      {isLong ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
      {direction}
    </span>
  );
}

function AlphaCard({ signal }: { signal: AlphaSignal }) {
  const accentColor = typeAccentColors[signal.type] || "text-foreground";
  const gradientClass = typeColors[signal.type] || "";

  return (
    <div className={`hud-card overflow-hidden`}>
      <div className={`bg-gradient-to-b ${gradientClass} border-b border-border/30 px-4 py-3`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className={`w-7 h-7 rounded flex items-center justify-center text-[12px] font-bold data-value bg-background/50 ${accentColor}`}>
              {typeIcons[signal.type]}
            </span>
            <div>
              <h3 className="text-[13px] font-semibold text-foreground">{signal.name}</h3>
              <span className="text-[10px] text-muted-foreground">{timeAgoShort(signal.lastUpdate)}</span>
            </div>
          </div>
          <DirectionBadge direction={signal.direction} />
        </div>
      </div>
      <div className="px-4 py-3">
        <div className="mb-3">
          <span className="text-[10px] uppercase tracking-widest text-muted-foreground font-medium">Signal Strength</span>
          <div className="mt-1.5">
            <StrengthMeter value={signal.strength} color={accentColor} />
          </div>
        </div>
        <p className="text-[11px] text-muted-foreground leading-relaxed">{signal.description}</p>
      </div>
    </div>
  );
}

export default function AlphaSignals() {
  const { data: signals, loading } = useApiData(api.getAlphaSignals, { refreshInterval: 5000 });

  const avgStrength = signals?.length
    ? Math.round(signals.reduce((a, s) => a + s.strength, 0) / signals.length)
    : 0;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Zap className="w-5 h-5 text-emerald" />
          <h1 className="text-lg font-semibold text-foreground">Alpha Signals</h1>
        </div>
        <div className="flex items-center gap-4">
          <div className="hud-card px-3 py-1.5 flex items-center gap-2">
            <span className="text-[10px] uppercase tracking-widest text-muted-foreground">Avg Strength</span>
            <span className={`data-value text-[13px] font-bold ${avgStrength >= 60 ? "text-emerald" : "text-warning"}`}>{avgStrength}</span>
          </div>
        </div>
      </div>

      {/* Alpha signal cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {signals?.map(signal => <AlphaCard key={signal.type} signal={signal} />)}
      </div>
    </div>
  );
}
