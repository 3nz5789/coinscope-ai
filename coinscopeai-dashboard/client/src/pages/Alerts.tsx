/* Alerts — Telegram alert history, configurable alert rules */
import DashboardLayout from '@/components/DashboardLayout';
import PageHeader from '@/components/PageHeader';
import StatusBadge from '@/components/StatusBadge';
import { ALERTS } from '@/lib/mockData';
import { cn } from '@/lib/utils';
import { AlertTriangle, Bell, CheckCircle, Radio, Send, Shield, Zap } from 'lucide-react';

type AlertVariant = 'green' | 'yellow' | 'red' | 'cyan' | 'muted';

function getAlertVariant(type: string): AlertVariant {
  switch (type) {
    case 'SIGNAL': return 'cyan';
    case 'RISK': return 'yellow';
    case 'EXECUTION': return 'green';
    case 'REGIME': return 'muted';
    case 'SYSTEM': return 'green';
    default: return 'muted';
  }
}

function getAlertIcon(type: string) {
  switch (type) {
    case 'SIGNAL': return Zap;
    case 'RISK': return Shield;
    case 'EXECUTION': return Send;
    case 'REGIME': return Radio;
    case 'SYSTEM': return Bell;
    default: return AlertTriangle;
  }
}

export default function Alerts() {
  return (
    <DashboardLayout>
      <PageHeader title="Alerts & Notifications" subtitle={`${ALERTS.length} alerts — Telegram delivery`} />

      {/* Alert stats */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-6">
        {['SIGNAL', 'RISK', 'EXECUTION', 'REGIME', 'SYSTEM'].map((type) => {
          const count = ALERTS.filter((a) => a.type === type).length;
          const Icon = getAlertIcon(type);
          return (
            <div key={type} className="hud-panel p-3 flex items-center gap-3">
              <Icon className="w-5 h-5 text-muted-foreground" />
              <div>
                <div className="text-[10px] font-semibold tracking-[0.12em] uppercase text-muted-foreground">{type}</div>
                <div className="font-mono text-lg font-semibold text-foreground tabular-nums">{count}</div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Alert feed */}
      <div className="hud-panel overflow-hidden">
        <div className="space-y-0">
          {ALERTS.map((alert) => {
            const Icon = getAlertIcon(alert.type);
            return (
              <div
                key={alert.id}
                className="flex items-start gap-3 p-4 border-b border-border/50 hover:bg-secondary/20 transition-colors"
              >
                <div className={cn(
                  'w-8 h-8 rounded-md flex items-center justify-center shrink-0',
                  alert.type === 'SIGNAL' && 'bg-cyan-accent/10',
                  alert.type === 'RISK' && 'bg-amber-warn/10',
                  alert.type === 'EXECUTION' && 'bg-emerald/10',
                  alert.type === 'REGIME' && 'bg-muted',
                  alert.type === 'SYSTEM' && 'bg-emerald/10',
                )}>
                  <Icon className={cn(
                    'w-4 h-4',
                    alert.type === 'SIGNAL' && 'text-cyan-accent',
                    alert.type === 'RISK' && 'text-amber-warn',
                    alert.type === 'EXECUTION' && 'text-emerald',
                    alert.type === 'REGIME' && 'text-muted-foreground',
                    alert.type === 'SYSTEM' && 'text-emerald',
                  )} />
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <StatusBadge label={alert.type} variant={getAlertVariant(alert.type)} />
                    {alert.symbol && (
                      <span className="text-xs font-semibold text-foreground">{alert.symbol}</span>
                    )}
                  </div>
                  <p className="text-xs text-foreground leading-relaxed">{alert.message}</p>
                </div>

                <div className="text-right shrink-0">
                  <div className="text-[10px] text-muted-foreground whitespace-nowrap">{alert.time}</div>
                  {alert.sent && (
                    <div className="flex items-center gap-1 mt-1 justify-end">
                      <CheckCircle className="w-3 h-3 text-emerald" />
                      <span className="text-[10px] text-emerald">{alert.channel}</span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </DashboardLayout>
  );
}
