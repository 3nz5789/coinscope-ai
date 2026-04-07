/**
 * DashboardLayout — Command Center HUD
 * Wraps all pages with sidebar + status bar.
 */
import { ReactNode } from "react";
import Sidebar from "./Sidebar";
import StatusBar from "./StatusBar";

interface DashboardLayoutProps {
  children: ReactNode;
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex flex-col flex-1 ml-[220px] transition-all duration-200">
        <StatusBar />
        <main className="flex-1 overflow-y-auto p-5 grid-bg">
          <div className="scanline-overlay fixed inset-0 pointer-events-none z-[1]" />
          <div className="relative z-[2]">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
