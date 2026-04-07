/**
 * HudCard — Command Center HUD
 * Card with subtle border glow on hover and optional status indicator.
 */
import { ReactNode } from "react";
import { RefreshCw } from "lucide-react";

interface HudCardProps {
  title?: string;
  subtitle?: string;
  children: ReactNode;
  className?: string;
  headerRight?: ReactNode;
  loading?: boolean;
  noPadding?: boolean;
}

export default function HudCard({ title, subtitle, children, className = "", headerRight, loading, noPadding }: HudCardProps) {
  const hasHeader = title || subtitle || headerRight || loading;
  return (
    <div className={`hud-card overflow-hidden ${className}`}>
      {/* Header */}
      {hasHeader && (
        <div className="flex items-center justify-between px-4 py-3 border-b border-border/50">
          <div className="flex items-center gap-2">
            {title && <h3 className="text-[13px] font-semibold text-foreground uppercase tracking-wider">{title}</h3>}
            {subtitle && <span className="text-[11px] text-muted-foreground">{subtitle}</span>}
            {loading && <RefreshCw className="w-3 h-3 text-muted-foreground animate-spin" />}
          </div>
          {headerRight && <div className="flex items-center gap-2">{headerRight}</div>}
        </div>
      )}
      {/* Content */}
      <div className={noPadding ? "" : "p-4"}>
        {children}
      </div>
    </div>
  );
}
