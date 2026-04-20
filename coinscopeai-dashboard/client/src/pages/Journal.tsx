/* Trade Journal — Historical trades with entry/exit, P&L, duration, strategy, notes (live) */
import DashboardLayout from '@/components/DashboardLayout';
import PageHeader from '@/components/PageHeader';
import { useJournal, useTradeTrace } from '@/lib/engine/hooks';
import { cn as _cn } from '@/lib/utils';

/** Compact key-value row. */
function KV({ k, v }: { k: string; v: any }) {
  return (
    <div className="flex justify-between py-0.5 gap-4">
      <span className="text-muted-foreground whitespace-nowrap">{k}</span>
      <span className="font-mono text-foreground tabular-nums text-right break-all">{v ?? '—'}</span>
    </div>
  );
}

/** Full provenance trace panel — fetched per entry_id when the row expands. */
function TradeTracePanel({ id, fallbackEntry }: { id: string; fallbackEntry: any }) {
  const t = useTradeTrace(id);
  const entry = t.data?.entry ?? fallbackEntry;
  const decisions = t.data?.decisions ?? [];
  const algo = t.data?.algo_orders ?? [];

  const fmtMs = (ms: number | null | undefined) =>
    ms ? new Date(ms).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—';
  const fmtIso = (s: string | null | undefined) =>
    s ? new Date(s).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—';

  const ind = entry?.indicators_at_entry ?? {};

  return (
    <div className="p-4 text-xs">
      {t.isLoading && <div className="text-muted-foreground mb-3">Loading trace…</div>}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* ── Signal origin ──────────────────────────────── */}
        <div className="rounded-md border border-border/40 bg-card/40 p-3">
          <h3 className="text-[10px] uppercase tracking-wider text-muted-foreground mb-2">Signal origin</h3>
          <KV k="Source"      v={entry.source || entry.strategy} />
          <KV k="Signal score"v={entry.signal_score != null ? Number(entry.signal_score).toFixed(1) : null} />
          <KV k="Strength"    v={entry.strength} />
          <KV k="Regime"      v={entry.regime} />
          <KV k="HTF trend (4h)" v={entry.htf_trend} />
          {entry.scanner_hits && entry.scanner_hits.length > 0 && (
            <KV k="Scanners" v={entry.scanner_hits.map((s: any) => s.name ?? s).join(' · ')} />
          )}
          {entry.reasons && entry.reasons.length > 0 && (
            <div className="mt-2 pt-2 border-t border-border/30">
              <div className="text-muted-foreground mb-1">Reasons</div>
              {entry.reasons.map((r: string, i: number) => (
                <div key={i} className="text-foreground">• {r}</div>
              ))}
            </div>
          )}
          {ind && Object.keys(ind).length > 0 && (
            <div className="mt-2 pt-2 border-t border-border/30">
              <div className="text-muted-foreground mb-1">Indicators at entry</div>
              {ind.rsi != null    && <KV k="RSI"   v={Number(ind.rsi).toFixed(1)} />}
              {ind.adx != null    && <KV k="ADX"   v={Number(ind.adx).toFixed(1)} />}
              {ind.trend          && <KV k="Trend" v={ind.trend} />}
              {ind.momentum       && <KV k="Mom"   v={ind.momentum} />}
              {ind.volatility     && <KV k="Vol"   v={ind.volatility} />}
            </div>
          )}
        </div>

        {/* ── Entry order + bracket ─────────────────────── */}
        <div className="rounded-md border border-border/40 bg-card/40 p-3">
          <h3 className="text-[10px] uppercase tracking-wider text-muted-foreground mb-2">Entry order</h3>
          <KV k="Client ID"     v={entry.entry_client_id} />
          <KV k="Binance order" v={entry.entry_order_id ? `#${entry.entry_order_id}` : null} />
          <KV k="Submit"        v={fmtMs(entry.entry_submit_ms)} />
          <KV k="Fill"          v={fmtMs(entry.entry_fill_ms)} />
          <KV k="Fill price"    v={entry.entry_price ? `$${Number(entry.entry_price).toFixed(4)}` : null} />
          <KV k="Qty"           v={entry.qty} />
          <KV k="Leverage"      v={entry.leverage ? `${entry.leverage}x` : null} />
          <KV k="Notional"      v={entry.kelly_usd ? `$${Number(entry.kelly_usd).toFixed(2)}` : null} />
          {entry.slippage_bps != null && (
            <KV k="Slippage"    v={`${Number(entry.slippage_bps).toFixed(1)} bps`} />
          )}
          <div className="mt-2 pt-2 border-t border-border/30">
            <div className="text-muted-foreground mb-1">Protective bracket</div>
            <KV k="Stop loss"   v={entry.sl_price ? `$${Number(entry.sl_price).toFixed(4)}` : null} />
            <KV k="Take profit" v={entry.tp_price ? `$${Number(entry.tp_price).toFixed(4)}` : null} />
            <KV k="SL algoId"   v={entry.sl_algo_id ? `#${entry.sl_algo_id}` : null} />
            <KV k="TP algoId"   v={entry.tp_algo_id ? `#${entry.tp_algo_id}` : null} />
            {algo.length > 0 && (
              <div className="mt-1 text-[10px]">
                <span className={_cn('px-1.5 py-0.5 rounded-sm',
                  algo[0]?.error ? 'bg-crimson/10 text-crimson' :
                  'bg-emerald/10 text-emerald')}>
                  {algo[0]?.error ? algo[0].error : `${algo.length} algo order(s) still live`}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* ── Exit + P&L ────────────────────────────────── */}
        <div className="rounded-md border border-border/40 bg-card/40 p-3">
          <h3 className="text-[10px] uppercase tracking-wider text-muted-foreground mb-2">Exit</h3>
          <KV k="Status"        v={entry.status} />
          <KV k="Trigger"       v={entry.exit_trigger} />
          <KV k="Closed by"     v={entry.closed_by} />
          <KV k="Exit order"    v={entry.exit_order_id ? `#${entry.exit_order_id}` : null} />
          <KV k="Exit price"    v={entry.exit_price ? `$${Number(entry.exit_price).toFixed(4)}` : null} />
          <KV k="Opened"        v={fmtIso(entry.entry_time ?? entry.opened_at)} />
          <KV k="Closed"        v={fmtIso(entry.exit_time ?? entry.closed_at)} />
          <div className="mt-2 pt-2 border-t border-border/30">
            <div className="text-muted-foreground mb-1">Result</div>
            <KV k="P&L"     v={entry.pnl != null ? `$${Number(entry.pnl).toFixed(2)}` : null} />
            <KV k="P&L %"   v={entry.pnl_pct != null ? `${Number(entry.pnl_pct).toFixed(2)}%` : null} />
          </div>
        </div>
      </div>

      {/* ── Decisions timeline ───────────────────────── */}
      {decisions.length > 0 && (
        <div className="mt-4 rounded-md border border-border/40 bg-card/40 p-3">
          <h3 className="text-[10px] uppercase tracking-wider text-muted-foreground mb-2">
            Decision timeline · {decisions.length} events within window
          </h3>
          <div className="space-y-1 max-h-[260px] overflow-y-auto">
            {decisions.slice().reverse().map((d: any, i: number) => {
              const ts = new Date(d.ts * 1000);
              const color =
                d.action === 'accept' || d.action === 'open' ? 'text-emerald' :
                d.action === 'reject' || d.action === 'error' ? 'text-crimson' :
                d.action === 'skip' || d.action === 'pause' ? 'text-amber-warn' :
                d.action === 'signal' ? 'text-cyan-accent' :
                'text-muted-foreground';
              return (
                <div key={i} className="flex items-start gap-2 text-[11px] border-b border-border/20 pb-1">
                  <span className="font-mono text-muted-foreground w-20 shrink-0">{ts.toLocaleTimeString('en-GB', { hour12: false })}</span>
                  <span className={_cn('font-bold uppercase w-14 shrink-0', color)}>{d.action}</span>
                  {d.direction && <span className={_cn('font-bold w-12 shrink-0', d.direction === 'LONG' ? 'text-emerald' : 'text-crimson')}>{d.direction}</span>}
                  {d.signal_score != null && <span className="font-mono text-muted-foreground w-10 shrink-0">{Number(d.signal_score).toFixed(0)}</span>}
                  <span className="text-muted-foreground flex-1 break-words">{d.reason}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
import { formatPct, formatUSD } from '@/lib/mockData';
import { cn } from '@/lib/utils';
import { Fragment, useState } from 'react';

function formatDuration(hours?: number | null): string {
  if (hours == null || !isFinite(hours) || hours < 0) return '—';
  const mins = hours * 60;
  if (mins < 1)       return '<1m';
  if (mins < 60)      return `${Math.round(mins)}m`;
  const h = Math.floor(hours);
  const m = Math.round((hours - h) * 60);
  if (hours < 24)     return m ? `${h}h ${m}m` : `${h}h`;
  const d = Math.floor(hours / 24);
  const rh = Math.floor(hours - d * 24);
  return rh ? `${d}d ${rh}h` : `${d}d`;
}

export default function Journal() {
  const [expandedId, setExpandedId] = useState<string | number | null>(null);
  const journal = useJournal();
  const entries = journal.data?.entries ?? [];

  const closedEntries = entries.filter((t: any) => t.status === 'CLOSED');
  const openEntries   = entries.filter((t: any) => t.status === 'OPEN');
  const totalPnl = closedEntries.reduce((sum, t) => sum + Number(t.pnl ?? 0), 0);
  const wins = closedEntries.filter((t) => Number(t.pnl ?? 0) > 0).length;

  return (
    <DashboardLayout>
      <PageHeader
        title="Trade Journal"
        subtitle={`${closedEntries.length} closed · ${openEntries.length} open — ${wins}W / ${closedEntries.length - wins}L`}
      >
        <div className="flex items-center gap-3 text-xs">
          <span className="text-muted-foreground">Realised P&L:</span>
          <span className={cn('font-mono font-semibold tabular-nums', totalPnl >= 0 ? 'text-emerald' : 'text-crimson')}>
            {formatUSD(totalPnl)}
          </span>
        </div>
      </PageHeader>

      <div className="hud-panel overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border bg-navy-900/50">
                {['Symbol', 'Side', 'Entry', 'Exit', 'P&L', 'P&L %', 'Size', 'Leverage', 'Duration', 'Source', 'Date'].map((h) => (
                  <th key={h} className="text-left py-3 px-3 text-[10px] font-semibold tracking-[0.1em] uppercase text-muted-foreground first:pl-4 last:pr-4">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {entries.length === 0 ? (
                <tr>
                  <td colSpan={11} className="py-10 text-center text-muted-foreground">
                    {journal.isLoading ? 'Loading…' : 'No journal entries yet — run some trades.'}
                  </td>
                </tr>
              ) : (
                entries.map((t) => {
                  const entryPrice = Number(t.entry_price ?? 0);
                  const exitPrice = Number(t.exit_price ?? 0);
                  const pnl = Number(t.pnl ?? 0);
                  const pnlPct = Number(t.pnl_pct ?? 0);
                  const size = t.size ?? t.qty ?? '—';
                  const duration = formatDuration(t.duration_hours ?? null);
                  const dateOnly = (t.entry_time ?? '').split('T')[0] || '—';
                  const levDisplay = (t as any).leverage ? `${(t as any).leverage}x` : '—';
                  const strategy = (t as any).strategy || '—';
                  const reasons = (t as any).reasons as string[] | undefined;
                  const regime = (t as any).regime;
                  const score   = (t as any).signal_score;
                  return (
                    <Fragment key={t.id}>
                      <tr
                        className={cn(
                          'border-b border-border/50 hover:bg-secondary/30 transition-colors cursor-pointer',
                          (t as any).status === 'OPEN' && 'bg-cyan-accent/5'
                        )}
                        onClick={() => setExpandedId(expandedId === t.id ? null : t.id)}
                      >
                        <td className="py-3 px-3 pl-4 font-semibold text-foreground">
                          {t.symbol}
                          {(t as any).status === 'OPEN' && (
                            <span className="ml-2 text-[10px] font-bold text-cyan-accent bg-cyan-accent/10 px-1.5 py-0.5 rounded-sm border border-cyan-accent/30">
                              OPEN
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-3">
                          <span className={cn('font-bold', t.side === 'LONG' ? 'text-emerald' : 'text-crimson')}>
                            {t.side}
                          </span>
                        </td>
                        <td className="py-3 px-3 font-mono tabular-nums text-foreground">{formatUSD(entryPrice, entryPrice < 10 ? 4 : 2)}</td>
                        <td className="py-3 px-3 font-mono tabular-nums text-foreground">
                          {t.exit_price != null ? formatUSD(exitPrice, exitPrice < 10 ? 4 : 2) : '—'}
                        </td>
                        <td className={cn('py-3 px-3 font-mono tabular-nums font-semibold', pnl >= 0 ? 'text-emerald' : 'text-crimson')}>
                          {formatUSD(pnl)}
                        </td>
                        <td className={cn('py-3 px-3 font-mono tabular-nums', pnlPct >= 0 ? 'text-emerald' : 'text-crimson')}>
                          {formatPct(pnlPct)}
                        </td>
                        <td className="py-3 px-3 font-mono tabular-nums text-foreground">{size}</td>
                        <td className="py-3 px-3 font-mono tabular-nums text-foreground">{levDisplay}</td>
                        <td className="py-3 px-3 text-muted-foreground whitespace-nowrap">{duration}</td>
                        <td className="py-3 px-3">
                          <span className={cn(
                            'px-1.5 py-0.5 rounded-sm text-[10px] uppercase tracking-wider',
                            strategy === 'auto'   ? 'bg-emerald/10 text-emerald border border-emerald/30' :
                            strategy === 'manual' ? 'bg-cyan-accent/10 text-cyan-accent border border-cyan-accent/30' :
                            'bg-secondary text-secondary-foreground'
                          )}>
                            {strategy}
                          </span>
                        </td>
                        <td className="py-3 px-3 pr-4 text-muted-foreground whitespace-nowrap">{dateOnly}</td>
                      </tr>
                      {expandedId === t.id && (
                        <tr className="border-b border-border/50">
                          <td colSpan={11} className="p-0 bg-navy-900/30">
                            <TradeTracePanel id={String(t.id)} fallbackEntry={t} />
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </DashboardLayout>
  );
}
