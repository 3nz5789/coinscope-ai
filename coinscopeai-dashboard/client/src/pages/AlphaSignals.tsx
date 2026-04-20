/* Alpha Signals — Funding rates, liquidation cascades, order book imbalance, alpha scores */
import DashboardLayout from '@/components/DashboardLayout';
import PageHeader from '@/components/PageHeader';
import StatusBadge, { getSignalVariant } from '@/components/StatusBadge';
import { ALPHA_SIGNALS, formatCompact, formatPct } from '@/lib/mockData';
import { cn } from '@/lib/utils';
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, ResponsiveContainer } from 'recharts';

export default function AlphaSignals() {
  return (
    <DashboardLayout>
      <PageHeader title="Alpha Signals" subtitle="Multi-factor alpha generation and market microstructure signals" />

      {/* Alpha composite scores */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-3 mb-6">
        {ALPHA_SIGNALS.alphaScores.map((s) => (
          <div key={s.symbol} className="hud-panel p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-foreground">{s.symbol}</span>
              <span className={cn(
                'font-mono text-lg font-bold tabular-nums',
                s.composite >= 70 ? 'text-emerald' : s.composite >= 50 ? 'text-cyan-accent' : 'text-amber-warn'
              )}>
                {s.composite}
              </span>
            </div>
            <div className="space-y-1.5">
              {[
                ['Momentum', s.momentum],
                ['Mean Rev', s.meanReversion],
                ['Volatility', s.volatility],
                ['Volume', s.volume],
              ].map(([label, val]) => (
                <div key={label as string} className="flex items-center gap-2">
                  <span className="text-[10px] text-muted-foreground w-16">{label}</span>
                  <div className="flex-1 h-1.5 bg-navy-800 rounded-full overflow-hidden">
                    <div
                      className={cn('h-full rounded-full', (val as number) >= 70 ? 'bg-emerald' : (val as number) >= 50 ? 'bg-cyan-accent' : 'bg-amber-warn')}
                      style={{ width: `${val}%` }}
                    />
                  </div>
                  <span className="text-[10px] font-mono tabular-nums text-muted-foreground w-6 text-right">{val as number}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        {/* Funding Rate Arbitrage */}
        <div className="hud-panel p-4">
          <h2 className="text-xs font-semibold tracking-[0.12em] uppercase text-muted-foreground mb-3">Funding Rate Arbitrage</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border">
                  {['Symbol', 'Rate', 'Annualized', 'Signal'].map((h) => (
                    <th key={h} className="text-left py-2 px-2 text-[10px] font-semibold tracking-[0.1em] uppercase text-muted-foreground">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ALPHA_SIGNALS.fundingRates.map((f) => (
                  <tr key={f.symbol} className="border-b border-border/50 hover:bg-secondary/30 transition-colors">
                    <td className="py-2 px-2 font-medium text-foreground">{f.symbol}</td>
                    <td className={cn('py-2 px-2 font-mono tabular-nums', f.rate >= 0 ? 'text-emerald' : 'text-crimson')}>
                      {f.rate >= 0 ? '+' : ''}{(f.rate * 100).toFixed(4)}%
                    </td>
                    <td className={cn('py-2 px-2 font-mono tabular-nums', f.annualized >= 0 ? 'text-emerald' : 'text-crimson')}>
                      {formatPct(f.annualized)}
                    </td>
                    <td className="py-2 px-2">
                      <StatusBadge label={f.signal} variant={getSignalVariant(f.signal)} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Order Book Imbalance */}
        <div className="hud-panel p-4">
          <h2 className="text-xs font-semibold tracking-[0.12em] uppercase text-muted-foreground mb-3">Order Book Imbalance</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border">
                  {['Symbol', 'Bid Depth', 'Ask Depth', 'Imbalance', 'Signal'].map((h) => (
                    <th key={h} className="text-left py-2 px-2 text-[10px] font-semibold tracking-[0.1em] uppercase text-muted-foreground">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ALPHA_SIGNALS.orderBookImbalance.map((o) => (
                  <tr key={o.symbol} className="border-b border-border/50 hover:bg-secondary/30 transition-colors">
                    <td className="py-2 px-2 font-medium text-foreground">{o.symbol}</td>
                    <td className="py-2 px-2 font-mono tabular-nums text-emerald">{formatCompact(o.bidDepth)}</td>
                    <td className="py-2 px-2 font-mono tabular-nums text-crimson">{formatCompact(o.askDepth)}</td>
                    <td className={cn('py-2 px-2 font-mono tabular-nums', o.imbalance >= 0 ? 'text-emerald' : 'text-crimson')}>
                      {o.imbalance >= 0 ? '+' : ''}{(o.imbalance * 100).toFixed(1)}%
                    </td>
                    <td className="py-2 px-2">
                      <StatusBadge label={o.signal} variant={getSignalVariant(o.signal)} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Liquidation Cascade Detection */}
      <div className="hud-panel p-4">
        <h2 className="text-xs font-semibold tracking-[0.12em] uppercase text-muted-foreground mb-3">Liquidation Cascade Detection</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border">
                {['Symbol', 'Long Liq Zone', 'Short Liq Zone', 'Intensity', 'Est. Volume'].map((h) => (
                  <th key={h} className="text-left py-2 px-3 text-[10px] font-semibold tracking-[0.1em] uppercase text-muted-foreground">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {ALPHA_SIGNALS.liquidationCascades.map((l) => (
                <tr key={l.symbol} className="border-b border-border/50 hover:bg-secondary/30 transition-colors">
                  <td className="py-2 px-3 font-medium text-foreground">{l.symbol}</td>
                  <td className="py-2 px-3 font-mono tabular-nums text-crimson">${l.longLiqZone.toLocaleString()}</td>
                  <td className="py-2 px-3 font-mono tabular-nums text-emerald">${l.shortLiqZone.toLocaleString()}</td>
                  <td className="py-2 px-3">
                    <StatusBadge
                      label={l.intensity}
                      variant={l.intensity === 'High' ? 'red' : l.intensity === 'Medium' ? 'yellow' : 'muted'}
                    />
                  </td>
                  <td className="py-2 px-3 font-mono tabular-nums text-foreground">{formatCompact(l.estimatedVolume)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </DashboardLayout>
  );
}
