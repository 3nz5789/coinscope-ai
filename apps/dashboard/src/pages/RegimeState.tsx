/**
 * Regime State Page — Command Center HUD
 * Market regime per symbol with visual indicators and 24h price change badges.
 */
import { useApiData } from "@/hooks/useApiData";
import { api, RegimeState as RegimeType } from "@/lib/api";
import { timeAgoShort, formatPrice } from "@/lib/format";
import HudCard from "@/components/HudCard";
import PriceChangeBadge from "@/components/PriceChangeBadge";
import { Gauge, TrendingUp, TrendingDown, Minus, Zap } from "lucide-react";

const regimeConfig: Record<string, { label: string; color: string; bg: string; icon: React.ComponentType<{ className?: string }> }> = {
  trending_up: { label: "Trending Up", color: "text-emerald", bg: "bg-emerald/10 border-emerald/20", icon: TrendingUp },
  trending_down: { label: "Trending Down", color: "text-destructive", bg: "bg-destructive/10 border-destructive/20", icon: TrendingDown },
  ranging: { label: "Ranging", color: "text-blue-400", bg: "bg-blue-400/10 border-blue-400/20", icon: Minus },
  volatile: { label: "Volatile", color: "text-warning", bg: "bg-warning/10 border-warning/20", icon: Zap },
};

function RegimeCard({ regime, ticker, price }: { regime: RegimeType; ticker?: any; price?: number }) {
  const config = regimeConfig[regime.regime] || regimeConfig.ranging;
  const Icon = config.icon;

  return (
    <div className={`hud-card p-4 border-l-[3px] ${config.color.replace("text-", "border-")}`}>
      <div className="flex items-start justify-between mb-3">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <span className="data-value text-[15px] font-bold text-foreground">{regime.symbol}</span>
            {ticker && <PriceChangeBadge pct={ticker.priceChangePercent} size="sm" showIcon={false} />}
          </div>
          {price !== undefined && price > 0 && (
            <span className="data-value text-[12px] text-muted-foreground">{formatPrice(price)}</span>
          )}
        </div>
        <span className={`inline-flex items-center gap-1.5 px-2 py-1 rounded border text-[11px] font-semibold ${config.bg} ${config.color}`}>
          <Icon className="w-3.5 h-3.5" />
          {config.label}
        </span>
      </div>

      <div className="space-y-2">
        <div className="flex justify-between">
          <span className="text-[10px] uppercase tracking-widest text-muted-foreground">Confidence</span>
          <span className={`data-value text-[12px] font-semibold ${config.color}`}>{regime.confidence}%</span>
        </div>
        <div className="w-full h-1.5 rounded-full bg-muted overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${config.color.replace("text-", "bg-")}`}
            style={{ width: `${regime.confidence}%` }}
          />
        </div>
        <div className="flex justify-between pt-1">
          <span className="text-[10px] text-muted-foreground">Duration: <span className="data-value">{regime.duration}</span></span>
          <span className="text-[10px] text-muted-foreground">{timeAgoShort(regime.lastUpdate)}</span>
        </div>

        {/* 24h stats if ticker available */}
        {ticker && (
          <div className="pt-2 border-t border-border/20 grid grid-cols-2 gap-x-4 gap-y-1">
            <div className="flex justify-between">
              <span className="text-[10px] text-muted-foreground">24h High</span>
              <span className="data-value text-[10px] text-emerald">{formatPrice(ticker.highPrice)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[10px] text-muted-foreground">24h Low</span>
              <span className="data-value text-[10px] text-destructive">{formatPrice(ticker.lowPrice)}</span>
            </div>
            <div className="flex justify-between col-span-2">
              <span className="text-[10px] text-muted-foreground">Volume</span>
              <span className="data-value text-[10px] text-foreground">
                {ticker.quoteVolume >= 1e9
                  ? `$${(ticker.quoteVolume / 1e9).toFixed(2)}B`
                  : `$${(ticker.quoteVolume / 1e6).toFixed(1)}M`}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function RegimeState() {
  const { data: regimes, loading } = useApiData(api.getRegimes, { refreshInterval: 10000 });
  const { data: tickers } = useApiData(api.getTicker24h, { refreshInterval: 30000 });
  const { data: prices } = useApiData(api.getLivePrices, { refreshInterval: 3000 });

  const regimeCounts = regimes?.reduce((acc, r) => {
    acc[r.regime] = (acc[r.regime] || 0) + 1;
    return acc;
  }, {} as Record<string, number>) || {};

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Gauge className="w-5 h-5 text-emerald" />
        <h1 className="text-lg font-semibold text-foreground">Market Regime</h1>
      </div>

      {/* Regime distribution */}
      <div className="grid grid-cols-4 gap-3">
        {Object.entries(regimeConfig).map(([key, config]) => {
          const Icon = config.icon;
          return (
            <div key={key} className="hud-card px-4 py-3">
              <div className="flex items-center gap-2 mb-1">
                <Icon className={`w-4 h-4 ${config.color}`} />
                <span className="text-[10px] uppercase tracking-widest text-muted-foreground font-medium">{config.label}</span>
              </div>
              <p className={`data-value text-xl font-bold ${config.color}`}>{regimeCounts[key] || 0}</p>
            </div>
          );
        })}
      </div>

      {/* Regime cards grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {regimes?.map(regime => (
          <RegimeCard
            key={regime.symbol}
            regime={regime}
            ticker={tickers?.[regime.symbol]}
            price={prices?.[regime.symbol]}
          />
        ))}
      </div>
    </div>
  );
}
