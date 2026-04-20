/* Live Scanner — Live signal feed via engine /signals + POST /scan */
import DashboardLayout from '@/components/DashboardLayout';
import ExecuteOrderDialog from '@/components/ExecuteOrderDialog';
import PageHeader from '@/components/PageHeader';
import StatusBadge, { getRegimeVariant } from '@/components/StatusBadge';
import { qk, useConfig, useScan, useSignals } from '@/lib/engine/hooks';
import { formatUSD } from '@/lib/mockData';
import { cn } from '@/lib/utils';
import { useQueryClient } from '@tanstack/react-query';
import { Play, RefreshCw } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

function relTime(ts: number): string {
  const secs = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (secs < 60) return `${secs}s ago`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  return `${Math.floor(secs / 3600)}h ago`;
}

export default function Scanner() {
  const signals = useSignals();
  const config  = useConfig();
  const scan    = useScan();
  const qc      = useQueryClient();

  const list = signals.data?.signals ?? [];
  const pairs = config.data?.scan_pairs ?? [];
  const minScore = config.data?.min_confluence_score ?? 65;
  const loop = signals.data?.loop;

  const [executeTarget, setExecuteTarget] = useState<{
    symbol: string; side: 'BUY'|'SELL'; entry: number; stopLoss?: number | null; takeProfit?: number | null; scoreLabel?: string;
  } | null>(null);

  async function runScan() {
    try {
      await scan.mutateAsync({ pairs, timeframe: '1h', limit: 100 });
      await qc.invalidateQueries({ queryKey: qk.signals });
      toast.success('Scan complete');
    } catch (err: any) {
      toast.error(`Scan failed: ${err?.response?.data?.detail ?? err?.message ?? err}`);
    }
  }

  return (
    <DashboardLayout>
      <PageHeader
        title="Live Scanner"
        subtitle={`Confluence signal detection across ${pairs.length} pair${pairs.length === 1 ? '' : 's'} · min score ${minScore}`}
      >
        <div className="flex items-center gap-3 text-xs">
          {loop && (
            <>
              <span className={cn('flex items-center gap-1.5', loop.running ? 'text-emerald' : 'text-amber-warn')}>
                <span className={cn('w-1.5 h-1.5 rounded-full', loop.running ? 'bg-emerald animate-pulse' : 'bg-amber-warn')} />
                {loop.running ? 'Auto-scan ON' : 'Idle'}
              </span>
              <span className="text-muted-foreground">
                tick #{loop.scans_total} · {loop.last_duration_ms}ms · {loop.last_actionable}/{loop.last_signals} actionable
              </span>
              <span className="text-muted-foreground">
                {loop.seconds_to_next != null && loop.seconds_to_next > 0
                  ? `next in ${loop.seconds_to_next.toFixed(0)}s`
                  : 'scanning…'}
              </span>
            </>
          )}
          <button
            onClick={runScan}
            disabled={scan.isPending}
            className="flex items-center gap-2 bg-emerald/10 border border-emerald/30 text-emerald text-xs font-medium px-3 py-1.5 rounded-md hover:bg-emerald/20 disabled:opacity-50 transition-colors"
          >
            <RefreshCw className={cn('w-3.5 h-3.5', scan.isPending && 'animate-spin')} />
            {scan.isPending ? 'Scanning…' : 'Run Now'}
          </button>
        </div>
      </PageHeader>

      <div className="space-y-3">
        {list.length === 0 ? (
          <div className="hud-panel p-10 text-center text-sm text-muted-foreground">
            {signals.isLoading ? 'Loading signals…' : 'No signals yet — click Run Scan to evaluate the configured pairs.'}
          </div>
        ) : (
          list.map((sig) => {
            const scorePct = Math.max(0, Math.min(100, sig.score));
            const regime = sig.regime && sig.regime !== 'UNKNOWN' ? sig.regime : '—';
            const rr = sig.setup?.rr_ratio ?? 0;
            const entry = sig.setup?.entry ?? 0;
            const tp = sig.setup?.tp2 ?? sig.setup?.tp1 ?? 0;
            const sl = sig.setup?.stop_loss ?? 0;

            return (
              <div key={`${sig.symbol}-${sig.scanned_at}`} className="hud-panel p-4 hover:border-emerald/20 transition-colors">
                <div className="flex flex-col lg:flex-row lg:items-center gap-4">
                  {/* Symbol + Direction */}
                  <div className="flex items-center gap-3 lg:w-48">
                    <div className="text-base font-semibold text-foreground">{sig.symbol}</div>
                    <span className={cn(
                      'text-xs font-bold px-2 py-0.5 rounded-sm',
                      sig.direction === 'LONG' && 'bg-emerald/10 text-emerald',
                      sig.direction === 'SHORT' && 'bg-crimson/10 text-crimson',
                      sig.direction === 'NEUTRAL' && 'bg-muted text-muted-foreground',
                    )}>
                      {sig.direction}
                    </span>
                    {sig.actionable && (
                      <span className="text-[10px] font-bold text-emerald bg-emerald/10 px-1.5 py-0.5 rounded-sm border border-emerald/30">
                        LIVE
                      </span>
                    )}
                  </div>

                  {/* Confluence score */}
                  <div className="lg:w-40">
                    <div className="text-[10px] font-semibold tracking-[0.12em] uppercase text-muted-foreground mb-1">
                      Score / {sig.strength}
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-2 bg-navy-800 rounded-full overflow-hidden">
                        <div
                          className={cn(
                            'h-full rounded-full transition-all',
                            scorePct >= 80 ? 'bg-emerald' : scorePct >= 60 ? 'bg-cyan-accent' : scorePct >= 40 ? 'bg-amber-warn' : 'bg-crimson'
                          )}
                          style={{ width: `${scorePct}%` }}
                        />
                      </div>
                      <span className="font-mono text-sm font-semibold text-foreground tabular-nums w-10">{scorePct.toFixed(0)}</span>
                    </div>
                  </div>

                  {/* Regime + 4h trend */}
                  <div className="lg:w-36">
                    <div className="text-[10px] font-semibold tracking-[0.12em] uppercase text-muted-foreground mb-1">Regime · 4h</div>
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <StatusBadge label={regime} variant={getRegimeVariant(regime)} />
                      {sig.htf_trend && (
                        <span
                          title={sig.htf_agrees ? '4h agrees with direction' : '4h opposes direction'}
                          className={cn(
                            'text-[10px] font-bold px-1.5 py-0.5 rounded-sm uppercase tracking-wider',
                            sig.htf_agrees ? 'bg-emerald/10 text-emerald border border-emerald/30' :
                            sig.htf_trend === 'neutral' ? 'bg-muted/30 text-muted-foreground border border-border' :
                            'bg-crimson/10 text-crimson border border-crimson/30',
                          )}
                        >
                          {sig.htf_trend}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Scanners */}
                  <div className="lg:w-44">
                    <div className="text-[10px] font-semibold tracking-[0.12em] uppercase text-muted-foreground mb-1">Scanners</div>
                    <div className="text-xs text-foreground">
                      {sig.scanners.length > 0 ? sig.scanners.map(s => s.replace('Scanner', '')).join(' · ') : '—'}
                    </div>
                  </div>

                  {/* Prices */}
                  <div className="flex gap-4 lg:flex-1">
                    <div>
                      <div className="text-[10px] font-semibold tracking-[0.12em] uppercase text-muted-foreground mb-1">Entry</div>
                      <span className="font-mono text-sm text-foreground tabular-nums">{formatUSD(entry, entry < 10 ? 4 : 2)}</span>
                    </div>
                    <div>
                      <div className="text-[10px] font-semibold tracking-[0.12em] uppercase text-muted-foreground mb-1">Target</div>
                      <span className="font-mono text-sm text-emerald tabular-nums">{formatUSD(tp, tp < 10 ? 4 : 2)}</span>
                    </div>
                    <div>
                      <div className="text-[10px] font-semibold tracking-[0.12em] uppercase text-muted-foreground mb-1">Stop</div>
                      <span className="font-mono text-sm text-crimson tabular-nums">{formatUSD(sl, sl < 10 ? 4 : 2)}</span>
                    </div>
                    <div>
                      <div className="text-[10px] font-semibold tracking-[0.12em] uppercase text-muted-foreground mb-1">R:R</div>
                      <span className="font-mono text-sm text-cyan-accent tabular-nums">{rr.toFixed(2)}</span>
                    </div>
                  </div>

                  {/* Last update */}
                  <div className="text-xs text-muted-foreground lg:w-20 text-right">
                    {relTime(sig.scanned_at)}
                  </div>

                  {/* Execute button (enabled only when signal is valid + actionable) */}
                  <button
                    disabled={!sig.actionable || !sig.setup?.valid}
                    onClick={() => setExecuteTarget({
                      symbol:     sig.symbol,
                      side:       sig.direction === 'SHORT' ? 'SELL' : 'BUY',
                      entry:      sig.setup?.entry ?? 0,
                      stopLoss:   sig.setup?.stop_loss ?? null,
                      takeProfit: sig.setup?.tp2 ?? sig.setup?.tp1 ?? null,
                      scoreLabel: `${sig.strength} ${scorePct.toFixed(0)}`,
                    })}
                    title={sig.actionable ? 'Open this trade on Binance Demo' : 'Score below actionable threshold'}
                    className={cn(
                      'flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-md transition-colors',
                      sig.actionable && sig.setup?.valid
                        ? (sig.direction === 'LONG'
                            ? 'bg-emerald/10 text-emerald border border-emerald/40 hover:bg-emerald/20'
                            : 'bg-crimson/10 text-crimson border border-crimson/40 hover:bg-crimson/20')
                        : 'bg-muted/30 text-muted-foreground border border-border cursor-not-allowed',
                    )}
                  >
                    <Play className="w-3 h-3" />
                    Execute
                  </button>
                </div>

                {/* Reasons row */}
                {sig.reasons.length > 0 && (
                  <div className="mt-3 pt-2 border-t border-border/40 text-xs text-muted-foreground">
                    <span className="text-foreground font-medium">Reasons:</span>{' '}
                    {sig.reasons.join(' · ')}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Legend */}
      <div className="mt-6 hud-panel p-4">
        <h3 className="text-[10px] font-semibold tracking-[0.12em] uppercase text-muted-foreground mb-2">Signal Legend</h3>
        <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
          <span><span className="text-emerald">●</span> Score ≥ 80 — Strong confluence</span>
          <span><span className="text-cyan-accent">●</span> 60–79 — Moderate confluence</span>
          <span><span className="text-amber-warn">●</span> 40–59 — Weak confluence</span>
          <span><span className="text-crimson">●</span> &lt; 40 — Noise</span>
          <span className="ml-auto text-[11px]">Actionable threshold: {minScore}</span>
        </div>
      </div>

      {executeTarget && (
        <ExecuteOrderDialog
          open={executeTarget !== null}
          onOpenChange={(v) => !v && setExecuteTarget(null)}
          {...executeTarget}
        />
      )}
    </DashboardLayout>
  );
}
