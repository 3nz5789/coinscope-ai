/* Backtest Results — live runner for signals/backtester.py
 *
 * Kick off a job with the current scan config, poll it to completion, show
 * win rate / PF / drawdown / equity curve / per-trade breakdown.
 */
import DashboardLayout from '@/components/DashboardLayout';
import MetricCard from '@/components/MetricCard';
import PageHeader from '@/components/PageHeader';
import {
  useBacktestJob,
  useBacktestList,
  useBacktestRun,
  useConfig,
} from '@/lib/engine/hooks';
import { formatPct, formatUSD } from '@/lib/mockData';
import { cn } from '@/lib/utils';
import { useQueryClient } from '@tanstack/react-query';
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Play,
  Target,
  TrendingDown,
  TrendingUp,
  Trophy,
} from 'lucide-react';
import { useState } from 'react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { toast } from 'sonner';

const TIMEFRAMES = ['5m', '15m', '1h', '4h'];

export default function BacktestResults() {
  const config = useConfig();
  const list   = useBacktestList();
  const runMut = useBacktestRun();
  const qc     = useQueryClient();

  const [pairs, setPairs]         = useState<string[] | null>(null);
  const [timeframe, setTimeframe] = useState<string>('1h');
  const [days, setDays]           = useState<number>(30);
  const [minScore, setMinScore]   = useState<number>(60);
  const [risk, setRisk]           = useState<number>(1);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const selected = useBacktestJob(selectedId);

  const availablePairs = config.data?.scan_pairs ?? ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT'];
  const usedPairs = pairs ?? availablePairs;

  async function runNow() {
    try {
      const resp = await runMut.mutateAsync({
        pairs: usedPairs,
        timeframe,
        lookback_days: days,
        min_confluence_score: minScore,
        risk_per_trade_pct: risk,
      });
      toast.success(`Backtest queued · ${resp.job_id}`);
      setSelectedId(resp.job_id);
      await qc.invalidateQueries({ queryKey: ["engine","backtest","jobs"] });
    } catch (err: any) {
      toast.error(err?.response?.data?.detail ?? err?.message ?? String(err));
    }
  }

  const jobs = list.data?.jobs ?? [];
  const latestDone = jobs.find((j: any) => j.status === 'done');
  const viewing = selected.data ?? null;
  const summary = viewing?.results?.summary ?? (selectedId ? null : latestDone?.summary);
  const equity = viewing?.results?.equity_curve ?? [];
  const trades = viewing?.results?.trades ?? [];

  const equityData = equity.map((v: number, i: number) => ({ i, equity: v }));

  return (
    <DashboardLayout>
      <PageHeader
        title="Backtest Results"
        subtitle="Replay the scanner pipeline on historical klines — no live orders placed"
      />

      {/* ── Runner ───────────────────────────────────────────────────── */}
      <div className="hud-panel p-5 mb-6">
        <h2 className="text-xs font-semibold tracking-[0.12em] uppercase text-muted-foreground mb-4">
          Run a Backtest
        </h2>

        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 items-end">
          <div className="lg:col-span-2">
            <label className="text-xs text-muted-foreground block mb-1">Pairs</label>
            <div className="flex flex-wrap gap-1.5">
              {availablePairs.map((p) => {
                const on = usedPairs.includes(p);
                return (
                  <button
                    key={p}
                    onClick={() => {
                      const next = on ? usedPairs.filter(x => x !== p) : [...usedPairs, p];
                      setPairs(next);
                    }}
                    className={cn(
                      'px-2 py-1 text-xs rounded-md border transition-colors',
                      on ? 'bg-emerald/10 text-emerald border-emerald/30' : 'bg-secondary text-muted-foreground border-border',
                    )}
                  >
                    {p.replace('USDT','')}
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <label className="text-xs text-muted-foreground block mb-1">Timeframe</label>
            <div className="flex gap-1">
              {TIMEFRAMES.map((tf) => (
                <button
                  key={tf}
                  onClick={() => setTimeframe(tf)}
                  className={cn(
                    'px-2.5 py-1.5 text-xs rounded-md border transition-colors',
                    timeframe === tf ? 'bg-emerald/10 text-emerald border-emerald/30' : 'bg-secondary text-muted-foreground border-border',
                  )}
                >
                  {tf}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-xs text-muted-foreground block mb-1">Lookback: {days}d</label>
            <input type="range" min={7} max={90} step={1} value={days} onChange={(e) => setDays(Number(e.target.value))} className="w-full accent-emerald" />
          </div>

          <div>
            <label className="text-xs text-muted-foreground block mb-1">Min Score: {minScore}</label>
            <input type="range" min={40} max={90} step={1} value={minScore} onChange={(e) => setMinScore(Number(e.target.value))} className="w-full accent-emerald" />
          </div>
        </div>

        <div className="mt-4 flex items-center gap-3">
          <div className="flex-1">
            <label className="text-xs text-muted-foreground block mb-1">Risk per trade: {risk}%</label>
            <input type="range" min={0.25} max={3} step={0.25} value={risk} onChange={(e) => setRisk(Number(e.target.value))} className="w-full max-w-sm accent-emerald" />
          </div>
          <button
            onClick={runNow}
            disabled={runMut.isPending || usedPairs.length === 0}
            className="flex items-center gap-2 bg-emerald text-white text-sm font-semibold px-4 py-2 rounded-md hover:bg-emerald/90 disabled:opacity-50 transition-colors"
          >
            <Play className="w-3.5 h-3.5" />
            {runMut.isPending ? 'Queuing…' : 'Run Backtest'}
          </button>
        </div>
      </div>

      {/* ── Job picker + status ──────────────────────────────────────── */}
      <div className="hud-panel p-4 mb-6">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-semibold tracking-[0.12em] uppercase text-muted-foreground">
            Recent Jobs ({jobs.length})
          </h2>
          {viewing && (
            <span className={cn(
              'text-[10px] font-semibold tracking-wider uppercase px-2 py-0.5 rounded-sm',
              viewing.status === 'done' ? 'bg-emerald/10 text-emerald' :
              viewing.status === 'running' ? 'bg-cyan-accent/10 text-cyan-accent' :
              viewing.status === 'queued' ? 'bg-amber-warn/10 text-amber-warn' :
              'bg-crimson/10 text-crimson',
            )}>
              {viewing.status}
            </span>
          )}
        </div>
        <div className="flex flex-wrap gap-1.5 text-xs">
          {jobs.length === 0 && (
            <span className="text-muted-foreground">No jobs yet — run one above.</span>
          )}
          {jobs.slice(0, 10).map((j: any) => (
            <button
              key={j.job_id}
              onClick={() => setSelectedId(j.job_id)}
              className={cn(
                'px-2 py-1 rounded-md border transition-colors font-mono',
                selectedId === j.job_id ? 'bg-emerald/10 text-emerald border-emerald/40' : 'bg-secondary text-muted-foreground border-border hover:border-border/80',
              )}
              title={`${j.status} · ${new Date(j.created_at * 1000).toLocaleString()}`}
            >
              {j.job_id.slice(-8)} · {j.status}{j.summary ? ` · ${j.summary.win_rate.toFixed(0)}% WR` : ''}
            </button>
          ))}
        </div>
      </div>

      {/* ── Summary metrics ──────────────────────────────────────────── */}
      {summary && (
        <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3 mb-6">
          <MetricCard label="Trades" value={String(summary.total_trades)} subValue={`${summary.winning_trades}W / ${summary.losing_trades}L`} icon={Activity} />
          <MetricCard label="Win Rate" value={`${summary.win_rate.toFixed(1)}%`} icon={Trophy} />
          <MetricCard label="Profit Factor" value={summary.profit_factor.toFixed(2)} icon={BarChart3} trend={summary.profit_factor >= 1 ? 'up' : 'down'} />
          <MetricCard label="Max Drawdown" value={`${summary.max_drawdown_pct.toFixed(1)}%`} trend="down" icon={TrendingDown} />
          <MetricCard label="Total Return" value={`${summary.total_return_pct.toFixed(1)}%`} subValue={formatUSD(summary.total_pnl_usdt)} trend={summary.total_pnl_usdt >= 0 ? 'up' : 'down'} icon={TrendingUp} />
          <MetricCard label="Sharpe" value={summary.sharpe_ratio.toFixed(2)} subValue={`avg R:R ${summary.avg_rr_achieved.toFixed(2)}`} icon={Target} />
        </div>
      )}

      {summary && summary.profit_factor < 1 && (
        <div className="mb-4 rounded-md border border-amber-warn/40 bg-amber-warn/5 p-3 flex items-start gap-2 text-xs">
          <AlertTriangle className="w-4 h-4 text-amber-warn shrink-0 mt-0.5" />
          <div>
            <div className="font-medium text-foreground">This config loses money on historical data.</div>
            <div className="text-muted-foreground mt-0.5">
              Profit factor &lt; 1 (losses exceed wins). Increase <b>min score</b> to be more selective,
              shorten the timeframe, or reduce the pair set. <b>Do not enable autotrade at this configuration.</b>
            </div>
          </div>
        </div>
      )}

      {/* ── Equity curve ────────────────────────────────────────────── */}
      {equityData.length > 0 && (
        <div className="hud-panel p-4 mb-6">
          <h2 className="text-xs font-semibold tracking-[0.12em] uppercase text-muted-foreground mb-3">
            Equity Curve · {equityData.length} trades
          </h2>
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={equityData} margin={{ top: 5, right: 5, bottom: 0, left: 5 }}>
              <defs>
                <linearGradient id="bteq" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#10b981" stopOpacity={0.25} />
                  <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.25 0.025 260 / 0.5)" />
              <XAxis dataKey="i" tick={{ fontSize: 10, fill: '#64748b' }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fontSize: 10, fill: '#64748b' }} tickLine={false} axisLine={false} tickFormatter={(v) => `$${(v / 1000).toFixed(1)}k`} domain={['auto','auto']} />
              <Tooltip contentStyle={{ background: '#131b2e', border: '1px solid #1e293b', borderRadius: '6px', fontSize: '12px' }} labelStyle={{ color: '#94a3b8' }} formatter={(v: number) => [formatUSD(v), 'Equity']} />
              <Area type="monotone" dataKey="equity" stroke="#10b981" strokeWidth={2} fill="url(#bteq)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* ── Trade list ──────────────────────────────────────────────── */}
      {trades.length > 0 && (
        <div className="hud-panel p-4">
          <h2 className="text-xs font-semibold tracking-[0.12em] uppercase text-muted-foreground mb-3">
            Per-Trade Breakdown (latest {Math.min(trades.length, 50)} of {trades.length})
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border">
                  {['Symbol','Dir','Score','Entry','Exit','P&L %','P&L USD','R:R','Exit','Bars'].map((h) => (
                    <th key={h} className="text-left py-2 px-3 text-[10px] font-semibold tracking-[0.1em] uppercase text-muted-foreground">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {trades.slice(-50).reverse().map((t: any, i: number) => (
                  <tr key={i} className="border-b border-border/50 hover:bg-secondary/30 transition-colors">
                    <td className="py-2 px-3 font-medium text-foreground">{t.symbol}</td>
                    <td className="py-2 px-3">
                      <span className={cn('font-bold', t.direction === 'LONG' ? 'text-emerald' : 'text-crimson')}>{t.direction}</span>
                    </td>
                    <td className="py-2 px-3 font-mono tabular-nums text-foreground">{t.signal_score.toFixed(0)}</td>
                    <td className="py-2 px-3 font-mono tabular-nums text-foreground">{formatUSD(t.entry_price, t.entry_price < 10 ? 4 : 2)}</td>
                    <td className="py-2 px-3 font-mono tabular-nums text-foreground">{formatUSD(t.exit_price, t.exit_price < 10 ? 4 : 2)}</td>
                    <td className={cn('py-2 px-3 font-mono tabular-nums font-semibold', t.pnl_pct >= 0 ? 'text-emerald' : 'text-crimson')}>{formatPct(t.pnl_pct)}</td>
                    <td className={cn('py-2 px-3 font-mono tabular-nums', t.pnl_usdt >= 0 ? 'text-emerald' : 'text-crimson')}>{formatUSD(t.pnl_usdt)}</td>
                    <td className="py-2 px-3 font-mono tabular-nums text-cyan-accent">{t.rr_achieved.toFixed(2)}</td>
                    <td className="py-2 px-3 text-muted-foreground">{t.exit_reason}</td>
                    <td className="py-2 px-3 font-mono tabular-nums text-muted-foreground">{t.bars_held}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
