/* System Status — Engine health, WebSocket, data feeds, recording daemon, heartbeat */
import DashboardLayout from '@/components/DashboardLayout';
import PageHeader from '@/components/PageHeader';
import StatusBadge from '@/components/StatusBadge';
import { SYSTEM_STATUS } from '@/lib/mockData';
import { cn } from '@/lib/utils';
import { Activity, Database, Radio, Server, Wifi } from 'lucide-react';

type StatusVariant = 'green' | 'yellow' | 'red' | 'cyan' | 'muted';

function getStatusVariant(status: string): StatusVariant {
  switch (status) {
    case 'ONLINE': case 'CONNECTED': case 'ACTIVE': return 'green';
    case 'CONFIGURED': case 'STANDBY': return 'cyan';
    case 'DEGRADED': case 'RECONNECTING': return 'yellow';
    case 'OFFLINE': case 'DISCONNECTED': case 'ERROR': return 'red';
    default: return 'muted';
  }
}

export default function SystemStatus() {
  const { engine, websocket, dataFeeds, recordingDaemon, telegramBot } = SYSTEM_STATUS;
  const engineStatus: string = engine.status;

  return (
    <DashboardLayout>
      <PageHeader title="System Status" subtitle="Engine health and infrastructure monitoring" />

      {/* Engine status banner */}
      <div className={cn(
        'hud-panel p-5 mb-6 border-l-4',
        engineStatus === 'ONLINE' ? 'border-l-emerald' : 'border-l-amber-warn'
      )}>
        <div className="flex items-center gap-4">
          <Server className={cn('w-10 h-10', engineStatus === 'ONLINE' ? 'text-emerald' : 'text-amber-warn')} />
          <div className="flex-1">
            <div className="flex items-center gap-3">
              <h2 className="text-base font-semibold text-foreground">CoinScopeAI Engine</h2>
              <StatusBadge label={engine.status} variant={getStatusVariant(engine.status)} pulse />
              <span className="text-xs text-muted-foreground">{engine.version}</span>
            </div>
            <p className="text-xs text-muted-foreground mt-1">{engine.note}</p>
          </div>
          <div className="text-right text-xs">
            <div className="text-muted-foreground">Uptime</div>
            <div className="font-mono text-foreground">{engine.uptime}</div>
            <div className="text-muted-foreground mt-1">Last Heartbeat</div>
            <div className="font-mono text-foreground">{engine.lastHeartbeat}</div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        {/* WebSocket status */}
        <div className="hud-panel p-4">
          <h2 className="text-xs font-semibold tracking-[0.12em] uppercase text-muted-foreground flex items-center gap-2 mb-4">
            <Wifi className="w-4 h-4" /> WebSocket Connection
          </h2>
          <div className="space-y-3 text-xs">
            <div className="flex justify-between items-center">
              <span className="text-muted-foreground">Status</span>
              <StatusBadge label={websocket.status} variant={getStatusVariant(websocket.status)} />
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Reconnect Attempts</span>
              <span className="font-mono tabular-nums text-foreground">{websocket.reconnectAttempts}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Last Connected</span>
              <span className="font-mono tabular-nums text-foreground">{websocket.lastConnected}</span>
            </div>
          </div>
        </div>

        {/* Recording daemon */}
        <div className="hud-panel p-4">
          <h2 className="text-xs font-semibold tracking-[0.12em] uppercase text-muted-foreground flex items-center gap-2 mb-4">
            <Database className="w-4 h-4" /> Recording Daemon
          </h2>
          <div className="space-y-3 text-xs">
            <div className="flex justify-between items-center">
              <span className="text-muted-foreground">Status</span>
              <StatusBadge label={recordingDaemon.status} variant={getStatusVariant(recordingDaemon.status)} />
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Records Saved</span>
              <span className="font-mono tabular-nums text-foreground">{recordingDaemon.recordsSaved.toLocaleString()}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Disk Usage</span>
              <span className="font-mono tabular-nums text-foreground">{recordingDaemon.diskUsage}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Data feeds */}
      <div className="hud-panel p-4 mb-4">
        <h2 className="text-xs font-semibold tracking-[0.12em] uppercase text-muted-foreground flex items-center gap-2 mb-4">
          <Radio className="w-4 h-4" /> Data Feeds
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {dataFeeds.map((feed) => (
            <div key={feed.name} className="bg-secondary/50 rounded-md p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium text-foreground">{feed.name}</span>
                <StatusBadge label={feed.status} variant={getStatusVariant(feed.status)} />
              </div>
              <div className="space-y-1 text-[10px]">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Latency</span>
                  <span className="font-mono text-foreground">{feed.latency ?? '—'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Last Message</span>
                  <span className="font-mono text-foreground">{feed.lastMessage}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Telegram bot */}
      <div className="hud-panel p-4">
        <h2 className="text-xs font-semibold tracking-[0.12em] uppercase text-muted-foreground flex items-center gap-2 mb-4">
          <Activity className="w-4 h-4" /> Telegram Bot
        </h2>
        <div className="space-y-3 text-xs">
          <div className="flex justify-between items-center">
            <span className="text-muted-foreground">Status</span>
            <StatusBadge label={telegramBot.status} variant={getStatusVariant(telegramBot.status)} />
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Last Alert Sent</span>
            <span className="font-mono tabular-nums text-foreground">{telegramBot.lastAlert}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Total Alerts Sent</span>
            <span className="font-mono tabular-nums text-foreground">{telegramBot.alertsSent}</span>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
