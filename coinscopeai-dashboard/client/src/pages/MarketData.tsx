/* Market Data — Real-time prices, funding rates, OI, liquidation feed across 4 exchanges */
import DashboardLayout from '@/components/DashboardLayout';
import PageHeader from '@/components/PageHeader';
import { MARKET_DATA, SYMBOLS, formatCompact, formatUSD, type Symbol } from '@/lib/mockData';
import { cn } from '@/lib/utils';
import { useState } from 'react';

export default function MarketData() {
  const [activeTab, setActiveTab] = useState<'prices' | 'funding' | 'oi' | 'liquidations'>('prices');
  const exchanges = MARKET_DATA.exchanges;

  return (
    <DashboardLayout>
      <PageHeader title="Market Data" subtitle="Cross-exchange data feeds — Binance, Bybit, OKX, Hyperliquid" />

      {/* Tab selector */}
      <div className="flex items-center gap-1 mb-6 bg-secondary rounded-md p-0.5 w-fit">
        {[
          { key: 'prices' as const, label: 'Prices' },
          { key: 'funding' as const, label: 'Funding Rates' },
          { key: 'oi' as const, label: 'Open Interest' },
          { key: 'liquidations' as const, label: 'Liquidations' },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              'px-3 py-1.5 text-xs font-medium rounded-sm transition-colors',
              activeTab === tab.key ? 'bg-emerald/20 text-emerald' : 'text-muted-foreground hover:text-foreground'
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Prices table */}
      {activeTab === 'prices' && (
        <div className="hud-panel overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border bg-navy-900/50">
                  <th className="text-left py-3 px-4 text-[10px] font-semibold tracking-[0.1em] uppercase text-muted-foreground">Symbol</th>
                  {exchanges.map((ex) => (
                    <th key={ex} className="text-right py-3 px-4 text-[10px] font-semibold tracking-[0.1em] uppercase text-muted-foreground">{ex}</th>
                  ))}
                  <th className="text-right py-3 px-4 text-[10px] font-semibold tracking-[0.1em] uppercase text-muted-foreground">Spread</th>
                </tr>
              </thead>
              <tbody>
                {SYMBOLS.map((sym) => {
                  const prices = exchanges.map((ex) => MARKET_DATA.prices[sym][ex]);
                  const spread = Math.max(...prices) - Math.min(...prices);
                  return (
                    <tr key={sym} className="border-b border-border/50 hover:bg-secondary/30 transition-colors">
                      <td className="py-3 px-4 font-semibold text-foreground">{sym}</td>
                      {exchanges.map((ex) => (
                        <td key={ex} className="py-3 px-4 text-right font-mono tabular-nums text-foreground">
                          {formatUSD(MARKET_DATA.prices[sym][ex], MARKET_DATA.prices[sym][ex] < 10 ? 4 : 2)}
                        </td>
                      ))}
                      <td className="py-3 px-4 text-right font-mono tabular-nums text-amber-warn">
                        {formatUSD(spread, spread < 1 ? 4 : 2)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Funding rates table */}
      {activeTab === 'funding' && (
        <div className="hud-panel overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border bg-navy-900/50">
                  <th className="text-left py-3 px-4 text-[10px] font-semibold tracking-[0.1em] uppercase text-muted-foreground">Symbol</th>
                  {exchanges.map((ex) => (
                    <th key={ex} className="text-right py-3 px-4 text-[10px] font-semibold tracking-[0.1em] uppercase text-muted-foreground">{ex}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {SYMBOLS.map((sym) => (
                  <tr key={sym} className="border-b border-border/50 hover:bg-secondary/30 transition-colors">
                    <td className="py-3 px-4 font-semibold text-foreground">{sym}</td>
                    {exchanges.map((ex) => {
                      const rate = MARKET_DATA.fundingRates[sym][ex];
                      return (
                        <td key={ex} className={cn('py-3 px-4 text-right font-mono tabular-nums', rate >= 0 ? 'text-emerald' : 'text-crimson')}>
                          {rate >= 0 ? '+' : ''}{(rate * 100).toFixed(4)}%
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Open Interest table */}
      {activeTab === 'oi' && (
        <div className="hud-panel overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border bg-navy-900/50">
                  <th className="text-left py-3 px-4 text-[10px] font-semibold tracking-[0.1em] uppercase text-muted-foreground">Symbol</th>
                  {exchanges.map((ex) => (
                    <th key={ex} className="text-right py-3 px-4 text-[10px] font-semibold tracking-[0.1em] uppercase text-muted-foreground">{ex}</th>
                  ))}
                  <th className="text-right py-3 px-4 text-[10px] font-semibold tracking-[0.1em] uppercase text-muted-foreground">Total</th>
                </tr>
              </thead>
              <tbody>
                {SYMBOLS.map((sym) => {
                  const total = exchanges.reduce((sum, ex) => sum + MARKET_DATA.openInterest[sym][ex], 0);
                  return (
                    <tr key={sym} className="border-b border-border/50 hover:bg-secondary/30 transition-colors">
                      <td className="py-3 px-4 font-semibold text-foreground">{sym}</td>
                      {exchanges.map((ex) => (
                        <td key={ex} className="py-3 px-4 text-right font-mono tabular-nums text-foreground">
                          {formatCompact(MARKET_DATA.openInterest[sym][ex])}
                        </td>
                      ))}
                      <td className="py-3 px-4 text-right font-mono tabular-nums text-cyan-accent font-semibold">
                        {formatCompact(total)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Liquidation feed */}
      {activeTab === 'liquidations' && (
        <div className="hud-panel overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border bg-navy-900/50">
                  {['Time', 'Symbol', 'Side', 'Size', 'Price', 'Exchange'].map((h) => (
                    <th key={h} className="text-left py-3 px-4 text-[10px] font-semibold tracking-[0.1em] uppercase text-muted-foreground">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {MARKET_DATA.recentLiquidations.map((liq, i) => (
                  <tr key={i} className="border-b border-border/50 hover:bg-secondary/30 transition-colors">
                    <td className="py-3 px-4 font-mono tabular-nums text-muted-foreground">{liq.time}</td>
                    <td className="py-3 px-4 font-semibold text-foreground">{liq.symbol}</td>
                    <td className="py-3 px-4">
                      <span className={cn('font-bold', liq.side === 'LONG' ? 'text-crimson' : 'text-emerald')}>
                        {liq.side} LIQ
                      </span>
                    </td>
                    <td className="py-3 px-4 font-mono tabular-nums text-foreground">{formatCompact(liq.size)}</td>
                    <td className="py-3 px-4 font-mono tabular-nums text-foreground">{formatUSD(liq.price, liq.price < 10 ? 4 : 2)}</td>
                    <td className="py-3 px-4 text-muted-foreground">{liq.exchange}</td>
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
