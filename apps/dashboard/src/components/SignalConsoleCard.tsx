/**
 * SignalConsoleCard — primary one-panel signal view for the operator.
 *
 * Surfaces every datum the operator needs to decide on a single candidate
 * without navigating between Live Scanner, Risk Gate, Position Sizer, and
 * Regime State views:
 *
 *   1. Confluence (the score)
 *   2. Regime (HMM label + confidence)
 *   3. Kelly size (per-trade USD + % of equity, with regime scaling visible)
 *   4. Gate pass/fail (with rejection reason if failed)
 *   5. Breaker state (closed / daily_loss / drawdown / consecutive_loss / kill_switch)
 *   6. Operator action guidance (HALT / SKIP / WATCH / CONSIDER / EXECUTE)
 *
 * The guidance is derived deterministically from the other five — there is
 * no separate "advice" feed. If the operator and the panel disagree, the
 * panel is wrong (or the engine state is wrong), not the operator.
 *
 * The panel never makes the decision for the operator. It states what the
 * inputs are and what the next move should be. The operator executes.
 */
import type { Signal } from "@/lib/api";
import {
  ArrowUpRight,
  ArrowDownRight,
  ShieldCheck,
  ShieldX,
  Power,
  Activity,
  Gauge,
  AlertTriangle,
  PauseCircle,
  PlayCircle,
  Eye,
  Radar,
  RefreshCw,
  WifiOff,
} from "lucide-react";

// ──────────────────────────────────────────────────────────────────────────
// Types — local for now. Once these land on the canonical Signal type in
// @/lib/api they can move out of this file and the props can flatten.
// ──────────────────────────────────────────────────────────────────────────

export interface KellyResult {
  usd: number;
  pctOfEquity: number;
  regimeMultiplier: number; // 1.0 (bull) / 0.5 (chop) / 0.3 (bear, volatile, quiet)
  hardCappedAt2pct: boolean;
}

export interface GateCheck {
  name: string;
  passed: boolean;
}

export interface GateDecision {
  pass: boolean;
  reason?: string; // present iff pass === false
  checks?: GateCheck[];
}

export type BreakerState =
  | "closed"
  | "daily_loss"
  | "drawdown"
  | "consecutive_loss"
  | "kill_switch";

export interface BreakerInfo {
  state: BreakerState;
  dailyLossPct: number;
  dailyLossLimit: number;
  drawdownPct: number;
  drawdownLimit: number;
  heatPct: number;
  heatLimit: number;
}

export type ActionLevel = "halt" | "skip" | "watch" | "consider" | "execute";

export interface ActionGuidance {
  level: ActionLevel;
  text: string;
}

// ──────────────────────────────────────────────────────────────────────────
// Action-guidance derivation
//
// Pure function of (signal, gate, breaker). Order matters — a tripped
// breaker dominates a passing gate, a failing gate dominates a strong
// score. The operator never has to compose these in their head.
// ──────────────────────────────────────────────────────────────────────────

export function deriveActionGuidance(
  signal: Signal,
  gate: GateDecision | undefined,
  breaker: BreakerInfo | undefined,
): ActionGuidance {
  // 1) Kill switch and any non-closed breaker dominate everything else.
  if (breaker && breaker.state === "kill_switch") {
    return {
      level: "halt",
      text:
        "Kill switch engaged. Do not execute. Disengage requires a written reason in the journal.",
    };
  }
  if (breaker && breaker.state !== "closed") {
    return {
      level: "halt",
      text: `Circuit breaker '${breaker.state.replace(
        "_",
        " ",
      )}' tripped — no new entries until the reset window elapses.`,
    };
  }

  // 2) Risk-gate rejection.
  if (gate && !gate.pass) {
    return {
      level: "skip",
      text: `Gate rejected${
        gate.reason ? `: ${gate.reason}` : ""
      }. No action — wait for the next candidate.`,
    };
  }

  // 3) Confluence-driven branches.
  if (signal.confidence < 60) {
    return {
      level: "watch",
      text: "Below confluence floor — observe only. Do not enter on this signal.",
    };
  }
  if (signal.confidence < 80) {
    return {
      level: "consider",
      text:
        "Mid-confluence. Verify regime alignment and funding direction before executing.",
    };
  }

  // 4) Strong, gate-passing, breakers closed.
  return {
    level: "execute",
    text:
      "Execute as a bracket order. Size is the Kelly value above; stop and take-profit are submitted alongside. The journal will record automatically.",
  };
}

// ──────────────────────────────────────────────────────────────────────────
// Visual helpers
// ──────────────────────────────────────────────────────────────────────────

const ACTION_STYLE: Record<
  ActionLevel,
  { border: string; icon: typeof PlayCircle; chip: string; label: string }
