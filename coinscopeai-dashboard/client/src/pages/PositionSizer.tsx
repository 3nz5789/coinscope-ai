/* Position Sizer — Risk-adjusted position sizing against engine /position-size */
import DashboardLayout from '@/components/DashboardLayout';
import PageHeader from '@/components/PageHeader';
import { useConfig, useExposure, usePositionSize } from '@/lib/engine/hooks';
import { formatUSD } from '@/lib/mockData';
import { cn } from '@/lib/utils';
import { Calculator } from 'lucide-react';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

export default function PositionSizer() {
  const config = useConfig();
  const exposure = useExposure();
  const sizer = usePositionSize();

  const scanPairs = config.data?.scan_pairs ?? ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT'];
  const defaultBalance = exposure.data?.balance ?? 10_000;
  const configuredRisk = config.data?.risk_per_trade_pct ?? 1.0;
  const maxLeverage = config.data?.max_leverage ?? 10;

  const [symbol, setSymbol]   = useState<string>(scanPairs[0]);
  const [balance, setBalance] = useState<number>(defaultBalance);
  const [riskPct, setRiskPct] = useState<number>(configuredRisk);
  const [leverage, setLeverage] = useState<number>(Math.min(10, maxLeverage));
  const [entry, setEntry]     = useState<number>(0);
  const [stopPct, setStopPct] = useState<number>(2.0);

  // Keep defaults in sync once engine responses arrive
  useEffect(() => { if (exposure.data) setBalance((b) => (b === 10_000 ? exposure.data!.balance : b)); }, [exposure.data]);
  useEffect(() => { if (config.data?.scan_pairs?.length && !scanPairs.includes(symbol)) setSymbol(config.data.scan_pairs[0]); }, [config.data]);

  const stopLoss = entry > 0 ? entry * (1 - stopPct / 100) : 0;
  const result = sizer.data;

  async function recalc() {
    if (!entry || entry <= 0) {
      toast.error('Enter an entry price to compute size.');
      return;
    }
    try {
      await sizer.mutateAsync({
        symbol,
        entry,
        stop_loss: stopLoss,
        balance,
        risk_pct: riskPct,
        leverage,
      });
    } catch (err: any) {
      toast.error(`Engine error: ${err?.response?.data?.detail ?? err?.message ?? err}`);
    }
  }

  return (
    <DashboardLayout>
      <PageHeader title="Position Sizer" subtitle="Risk-adjusted position sizing backed by the engine risk gate" />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Input panel */}
        <div className="hud-panel p-5 space-y-5">
          <h2 className="text-xs font-semibold tracking-[0.12em] uppercase text-muted-foreground flex items-center gap-2">
            <Calculator className="w-4 h-4" /> Parameters
          </h2>

          <div className="space-y-4">
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Symbol</label>
              <div className="flex flex-wrap gap-1.5">
                {scanPairs.map((s) => (
                  <button
                    key={s}
                    onClick={() => setSymbol(s)}
                    className={cn(
                      'px-2.5 py-1 text-xs rounded-md border transition-colors',
                      symbol === s ? 'bg-emerald/10 text-emerald border-emerald/30' : 'bg-secondary text-muted-foreground border-border'
                    )}
                  >
                    {s.replace('USDT', '')}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="text-xs text-muted-foreground block mb-1">Account Balance</label>
              <input
                type="number"
                value={balance}
                onChange={(e) => setBalance(Number(e.target.value))}
                className="w-full bg-input border border-border rounded-md px-3 py-2 text-sm font-mono text-foreground focus:border-emerald/50 focus:outline-none"
              />
              <p className="text-[10px] text-muted-foreground mt-1">Engine reports {formatUSD(defaultBalance)}</p>
            </div>

            <div>
              <label className="text-xs text-muted-foreground block mb-1">Entry Price</label>
              <input
                type="number"
                value={entry || ''}
                onChange={(e) => setEntry(Number(e.target.value))}
                placeholder="e.g. 75000"
                className="w-full bg-input border border-border rounded-md px-3 py-2 text-sm font-mono text-foreground focus:border-emerald/50 focus:outline-none"
              />
            </div>

            <div>
              <label className="text-xs text-muted-foreground block mb-1">Risk Per Trade: {riskPct}%</label>
              <input
                type="range"
                min={0.25}
                max={5}
                step={0.25}
                value={riskPct}
                onChange={(e) => setRiskPct(Number(e.target.value))}
                className="w-full accent-emerald"
              />
              <div className="flex justify-between text-[10px] text-muted-foreground mt-0.5">
                <span>0.25%</span><span>5%</span>
              </div>
            </div>

            <div>
              <label className="text-xs text-muted-foreground block mb-1">Leverage: {leverage}x</label>
              <input
                type="range"
                min={1}
                max={maxLeverage}
                step={1}
                value={leverage}
                onChange={(e) => setLeverage(Number(e.target.value))}
                className="w-full accent-emerald"
              />
              <div className="flex justify-between text-[10px] text-muted-foreground mt-0.5">
                <span>1x</span><span>{maxLeverage}x</span>
              </div>
            </div>

            <div>
              <label className="text-xs text-muted-foreground block mb-1">Stop Loss Distance: {stopPct}%</label>
              <input
                type="range"
                min={0.5}
                max={10}
                step={0.5}
                value={stopPct}
                onChange={(e) => setStopPct(Number(e.target.value))}
                className="w-full accent-emerald"
              />
              <div className="flex justify-between text-[10px] text-muted-foreground mt-0.5">
                <span>0.5%</span><span>10%</span>
              </div>
              <p className="text-[10px] text-muted-foreground mt-1">
                Stop @ {stopLoss > 0 ? formatUSD(stopLoss, stopLoss < 10 ? 4 : 2) : '—'}
              </p>
            </div>

            <button
              onClick={recalc}
              disabled={sizer.isPending || !entry}
              className="w-full bg-emerald/10 border border-emerald/30 text-emerald font-medium text-xs py-2 rounded-md hover:bg-emerald/20 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {sizer.isPending ? 'Computing…' : 'Compute Size'}
            </button>
          </div>
        </div>

        {/* Results panel */}
        <div className="space-y-4">
          <div className="hud-panel-glow p-5">
            <h2 className="text-xs font-semibold tracking-[0.12em] uppercase text-muted-foreground mb-4">Recommended Position</h2>

            <div className="text-center mb-4">
              <div className="text-[10px] font-semibold tracking-[0.12em] uppercase text-muted-foreground mb-1">Qty (Engine)</div>
              <div className="font-mono text-3xl font-bold text-emerald tabular-nums">
                {result ? result.qty.toFixed(entry < 10 ? 0 : 4) : '—'}
              </div>
              <div className="text-xs text-muted-foreground mt-1">{symbol} {result?.direction ?? ''}</div>
              {result && !result.valid && result.reason && (
                <div className="text-xs text-amber-warn mt-2">{result.reason}</div>
              )}
            </div>

            <div className="space-y-2 text-xs">
              {[
                ['Method',           result?.method ?? '—'],
                ['Entry Price',      entry > 0 ? formatUSD(entry, entry < 10 ? 4 : 2) : '—'],
                ['Stop Loss',        stopLoss > 0 ? formatUSD(stopLoss, stopLoss < 10 ? 4 : 2) : '—'],
                ['Leverage',         result ? `${result.leverage}x` : '—'],
                ['Risk Amount',      result ? formatUSD(result.risk_usdt) : '—'],
                ['Risk %',           result ? `${result.risk_pct.toFixed(2)}%` : '—'],
                ['Notional Value',   result ? formatUSD(result.notional) : '—'],
                ['Margin Required',  result ? formatUSD(result.margin_usdt) : '—'],
              ].map(([label, value]) => (
                <div key={label} className="flex justify-between py-1.5 border-b border-border/30">
                  <span className="text-muted-foreground">{label}</span>
                  <span className="font-mono tabular-nums text-foreground">{value}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="hud-panel p-4">
            <h3 className="text-[10px] font-semibold tracking-[0.12em] uppercase text-muted-foreground mb-2">Sizing Notes</h3>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Size is returned by the engine's risk gate, which enforces the hard 2% per-trade cap and applies the
              regime-aware Kelly adjustment when in KELLY mode. Fixed-fractional uses{' '}
              <code className="text-foreground">risk_per_trade_pct</code> of the supplied balance divided by the entry-to-stop distance.
            </p>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
