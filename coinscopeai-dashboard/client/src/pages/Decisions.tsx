/* Decisions — full filterable gate-verdict log.
 *
 * Surfaces the persistent DecisionJournal (JSONL primary + Postgres
 * mirror). Filters by symbol, action, and keyword. Newest first, polls
 * every 5s. Complements the summary panel on the Risk Gate page.
 */
import DashboardLayout from '@/components/DashboardLayout';
import MetricCard from '@/components/MetricCard';
import PageHeader from '@/components/PageHeader';
import {
  useDecisions,
  useDecisionStats,
  useDecisionPerSymbol,
  useConfig,
} from '@/lib/engine/hooks';
import { cn } from '@/lib/utils';
import { AlertTriangle, Ban, CheckCircle2, Play, Search, SkipForward } from 'lucide-react';
import { useMemo, useState } from 'react';

const ACTIONS = [
  { id: '',        label: 'All',      color: 'text-foreground' },
  { id: 'accept',  label: 'Accept',   color: 'text-emerald' },
  { id: 'reject',  label: 'Reject',   color: 'text-crimson' },
  { id: 'skip',    label: 'Skip',     color: 'text-amber-warn' },
  { id: 'signal',  label: 'Signal',   color: 'text-cyan-accent' },
  { id: 'open',    label: 'Opened',   color: 'text-emerald' },
  { id: 'close',   label: 'Closed',   color: 'text-muted-foreground' },
  { id: 'error',   label: 'Error',    color: 'text-crimson' },
] as const;

