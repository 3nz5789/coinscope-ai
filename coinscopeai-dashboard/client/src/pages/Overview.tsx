/* Overview — Portfolio summary, account balance, daily P&L, risk gate, equity chart
 * Live data via engine hooks (replaces demo mock fixtures).
 */
import DashboardLayout from '@/components/DashboardLayout';
import MetricCard from '@/components/MetricCard';
import PageHeader from '@/components/PageHeader';
import StatusBadge, { getRiskVariant } from '@/components/StatusBadge';
import {
  useAccount,
  useAccountPositions,
  useCircuitBreaker,
  useConfig,
  useEquityCurve,
  useExposure,
  usePerformance,
  usePositions,
} from '@/lib/engine/hooks';
import { formatPct, formatUSD } from '@/lib/mockData';
import { cn } from '@/lib/utils';
import { Activity, DollarSign, Shield, TrendingUp, Wallet } from 'lucide-react';
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

export default function Overview() {
  const account     = useAccount();
  const acctPos     = useAccountPositions();
  const positions   = usePositions();
  const exposure    = useExposure();
  const cb          = useCircuitBreaker();
  const perf        = usePerformance();
  const equity      = useEquityCurve();
  const config      = useConfig();

  // Prefer the live Binance Futures Demo numbers when available.
  const liveAccount  = account.data;
  const balance      = liveAccount?.total_wallet_balance ?? exposure.data?.balance ?? positions.data?.balance ?? 0;
  const marginBal    = liveAccount?.total_margin_balance ?? balance;
  const unrealised   = liveAccount?.total_unrealized_pnl ?? exposure.data?.unrealised_pnl ?? 0;
  const realised     = exposure.data?.realised_pnl ?? 0;
  const dailyPnl     = exposure.data?.daily_pnl ?? 0;
  const dailyLossPct = exposure.data?.daily_loss_pct ?? 0;
  const totalEquity  = marginBal;   // margin balance already includes unrealised PnL
  const posCount     = liveAccount?.position_count ?? acctPos.data?.count ?? positions.data?.position_count ?? 0;
  const maxPos       = config.data?.max_open_positions ?? 3;
  const canTrade     = liveAccount?.can_trade ?? false;
  const availBalance = liveAccount?.available_balance ?? balance;
  const acctFresh    = liveAccount?.age_s != null && liveAccount.age_s < 30;

  // Engine returns equity points with various key shapes — normalise
  const equityPoints = (equity.data?.points ?? []).map((p: any) => ({
    date: p.date ?? p.ts ?? '',
    equity: Number(p.equity ?? 0),
  }));

  const firstEq = equityPoints[0]?.equity ?? 0;
  const lastEq  = equityPoints[equityPoints.length - 1]?.equity ?? 0;
  const eqChangePct = firstEq > 0 ? ((lastEq - firstEq) / firstEq) * 100 : 0;

  // Risk-gate label: engine uses CLOSED (safe). Map to GREEN/YELLOW/RED.
  const riskLabel =
    cb.data?.state === 'CLOSED'
      ? 'GREEN'
      : cb.data?.state === 'TRIPPED' || cb.data?.state === 'OPEN'
      ? 'RED'
      : 'YELLOW';

  // Prefer the Binance-native shape (/account/positions) when we have data.
  // Fall back to ExposureTracker snapshot shape otherwise.
  const livePositions = (acctPos.data?.positions ?? []).map((p) => ({
    symbol: p.symbol,
    side: p.side,
    entry_price: p.entry_price,
    mark_price: p.mark_price,
    unrealised_pnl: p.unrealized_pnl,
    leverage: p.leverage,
    qty: p.position_amt,
  })) as any[];
  const legacyPositions = positions.data?.positions ?? [];
  const showPositions = livePositions.length > 0 ? livePositions : legacyPositions;

  return (
    <DashboardLayout>
      <PageHeader
        title="Command Center"
        subtitle={`Portfolio overview · Binance Futures Demo · ${canTrade ? 'trading enabled' : 'read-only'}`}
      >
        <div className="flex items-center gap-2 text-xs">
          <span className={cn('w-2 h-2 rounded-full', acctFresh ? 'bg-emerald animate-pulse' : 'bg-amber-warn')} />
          <span className="text-muted-foreground">
            {account.isLoading && !liveAccount ? 'Syncing…'
              : liveAccount?.error ? `Sync error: ${liveAccount.error}`
              : acctFresh ? `Live · ${liveAccount?.age_s?.toFixed(0)}s ago`
              : 'Stale — click refresh'}
          </span>
        </div>
      </PageHeader>

      {/* Top metrics row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 xl:grid-cols-5 gap-3 mb-6">
        <MetricCard
          label="Wallet Balance"
          value={formatUSD(balance)}
          subValue={`Available ${formatUSD(availBalance)}`}
          icon={Wallet}
        />
        <MetricCard
          label="Margin Balance"
          value={formatUSD(totalEquity)}
          subValue={unrealised !== 0 ? `uPnL ${formatUSD(unrealised)}` : 'flat'}
          trend={unrealised >= 0 ? 'up' : 'down'}
          icon={DollarSign}
        />
        <MetricCard
          label="Daily P&L"
          value={formatUSD(dailyPnl)}
          subValue={formatPct(-dailyLossPct)}
          trend={dailyPnl >= 0 ? 'up' : 'down'}
          icon={TrendingUp}
        />
        <MetricCard
          label="Unrealized P&L"
          value={formatUSD(unrealised)}
          trend={unrealised >= 0 ? 'up' : 'down'}
          icon={Activity}
        />
        <MetricCard
          label="Active Positions"
          value={String(posCount)}
          subValue={`/ ${maxPos} max`}
          icon={Shield}
        />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        {/* Equity mini-chart */}
        <div className="xl:col-span-2 hud-panel p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xs font-semibold tracking-[0.12em] uppercase text-muted-foreground">
              Equity Curve
            </h2>
            <span className={cn('text-xs font-mono tabular-nums', eqChangePct >= 0 ? 'text-emerald' : 'text-crimson')}>
              {formatPct(eqChangePct)}
            </span>
          </div>
          {equityPoints.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={equityPoints} margin={{ top: 5, right: 5, bottom: 0, left: 5 }}>
                <defs>
                  <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#10b981" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#64748b' }} tickLine={false} axisLine={false} tickFormatter={(v) => String(v).slice(5)} />
                <YAxis tick={{ fontSize: 10, fill: '#64748b' }} tickLine={false} axisLine={false} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} domain={['auto', 'auto']} />
                <Tooltip
                  contentStyle={{ background: '#131b2e', border: '1px solid #1e293b', borderRadius: '6px', fontSize: '12px' }}
                  labelStyle={{ color: '#94a3b8' }}
                  itemStyle={{ color: '#10b981' }}
                  formatter={(value: number) => [formatUSD(value), 'Equity']}
                />
                <Area type="monotone" dataKey="equity" stroke="#10b981" strokeWidth={2} fill="url(#eqGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[220px] flex items-center justify-center text-xs text-muted-foreground">
              {equity.isLoading ? 'Loading…' : 'No equity history yet — run some trades.'}
            </div>
          )}
        </div>

        {/* Right column */}
        <div className="space-y-4">
          {/* Risk Gate Status */}
          <div className="hud-panel p-4">
            <h2 className="text-xs font-semibold tracking-[0.12em] uppercase text-muted-foreground mb-3">
              Risk Gate Status
            </h2>
            <div className="flex items-center gap-3 mb-3">
              <StatusBadge label={riskLabel} variant={getRiskVariant(riskLabel)} pulse />
              <span className="text-sm text-muted-foreground">
                {cb.data?.state === 'CLOSED' ? 'All parameters nominal' : `Breaker ${cb.data?.state ?? '…'}`}
              </span>
            </div>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Win Rate</span>
                <span className="font-mono text-foreground tabular-nums">
                  {perf.data ? `${(perf.data.win_rate ?? 0).toFixed(1)}%` : '—'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Total Trades</span>
                <span className="font-mono text-foreground tabular-nums">
                  {perf.data?.total_trades ?? 0}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Exposure</span>
                <span className="font-mono text-foreground tabular-nums">
                  {(exposure.data?.total_exposure_pct ?? 0).toFixed(1)}% / {exposure.data?.max_total_exposure_pct ?? 80}%
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Realised P&L</span>
                <span className="font-mono text-foreground tabular-nums">{formatUSD(realised)}</span>
              </div>
            </div>
          </div>

          {/* Scan pairs summary (replaces per-symbol 24h change — engine has no price feed) */}
          <div className="hud-panel p-4">
            <h2 className="text-xs font-semibold tracking-[0.12em] uppercase text-muted-foreground mb-3">
              Scan Universe
            </h2>
            <div className="space-y-2">
              {(config.data?.scan_pairs ?? []).map((sym) => (
                <div key={sym} className="flex items-center justify-between text-xs">
                  <span className="font-medium text-foreground">{sym.replace('USDT', '')}</span>
                  <span className="font-mono text-muted-foreground tabular-nums">{sym}</span>
                </div>
              ))}
              {!config.data && (
                <div className="text-xs text-muted-foreground">Loading config…</div>
              )}
            </div>
            <div className="mt-3 pt-2 border-t border-border text-xs flex justify-between">
              <span className="text-muted-foreground">Min score</span>
              <span className="font-mono text-foreground">{config.data?.min_confluence_score ?? '—'}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Active positions summary */}
      <div className="mt-4 hud-panel p-4">
        <h2 className="text-xs font-semibold tracking-[0.12em] uppercase text-muted-foreground mb-3">
          Active Positions
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-2 px-2 text-muted-foreground font-medium">Symbol</th>
                <th className="text-left py-2 px-2 text-muted-foreground font-medium">Side</th>
                <th className="text-right py-2 px-2 text-muted-foreground font-medium">Entry</th>
                <th className="text-right py-2 px-2 text-muted-foreground font-medium">Mark</th>
                <th className="text-right py-2 px-2 text-muted-foreground font-medium">Unrealized P&L</th>
                <th className="text-right py-2 px-2 text-muted-foreground font-medium">Leverage</th>
                <th className="text-right py-2 px-2 text-muted-foreground font-medium">Qty</th>
              </tr>
            </thead>
            <tbody>
              {showPositions.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-6 text-center text-muted-foreground">
                    {acctPos.isLoading && positions.isLoading ? 'Loading…' : 'No open positions'}
                  </td>
                </tr>
              ) : (
                showPositions.map((pos, idx) => (
                  <tr key={`${pos.symbol}-${idx}`} className="border-b border-border/50 hover:bg-secondary/30 transition-colors">
                    <td className="py-2 px-2 font-medium text-foreground">{pos.symbol}</td>
                    <td className="py-2 px-2">
                      <span className={cn('font-semibold', pos.side === 'LONG' ? 'text-emerald' : 'text-crimson')}>
                        {pos.side}
                      </span>
                    </td>
                    <td className="py-2 px-2 text-right font-mono tabular-nums text-foreground">{formatUSD(pos.entry_price)}</td>
                    <td className="py-2 px-2 text-right font-mono tabular-nums text-foreground">
                      {pos.mark_price != null ? formatUSD(pos.mark_price) : '—'}
                    </td>
                    <td className={cn('py-2 px-2 text-right font-mono tabular-nums', (pos.unrealised_pnl ?? 0) >= 0 ? 'text-emerald' : 'text-crimson')}>
                      {formatUSD(pos.unrealised_pnl ?? 0)}
                    </td>
                    <td className="py-2 px-2 text-right font-mono tabular-nums text-foreground">{pos.leverage}x</td>
                    <td className="py-2 px-2 text-right text-muted-foreground">{pos.qty}</td>
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
