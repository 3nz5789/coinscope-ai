/* Positions — Open positions table with entry, mark, P&L, leverage, SL/TP (live) */
import DashboardLayout from '@/components/DashboardLayout';
import MetricCard from '@/components/MetricCard';
import PageHeader from '@/components/PageHeader';
import { qk, useAccount, useAccountPositions, useClosePosition, useConfig, useExposure, useOpenAlgoOrders, usePositions } from '@/lib/engine/hooks';
import { formatPct, formatUSD } from '@/lib/mockData';
import { cn } from '@/lib/utils';
import { useQueryClient } from '@tanstack/react-query';
import { Activity, DollarSign, TrendingUp, X } from 'lucide-react';
import { toast } from 'sonner';

export default function Positions() {
  const acct    = useAccount();
  const acctPos = useAccountPositions();
  const pos     = usePositions();
  const expo    = useExposure();
  const config  = useConfig();
  const close   = useClosePosition();
  const qc      = useQueryClient();

  async function onClose(symbol: string) {
    if (!confirm(`Market-close open position on ${symbol}? This uses a reduce-only MARKET order.`)) return;
    try {
      const resp: any = await close.mutateAsync({ symbol });
      toast.success(`Close sent: ${symbol} · #${resp.order?.orderId}`);
      await Promise.all([
        qc.invalidateQueries({ queryKey: qk.account }),
        qc.invalidateQueries({ queryKey: qk.accountPositions }),
        qc.invalidateQueries({ queryKey: qk.positions }),
      ]);
    } catch (err: any) {
      toast.error(`Close failed: ${err?.response?.data?.detail ?? err?.message ?? err}`);
    }
  }

  // Active Algo (SL/TP) orders grouped by symbol for quick lookup
  const algo = useOpenAlgoOrders();
  const bracketBySymbol: Record<string, { sl?: number; tp?: number }> = {};
  (algo.data?.orders ?? []).forEach((o: any) => {
    const sym = o.symbol;
    if (!sym) return;
    const trigger = Number(o.triggerPrice ?? o.stopPrice ?? 0);
    if (!bracketBySymbol[sym]) bracketBySymbol[sym] = {};
    const t = String(o.orderType ?? o.type ?? '').toUpperCase();
    if (t.startsWith('STOP'))         bracketBySymbol[sym].sl = trigger;
    if (t.startsWith('TAKE_PROFIT'))  bracketBySymbol[sym].tp = trigger;
  });

  // Use the live Binance shape when available (richer fields: liq, leverage, margin type)
  const livePositions = (acctPos.data?.positions ?? []).map((p) => ({
    symbol: p.symbol,
    side: p.side,
    qty: p.position_amt,
    leverage: p.leverage,
    entry_price: p.entry_price,
    mark_price: p.mark_price,
    unrealised_pnl: p.unrealized_pnl,
    liquidation_price: p.liquidation_price,
    stop_loss:   bracketBySymbol[p.symbol]?.sl ?? null,
    take_profit: bracketBySymbol[p.symbol]?.tp ?? null,
    opened_at: p.update_time ? new Date(p.update_time).toLocaleString() : null,
  }));
  const positions = livePositions.length > 0 ? livePositions : (pos.data?.positions ?? []);
  const totalUnrealized = acct.data?.total_unrealized_pnl ?? pos.data?.unrealised_pnl ?? 0;
  const totalNotional   = acct.data?.total_position_notional ?? pos.data?.total_notional ?? 0;
  const balance         = acct.data?.total_wallet_balance ?? pos.data?.balance ?? 0;
  const maxPos          = config.data?.max_open_positions ?? 3;
  const exposurePct     = expo.data?.total_exposure_pct ?? 0;

  return (
    <DashboardLayout>
      <PageHeader title="Open Positions" subtitle={`${positions.length} active position${positions.length === 1 ? '' : 's'}`} />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <MetricCard label="Unrealized P&L" value={formatUSD(totalUnrealized)} trend={totalUnrealized >= 0 ? 'up' : 'down'} icon={TrendingUp} />
        <MetricCard label="Total Notional" value={formatUSD(totalNotional)} icon={DollarSign} />
        <MetricCard label="Available Balance" value={formatUSD(balance)} icon={Activity} />
        <MetricCard label="Positions" value={`${positions.length} / ${maxPos}`} subValue={`Exposure ${exposurePct.toFixed(1)}%`} />
      </div>

      <div className="hud-panel overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border bg-navy-900/50">
                {['Symbol', 'Side', 'Qty', 'Leverage', 'Entry Price', 'Mark Price', 'Unrealized P&L', 'Liq. Price', 'Stop Loss', 'Take Profit', 'Opened', ''].map((h) => (
                  <th key={h} className="text-left py-3 px-3 text-[10px] font-semibold tracking-[0.1em] uppercase text-muted-foreground first:pl-4 last:pr-4">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {positions.length === 0 ? (
                <tr>
                  <td colSpan={12} className="py-10 text-center text-muted-foreground">
                    {pos.isLoading ? 'Loading…' : 'No open positions'}
                  </td>
                </tr>
              ) : (
                positions.map((p, idx) => {
                  const entry = Number(p.entry_price ?? 0);
                  const mark = Number(p.mark_price ?? entry);
                  const upnl = Number(p.unrealised_pnl ?? 0);
                  const pnlPct = entry > 0 && p.qty ? ((mark - entry) / entry) * 100 * (p.side === 'LONG' ? 1 : -1) : 0;
                  return (
                    <tr key={`${p.symbol}-${idx}`} className="border-b border-border/50 hover:bg-secondary/30 transition-colors">
                      <td className="py-3 px-3 pl-4 font-semibold text-foreground">{p.symbol}</td>
                      <td className="py-3 px-3">
                        <span className={cn('font-bold', p.side === 'LONG' ? 'text-emerald' : 'text-crimson')}>
                          {p.side}
                        </span>
                      </td>
                      <td className="py-3 px-3 font-mono tabular-nums text-foreground">{p.qty ?? '—'}</td>
                      <td className="py-3 px-3 font-mono tabular-nums text-foreground">{p.leverage ?? '—'}x</td>
                      <td className="py-3 px-3 font-mono tabular-nums text-foreground">{formatUSD(entry)}</td>
                      <td className="py-3 px-3 font-mono tabular-nums text-foreground">{formatUSD(mark)}</td>
                      <td className={cn('py-3 px-3 font-mono tabular-nums font-semibold', upnl >= 0 ? 'text-emerald' : 'text-crimson')}>
                        {formatUSD(upnl)}{' '}
                        <span className="ml-1 font-normal">({formatPct(pnlPct)})</span>
                      </td>
                      <td className="py-3 px-3 font-mono tabular-nums text-amber-warn">
                        {p.liquidation_price != null ? formatUSD(p.liquidation_price) : '—'}
                      </td>
                      <td className="py-3 px-3 font-mono tabular-nums text-crimson">
                        {p.stop_loss != null ? formatUSD(p.stop_loss) : '—'}
                      </td>
                      <td className="py-3 px-3 font-mono tabular-nums text-emerald">
                        {p.take_profit != null ? formatUSD(p.take_profit) : '—'}
                      </td>
                      <td className="py-3 px-3 text-muted-foreground whitespace-nowrap">
                        {p.opened_at ?? '—'}
                      </td>
                      <td className="py-3 px-3 pr-4">
                        <button
                          onClick={() => onClose(p.symbol)}
                          disabled={close.isPending}
                          className="flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-md bg-crimson/10 text-crimson border border-crimson/30 hover:bg-crimson/20 disabled:opacity-50"
                          title="Market-close this position (reduce-only)"
                        >
                          <X className="w-3 h-3" />
                          Close
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </DashboardLayout>
  );
}
