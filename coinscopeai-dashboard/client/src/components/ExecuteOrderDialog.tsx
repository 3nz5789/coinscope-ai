/* ExecuteOrderDialog — confirm + submit a discretionary trade on Binance Demo.
 *
 * Shown from the Scanner "Execute" button or the Positions "Close" flow.
 * Uses PositionSizer on the engine to pre-compute qty based on risk, then
 * lets the trader review before clicking the red button.
 */
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  qk,
  usePlaceOrder,
  usePositionSize,
  useAttachBracket,
  useConfig,
  useAccount,
} from '@/lib/engine/hooks';
import { formatUSD } from '@/lib/mockData';
import { cn } from '@/lib/utils';
import { useQueryClient } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

export interface ExecuteOrderDialogProps {
  open: boolean;
  onOpenChange: (v: boolean) => void;

  // Signal context (comes from a Scanner signal row or manual form)
  symbol:        string;
  side:          'BUY' | 'SELL';
  entry:         number;
  stopLoss?:     number | null;
  takeProfit?:   number | null;

  scoreLabel?:   string;   // e.g. "STRONG 74" — shown as context
}

export default function ExecuteOrderDialog(props: ExecuteOrderDialogProps) {
  const { open, onOpenChange, symbol, side, entry, stopLoss, takeProfit, scoreLabel } = props;
  const config   = useConfig();
  const account  = useAccount();
  const sizer    = usePositionSize();
  const place    = usePlaceOrder();
  const bracket  = useAttachBracket();
  const qc       = useQueryClient();

  const [leverage, setLeverage] = useState<number>(5);
  const [attachBracket, setAttachBracket] = useState<boolean>(true);
  const [riskPct, setRiskPct]   = useState<number>(1);

  const balance = account.data?.available_balance ?? 0;
  const maxLev  = config.data?.max_leverage ?? 10;

  // Ask the engine to compute qty whenever inputs change
  useEffect(() => {
    if (!open) return;
    if (!entry || !stopLoss || balance <= 0) return;
    sizer.mutate(
      { symbol, entry, stop_loss: stopLoss, balance, risk_pct: riskPct, leverage },
      { onError: () => {} },
    );
  }, [open, symbol, entry, stopLoss, balance, riskPct, leverage]);

  const qty = sizer.data?.qty ?? 0;
  const notional = sizer.data?.notional ?? qty * entry;
  const marginReq = sizer.data?.margin_usdt ?? (leverage > 0 ? notional / leverage : 0);
  const riskUsd = sizer.data?.risk_usdt ?? 0;

  async function onSubmit() {
    if (qty <= 0) {
      toast.error('Engine computed qty=0 — check stop-loss.');
      return;
    }
    try {
      const resp = await place.mutateAsync({
        symbol,
        side,
        type: 'MARKET',
        qty,
        leverage,
      });
      toast.success(`${side} ${symbol} ${qty} placed · order #${resp.order.orderId}`);

      if (attachBracket && (stopLoss || takeProfit)) {
        try {
          await bracket.mutateAsync({
            symbol,
            side,
            stop_price: stopLoss ?? undefined,
            tp_price:   takeProfit ?? undefined,
          });
          toast.success('SL + TP bracket attached.');
        } catch (err: any) {
          toast.error(`Bracket failed: ${err?.response?.data?.detail ?? err?.message}`);
        }
      }

      // Force fresh account + positions so the UI reflects the new state
      await Promise.all([
        qc.invalidateQueries({ queryKey: qk.account }),
        qc.invalidateQueries({ queryKey: qk.accountPositions }),
        qc.invalidateQueries({ queryKey: qk.positions }),
      ]);
      onOpenChange(false);
    } catch (err: any) {
      const msg = err?.response?.data?.detail ?? err?.message ?? String(err);
      toast.error(`Order rejected: ${msg}`);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-3">
            Execute
            <span className={cn(
              'text-xs font-bold px-2 py-0.5 rounded-sm',
              side === 'BUY'  ? 'bg-emerald/10 text-emerald' : 'bg-crimson/10 text-crimson',
            )}>
              {side === 'BUY' ? 'LONG' : 'SHORT'} {symbol}
            </span>
          </DialogTitle>
          <DialogDescription>
            {scoreLabel ? `Signal: ${scoreLabel}. ` : ''}Posting to Binance Futures Demo.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 text-sm">
          {/* Risk slider */}
          <div>
            <label className="text-xs text-muted-foreground block mb-1">Risk: {riskPct}%</label>
            <input
              type="range" min={0.25} max={3} step={0.25}
              value={riskPct}
              onChange={(e) => setRiskPct(Number(e.target.value))}
              className="w-full accent-emerald"
            />
          </div>

          {/* Leverage slider */}
          <div>
            <label className="text-xs text-muted-foreground block mb-1">Leverage: {leverage}x</label>
            <input
              type="range" min={1} max={maxLev} step={1}
              value={leverage}
              onChange={(e) => setLeverage(Number(e.target.value))}
              className="w-full accent-emerald"
            />
          </div>

          {/* Bracket toggle */}
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={attachBracket}
              onChange={(e) => setAttachBracket(e.target.checked)}
              className="accent-emerald"
            />
            Attach SL + TP bracket after fill
          </label>

          {/* Computed breakdown */}
          <div className="hud-panel p-3 space-y-1.5 text-xs">
            {[
              ['Entry',       entry ? formatUSD(entry, entry < 10 ? 4 : 2) : '—'],
              ['Stop loss',   stopLoss ? formatUSD(stopLoss, stopLoss < 10 ? 4 : 2) : '—'],
              ['Take profit', takeProfit ? formatUSD(takeProfit, takeProfit < 10 ? 4 : 2) : '—'],
              ['Qty (engine)',qty ? qty.toFixed(entry < 10 ? 0 : 4) : (sizer.isPending ? 'calculating…' : '—')],
              ['Notional',    notional > 0 ? formatUSD(notional) : '—'],
              ['Margin req',  marginReq > 0 ? formatUSD(marginReq) : '—'],
              ['Risk amount', riskUsd > 0 ? formatUSD(riskUsd) : '—'],
              ['Available',   formatUSD(balance)],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between">
                <span className="text-muted-foreground">{k}</span>
                <span className="font-mono tabular-nums text-foreground">{v}</span>
              </div>
            ))}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={place.isPending}>
            Cancel
          </Button>
          <Button
            onClick={onSubmit}
            disabled={place.isPending || qty <= 0}
            className={cn(
              side === 'BUY' ? 'bg-emerald hover:bg-emerald/90 text-white' : 'bg-crimson hover:bg-crimson/90 text-white',
            )}
          >
            {place.isPending && <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />}
            Confirm {side === 'BUY' ? 'LONG' : 'SHORT'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
