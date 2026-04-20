import { create } from 'zustand';

interface AppState {
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  billingCycle: 'monthly' | 'annual';
  setBillingCycle: (cycle: 'monthly' | 'annual') => void;
}

export const useAppStore = create<AppState>((set) => ({
  sidebarCollapsed: false,
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
  billingCycle: 'monthly',
  setBillingCycle: (cycle) => set({ billingCycle: cycle }),
}));
