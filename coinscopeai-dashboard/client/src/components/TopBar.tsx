import { useCircuitBreaker, useLivePrices } from '@/lib/engine/hooks';
import { formatUSD } from '@/lib/mockData';
import { cn } from '@/lib/utils';
import { Wifi, WifiOff } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

export default function TopBar() {
  const [time, setTime] = useState(new Date());
  const prices = useLivePrices();
  const cb     = useCircuitBreaker();

  // Remember the first observed price for each symbol so we can show a
  // session delta until the engine exposes 24h change.
  const basePricesRef = useRef<Record<string, number>>({});
  const rows = prices.data?.prices ?? [];
  rows.forEach(r => {
    if (basePricesRef.current[r.symbol] == null && r.mark_price > 0) {
      basePricesRef.current[r.symbol] = r.mark_price;
    }
  });

  useEffect(() => {
    const interval = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(interval);
  }, []);

  const connected = prices.data?.feed?.connected ?? false;
  const lastAge   = prices.data?.feed?.last_msg_age_s;
  const isFresh   = connected && lastAge != null && lastAge < 5;

  // Map circuit-breaker state to the green/yellow/red badge the old UI showed
  const cbState = cb.data?.state ?? 'CLOSED';
  const riskStatus =
    cbState === 'CLOSED' ? 'GREEN' :
    cbState === 'TRIPPED' || cbState === 'OPEN' ? 'RED' : 'YELLOW';

  return (
    <header className="h-10 border-b border-border bg-card/50 backdrop-blur-sm flex items-center px-4 gap-6 text-xs shrink-0">
      {/* Live price ticker */}
      <div className="flex items-center gap-4 overflow-x-auto">
        {rows.length === 0 && (
          <span className="text-muted-foreground">
            {prices.isLoading ? 'Loading prices…' : 'No prices yet'}
          </span>
        )}
        {rows.map((r) => {
          const base = basePricesRef.current[r.symbol] ?? r.mark_price;
          const changePct = base > 0 ? ((r.mark_price - base) / base) * 100 : 0;
          return (
            <div key={r.symbol} className="flex items-center gap-1.5 whitespace-nowrap">
              <span className="font-medium text-foreground">{r.symbol.replace('USDT', '')}</span>
              <span className="font-mono text-foreground tabular-nums">
                {formatUSD(r.mark_price, r.mark_price < 10 ? 4 : 2)}
              </span>
              <span className={cn(
                'font-mono tabular-nums text-[10px]',
                changePct >= 0 ? 'text-emerald' : 'text-crimson',
              )}>
                {changePct >= 0 ? '+' : ''}{changePct.toFixed(2)}%
              </span>
              {r.funding_rate !== 0 && (
                <span
                  className={cn(
                    'font-mono tabular-nums text-[10px] opacity-70',
                    r.funding_rate >= 0 ? 'text-emerald' : 'text-crimson',
                  )}
                  title="Current funding rate"
                >
                  f{(r.funding_rate * 100).toFixed(3)}%
                </span>
              )}
            </div>
          );
        })}
      </div>

      <div className="ml-auto flex items-center gap-4">
        {/* WS feed status */}
        <div className="flex items-center gap-1.5" title={prices.data?.feed?.error ?? (isFresh ? 'WS live' : 'WS stale')}>
          {isFresh ? (
            <Wifi className="w-3 h-3 text-emerald" />
          ) : (
            <WifiOff className="w-3 h-3 text-amber-warn" />
          )}
          <span className="text-muted-foreground">
            {isFresh ? `Live · ${lastAge?.toFixed(1)}s` : connected ? 'Connecting…' : 'Offline'}
          </span>
        </div>

        {/* Risk badge */}
        <div className={cn(
          'flex items-center gap-1 px-2 py-0.5 rounded-sm text-[10px] font-semibold tracking-wider uppercase',
          riskStatus === 'GREEN' && 'bg-emerald/10 text-emerald',
          riskStatus === 'YELLOW' && 'bg-amber-warn/10 text-amber-warn',
          riskStatus === 'RED' && 'bg-crimson/10 text-crimson',
        )}>
          <div className={cn(
            'w-1.5 h-1.5 rounded-full animate-pulse-dot',
            riskStatus === 'GREEN' && 'bg-emerald',
            riskStatus === 'YELLOW' && 'bg-amber-warn',
            riskStatus === 'RED' && 'bg-crimson',
          )} />
          {riskStatus}
        </div>

        {/* Clock */}
        <span className="font-mono text-muted-foreground tabular-nums">
          {time.toUTCString().slice(17, 25)} UTC
        </span>
      </div>
    </header>
  );
}
