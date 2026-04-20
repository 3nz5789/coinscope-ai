/* Equity Curve — Live area chart with time range selector and drawdown overlay */
import DashboardLayout from '@/components/DashboardLayout';
import PageHeader from '@/components/PageHeader';
import { useEquityCurve } from '@/lib/engine/hooks';
import { formatPct, formatUSD } from '@/lib/mockData';
import { cn } from '@/lib/utils';
import { useMemo, useState } from 'react';
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

const RANGES = ['7D', '30D', '90D', 'ALL'] as const;
type Range = typeof RANGES[number];

export default function EquityCurve() {
  const [range, setRange] = useState<Range>('30D');
  const eq = useEquityCurve();

  const points = (eq.data?.points ?? []).map((p: any) => ({
    date: p.date ?? p.ts ?? '',
    equity: Number(p.equity ?? 0),
    drawdown: Number(p.drawdown ?? 0),
  }));

  const data = useMemo(() => {
    if (range === 'ALL') return points;
    const take = range === '7D' ? 7 : range === '30D' ? 30 : 90;
    return points.slice(-take);
  }, [points, range]);

  const startEquity = data[0]?.equity ?? 0;
  const endEquity = data[data.length - 1]?.equity ?? 0;
  const returnPct = startEquity > 0 ? ((endEquity - startEquity) / startEquity) * 100 : 0;
  const maxDD = data.length ? Math.max(...data.map((d) => d.drawdown)) : 0;

  return (
    <DashboardLayout>
      <PageHeader title="Equity Curve" subtitle="Portfolio equity over time with drawdown overlay">
        <div className="flex items-center gap-1 bg-secondary rounded-md p-0.5">
          {RANGES.map((r) => (
            <button
              key={r}
              onClick={() => setRange(r)}
              className={cn(
                'px-3 py-1 text-xs font-medium rounded-sm transition-colors',
                range === r ? 'bg-emerald/20 text-emerald' : 'text-muted-foreground hover:text-foreground'
              )}
            >
              {r}
            </button>
          ))}
        </div>
      </PageHeader>

      {/* Summary stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <div className="hud-panel p-3">
          <div className="text-[10px] font-semibold tracking-[0.12em] uppercase text-muted-foreground">Period Return</div>
          <div className={cn('font-mono text-xl font-semibold tabular-nums mt-1', returnPct >= 0 ? 'text-emerald' : 'text-crimson')}>
            {formatPct(returnPct)}
          </div>
        </div>
        <div className="hud-panel p-3">
          <div className="text-[10px] font-semibold tracking-[0.12em] uppercase text-muted-foreground">Current Equity</div>
          <div className="font-mono text-xl font-semibold text-foreground tabular-nums mt-1">{formatUSD(endEquity)}</div>
        </div>
        <div className="hud-panel p-3">
          <div className="text-[10px] font-semibold tracking-[0.12em] uppercase text-muted-foreground">Max Drawdown</div>
          <div className="font-mono text-xl font-semibold text-crimson tabular-nums mt-1">{maxDD.toFixed(2)}%</div>
        </div>
        <div className="hud-panel p-3">
          <div className="text-[10px] font-semibold tracking-[0.12em] uppercase text-muted-foreground">P&L Amount</div>
          <div className={cn('font-mono text-xl font-semibold tabular-nums mt-1', returnPct >= 0 ? 'text-emerald' : 'text-crimson')}>
            {formatUSD(endEquity - startEquity)}
          </div>
        </div>
      </div>

      {/* Main chart */}
      <div className="hud-panel p-4 mb-4">
        <h2 className="text-xs font-semibold tracking-[0.12em] uppercase text-muted-foreground mb-4">Equity</h2>
        {data.length > 0 ? (
          <ResponsiveContainer width="100%" height={350}>
            <AreaChart data={data} margin={{ top: 5, right: 5, bottom: 0, left: 5 }}>
              <defs>
                <linearGradient id="eqGradFull" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#10b981" stopOpacity={0.25} />
                  <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.25 0.025 260 / 0.5)" />
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#64748b' }} tickLine={false} axisLine={false} tickFormatter={(v) => String(v).slice(5)} />
              <YAxis tick={{ fontSize: 10, fill: '#64748b' }} tickLine={false} axisLine={false} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} domain={['auto', 'auto']} />
              <Tooltip
                contentStyle={{ background: '#131b2e', border: '1px solid #1e293b', borderRadius: '6px', fontSize: '12px' }}
                labelStyle={{ color: '#94a3b8' }}
                formatter={(value: number) => [formatUSD(value), 'Equity']}
              />
              <Area type="monotone" dataKey="equity" stroke="#10b981" strokeWidth={2} fill="url(#eqGradFull)" />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-[350px] flex items-center justify-center text-xs text-muted-foreground">
            {eq.isLoading ? 'Loading…' : 'No equity history yet.'}
          </div>
        )}
      </div>

      {/* Drawdown chart */}
      <div className="hud-panel p-4">
        <h2 className="text-xs font-semibold tracking-[0.12em] uppercase text-muted-foreground mb-4">Drawdown</h2>
        {data.length > 0 ? (
          <ResponsiveContainer width="100%" height={150}>
            <BarChart data={data} margin={{ top: 5, right: 5, bottom: 0, left: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.25 0.025 260 / 0.5)" />
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#64748b' }} tickLine={false} axisLine={false} tickFormatter={(v) => String(v).slice(5)} />
              <YAxis tick={{ fontSize: 10, fill: '#64748b' }} tickLine={false} axisLine={false} tickFormatter={(v) => `${v}%`} />
              <Tooltip
                contentStyle={{ background: '#131b2e', border: '1px solid #1e293b', borderRadius: '6px', fontSize: '12px' }}
                labelStyle={{ color: '#94a3b8' }}
                formatter={(value: number) => [`${value.toFixed(2)}%`, 'Drawdown']}
              />
              <Bar dataKey="drawdown" fill="#ef4444" opacity={0.6} radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-[150px] flex items-center justify-center text-xs text-muted-foreground">
            {eq.isLoading ? 'Loading…' : 'No drawdown data.'}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
