/* Risk Gate — Real-time risk monitoring + kill switch (live engine) */
import DashboardLayout from '@/components/DashboardLayout';
import PageHeader from '@/components/PageHeader';
import StatusBadge, { getRiskVariant } from '@/components/StatusBadge';
import { engine } from '@/lib/engine/client';
import {
  qk, useCircuitBreaker, useConfig, useDecisions, useDecisionPerSymbol,
  useExposure, useHistoricalStats, usePositions, useUnpauseSymbol,
} from '@/lib/engine/hooks';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import { AlertTriangle, Database, Power, Shield, ShieldAlert, ShieldCheck } from 'lucide-react';

function GaugeBar({ label, value, max, unit = '%' }: { label: string; value: number; max: number; unit?: string }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  const isHigh = pct >= 80;
  const isMed = pct >= 60;

  return (
    <div className="space-y-1.5">
      <div className="flex justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className={cn('font-mono tabular-nums font-medium', isHigh ? 'text-crimson' : isMed ? 'text-amber-warn' : 'text-emerald')}>
          {value}{unit} / {max}{unit}
        </span>
      </div>
      <div className="h-2 bg-navy-800 rounded-full overflow-hidden">
        <div
          className={cn('h-full rounded-full transition-all duration-500', isHigh ? 'bg-crimson' : isMed ? 'bg-amber-warn' : 'bg-emerald')}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export default function RiskGate() {
  const cb = useCircuitBreaker();
  const expo = useExposure();
  const pos = usePositions();
  const config = useConfig();
  const perSymbol = useDecisionPerSymbol();
  const recentDecisions = useDecisions({ limit: 20 });
  const histStats = useHistoricalStats();
  const unpauseMut = useUnpauseSymbol();
  const qc = useQueryClient();

  const state = cb.data?.state ?? 'CLOSED';
  const killActive = state !== 'CLOSED';
  const statusLabel = state === 'CLOSED' ? 'GREEN' : state === 'TRIPPED' || state === 'OPEN' ? 'RED' : 'YELLOW';

  const dailyLossPct = expo.data?.daily_loss_pct ?? 0;
  const maxDailyLossPct = cb.data?.max_daily_loss_pct ?? 2;
  const maxDrawdownPct = cb.data?.max_drawdown_pct ?? 10;
  const exposurePct = expo.data?.total_exposure_pct ?? 0;
  const maxExposurePct = expo.data?.max_total_exposure_pct ?? 80;
  const posCount = pos.data?.position_count ?? 0;
  const maxPos = config.data?.max_open_positions ?? 3;
  const maxLev = config.data?.max_leverage ?? 20;

  async function toggleKillSwitch() {
    try {
      if (killActive) {
        await engine.post('/circuit-breaker/reset');
        toast.success('Circuit breaker reset');
      } else {
        await engine.post('/circuit-breaker/trip', { reason: 'Manual trip via dashboard' });
        toast.warning('Circuit breaker tripped — trading halted');
      }
      await qc.invalidateQueries({ queryKey: qk.circuitBreaker });
    } catch (err: any) {
      toast.error(`Kill switch action failed: ${err?.message ?? err}`);
    }
  }

  const alerts: { level: 'INFO' | 'WARN'; message: string; time: string }[] = [
    {
      level: 'INFO',
      message: cb.data
        ? `Breaker ${state} · ${cb.data.trip_count} trip${cb.data.trip_count === 1 ? '' : 's'} lifetime`
        : 'Awaiting breaker state…',
      time: cb.data ? new Date(cb.data.timestamp * 1000).toLocaleTimeString() : '—',
    },
    ...(posCount >= maxPos
      ? [{ level: 'WARN' as const, message: `Position count at maximum (${posCount}/${maxPos})`, time: new Date().toLocaleTimeString() }]
      : []),
    ...(exposurePct >= maxExposurePct * 0.8
      ? [{ level: 'WARN' as const, message: `Exposure approaching cap (${exposurePct.toFixed(1)}% / ${maxExposurePct}%)`, time: new Date().toLocaleTimeString() }]
      : []),
    ...(dailyLossPct >= maxDailyLossPct * 0.8
      ? [{ level: 'WARN' as const, message: `Daily loss approaching threshold (${dailyLossPct.toFixed(2)}% / ${maxDailyLossPct}%)`, time: new Date().toLocaleTimeString() }]
      : []),
  ];

  return (
    <DashboardLayout>
      <PageHeader title="Risk Gate" subtitle="Real-time risk monitoring and kill switch control" />

      {/* Main status */}
      <div className="hud-panel-glow p-6 mb-6">
        <div className="flex flex-col lg:flex-row lg:items-center gap-6">
          <div className="flex items-center gap-4">
            {statusLabel === 'GREEN' ? (
              <ShieldCheck className="w-12 h-12 text-emerald" />
            ) : statusLabel === 'YELLOW' ? (
              <Shield className="w-12 h-12 text-amber-warn" />
            ) : (
              <ShieldAlert className="w-12 h-12 text-crimson" />
            )}
            <div>
              <div className="flex items-center gap-3">
                <StatusBadge label={statusLabel} variant={getRiskVariant(statusLabel)} pulse />
                <span className="text-sm text-muted-foreground">Circuit Breaker: {state}</span>
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                Last check: {cb.data ? new Date(cb.data.timestamp * 1000).toLocaleString() : '—'}
              </p>
            </div>
          </div>

          {/* Kill Switch */}
          <div className="lg:ml-auto flex items-center gap-4">
            <div className="text-right">
              <div className="text-[10px] font-semibold tracking-[0.12em] uppercase text-muted-foreground">Kill Switch</div>
              <div className={cn('text-sm font-semibold', killActive ? 'text-crimson' : 'text-emerald')}>
                {killActive ? 'ACTIVATED' : 'INACTIVE'}
              </div>
            </div>
            <button
              onClick={toggleKillSwitch}
              className={cn(
                'w-14 h-14 rounded-lg flex items-center justify-center transition-all border-2',
                killActive
                  ? 'bg-crimson/20 border-crimson text-crimson hover:bg-crimson/30'
                  : 'bg-secondary border-border text-muted-foreground hover:border-crimson hover:text-crimson'
              )}
              title={killActive ? 'Reset circuit breaker' : 'Trip circuit breaker (halt trading)'}
            >
              <Power className="w-6 h-6" />
            </button>
          </div>
        </div>
      </div>

      {/* Risk gauges */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <div className="hud-panel p-4 space-y-4">
          <h2 className="text-xs font-semibold tracking-[0.12em] uppercase text-muted-foreground">Risk Parameters</h2>
          <GaugeBar label="Daily Loss" value={Number(dailyLossPct.toFixed(2))} max={maxDailyLossPct} />
          <GaugeBar label="Open Positions" value={posCount} max={maxPos} unit="" />
          <GaugeBar label="Total Exposure" value={Number(exposurePct.toFixed(1))} max={maxExposurePct} />
        </div>

        {/* Thresholds */}
        <div className="space-y-4">
          <div className="hud-panel p-4">
            <h2 className="text-xs font-semibold tracking-[0.12em] uppercase text-muted-foreground mb-3">Risk Thresholds</h2>
            <div className="space-y-2 text-xs">
              {[
                ['Max Drawdown', `${maxDrawdownPct}%`, 'Account-level stop loss'],
                ['Daily Loss Limit', `${maxDailyLossPct}%`, 'Resets at 00:00 UTC'],
                ['Max Leverage', `${maxLev}x`, 'Per-position limit'],
                ['Max Positions', String(maxPos), 'Concurrent open positions'],
                ['Exposure Cap', `${maxExposurePct}%`, 'Aggregate position exposure'],
              ].map(([label, value, desc]) => (
                <div key={label} className="flex items-center justify-between py-1.5 border-b border-border/30">
                  <div>
                    <span className="text-foreground font-medium">{label}</span>
                    <span className="text-muted-foreground ml-2">— {desc}</span>
                  </div>
                  <span className="font-mono tabular-nums text-foreground">{value}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Live-derived alerts */}
          <div className="hud-panel p-4">
            <h2 className="text-xs font-semibold tracking-[0.12em] uppercase text-muted-foreground mb-3">Status</h2>
            <div className="space-y-2">
              {alerts.map((alert, i) => (
                <div key={i} className="flex items-start gap-2 text-xs">
                  <AlertTriangle className={cn(
                    'w-3.5 h-3.5 mt-0.5 shrink-0',
                    alert.level === 'WARN' ? 'text-amber-warn' : 'text-muted-foreground'
                  )} />
                  <div className="flex-1">
                    <span className="text-foreground">{alert.message}</span>
                    <span className="text-muted-foreground ml-2">{alert.time}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ── Per-symbol health grid ─────────────────────────────────── */}
      <div className="hud-panel p-4 mt-4">
        <h2 className="text-xs font-semibold tracking-[0.12em] uppercase text-muted-foreground mb-3">
          Per-Symbol Health <span className="ml-2 text-muted-foreground/60 normal-case tracking-normal">(rolling 24h)</span>
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border">
                {['Symbol','Last','Accepts','Rejects','Skips','Consec Losses','Daily PnL','Status',''].map(h => (
                  <th key={h} className="text-left py-2 px-3 text-[10px] font-semibold tracking-[0.1em] uppercase text-muted-foreground">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Object.values(perSymbol.data?.symbols ?? {}).length === 0 ? (
                <tr><td colSpan={9} className="py-6 text-center text-muted-foreground">No decisions yet — run a scan or enable autotrade.</td></tr>
              ) : (
                Object.values(perSymbol.data!.symbols).map((h: any) => (
                  <tr key={h.symbol} className={cn('border-b border-border/50', h.is_paused && 'bg-amber-warn/5')}>
                    <td className="py-2 px-3 font-medium text-foreground">{h.symbol}</td>
                    <td className="py-2 px-3 text-muted-foreground uppercase text-[10px]">{h.last_action}</td>
                    <td className="py-2 px-3 font-mono tabular-nums text-emerald">{h.accepts_24h}</td>
                    <td className="py-2 px-3 font-mono tabular-nums text-crimson">{h.rejects_24h}</td>
                    <td className="py-2 px-3 font-mono tabular-nums text-muted-foreground">{h.skips_24h}</td>
                    <td className={cn('py-2 px-3 font-mono tabular-nums', h.consecutive_losses >= 3 ? 'text-crimson' : h.consecutive_losses > 0 ? 'text-amber-warn' : 'text-muted-foreground')}>{h.consecutive_losses}</td>
                    <td className={cn('py-2 px-3 font-mono tabular-nums', h.daily_pnl_usd >= 0 ? 'text-emerald' : 'text-crimson')}>
                      ${h.daily_pnl_usd.toFixed(2)} ({(h.daily_pnl_pct * 100).toFixed(2)}%)
                    </td>
                    <td className="py-2 px-3">
                      {h.is_paused ? (
                        <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-sm bg-amber-warn/10 text-amber-warn border border-amber-warn/40">
                          PAUSED {Math.floor(h.pause_remaining/60)}m
                        </span>
                      ) : (
                        <span className="text-[10px] text-muted-foreground">active</span>
                      )}
                    </td>
                    <td className="py-2 px-3">
                      {h.is_paused && (
                        <button
                          onClick={async () => {
                            try {
                              await unpauseMut.mutateAsync(h.symbol);
                              toast.success(`Unpaused ${h.symbol}`);
                              await qc.invalidateQueries({ queryKey: ["engine","decisions","per-symbol"] });
                            } catch (err: any) {
                              toast.error(err?.message ?? String(err));
                            }
                          }}
                          className="text-[10px] font-medium px-2 py-0.5 rounded-sm bg-emerald/10 text-emerald border border-emerald/30 hover:bg-emerald/20"
                        >
                          Unpause
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Recent decisions feed ──────────────────────────────────── */}
      <div className="hud-panel p-4 mt-4">
        <h2 className="text-xs font-semibold tracking-[0.12em] uppercase text-muted-foreground mb-3">
          Recent Gate Decisions <span className="ml-2 text-muted-foreground/60 normal-case tracking-normal">(persistent log)</span>
        </h2>
        <div className="space-y-1.5 max-h-[380px] overflow-y-auto pr-2">
          {(recentDecisions.data?.decisions ?? []).length === 0 ? (
            <div className="text-xs text-muted-foreground py-4 text-center">No decisions logged yet.</div>
          ) : (
            recentDecisions.data!.decisions.map((d: any, i: number) => {
              const ts = new Date(d.ts * 1000);
              const color =
                d.action === 'accept' ? 'text-emerald' :
                d.action === 'reject' || d.action === 'error' ? 'text-crimson' :
                d.action === 'skip'   ? 'text-amber-warn' :
                'text-muted-foreground';
              return (
                <div key={i} className="flex items-start gap-2 text-[11px] border-b border-border/30 pb-1">
                  <span className="font-mono text-muted-foreground w-16 shrink-0">{ts.toLocaleTimeString('en-GB', { hour12: false })}</span>
                  <span className={cn('font-bold uppercase text-[10px] tracking-wider w-16 shrink-0', color)}>{d.action}</span>
                  <span className="font-mono text-foreground w-20 shrink-0">{d.symbol}</span>
                  {d.direction && <span className={cn('font-bold text-[10px] w-12 shrink-0', d.direction === 'LONG' ? 'text-emerald' : 'text-crimson')}>{d.direction}</span>}
                  {d.signal_score != null && <span className="font-mono text-muted-foreground w-10 shrink-0">{Number(d.signal_score).toFixed(0)}</span>}
                  <span className="text-muted-foreground flex-1 break-words">{d.reason}</span>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* ── Historical klines store ────────────────────────────────── */}
      <div className="hud-panel p-4 mt-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-semibold tracking-[0.12em] uppercase text-muted-foreground flex items-center gap-2">
            <Database className="w-3.5 h-3.5" /> Historical Data Store
          </h2>
          <span className="text-[10px] text-muted-foreground">
            {histStats.data
              ? `${histStats.data.total_rows?.toLocaleString() ?? 0} rows · ${((histStats.data.db_size_bytes ?? 0) / 1024 / 1024).toFixed(2)} MB · ${histStats.data.configured_lookback_d ?? 90}d rolling`
              : '—'}
          </span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
          {(histStats.data?.streams ?? []).map((s: any) => (
            <div key={`${s.symbol}-${s.interval}`} className="rounded-md border border-border/40 bg-card/50 p-2">
              <div className="flex justify-between text-[10px] text-muted-foreground uppercase tracking-wider">
                <span>{s.symbol}</span>
                <span>{s.interval}</span>
              </div>
              <div className="font-mono text-sm text-foreground tabular-nums mt-1">{s.rows.toLocaleString()} bars</div>
              {s.last_ts && (
                <div className="text-[10px] text-muted-foreground">
                  up to {new Date(s.last_ts).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </DashboardLayout>
  );
}
