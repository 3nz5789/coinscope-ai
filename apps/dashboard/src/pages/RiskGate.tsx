/**
 * Risk Gate Page — Command Center HUD
 * Risk status with red/yellow/green indicators.
 */
import { useApiData } from "@/hooks/useApiData";
import { api, RiskGate as RiskGateType } from "@/lib/api";
import HudCard from "@/components/HudCard";
import { ShieldAlert, ShieldCheck, ShieldX, AlertTriangle, Power } from "lucide-react";

function RiskGauge({ label, value, limit, unit = "%" }: { label: string; value: number; limit: number; unit?: string }) {
  const ratio = value / limit;
  const color = ratio >= 0.8 ? "text-destructive" : ratio >= 0.5 ? "text-warning" : "text-emerald";
  const bgColor = ratio >= 0.8 ? "bg-destructive" : ratio >= 0.5 ? "bg-warning" : "bg-emerald";
  const statusLabel = ratio >= 0.8 ? "CRITICAL" : ratio >= 0.5 ? "WARNING" : "NOMINAL";

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-[11px] text-muted-foreground uppercase tracking-wider font-medium">{label}</span>
        <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${
          ratio >= 0.8 ? "bg-destructive/10 text-destructive" : ratio >= 0.5 ? "bg-warning/10 text-warning" : "bg-emerald/10 text-emerald"
        }`}>
          {statusLabel}
        </span>
      </div>
      <div className="flex items-end gap-2">
        <span className={`data-value text-2xl font-bold ${color}`}>{value.toFixed(2)}{unit}</span>
        <span className="text-[11px] text-muted-foreground mb-1">/ {limit}{unit}</span>
      </div>
      <div className="w-full h-2 rounded-full bg-muted overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${bgColor}`}
          style={{ width: `${Math.min(100, ratio * 100)}%` }}
        />
      </div>
    </div>
  );
}

function KillSwitchIndicator({ active }: { active: boolean }) {
  return (
    <div className={`hud-card p-4 border-l-[3px] ${active ? "border-l-destructive" : "border-l-emerald"}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Power className={`w-6 h-6 ${active ? "text-destructive" : "text-emerald"}`} />
          <div>
            <h3 className="text-[13px] font-semibold text-foreground">Kill Switch</h3>
            <p className="text-[11px] text-muted-foreground">Emergency position liquidation</p>
          </div>
        </div>
        <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[12px] font-bold data-value ${
          active ? "bg-destructive/10 text-destructive border border-destructive/20" : "bg-emerald/10 text-emerald border border-emerald/20"
        }`}>
          <span className={`w-2 h-2 rounded-full ${active ? "bg-destructive pulse-live" : "bg-emerald"}`} />
          {active ? "ACTIVATED" : "DISARMED"}
        </span>
      </div>
    </div>
  );
}

export default function RiskGate() {
  const { data: risk, loading } = useApiData(api.getRiskGate, { refreshInterval: 5000 });

  const StatusIcon = risk?.status === "critical" ? ShieldX : risk?.status === "warning" ? AlertTriangle : ShieldCheck;
  const statusColor = risk?.status === "critical" ? "text-destructive" : risk?.status === "warning" ? "text-warning" : "text-emerald";
  const statusLabel = risk?.status?.toUpperCase() || "LOADING";

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ShieldAlert className="w-5 h-5 text-emerald" />
          <h1 className="text-lg font-semibold text-foreground">Risk Gate</h1>
        </div>
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-md border ${
          risk?.status === "critical" ? "bg-destructive/10 border-destructive/20" : risk?.status === "warning" ? "bg-warning/10 border-warning/20" : "bg-emerald/10 border-emerald/20"
        }`}>
          <StatusIcon className={`w-4 h-4 ${statusColor}`} />
          <span className={`text-[12px] font-bold data-value ${statusColor}`}>{statusLabel}</span>
        </div>
      </div>

      {/* Kill switch */}
      <KillSwitchIndicator active={risk?.killSwitch || false} />

      {/* Risk gauges */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <HudCard title="Daily Loss">
          {risk && <RiskGauge label="Daily P&L Loss" value={risk.dailyLossPct} limit={risk.dailyLossLimit} />}
        </HudCard>
        <HudCard title="Drawdown">
          {risk && <RiskGauge label="Current Drawdown" value={risk.drawdownPct} limit={risk.drawdownLimit} />}
        </HudCard>
        <HudCard title="Position Heat">
          {risk && <RiskGauge label="Portfolio Heat" value={risk.positionHeat} limit={risk.positionHeatLimit} />}
        </HudCard>
        <HudCard title="Leverage">
          {risk && <RiskGauge label="Current Leverage" value={risk.currentLeverage} limit={risk.maxLeverage} unit="x" />}
        </HudCard>
      </div>

      {/* Additional risk metrics */}
      <HudCard title="Risk Metrics">
        <div className="grid grid-cols-2 gap-4">
          <div className="flex justify-between items-center py-2 border-b border-border/30">
            <span className="text-[11px] text-muted-foreground uppercase tracking-wider">Correlation Risk</span>
            <span className={`data-value text-[13px] font-semibold ${(risk?.correlationRisk || 0) > 50 ? "text-warning" : "text-emerald"}`}>
              {risk?.correlationRisk || 0}%
            </span>
          </div>
          <div className="flex justify-between items-center py-2 border-b border-border/30">
            <span className="text-[11px] text-muted-foreground uppercase tracking-wider">Max Leverage</span>
            <span className="data-value text-[13px] font-semibold text-foreground">{risk?.maxLeverage || 0}x</span>
          </div>
        </div>
      </HudCard>
    </div>
  );
}
