import { cn } from '@/lib/utils';

type BadgeVariant = 'green' | 'yellow' | 'red' | 'cyan' | 'muted' | 'black';

interface StatusBadgeProps {
  label: string;
  variant?: BadgeVariant;
  pulse?: boolean;
  className?: string;
}

const variantStyles: Record<BadgeVariant, string> = {
  green: 'bg-emerald/10 text-emerald border-emerald/20',
  yellow: 'bg-amber-warn/10 text-amber-warn border-amber-warn/20',
  red: 'bg-crimson/10 text-crimson border-crimson/20',
  cyan: 'bg-cyan-accent/10 text-cyan-accent border-cyan-accent/20',
  muted: 'bg-muted text-muted-foreground border-border',
  black: 'bg-zinc-900 text-zinc-400 border-zinc-700',
};

export function getRegimeVariant(regime: string): BadgeVariant {
  switch (regime) {
    case 'Trending': return 'green';
    case 'Mean-Reverting': return 'cyan';
    case 'Volatile': return 'yellow';
    case 'Quiet': return 'muted';
    default: return 'muted';
  }
}

export function getRiskVariant(status: string): BadgeVariant {
  switch (status) {
    case 'GREEN': return 'green';
    case 'YELLOW': return 'yellow';
    case 'RED': return 'red';
    case 'BLACK': return 'black';
    default: return 'muted';
  }
}

export function getSignalVariant(signal: string): BadgeVariant {
  switch (signal) {
    case 'Bullish': return 'green';
    case 'Bearish': return 'red';
    case 'Neutral': return 'muted';
    default: return 'muted';
  }
}

export default function StatusBadge({ label, variant = 'muted', pulse, className }: StatusBadgeProps) {
  return (
    <span className={cn(
      'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-sm text-[11px] font-medium border',
      variantStyles[variant],
      className,
    )}>
      {pulse && (
        <span className={cn(
          'w-1.5 h-1.5 rounded-full animate-pulse-dot',
          variant === 'green' && 'bg-emerald',
          variant === 'yellow' && 'bg-amber-warn',
          variant === 'red' && 'bg-crimson',
          variant === 'cyan' && 'bg-cyan-accent',
          variant === 'muted' && 'bg-muted-foreground',
          variant === 'black' && 'bg-zinc-500',
        )} />
      )}
      {label}
    </span>
  );
}
