/* Settings — real Autotrade control panel (Phase 3c) + cosmetic alerts.
 *
 * The "Autotrade" card turns the engine from a signal-watcher into an
 * executor. When enabled, every scan-loop tick that produces a valid,
 * actionable signal will be placed on Binance Futures Demo — subject to
 * circuit breaker, position count, exposure cap, cooldown, and min score.
 */
import DashboardLayout from '@/components/DashboardLayout';
import PageHeader from '@/components/PageHeader';
import {
  useAutotradeConfig,
  useAutotradeDisable,
  useAutotradeEnable,
  useAutotradeStatus,
  useConfig,
} from '@/lib/engine/hooks';
import { cn } from '@/lib/utils';
import { AlertTriangle, CheckCircle2, Play, Power } from 'lucide-react';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

export default function Settings() {
  const status = useAutotradeStatus();
  const config = useConfig();
  const enableMut  = useAutotradeEnable();
  const disableMut = useAutotradeDisable();
  const configMut  = useAutotradeConfig();

  // Form state mirrors the engine; hydrate once we have status.
  const [risk, setRisk] = useState<number>(1);
  const [lev,  setLev]  = useState<number>(5);
  const [minScore, setMinScore] = useState<number>(65);
  const [cooldown, setCooldown] = useState<number>(300);
  const [attachBracket, setAttachBracket] = useState<boolean>(true);
  const [allowedDirections, setAllowedDirections] = useState<"BOTH"|"LONG_ONLY"|"SHORT_ONLY">("LONG_ONLY");
  const [mtfFilter, setMtfFilter] = useState<boolean>(false);
  const [mtfBlockNeutral, setMtfBlockNeutral] = useState<boolean>(true);

  useEffect(() => {
    if (!status.data) return;
    setRisk(status.data.effective_risk_pct ?? 1);
    setLev(status.data.default_leverage ?? 5);
    setMinScore(status.data.effective_min_score ?? 65);
    setCooldown(status.data.cooldown_s ?? 300);
    setAttachBracket(status.data.attach_bracket ?? true);
    setAllowedDirections(status.data.allowed_directions ?? "LONG_ONLY");
    setMtfFilter(status.data.mtf_filter_enabled ?? true);
    setMtfBlockNeutral(status.data.mtf_block_neutral ?? true);
  }, [status.data?.enabled, status.data?.default_leverage]);  // bootstrap once

  const enabled = status.data?.enabled ?? false;
  const maxLev  = config.data?.max_leverage ?? 10;

  async function toggleAutotrade() {
    try {
      if (enabled) {
        if (!confirm('Turn autotrade OFF? Existing positions will remain open; only new entries are paused.')) return;
        await disableMut.mutateAsync();
        toast.success('Autotrade OFF');
      } else {
        if (!confirm(
          `Turn autotrade ON? The engine will place orders automatically whenever a ≥${minScore} score signal ` +
          `appears that passes all risk gates. Running on Binance Futures Demo.`
        )) return;
        await enableMut.mutateAsync();
        toast.success('Autotrade ON');
      }
      await status.refetch();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail ?? err?.message ?? String(err));
    }
  }

  async function saveConfig() {
    try {
      await configMut.mutateAsync({
        risk_per_trade_pct: risk,
        default_leverage:   lev,
        attach_bracket:     attachBracket,
        min_score:          minScore,
        cooldown_s:         cooldown,
        allowed_directions: allowedDirections,
        mtf_filter_enabled: mtfFilter,
        mtf_block_neutral:  mtfBlockNeutral,
      });
      toast.success('Config saved');
      await status.refetch();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail ?? err?.message ?? String(err));
    }
  }

  const events = status.data?.recent_events ?? [];

  return (
    <DashboardLayout>
      <PageHeader
        title="Settings"
        subtitle="Autotrade control + tunables · Binance Futures Demo"
      />

      {/* ── Autotrade master toggle ───────────────────────────────────── */}
      <div className={cn(
        'rounded-lg border p-5 mb-6 transition-colors',
        enabled ? 'border-emerald/40 bg-emerald/5' : 'border-border bg-card'
      )}>
        <div className="flex items-center gap-4">
          <button
            onClick={toggleAutotrade}
            disabled={enableMut.isPending || disableMut.isPending}
            className={cn(
              'w-16 h-16 rounded-xl flex items-center justify-center border-2 transition-all',
              enabled
                ? 'bg-emerald text-white border-emerald/60 shadow-lg shadow-emerald/20'
                : 'bg-secondary border-border text-muted-foreground hover:border-emerald hover:text-emerald',
            )}
            title={enabled ? 'Click to stop autotrade' : 'Click to start autotrade'}
          >
            <Power className="w-8 h-8" />
          </button>

          <div className="flex-1">
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-semibold text-foreground">Autotrade</h2>
              <span className={cn(
                'text-[10px] font-bold px-2 py-0.5 rounded-sm tracking-wider uppercase',
                enabled
                  ? 'bg-emerald/10 text-emerald border border-emerald/40'
                  : 'bg-muted/40 text-muted-foreground border border-border',
              )}>
                {enabled ? 'Running' : 'Stopped'}
              </span>
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {enabled
                ? `Engine auto-executes ≥${minScore}-score signals on every scan tick. Kill-switch via Risk Gate page.`
                : 'Engine is scanning only. Click the power button to let it trade autonomously.'}
            </p>
          </div>

          {/* Counters */}
          <div className="grid grid-cols-2 gap-4 text-right">
            <div>
              <div className="text-[10px] font-semibold tracking-wider uppercase text-muted-foreground">Entries</div>
              <div className="font-mono text-xl font-bold text-emerald tabular-nums">{status.data?.entries_total ?? 0}</div>
            </div>
            <div>
              <div className="text-[10px] font-semibold tracking-wider uppercase text-muted-foreground">Rejected</div>
              <div className="font-mono text-xl font-bold text-amber-warn tabular-nums">{status.data?.entries_rejected ?? 0}</div>
            </div>
          </div>
        </div>

        {status.data?.last_reject_reason && (
          <div className="mt-3 flex items-center gap-2 text-xs text-amber-warn">
            <AlertTriangle className="w-3.5 h-3.5" />
            Last reject: {status.data.last_reject_reason}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* ── Tunables ────────────────────────────────────────────────── */}
        <div className="hud-panel p-5">
          <h2 className="text-xs font-semibold tracking-[0.12em] uppercase text-muted-foreground mb-4">
            Autotrade Tunables
          </h2>

          <div className="space-y-5 text-sm">
            <div>
              <label className="text-xs text-muted-foreground block mb-2">
                Direction filter
              </label>
              <div className="flex gap-1.5">
                {(['BOTH','LONG_ONLY','SHORT_ONLY'] as const).map((opt) => (
                  <button
                    key={opt}
                    onClick={() => setAllowedDirections(opt)}
                    className={cn(
                      'px-3 py-1.5 text-xs rounded-md border transition-colors flex-1',
                      allowedDirections === opt
                        ? opt === 'LONG_ONLY'  ? 'bg-emerald/10 text-emerald border-emerald/40'
                        : opt === 'SHORT_ONLY' ? 'bg-crimson/10 text-crimson border-crimson/40'
                        : 'bg-cyan-accent/10 text-cyan-accent border-cyan-accent/40'
                        : 'bg-secondary text-muted-foreground border-border',
                    )}
                  >
                    {opt.replace('_ONLY','').replace('BOTH','BOTH sides')}
                  </button>
                ))}
              </div>
              <p className="text-[10px] text-muted-foreground mt-1">
                Backtest finding: <b>LONG-only</b> is the only config with PF&gt;1.0 on 30d 1h data.
                SHORTs on this scanner mix consistently lose money.
              </p>
            </div>

            {/* MTF trend filter */}
            <div className="pt-3 border-t border-border/30 space-y-2">
              <label className="flex items-center gap-2 text-xs">
                <input
                  type="checkbox"
                  checked={mtfFilter}
                  onChange={(e) => setMtfFilter(e.target.checked)}
                  className="accent-emerald"
                />
                <span className="text-foreground font-medium">Multi-timeframe trend filter</span>
              </label>
              <p className="text-[10px] text-muted-foreground pl-6">
                Require 4h EMA(9/21) trend to agree with signal direction.
                <b className="text-amber-warn"> A/B backtest (2026-04-20) showed this reduces PF from 1.05 → 0.68</b>
                because ConfluenceScorer already applies indicator-alignment bonuses
                that capture trend agreement. Keep OFF unless tuning a new strategy.
              </p>
              {mtfFilter && (
                <label className="flex items-center gap-2 text-xs pl-6">
                  <input
                    type="checkbox"
                    checked={mtfBlockNeutral}
                    onChange={(e) => setMtfBlockNeutral(e.target.checked)}
                    className="accent-emerald"
                  />
                  <span className="text-muted-foreground">
                    Also block when 4h is <b>neutral</b> (no clear trend)
                  </span>
                </label>
              )}
            </div>

            <div>
              <label className="text-xs text-muted-foreground block mb-1">
                Min Score (actionability threshold): <span className="font-mono text-foreground">{minScore}</span>
              </label>
              <input type="range" min={50} max={95} step={1} value={minScore}
                onChange={(e) => setMinScore(Number(e.target.value))}
                className="w-full accent-emerald" />
              <div className="flex justify-between text-[10px] text-muted-foreground mt-0.5">
                <span>50</span><span>95</span>
              </div>
              <p className="text-[10px] text-muted-foreground mt-1">
                Only signals at or above this score are eligible for auto-entry. The engine's confluence threshold is {config.data?.min_confluence_score ?? 65}.
              </p>
            </div>

            <div>
              <label className="text-xs text-muted-foreground block mb-1">
                Risk per trade: <span className="font-mono text-foreground">{risk}%</span>
              </label>
              <input type="range" min={0.25} max={3} step={0.25} value={risk}
                onChange={(e) => setRisk(Number(e.target.value))}
                className="w-full accent-emerald" />
              <p className="text-[10px] text-muted-foreground mt-1">
                Hard ceiling is 2% (Kelly cap). Lower = safer; higher = faster compounding and faster drawdowns.
              </p>
            </div>

            <div>
              <label className="text-xs text-muted-foreground block mb-1">
                Default leverage: <span className="font-mono text-foreground">{lev}x</span>
              </label>
              <input type="range" min={1} max={maxLev} step={1} value={lev}
                onChange={(e) => setLev(Number(e.target.value))}
                className="w-full accent-emerald" />
            </div>

            <div>
              <label className="text-xs text-muted-foreground block mb-1">
                Same-symbol cooldown: <span className="font-mono text-foreground">{cooldown}s ({(cooldown/60).toFixed(1)}m)</span>
              </label>
              <input type="range" min={60} max={1800} step={30} value={cooldown}
                onChange={(e) => setCooldown(Number(e.target.value))}
                className="w-full accent-emerald" />
              <p className="text-[10px] text-muted-foreground mt-1">
                After the engine enters on a symbol, it won't touch that symbol again for this many seconds (even if the signal recurs).
              </p>
            </div>

            <label className="flex items-center gap-2 text-xs text-muted-foreground">
              <input
                type="checkbox"
                checked={attachBracket}
                onChange={(e) => setAttachBracket(e.target.checked)}
                className="accent-emerald"
              />
              Attach SL + TP bracket via Algo Order API on every entry
            </label>

            <button
              onClick={saveConfig}
              disabled={configMut.isPending}
              className="w-full bg-emerald/10 border border-emerald/30 text-emerald text-sm font-medium py-2 rounded-md hover:bg-emerald/20 disabled:opacity-50 transition-colors"
            >
              {configMut.isPending ? 'Saving…' : 'Save'}
            </button>
          </div>
        </div>

        {/* ── Recent events ────────────────────────────────────────────── */}
        <div className="hud-panel p-5">
          <h2 className="text-xs font-semibold tracking-[0.12em] uppercase text-muted-foreground mb-4">
            Autotrade Decision Log
          </h2>
          <div className="space-y-2 max-h-[500px] overflow-y-auto pr-2">
            {events.length === 0 ? (
              <div className="text-xs text-muted-foreground py-6 text-center">
                No events yet. Turn autotrade ON and watch the engine think.
              </div>
            ) : events.map((e, i) => {
              const ts = new Date(e.ts * 1000);
              const color =
                e.action === 'open' ? 'text-emerald'
                : e.action === 'reject' ? 'text-amber-warn'
                : e.action === 'error' ? 'text-crimson'
                : 'text-muted-foreground';
              return (
                <div key={i} className="flex items-start gap-2 text-xs border-b border-border/30 pb-2">
                  <span className="font-mono text-muted-foreground w-16 shrink-0">
                    {ts.toLocaleTimeString('en-GB', { hour12: false })}
                  </span>
                  {e.action === 'open' ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald mt-0.5 shrink-0" />
                    : e.action === 'reject' || e.action === 'error' ? <AlertTriangle className="w-3.5 h-3.5 text-amber-warn mt-0.5 shrink-0" />
                    : <Play className="w-3.5 h-3.5 text-muted-foreground mt-0.5 shrink-0" />}
                  <div className="flex-1 min-w-0">
                    <div className={cn('font-semibold uppercase text-[10px] tracking-wider', color)}>
                      {e.action} {e.symbol !== '-' && <span className="text-foreground normal-case font-mono ml-1">{e.symbol}</span>}
                      {e.side && <span className="text-foreground normal-case ml-2">{e.side}</span>}
                      {e.score != null && <span className="text-muted-foreground normal-case ml-2">score {Number(e.score).toFixed(0)}</span>}
                    </div>
                    {e.reason && <div className="text-muted-foreground mt-0.5 break-words">{e.reason}</div>}
                    {e.entry != null && (
                      <div className="font-mono text-[10px] text-muted-foreground mt-0.5">
                        qty {Number(e.qty ?? 0).toFixed(4)} · entry {Number(e.entry).toFixed(2)}
                        {e.sl != null && ` · SL ${Number(e.sl).toFixed(2)}`}
                        {e.tp != null && ` · TP ${Number(e.tp).toFixed(2)}`}
                        {e.order_id != null && ` · #${e.order_id}`}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