export default function Decisions() {
  const config   = useConfig();
  const [actionFilter, setActionFilter] = useState<string>('');
  const [symbolFilter, setSymbolFilter] = useState<string>('');
  const [searchText,   setSearchText]   = useState<string>('');
  const [limit,        setLimit]        = useState<number>(200);

  const decisions = useDecisions({
    action: actionFilter || undefined,
    symbol: symbolFilter || undefined,
    limit,
  });
  const stats     = useDecisionStats(24 * 3600);
  const perSymbol = useDecisionPerSymbol();

  const availablePairs = config.data?.scan_pairs ?? ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT'];

  const filtered = useMemo(() => {
    const rows = decisions.data?.decisions ?? [];
    if (!searchText.trim()) return rows;
    const needle = searchText.toLowerCase();
    return rows.filter((d: any) =>
      (d.reason ?? '').toLowerCase().includes(needle) ||
      (d.symbol ?? '').toLowerCase().includes(needle)
    );
  }, [decisions.data, searchText]);

  const actionCounts = stats.data?.by_action ?? {};
  const topRejects   = stats.data?.top_rejections ?? [];

  return (
    <DashboardLayout>
      <PageHeader
        title="Gate Decisions"
        subtitle="Persistent audit log of every autotrade verdict · invariant #5"
      />

      {/* ── Stats row ───────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
        <MetricCard label="Total (24h)" value={String(stats.data?.total ?? 0)} icon={Play} />
        <MetricCard label="Accepted"  value={String(actionCounts.accept   ?? 0)} icon={CheckCircle2} />
        <MetricCard label="Rejected"  value={String(actionCounts.reject   ?? 0)} icon={Ban} trend="down" />
        <MetricCard label="Skipped"   value={String(actionCounts.skip     ?? 0)} icon={SkipForward} />
        <MetricCard label="Signals"   value={String(actionCounts.signal   ?? 0)} />
        <MetricCard label="Errors"    value={String(actionCounts.error    ?? 0)} icon={AlertTriangle} trend="down" />
      </div>

      {/* ── Filters ──────────────────────────────────────────────────── */}
      <div className="hud-panel p-4 mb-6">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground mr-2">Action</span>
            {ACTIONS.map((a) => (
              <button
                key={a.id}
                onClick={() => setActionFilter(a.id)}
                className={cn(
                  'px-2.5 py-1 text-xs rounded-md border transition-colors',
                  actionFilter === a.id
                    ? 'bg-emerald/10 text-emerald border-emerald/40'
                    : 'bg-secondary text-muted-foreground border-border hover:border-border/80'
                )}
              >
                {a.label}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground mr-2">Symbol</span>
            <button
              onClick={() => setSymbolFilter('')}
              className={cn('px-2.5 py-1 text-xs rounded-md border transition-colors',
                !symbolFilter ? 'bg-emerald/10 text-emerald border-emerald/40' : 'bg-secondary text-muted-foreground border-border')}>
              All
            </button>
            {availablePairs.map((s: string) => (
              <button key={s} onClick={() => setSymbolFilter(s)}
                className={cn('px-2.5 py-1 text-xs rounded-md border transition-colors',
                  symbolFilter === s ? 'bg-emerald/10 text-emerald border-emerald/40' : 'bg-secondary text-muted-foreground border-border')}>
                {s.replace('USDT','')}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2 flex-1 min-w-[200px]">
            <Search className="w-3.5 h-3.5 text-muted-foreground" />
            <input
              type="text"
              placeholder="search reason / symbol…"
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              className="flex-1 bg-input border border-border rounded-md px-2 py-1 text-xs text-foreground focus:border-emerald/50 focus:outline-none"
            />
          </div>

          <div>
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground mr-2">Limit {limit}</span>
            <input type="range" min={50} max={1000} step={50} value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
              className="accent-emerald w-32" />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* ── Main decisions list ─────────────────────────────────────── */}
        <div className="lg:col-span-3 hud-panel p-4">
          <h2 className="text-xs font-semibold tracking-[0.12em] uppercase text-muted-foreground mb-3">
            Decisions <span className="ml-2 text-muted-foreground/60 normal-case tracking-normal">{filtered.length} of {decisions.data?.decisions?.length ?? 0}</span>
          </h2>
          <div className="overflow-y-auto max-h-[70vh] pr-2">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-card z-10">
                <tr className="border-b border-border">
                  {['Time','Action','Symbol','Dir','Score','Reason'].map(h => (
                    <th key={h} className="text-left py-2 px-2 text-[10px] font-semibold tracking-[0.1em] uppercase text-muted-foreground">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr><td colSpan={6} className="py-10 text-center text-muted-foreground">
                    {decisions.isLoading ? 'Loading…' : 'No matching decisions.'}
                  </td></tr>
                ) : (
                  filtered.map((d: any, i: number) => {
                    const ts = new Date(d.ts * 1000);
                    const color =
                      d.action === 'accept' || d.action === 'open' ? 'text-emerald' :
                      d.action === 'reject' || d.action === 'error' ? 'text-crimson' :
                      d.action === 'skip' || d.action === 'pause' ? 'text-amber-warn' :
                      d.action === 'signal' ? 'text-cyan-accent' :
                      'text-muted-foreground';
                    return (
                      <tr key={i} className="border-b border-border/30 hover:bg-secondary/30 transition-colors">
                        <td className="py-1.5 px-2 font-mono tabular-nums text-muted-foreground whitespace-nowrap">
                          {ts.toLocaleTimeString('en-GB', { hour12: false })}
                          <span className="ml-1 text-muted-foreground/50">
                            {ts.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })}
                          </span>
                        </td>
                        <td className={cn('py-1.5 px-2 font-bold uppercase text-[10px] tracking-wider', color)}>
                          {d.action}
                        </td>
                        <td className="py-1.5 px-2 font-mono text-foreground">{d.symbol}</td>
                        <td className={cn('py-1.5 px-2 font-bold text-[10px]',
                          d.direction === 'LONG' ? 'text-emerald' :
                          d.direction === 'SHORT' ? 'text-crimson' : 'text-muted-foreground')}>
                          {d.direction ?? '—'}
                        </td>
                        <td className="py-1.5 px-2 font-mono tabular-nums text-muted-foreground">
                          {d.signal_score != null ? Number(d.signal_score).toFixed(0) : ''}
                        </td>
                        <td className="py-1.5 px-2 text-muted-foreground max-w-md truncate" title={d.reason}>
                          {d.reason}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* ── Sidebar: top rejects + per-symbol ───────────────────────── */}
        <div className="space-y-6">
          <div className="hud-panel p-4">
            <h2 className="text-xs font-semibold tracking-[0.12em] uppercase text-muted-foreground mb-3">
              Top Rejection Reasons (24h)
            </h2>
            <div className="space-y-1.5 text-xs">
              {topRejects.length === 0 ? (
                <div className="text-muted-foreground py-4 text-center">No rejections yet.</div>
              ) : (
                topRejects.map((r: any, i: number) => (
                  <div key={i} className="flex items-center justify-between gap-2">
                    <span className="text-foreground truncate flex-1" title={r.reason}>{r.reason}</span>
                    <span className="font-mono tabular-nums text-amber-warn w-8 text-right">{r.count}</span>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="hud-panel p-4">
            <h2 className="text-xs font-semibold tracking-[0.12em] uppercase text-muted-foreground mb-3">
              Per-Symbol Activity
            </h2>
            <div className="space-y-1.5 text-xs">
              {Object.values(perSymbol.data?.symbols ?? {}).length === 0 ? (
                <div className="text-muted-foreground py-4 text-center">No symbols yet.</div>
              ) : (
                Object.values(perSymbol.data!.symbols).map((h: any) => (
                  <div key={h.symbol} className={cn('flex items-center justify-between gap-2 py-1 px-1 rounded', h.is_paused && 'bg-amber-warn/5')}>
                    <span className="font-mono text-foreground">{h.symbol}</span>
                    <div className="flex gap-1.5 text-[10px]">
                      <span className="text-emerald">{h.accepts_24h}</span>
                      <span className="text-muted-foreground">/</span>
                      <span className="text-crimson">{h.rejects_24h}</span>
                      <span className="text-muted-foreground">/</span>
                      <span className="text-amber-warn">{h.skips_24h}</span>
                      {h.is_paused && (
                        <span className="ml-1 text-amber-warn">PAUSED</span>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
            <div className="mt-3 pt-2 border-t border-border/30 text-[10px] text-muted-foreground">
              <span className="text-emerald">accept</span> / <span className="text-crimson">reject</span> / <span className="text-amber-warn">skip</span> counts (24h)
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
