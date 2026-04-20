import { useAppStore } from '@/lib/store';
import { cn } from '@/lib/utils';
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Bell,
  BookOpen,
  Calculator,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  CreditCard,
  Database,
  Gauge,
  LayoutDashboard,
  LineChart,
  Radio,
  Scan,
  Server,
  Settings,
  Shield,
  TrendingUp,
  Zap,
} from 'lucide-react';
import { useLocation } from 'wouter';

const NAV_SECTIONS = [
  {
    label: 'CORE',
    items: [
      { path: '/', label: 'Overview', icon: LayoutDashboard },
      { path: '/scanner', label: 'Live Scanner', icon: Scan },
      { path: '/positions', label: 'Positions', icon: Activity },
      { path: '/journal', label: 'Trade Journal', icon: BookOpen },
    ],
  },
  {
    label: 'ANALYTICS',
    items: [
      { path: '/performance', label: 'Performance', icon: BarChart3 },
      { path: '/equity', label: 'Equity Curve', icon: LineChart },
      { path: '/risk-gate', label: 'Risk Gate', icon: Shield },
      { path: '/regime', label: 'Regime Detection', icon: Radio },
    ],
  },
  {
    label: 'TOOLS',
    items: [
      { path: '/position-sizer', label: 'Position Sizer', icon: Calculator },
      { path: '/alpha', label: 'Alpha Signals', icon: Zap },
      { path: '/market-data', label: 'Market Data', icon: Database },
      { path: '/backtest', label: 'Backtest Results', icon: TrendingUp },
    ],
  },
  {
    label: 'SYSTEM',
    items: [
      { path: '/settings', label: 'Settings', icon: Settings },
      { path: '/pricing', label: 'Pricing', icon: CreditCard },
      { path: '/system-status', label: 'System Status', icon: Server },
      { path: '/decisions', label: 'Decisions', icon: ClipboardList },
      { path: '/alerts', label: 'Alerts', icon: Bell },
    ],
  },
];

export default function Sidebar() {
  const [location, setLocation] = useLocation();
  const { sidebarCollapsed, toggleSidebar } = useAppStore();

  return (
    <aside
      className={cn(
        'fixed left-0 top-0 h-screen z-40 flex flex-col border-r border-border bg-sidebar transition-all duration-200',
        sidebarCollapsed ? 'w-[64px]' : 'w-[240px]'
      )}
    >
      {/* Logo */}
      <div className="flex items-center h-14 px-4 border-b border-border shrink-0">
        <div className="flex items-center gap-2.5 overflow-hidden">
          <div className="w-7 h-7 rounded-md bg-emerald flex items-center justify-center shrink-0">
            <Gauge className="w-4 h-4 text-white" />
          </div>
          {!sidebarCollapsed && (
            <span className="text-sm font-semibold text-foreground tracking-tight whitespace-nowrap">
              CoinScope<span className="text-emerald">AI</span>
            </span>
          )}
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-3 px-2">
        {NAV_SECTIONS.map((section) => (
          <div key={section.label} className="mb-4">
            {!sidebarCollapsed && (
              <div className="px-2 mb-1.5 text-[10px] font-semibold tracking-[0.15em] text-muted-foreground/60 uppercase">
                {section.label}
              </div>
            )}
            <div className="space-y-0.5">
              {section.items.map((item) => {
                const isActive = location === item.path;
                const Icon = item.icon;
                return (
                  <button
                    key={item.path}
                    onClick={() => setLocation(item.path)}
                    className={cn(
                      'flex items-center gap-2.5 w-full rounded-md text-sm transition-colors duration-150',
                      sidebarCollapsed ? 'justify-center px-2 py-2' : 'px-2.5 py-1.5',
                      isActive
                        ? 'bg-emerald/10 text-emerald'
                        : 'text-muted-foreground hover:text-foreground hover:bg-secondary'
                    )}
                    title={sidebarCollapsed ? item.label : undefined}
                  >
                    <Icon className={cn('shrink-0', sidebarCollapsed ? 'w-5 h-5' : 'w-4 h-4')} />
                    {!sidebarCollapsed && (
                      <span className="truncate">{item.label}</span>
                    )}
                    {isActive && !sidebarCollapsed && (
                      <div className="ml-auto w-1.5 h-1.5 rounded-full bg-emerald animate-pulse-dot" />
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Collapse toggle */}
      <div className="border-t border-border p-2 shrink-0">
        <button
          onClick={toggleSidebar}
          className="flex items-center justify-center w-full py-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
        >
          {sidebarCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>
    </aside>
  );
}
