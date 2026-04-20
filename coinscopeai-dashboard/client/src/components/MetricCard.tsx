import { cn } from '@/lib/utils';
import type { LucideIcon } from 'lucide-react';

interface MetricCardProps {
  label: string;
  value: string;
  subValue?: string;
  icon?: LucideIcon;
  trend?: 'up' | 'down' | 'neutral';
  className?: string;
}

export default function MetricCard({ label, value, subValue, icon: Icon, trend, className }: MetricCardProps) {
  return (
    <div className={cn('hud-panel p-4', className)}>
      <div className="flex items-start justify-between mb-2">
        <span className="text-[10px] font-semibold tracking-[0.12em] uppercase text-muted-foreground">
          {label}
        </span>
        {Icon && <Icon className="w-4 h-4 text-muted-foreground/50" />}
      </div>
      <div className="font-mono text-2xl font-semibold text-foreground tabular-nums leading-none">
        {value}
      </div>
      {subValue && (
        <div className={cn(
          'mt-1.5 text-xs font-mono tabular-nums',
          trend === 'up' && 'text-emerald',
          trend === 'down' && 'text-crimson',
          trend === 'neutral' && 'text-muted-foreground',
          !trend && 'text-muted-foreground',
        )}>
          {subValue}
        </div>
      )}
    </div>
  );
}
