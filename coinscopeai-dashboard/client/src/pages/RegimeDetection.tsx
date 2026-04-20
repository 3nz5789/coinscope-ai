/* Regime Detection — Current regime per symbol, history chart, confidence */
import DashboardLayout from '@/components/DashboardLayout';
import PageHeader from '@/components/PageHeader';
import StatusBadge, { getRegimeVariant } from '@/components/StatusBadge';
import { REGIMES, SYMBOLS, type Symbol } from '@/lib/mockData';
import { cn } from '@/lib/utils';
import { useState } from 'react';
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

const REGIME_COLORS: Record<string, string> = {
  'Trending': '#10b981',
  'Mean-Reverting': '#22d3ee',
  'Volatile': '#f59e0b',
  'Quiet': '#64748b',
};

export default function RegimeDetection() {
  const [selectedSymbol, setSelectedSymbol] = useState<Symbol>(SYMBOLS[0]);
  const regime = REGIMES[selectedSymbol];

  const historyData = regime.history.map((h) => ({
    date: h.date.slice(5),
    regime: h.regime,
    value: 1,
  })).reverse();

  return (
    <DashboardLayout>
      <PageHeader title="Regime Detection" subtitle="ML-classified market regime per symbol" />

      {/* Symbol selector */}
      <div className="flex items-center gap-2 mb-6">
        {SYMBOLS.map((sym) => (
          <button
            key={sym}
            onClick={() => setSelectedSymbol(sym)}
            className={cn(
              'px-3 py-1.5 text-xs font-medium rounded-md transition-colors border',
              selectedSymbol === sym
                ? 'bg-emerald/10 text-emerald border-emerald/30'
                : 'bg-secondary text-muted-foreground border-border hover:text-foreground'
            )}
          >
            {sym}
          </button>
        ))}
      </div>

      {/* Current regime cards */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-3 mb-6">
        {SYMBOLS.map((sym) => {
          const r = REGIMES[sym];
          return (
            <div
              key={sym}
              className={cn(
                'hud-panel p-4 cursor-pointer transition-all',
                selectedSymbol === sym && 'border-emerald/30 bg-emerald/5'
              )}
              onClick={() => setSelectedSymbol(sym)}
            >
              <div className="text-xs font-semibold text-foreground mb-2">{sym}</div>
              <StatusBadge label={r.current} variant={getRegimeVariant(r.current)} />
              <div className="mt-2 text-xs text-muted-foreground">
                Confidence: <span className={cn(
                  'font-mono tabular-nums font-medium',
                  r.confidence >= 80 ? 'text-emerald' : r.confidence >= 60 ? 'text-cyan-accent' : 'text-amber-warn'
                )}>{r.confidence}%</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Regime history chart */}
      <div className="hud-panel p-4 mb-4">
        <h2 className="text-xs font-semibold tracking-[0.12em] uppercase text-muted-foreground mb-4">
          {selectedSymbol} — 10-Day Regime History
        </h2>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={historyData} margin={{ top: 5, right: 5, bottom: 0, left: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.25 0.025 260 / 0.5)" />
            <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#64748b' }} tickLine={false} axisLine={false} />
            <YAxis hide />
            <Tooltip
              contentStyle={{ background: '#131b2e', border: '1px solid #1e293b', borderRadius: '6px', fontSize: '12px' }}
              labelStyle={{ color: '#94a3b8' }}
              formatter={(_: any, __: any, props: any) => [props.payload.regime, 'Regime']}
            />
            <Bar dataKey="value" radius={[4, 4, 0, 0]}>
              {historyData.map((entry, i) => (
                <Cell key={i} fill={REGIME_COLORS[entry.regime] || '#64748b'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Legend */}
      <div className="hud-panel p-4">
        <h3 className="text-[10px] font-semibold tracking-[0.12em] uppercase text-muted-foreground mb-3">Regime Definitions</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
          <div className="flex items-start gap-2">
            <div className="w-3 h-3 rounded-sm bg-emerald mt-0.5 shrink-0" />
            <div>
              <span className="font-medium text-foreground">Trending</span>
              <span className="text-muted-foreground"> — Directional momentum detected. Trend-following strategies favored. Higher position sizes allowed.</span>
            </div>
          </div>
          <div className="flex items-start gap-2">
            <div className="w-3 h-3 rounded-sm bg-cyan-accent mt-0.5 shrink-0" />
            <div>
              <span className="font-medium text-foreground">Mean-Reverting</span>
              <span className="text-muted-foreground"> — Range-bound price action. Counter-trend entries at extremes. Tighter take-profit targets.</span>
            </div>
          </div>
          <div className="flex items-start gap-2">
            <div className="w-3 h-3 rounded-sm bg-amber-warn mt-0.5 shrink-0" />
            <div>
              <span className="font-medium text-foreground">Volatile</span>
              <span className="text-muted-foreground"> — High volatility, unclear direction. Reduced position sizes. Wider stops required.</span>
            </div>
          </div>
          <div className="flex items-start gap-2">
            <div className="w-3 h-3 rounded-sm bg-muted-foreground mt-0.5 shrink-0" />
            <div>
              <span className="font-medium text-foreground">Quiet</span>
              <span className="text-muted-foreground"> — Low volatility, no clear opportunity. Minimal trading. Wait for regime shift.</span>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
