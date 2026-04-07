/**
 * Positions Page — Command Center HUD
 * Open positions with entry/current price, P&L, leverage, SL/TP, and 24h change badges.
 */
import { useApiData } from "@/hooks/useApiData";
import { api, Position } from "@/lib/api";
import { formatPrice, formatPct, formatCurrency, timeAgoShort } from "@/lib/format";
import HudCard from "@/components/HudCard";
import PriceChangeBadge from "@/components/PriceChangeBadge";
import { BarChart3, ArrowUpRight, ArrowDownRight } from "lucide-react";

function PnlBadge({ value, pct }: { value: number; pct: number }) {
  const isPositive = value >= 0;
  return (
    <div className={`flex flex-col items-end ${isPositive ? "text-emerald" : "text-destructive"}`}>
      <span className="data-value text-[13px] font-semibold">{formatCurrency(value)}</span>
      <span className="data-value text-[11px]">{formatPct(pct)}</span>
    </div>
  );
}

function PositionCard({ position, ticker }: { position: Position; ticker?: any }) {
  const isLong = position.direction === "LONG";
  const isProfit = position.unrealizedPnl >= 0;

  return (
    <div className={`hud-card p-4 border-l-[3px] ${isProfit ? "border-l-emerald" : "border-l-destructive"}`}>
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="data-value text-[15px] font-bold text-foreground">{position.symbol}</span>
          <span className={`inline-flex items-center gap-0.5 text-[11px] font-semibold px-1.5 py-0.5 rounded ${
            isLong ? "bg-emerald/10 text-emerald" : "bg-destructive/10 text-destructive"
          }`}>
            {isLong ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
            {position.direction}
          </span>
          <span className="text-[11px] data-value text-warning font-medium">{position.leverage}x</span>
          {ticker && <PriceChangeBadge pct={ticker.priceChangePercent} size="sm" showIcon={false} />}
        </div>
        <PnlBadge value={position.unrealizedPnl} pct={position.unrealizedPnlPct} />
      </div>

      <div className="grid grid-cols-2 gap-x-6 gap-y-2">
        {[
          { label: "Entry", value: formatPrice(position.entryPrice) },
          { label: "Current", value: formatPrice(position.currentPrice) },
          { label: "Size", value: `${position.size}` },
          { label: "Opened", value: timeAgoShort(position.openedAt) },
          { label: "Stop Loss", value: formatPrice(position.stopLoss), color: "text-destructive" },
          { label: "Take Profit", value: formatPrice(position.takeProfit), color: "text-emerald" },
        ].map((item, i) => (
          <div key={i} className="flex justify-between">
            <span className="text-[10px] uppercase tracking-widest text-muted-foreground">{item.label}</span>
            <span className={`data-value text-[12px] font-medium ${(item as any).color || "text-foreground"}`}>{item.value}</span>
          </div>
        ))}
      </div>

      {/* P&L progress bar */}
      <div className="mt-3 pt-3 border-t border-border/30">
        <div className="flex justify-between text-[10px] text-muted-foreground mb-1">
          <span>SL: {formatPrice(position.stopLoss)}</span>
          <span>TP: {formatPrice(position.takeProfit)}</span>
        </div>
        <div className="w-full h-1.5 rounded-full bg-muted overflow-hidden relative">
          {(() => {
            const range = position.takeProfit - position.stopLoss;
            const progress = ((position.currentPrice - position.stopLoss) / range) * 100;
            const clamped = Math.max(0, Math.min(100, progress));
            return <div className={`h-full rounded-full transition-all duration-500 ${isProfit ? "bg-emerald" : "bg-destructive"}`} style={{ width: `${clamped}%` }} />;
          })()}
        </div>
      </div>

      {/* 24h High/Low if ticker available */}
      {ticker && (
        <div className="mt-2 pt-2 border-t border-border/20 grid grid-cols-2 gap-2">
          <div className="flex justify-between">
            <span className="text-[10px] text-muted-foreground">24h High</span>
            <span className="data-value text-[11px] text-emerald">{formatPrice(ticker.highPrice)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[10px] text-muted-foreground">24h Low</span>
            <span className="data-value text-[11px] text-destructive">{formatPrice(ticker.lowPrice)}</span>
          </div>
        </div>
      )}
    </div>
  );
}

export default function Positions() {
  const { data: positions, loading } = useApiData(api.getPositions, { refreshInterval: 5000 });
  const { data: tickers } = useApiData(api.getTicker24h, { refreshInterval: 30000 });

  const totalPnl = positions?.reduce((a, p) => a + p.unrealizedPnl, 0) || 0;
  const longCount = positions?.filter(p => p.direction === "LONG").length || 0;
  const shortCount = positions?.filter(p => p.direction === "SHORT").length || 0;

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <BarChart3 className="w-5 h-5 text-emerald" />
        <h1 className="text-lg font-semibold text-foreground">Open Positions</h1>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: "Total Positions", value: positions?.length || 0 },
          { label: "Long / Short", value: `${longCount} / ${shortCount}` },
          { label: "Unrealized P&L", value: formatCurrency(totalPnl), color: totalPnl >= 0 ? "text-emerald" : "text-destructive" },
          { label: "Total Exposure", value: positions ? `$${Math.round(positions.reduce((a, p) => a + p.size * p.currentPrice, 0)).toLocaleString()}` : "—" },
        ].map((card, i) => (
          <div key={i} className="hud-card px-4 py-3">
            <span className="text-[10px] uppercase tracking-widest text-muted-foreground font-medium">{card.label}</span>
            <p className={`data-value text-xl font-bold mt-1 ${(card as any).color || "text-foreground"}`}>{card.value}</p>
          </div>
        ))}
      </div>

      {/* Position cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {positions?.map(pos => (
          <PositionCard key={pos.id} position={pos} ticker={tickers?.[pos.symbol]} />
        ))}
        {!positions?.length && !loading && (
          <div className="col-span-2 hud-card p-12 text-center text-muted-foreground">No open positions</div>
        )}
      </div>
    </div>
  );
}
