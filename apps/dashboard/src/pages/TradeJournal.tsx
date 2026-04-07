/**
 * Trade Journal Page — Command Center HUD
 * Table of recent trades with full details.
 */
import { useApiData } from "@/hooks/useApiData";
import { api, TradeJournalEntry } from "@/lib/api";
import { formatPrice, formatCurrency, formatPct } from "@/lib/format";
import HudCard from "@/components/HudCard";
import { BookOpen, ArrowUpRight, ArrowDownRight } from "lucide-react";

function JournalRow({ trade }: { trade: TradeJournalEntry }) {
  const isLong = trade.direction === "LONG";
  const isProfit = trade.pnl >= 0;

  return (
    <tr className="border-b border-border/30 hover:bg-white/[0.02] transition-colors">
      <td className="py-2.5 px-3">
        <span className="data-value text-[13px] font-medium text-foreground">{trade.symbol}</span>
      </td>
      <td className="py-2.5 px-3">
        <span className={`inline-flex items-center gap-0.5 text-[11px] font-semibold ${isLong ? "text-emerald" : "text-destructive"}`}>
          {isLong ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
          {trade.direction}
        </span>
      </td>
      <td className="py-2.5 px-3">
        <span className="data-value text-[12px] text-foreground">{formatPrice(trade.entryPrice)}</span>
      </td>
      <td className="py-2.5 px-3">
        <span className="data-value text-[12px] text-foreground">{formatPrice(trade.exitPrice)}</span>
      </td>
      <td className="py-2.5 px-3">
        <div className={`flex flex-col ${isProfit ? "text-emerald" : "text-destructive"}`}>
          <span className="data-value text-[12px] font-semibold">{formatCurrency(trade.pnl)}</span>
          <span className="data-value text-[10px]">{formatPct(trade.pnlPct)}</span>
        </div>
      </td>
      <td className="py-2.5 px-3">
        <span className="data-value text-[11px] text-muted-foreground">{trade.duration}</span>
      </td>
      <td className="py-2.5 px-3">
        <span className="text-[11px] text-muted-foreground capitalize">{trade.signalSource}</span>
      </td>
      <td className="py-2.5 px-3">
        <span className="data-value text-[11px] text-muted-foreground">{trade.size}</span>
      </td>
    </tr>
  );
}

export default function TradeJournal() {
  const { data: journal, loading } = useApiData(api.getJournal, { refreshInterval: 15000 });

  const totalPnl = journal?.reduce((a, t) => a + t.pnl, 0) || 0;
  const winCount = journal?.filter(t => t.pnl > 0).length || 0;
  const lossCount = journal?.filter(t => t.pnl <= 0).length || 0;

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <BookOpen className="w-5 h-5 text-emerald" />
        <h1 className="text-lg font-semibold text-foreground">Trade Journal</h1>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: "Total Trades", value: journal?.length || 0 },
          { label: "Wins / Losses", value: `${winCount} / ${lossCount}`, color: "text-foreground" },
          { label: "Net P&L", value: formatCurrency(totalPnl), color: totalPnl >= 0 ? "text-emerald" : "text-destructive" },
          { label: "Win Rate", value: journal?.length ? `${((winCount / journal.length) * 100).toFixed(1)}%` : "—", color: winCount > lossCount ? "text-emerald" : "text-destructive" },
        ].map((card, i) => (
          <div key={i} className="hud-card px-4 py-3">
            <span className="text-[10px] uppercase tracking-widest text-muted-foreground font-medium">{card.label}</span>
            <p className={`data-value text-xl font-bold mt-1 ${(card as any).color || "text-foreground"}`}>{card.value}</p>
          </div>
        ))}
      </div>

      {/* Journal table */}
      <HudCard title="Recent Trades" loading={loading} noPadding>
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-border/50">
                {["Symbol", "Side", "Entry", "Exit", "P&L", "Duration", "Signal", "Size"].map(h => (
                  <th key={h} className="py-2 px-3 text-[10px] uppercase tracking-widest text-muted-foreground font-semibold">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {journal?.map(trade => <JournalRow key={trade.id} trade={trade} />)}
              {!journal?.length && !loading && (
                <tr><td colSpan={8} className="py-12 text-center text-muted-foreground text-sm">No trades recorded</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </HudCard>
    </div>
  );
}