> = {
  halt: {
    border: "border-l-destructive",
    icon: Power,
    chip: "bg-destructive/10 text-destructive border-destructive/20",
    label: "HALT",
  },
  skip: {
    border: "border-l-warning",
    icon: PauseCircle,
    chip: "bg-warning/10 text-warning border-warning/20",
    label: "SKIP",
  },
  watch: {
    border: "border-l-muted-foreground",
    icon: Eye,
    chip: "bg-muted/40 text-muted-foreground border-border",
    label: "WATCH",
  },
  consider: {
    border: "border-l-chart-3",
    icon: AlertTriangle,
    chip: "bg-chart-3/10 text-chart-3 border-chart-3/20",
    label: "CONSIDER",
  },
  execute: {
    border: "border-l-emerald",
    icon: PlayCircle,
    chip: "bg-emerald/10 text-emerald border-emerald/20",
    label: "EXECUTE",
  },
};

function ConfluenceBar({ value }: { value: number }) {
  const color =
    value >= 80
      ? "bg-emerald"
      : value >= 60
      ? "bg-warning"
      : "bg-muted-foreground";
  return (
    <div className="w-full h-1.5 rounded-full bg-muted overflow-hidden">
      <div
        className={`h-full rounded-full ${color} transition-all duration-500`}
        style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
      />
    </div>
  );
}

