/* Performance — Win rate, profit factor, Sharpe, drawdown, monthly breakdown (live) */
import DashboardLayout from '@/components/DashboardLayout';
import MetricCard from '@/components/MetricCard';
import PageHeader from '@/components/PageHeader';
import { useDailyPerformance, usePerformance } from '@/lib/engine/hooks';
import { formatPct, formatUSD } from '@/lib/mockData';
import { cn } from '@/lib/utils';
import { BarChart3, Target, TrendingDown, TrendingUp, Trophy, Zap } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

interface MonthlyAgg {
  month: string;
  pnl: number;
  pnlPct: number;
  trades: number;
  winRate: number;
}

/** Roll up engine daily PnL into calendar-month buckets for the bar chart. */
function rollupMonthly(days: { date: string; pnl: number; pnl_pct?: number; trades?: number; win_rate?: number }[]): MonthlyAgg[] {
  const buckets = new Map<string, MonthlyAgg>();
  for (const d of days) {
    const key = d.date.slice(0, 7); // YYYY-MM
    const label = new Date(d.date + 'T00:00:00Z').toLocaleString('en-US', { month: 'short', year: '2-digit', timeZone: 'UTC' });
    const b = buckets.get(key) ?? { month: label, pnl: 0, pnlPct: 0, trades: 0, winRate: 0 };
    b.pnl += Number(d.pnl ?? 0);
    b.pnlPct += Number(d.pnl_pct ?? 0);
    b.trades += Number(d.trades ?? 0);
    buckets.set(key, b);
  }
  // Compute win rate as (daily win_rate * days with trades) / count — approximation
  return Array.from(buckets.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([_k, v]) => v);
}

export default function Performance() {
  const perf = usePerformance();
  const daily = useDailyPerformance();

  const p = perf.data;
  const days = daily.data?.days ?? [];
  const monthly = rollupMonthly(days);

  const val = (n: number | undefined, fmt: (v: number) => string, fallback = '—') =>
    n == null ? fallback : fmt(n);

  return (
    <DashboardLayout>
      <PageHeader title="Performance Analytics" subtitle="Comprehensive trading performance metrics" />

      {/* Key metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3 mb-6">
        <MetricCard
          label="Win Rate"
          value={val(p?.win_rate, (n) => `${n.toFixed(1)}%`)}
          subValue={p?.winning_trades != null ? `${p.winning_trades}W / ${p.losing_trades ?? 0}L` : undefined}
          icon={Trophy}
        />
        <MetricCard label="Profit Factor" value={val(p?.profit_factor, (n) => n.toFixed(2))} icon={Zap} />
        <MetricCard label="Sharpe Ratio" value={val(p?.sharpe_ratio, (n) => n.toFixed(2))} icon={BarChart3} />
        <MetricCard
          label="Max Drawdown"
          value={val(p?.max_drawdown_pct, (n) => `${n.toFixed(1)}%`)}
          trend="down"
          icon={TrendingDown}
        />
        <MetricCard
          label="Total Return"
          value={val(p?.total_return_pct, (n) => `${n.toFixed(1)}%`)}
          subValue={p?.total_return != null ? formatUSD(p.total_return) : undefined}
          trend="up"
          icon={TrendingUp}
        />
        <MetricCard
          label="Avg Hold Time"
          value={val(p?.avg_hold_time_hours, (n) => `${n.toFixed(1)}h`)}
          icon={Target}
        />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 mb-4">
        {/* Monthly P&L Chart */}
        <div className="hud-panel p-4">
          <h2 className="text-xs font-semibold tracking-[0.12em] uppercase text-muted-foreground mb-4">Monthly P&L</h2>
          {monthly.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={monthly} margin={{ top: 5, right: 5, bottom: 0, left: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.25 0.025 260)" />
                <XAxis dataKey="month" tick={{ fontSize: 10, fill: '#64748b' }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 10, fill: '#64748b' }} tickLine={false} axisLine={false} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
                <Tooltip
                  contentStyle={{ background: '#131b2e', border: '1px solid #1e293b', borderRadius: '6px', fontSize: '12px' }}
                  labelStyle={{ color: '#94a3b8' }}
                  formatter={(value: number) => [formatUSD(value), 'P&L']}
                />
                <Bar dataKey="pnl" radius={[4, 4, 0, 0]}>
                  {monthly.map((entry, i) => (
                    <Cell key={i} fill={entry.pnl >= 0 ? '#10b981' : '#ef4444'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[260px] flex items-center justify-center text-xs text-muted-foreground">
              {daily.isLoading ? 'Loading…' : 'No daily performance recorded yet.'}
            </div>
          )}
        </div>

        {/* Detailed stats */}
        <div className="hud-panel p-4">
          <h2 className="text-xs font-semibold tracking-[0.12em] uppercase text-muted-foreground mb-4">Detailed Statistics</h2>
          <div className="space-y-3 text-xs">
            {[
              ['Total Trades', p?.total_trades != null ? String(p.total_trades) : '—'],
              ['Winning Trades', p?.winning_trades != null ? String(p.winning_trades) : '—'],
              ['Losing Trades', p?.losing_trades != null ? String(p.losing_trades) : '—'],
              ['Average Win', p?.avg_win != null ? formatUSD(p.avg_win) : '—'],
              ['Average Loss', p?.avg_loss != null ? formatUSD(p.avg_loss) : '—'],
              ['Largest Win', p?.largest_win != null ? formatUSD(p.largest_win) : '—'],
              ['Largest Loss', p?.largest_loss != null ? formatUSD(p.largest_loss) : '—'],
              ['Max Consecutive Wins', p?.consecutive_wins != null ? String(p.consecutive_wins) : '—'],
              ['Max Consecutive Losses', p?.consecutive_losses != null ? String(p.consecutive_losses) : '—'],
              ['Initial Capital', p?.initial_capital != null ? formatUSD(p.initial_capital) : '—'],
              ['Scale Profile', p?.scale_profile?.current ?? '—'],
            ].map(([label, value]) => (
              <div key={label} className="flex justify-between items-center py-1 border-b border-border/30">
                <span className="text-muted-foreground">{label}</span>
                <span className="font-mono tabular-nums text-foreground">{value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Monthly breakdown table */}
      <div className="hud-panel p-4">
        <h2 className="text-xs font-semibold tracking-[0.12em] uppercase text-muted-foreground mb-3">Monthly Breakdown</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border">
                {['Month', 'P&L', 'Return %', 'Trades'].map((h) => (
                  <th key={h} className="text-left py-2 px-3 text-[10px] font-semibold tracking-[0.1em] uppercase text-muted-foreground">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {monthly.length === 0 ? (
                <tr>
                  <td colSpan={4} className="py-8 text-center text-muted-foreground">
                    {daily.isLoading ? 'Loading…' : 'No monthly data yet.'}
                  </td>
                </tr>
              ) : (
                monthly.map((m) => (
                  <tr key={m.month} className="border-b border-border/50 hover:bg-secondary/30 transition-colors">
                    <td className="py-2 px-3 font-medium text-foreground">{m.month}</td>
                    <td className={cn('py-2 px-3 font-mono tabular-nums font-semibold', m.pnl >= 0 ? 'text-emerald' : 'text-crimson')}>
                      {formatUSD(m.pnl)}
                    </td>
                    <td className={cn('py-2 px-3 font-mono tabular-nums', m.pnlPct >= 0 ? 'text-emerald' : 'text-crimson')}>
                      {formatPct(m.pnlPct)}
                    </td>
                    <td className="py-2 px-3 font-mono tabular-nums text-foreground">{m.trades}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </DashboardLayout>
  );
}
