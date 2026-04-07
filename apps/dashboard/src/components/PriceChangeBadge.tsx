/**
 * PriceChangeBadge — Command Center HUD
 * Reusable 24h price change percentage badge.
 * Green for positive, red for negative.
 */
import { TrendingUp, TrendingDown } from "lucide-react";

interface PriceChangeBadgeProps {
  pct: number;
  size?: "sm" | "md";
  showIcon?: boolean;
}

export default function PriceChangeBadge({ pct, size = "sm", showIcon = true }: PriceChangeBadgeProps) {
  const isPositive = pct >= 0;
  const Icon = isPositive ? TrendingUp : TrendingDown;
  const color = isPositive ? "text-emerald bg-emerald/10 border-emerald/20" : "text-destructive bg-destructive/10 border-destructive/20";
  const textSize = size === "md" ? "text-[12px]" : "text-[10px]";
  const iconSize = size === "md" ? "w-3.5 h-3.5" : "w-3 h-3";

  return (
    <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded border data-value font-semibold ${color} ${textSize}`}>
      {showIcon && <Icon className={iconSize} />}
      {isPositive ? "+" : ""}{pct.toFixed(2)}%
    </span>
  );
}
