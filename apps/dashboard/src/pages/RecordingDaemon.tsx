/**
 * Recording Daemon Page — Command Center HUD
 * Events/second, total events, data size, uptime, exchange connections.
 */
import { useApiData } from "@/hooks/useApiData";
import { api, RecordingDaemon as DaemonType } from "@/lib/api";
import { formatLargeNumber, formatTimestamp } from "@/lib/format";
import HudCard from "@/components/HudCard";
import { Database, Wifi, WifiOff, Clock, HardDrive, Activity, Zap } from "lucide-react";

function ConnectionRow({ conn }: { conn: DaemonType["exchangeConnections"][0] }) {
  const statusConfig = {
    connected: { color: "text-emerald", bg: "bg-emerald", label: "CONNECTED", icon: Wifi },
    degraded: { color: "text-warning", bg: "bg-warning", label: "DEGRADED", icon: Wifi },
    disconnected: { color: "text-destructive", bg: "bg-destructive", label: "OFFLINE", icon: WifiOff },
  };
  const config = statusConfig[conn.status];
  const Icon = config.icon;

  return (
    <div className="flex items-center justify-between py-3 border-b border-border/30 last:border-b-0">
      <div className="flex items-center gap-3">
        <span className={`w-2 h-2 rounded-full ${config.bg} ${conn.status === "connected" ? "pulse-live" : ""}`} />
        <span className="text-[13px] font-medium text-foreground">{conn.name}</span>
      </div>
      <div className="flex items-center gap-4">
        <span className="data-value text-[11px] text-muted-foreground">{conn.latency}ms</span>
        <span className={`inline-flex items-center gap-1 text-[10px] font-semibold ${config.color}`}>
          <Icon className="w-3 h-3" />
          {config.label}
        </span>
      </div>
    </div>
  );
}

export default function RecordingDaemon() {
  const { data: daemon, loading } = useApiData(api.getRecordingDaemon, { refreshInterval: 3000 });

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Database className="w-5 h-5 text-emerald" />
        <h1 className="text-lg font-semibold text-foreground">Recording Daemon</h1>
        {daemon && (
          <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-emerald/10 border border-emerald/20">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald pulse-live" />
            <span className="text-[10px] font-medium text-emerald data-value">RECORDING</span>
          </span>
        )}
      </div>

      {/* Key metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="hud-card p-4">
          <div className="flex items-center gap-2 mb-2">
            <Zap className="w-4 h-4 text-emerald" />
            <span className="text-[10px] uppercase tracking-widest text-muted-foreground font-medium">Events/sec</span>
          </div>
          <p className="data-value text-2xl font-bold text-emerald">{daemon?.eventsPerSecond || 0}</p>
        </div>
        <div className="hud-card p-4">
          <div className="flex items-center gap-2 mb-2">
            <Activity className="w-4 h-4 text-foreground" />
            <span className="text-[10px] uppercase tracking-widest text-muted-foreground font-medium">Total Events</span>
          </div>
          <p className="data-value text-2xl font-bold text-foreground">{formatLargeNumber(daemon?.totalEvents || 0)}</p>
        </div>
        <div className="hud-card p-4">
          <div className="flex items-center gap-2 mb-2">
            <HardDrive className="w-4 h-4 text-foreground" />
            <span className="text-[10px] uppercase tracking-widest text-muted-foreground font-medium">Data Size</span>
          </div>
          <p className="data-value text-2xl font-bold text-foreground">{daemon?.dataSize || "—"}</p>
        </div>
        <div className="hud-card p-4">
          <div className="flex items-center gap-2 mb-2">
            <Clock className="w-4 h-4 text-foreground" />
            <span className="text-[10px] uppercase tracking-widest text-muted-foreground font-medium">Uptime</span>
          </div>
          <p className="data-value text-2xl font-bold text-foreground">{daemon?.uptime || "—"}</p>
        </div>
      </div>

      {/* Exchange connections */}
      <HudCard
        title="Exchange Connections"
        headerRight={
          daemon && (
            <span className="text-[10px] text-muted-foreground data-value">
              Heartbeat: {formatTimestamp(daemon.lastHeartbeat)}
            </span>
          )
        }
      >
        <div>
          {daemon?.exchangeConnections.map(conn => (
            <ConnectionRow key={conn.name} conn={conn} />
          ))}
        </div>
      </HudCard>

      {/* System info */}
      <HudCard title="System Information">
        <div className="grid grid-cols-2 gap-4">
          {[
            { label: "Recording Mode", value: "Full Tick" },
            { label: "Compression", value: "LZ4 Streaming" },
            { label: "Buffer Size", value: "512 MB" },
            { label: "Write Strategy", value: "Async Batch" },
            { label: "Retention Policy", value: "90 Days" },
            { label: "Backup Status", value: "Synced", color: "text-emerald" },
          ].map((item, i) => (
            <div key={i} className="flex justify-between items-center py-2 border-b border-border/30">
              <span className="text-[11px] text-muted-foreground uppercase tracking-wider">{item.label}</span>
              <span className={`data-value text-[12px] font-medium ${(item as any).color || "text-foreground"}`}>{item.value}</span>
            </div>
          ))}
        </div>
      </HudCard>
    </div>
  );
}
