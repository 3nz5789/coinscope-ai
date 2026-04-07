/**
 * Sidebar Navigation — Command Center HUD
 * Narrow icon-driven sidebar with text labels. Active state uses emerald left border.
 */
import { useLocation, Link } from "wouter";
import {
  LayoutDashboard,
  Radar,
  BarChart3,
  TrendingUp,
  Activity,
  Zap,
  Gauge,
  BookOpen,
  ShieldAlert,
  Database,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { useState } from "react";

const LOGO_URL = "https://d2xsxph8kpxj0f.cloudfront.net/310519663491724579/CV5Ce7m8AaAiL6pVeeTxLH/sidebar-logo-VKpUH5PEaRN6TUKU7PzvXB.webp";

interface NavItem {
  path: string;
  label: string;
  shortLabel: string;
  icon: React.ComponentType<{ className?: string }>;
}

const navItems: NavItem[] = [
  { path: "/", label: "Overview", shortLabel: "Overview", icon: LayoutDashboard },
  { path: "/scanner", label: "Live Scanner", shortLabel: "Scanner", icon: Radar },
  { path: "/positions", label: "Positions", shortLabel: "Positions", icon: BarChart3 },
  { path: "/equity", label: "Equity Curve", shortLabel: "Equity", icon: TrendingUp },
  { path: "/performance", label: "Performance", shortLabel: "Perf", icon: Activity },
  { path: "/alpha", label: "Alpha Signals", shortLabel: "Alpha", icon: Zap },
  { path: "/regime", label: "Regime State", shortLabel: "Regime", icon: Gauge },
  { path: "/journal", label: "Trade Journal", shortLabel: "Journal", icon: BookOpen },
  { path: "/risk", label: "Risk Gate", shortLabel: "Risk", icon: ShieldAlert },
  { path: "/daemon", label: "Recording Daemon", shortLabel: "Daemon", icon: Database },
];

export default function Sidebar() {
  const [location] = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={`fixed left-0 top-0 h-screen z-50 flex flex-col transition-all duration-200 ease-out ${
        collapsed ? "w-[68px]" : "w-[220px]"
      }`}
      style={{ background: "oklch(0.12 0.025 264.05)" }}
    >
      {/* Logo area */}
      <div className="flex items-center gap-3 px-4 h-16 border-b border-border/50 shrink-0">
        <img src={LOGO_URL} alt="CoinScopeAI" className="w-8 h-8 shrink-0" />
        {!collapsed && (
          <div className="overflow-hidden">
            <span className="text-sm font-semibold text-foreground tracking-wide whitespace-nowrap">
              CoinScope<span className="text-emerald">AI</span>
            </span>
          </div>
        )}
      </div>

      {/* Nav items */}
      <nav className="flex-1 py-3 overflow-y-auto">
        <ul className="space-y-0.5 px-2">
          {navItems.map((item) => {
            const isActive = location === item.path;
            const Icon = item.icon;
            return (
              <li key={item.path}>
                <Link
                  href={item.path}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-md text-[13px] font-medium transition-all duration-150 group relative ${
                    isActive
                      ? "bg-emerald/10 text-emerald"
                      : "text-muted-foreground hover:text-foreground hover:bg-white/[0.04]"
                  }`}
                >
                  {isActive && (
                    <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 bg-emerald rounded-r-full" />
                  )}
                  <Icon className={`w-[18px] h-[18px] shrink-0 ${isActive ? "text-emerald" : "text-muted-foreground group-hover:text-foreground"}`} />
                  {!collapsed && (
                    <span className="whitespace-nowrap overflow-hidden">{item.label}</span>
                  )}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex items-center justify-center h-10 border-t border-border/50 text-muted-foreground hover:text-foreground transition-colors shrink-0"
      >
        {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
      </button>
    </aside>
  );
}

export function useSidebarWidth() {
  return 220;
}
