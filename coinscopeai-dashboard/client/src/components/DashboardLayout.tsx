import { useAppStore } from '@/lib/store';
import { cn } from '@/lib/utils';
import Sidebar from './Sidebar';
import TopBar from './TopBar';

interface DashboardLayoutProps {
  children: React.ReactNode;
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  const { sidebarCollapsed } = useAppStore();

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <div
        className={cn(
          'transition-all duration-200',
          sidebarCollapsed ? 'ml-[64px]' : 'ml-[240px]'
        )}
      >
        <TopBar />
        <main className="p-4 lg:p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