function Datum({
  label,
  value,
  sub,
  accent = "default",
}: {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  accent?: "default" | "emerald" | "destructive" | "warning" | "muted";
}) {
  const valueColor = {
    default: "text-foreground",
    emerald: "text-emerald",
    destructive: "text-destructive",
    warning: "text-warning",
    muted: "text-muted-foreground",
  }[accent];
  return (
    <div className="space-y-1">
      <div className="text-[10px] uppercase tracking-widest text-muted-foreground font-medium">
        {label}
      </div>
      <div className={`data-value text-[15px] font-semibold ${valueColor}`}>
        {value}
      </div>
      {sub && <div className="text-[11px] text-muted-foreground">{sub}</div>}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Component
// ──────────────────────────────────────────────────────────────────────────

export interface SignalConsoleCardProps {
  signal: Signal;
  gate?: GateDecision;
  breaker?: BreakerInfo;
  kelly?: KellyResult;
}

export default function SignalConsoleCard({
  signal,
  gate,
  breaker,
  kelly,
}: SignalConsoleCardProps) {
  const guidance = deriveActionGuidance(signal, gate, breaker);
  const style = ACTION_STYLE[guidance.level];
  const ActionIcon = style.icon;
  const isLong = signal.direction === "LONG";

  // Gate visual
  const gateAccent: "emerald" | "destructive" | "muted" = !gate
    ? "muted"
    : gate.pass
    ? "emerald"
    : "destructive";
  const GateIcon = !gate ? AlertTriangle : gate.pass ? ShieldCheck : ShieldX;

  // Breaker visual
  const breakerAccent: "emerald" | "warning" | "destructive" | "muted" = !breaker
    ? "muted"
    : breaker.state === "closed"
    ? "emerald"
    : breaker.state === "kill_switch"
    ? "destructive"
    : "warning";

  return (
    <div className={`hud-card border-l-[3px] ${style.border} p-4 space-y-4`}>
      {/* Header — symbol, direction, action-level chip */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="data-value text-lg font-semibold text-foreground">
            {signal.symbol}
          </span>
          <span
            className={`inline-flex items-center gap-1 text-[12px] font-semibold data-value ${
              isLong ? "text-emerald" : "text-destructive"
            }`}
          >
            {isLong ? (
              <ArrowUpRight className="w-3.5 h-3.5" />
            ) : (
              <ArrowDownRight className="w-3.5 h-3.5" />
            )}
            {signal.direction}
          </span>
          <span className="text-[11px] text-muted-foreground uppercase tracking-wider">
            {signal.type?.replace(/_/g, " ")}
          </span>
        </div>
        <span
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-bold data-value border ${style.chip}`}
        >
          <ActionIcon className="w-3.5 h-3.5" />
          {style.label}
        </span>
      </div>

      {/* Six-cell grid: confluence, regime, kelly, gate, breaker, action */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-x-4 gap-y-3">
        <Datum
          label="Confluence"
          value={`${signal.confidence}/100`}
          sub={<ConfluenceBar value={signal.confidence} />}
        />

        <Datum
          label="Regime"
          value={
            <span className="capitalize">
              {signal.regime?.replace(/_/g, " ") || "—"}
            </span>
          }
          sub={
            typeof signal.strength === "number" ? (
              <>HMM confidence {(signal.strength * 100).toFixed(0)}%</>
            ) : (
              "no HMM read"
            )
          }
        />

        <Datum
          label="Kelly Size"
          value={kelly ? `$${kelly.usd.toLocaleString()}` : "—"}
          sub={
            kelly
              ? `${kelly.pctOfEquity.toFixed(2)}% of equity · regime ×${kelly.regimeMultiplier}${
                  kelly.hardCappedAt2pct ? " · capped at 2%" : ""
                }`
              : "no sizing computed yet"
          }
        />

        <Datum
          label="Gate"
          value={
            <span className="inline-flex items-center gap-1.5">
              <GateIcon className="w-3.5 h-3.5" />
              {gate ? (gate.pass ? "PASS" : "FAIL") : "—"}
            </span>
          }
          sub={gate?.reason || (gate?.pass ? "all checks passed" : "no gate read")}
          accent={gateAccent}
        />

        <Datum
          label="Breaker"
          value={breaker ? breaker.state.replace(/_/g, " ").toUpperCase() : "—"}
          sub={
            breaker
              ? `daily ${breaker.dailyLossPct.toFixed(1)}%/${breaker.dailyLossLimit}% · DD ${breaker.drawdownPct.toFixed(1)}%/${breaker.drawdownLimit}% · heat ${breaker.heatPct}%/${breaker.heatLimit}%`
              : "no breaker read"
          }
          accent={breakerAccent}
        />

        <Datum
          label="Action"
          value={style.label}
          sub={guidance.text}
          accent={
            guidance.level === "execute"
              ? "emerald"
              : guidance.level === "halt"
              ? "destructive"
              : guidance.level === "skip" || guidance.level === "consider"
              ? "warning"
              : "muted"
          }
        />
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// State variants — Loading / Empty / Error
//
// The primary-signal slot in LiveScanner must always render *something*.
// A blank slot leaves the operator unable to distinguish "engine quiet"
// from "engine broken" from "first paint" — which is exactly the trust
// gap a decision-support console must not have.
//
// All three variants share the SignalConsoleCard shell (hud-card,
// border-l-[3px], p-4) so the page layout does not reflow between states.
// ──────────────────────────────────────────────────────────────────────────

function ShellHeader({
  title,
  subtitle,
  icon: Icon,
  accent,
  pulse = false,
}: {
  title: string;
  subtitle?: string;
  icon: typeof Radar;
  accent: "muted" | "destructive";
  pulse?: boolean;
}) {
  const iconColor =
    accent === "destructive" ? "text-destructive" : "text-muted-foreground";
  return (
    <div className="flex items-center gap-3">
      <Icon
        className={`w-4 h-4 ${iconColor} ${pulse ? "pulse-live" : ""}`}
      />
      <div className="flex flex-col">
        <span className="data-value text-[13px] font-semibold text-foreground">
          {title}
        </span>
        {subtitle && (
          <span className="text-[11px] text-muted-foreground">{subtitle}</span>
        )}
      </div>
    </div>
  );
}

/**
 * Loading skeleton — first paint while the signals endpoint is in flight.
 * Mirrors the six-cell grid shape so the page does not jump when the real
 * card renders.
 */
export function SignalConsoleCardSkeleton() {
  return (
    <div
      className="hud-card border-l-[3px] border-l-muted-foreground/30 p-4 space-y-4"
      aria-busy="true"
      aria-label="Loading signal console"
    >
      <ShellHeader
        title="Loading signal feed…"
        subtitle="Awaiting first scan result"
        icon={Activity}
        accent="muted"
      />
      <div className="grid grid-cols-2 md:grid-cols-3 gap-x-4 gap-y-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="space-y-1.5 animate-pulse">
            <div className="h-2 w-16 rounded bg-muted/60" />
            <div className="h-4 w-24 rounded bg-muted/80" />
            <div className="h-2 w-32 rounded bg-muted/50" />
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Empty state — signals endpoint returned an empty list. The engine is
 * online and scanning; no candidate currently meets the active filters.
 * The visible Radar pulse tells the operator this is live, not stale.
 */
export function SignalConsoleCardEmpty() {
  return (
    <div
      className="hud-card border-l-[3px] border-l-muted-foreground/50 p-4 space-y-3"
      aria-live="polite"
    >
      <ShellHeader
        title="No active signals"
        subtitle="Engine is online and scanning — no candidate currently meets the active filters."
        icon={Radar}
        accent="muted"
        pulse
      />
      <div className="text-[11px] text-muted-foreground leading-relaxed">
        The console panel will populate as soon as the engine flags a
        candidate. Until then, no operator action is required.
      </div>
    </div>
  );
}

/**
 * Error state — the signals endpoint failed before returning any data.
 * Distinct from an empty list: this means the *feed* is broken, not the
 * market. The operator must intervene (likely a backend/exchange issue).
 */
export function SignalConsoleCardError({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div
      className="hud-card border-l-[3px] border-l-destructive p-4 space-y-3"
      role="alert"
    >
      <div className="flex items-start justify-between gap-3">
        <ShellHeader
          title="Signal feed unavailable"
          subtitle="The engine is not returning signals. Check the backend, exchange connectivity, and risk-gate status before trading."
          icon={WifiOff}
          accent="destructive"
        />
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-semibold data-value border border-destructive/30 bg-destructive/10 text-destructive hover:bg-destructive/15 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Retry
          </button>
        )}
      </div>
      <div className="text-[11px] font-mono text-destructive/80 bg-destructive/5 border border-destructive/20 rounded px-2 py-1.5 break-all">
        {message}
      </div>
    </div>
  );
}
