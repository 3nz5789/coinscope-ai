/**
 * StatusBar — Command Center HUD
 * Top strip showing global status: connection, time, live P&L, risk status
 */
import { useState, useEffect } from "react";
import { useApiData } from "@/hooks/useApiData";
import { api } from "@/lib/api";
import { Wifi, Clock, TrendingUp, TrendingDown, Shield, ShieldAlert, ShieldX } from "lucide-react";

export default function StatusBar() {
  const [time, setTime] = useState(new Date());
  const { data: perf } = useApiData(api.getPerformance, { refreshInterval: 30000 });
  const { data: risk } = useApiData(api.getRiskGate, { refreshInterval: 10000 });

  useEffect(() => {
    const interval = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(interval);
  }, []);

  const utcTime = time.toISOString().slice(11, 19);

  const returnPct = perf?.totalReturnPct ?? 0;
  const returnPositive = returnPct >= 0;
  const ReturnIcon = returnPositive ? TrendingUp : TrendingDown;
  const returnColor = returnPositive ? "text-emerald" : "text-destructive";

  const riskStatus = risk?.status ?? "nominal";
  const RiskIcon = riskStatus === "critical" ? ShieldX : riskStatus === "warning" ? ShieldAlert : Shield;
  const riskColor = riskStatus === "critical" ? "text-destructive" : riskStatus === "warning" ? "text-warning" : "text-emerald";
  const riskLabel = riskStatus.toUpperCase();

  return (
    <header className="h-10 border-b border-border/50 flex items-center justify-between px-5 shrink-0" style={{ background: "oklch(0.12 0.025 264.05)" }}>
      <div className="flex items-center gap-5">
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-emerald pulse-live" />
          <Wifi className="w-3.5 h-3.5 text-emerald" />
          <span className="text-[11px] font-medium text-emerald data-value">LIVE</span>
        </div>
        <div className="flex items-center gap-1.5 text-muted-foreground">
          <Clock className="w-3.5 h-3.5" />
          <span className="text-[11px] data-value">{utcTime} UTC</span>
        </div>
      </div>

      <div className="flex items-center gap-5">
        <div className="flex items-center gap-1.5">
          <ReturnIcon className={`w-3.5 h-3.5 ${returnColor}`} />
          <span className={`text-[11px] data-value ${returnColor}`}>
            {returnPositive ? "+" : ""}{returnPct.toFixed(2)}%
          </span>
          <span className="text-[11px] text-muted-foreground">Total Return</span>
        </div>
        <div className="flex items-center gap-1.5">
          <RiskIcon className={`w-3.5 h-3.5 ${riskColor}`} />
          <span className={`text-[11px] data-value ${riskColor}`}>{riskLabel}</span>
        </div>
      </div>
    </header>
  );
}
