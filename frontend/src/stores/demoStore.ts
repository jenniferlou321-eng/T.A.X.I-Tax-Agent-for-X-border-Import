import { create } from 'zustand';

interface DemoState {
  selectedPreset: string | null;
  erpConnectionOn: boolean;
  setSelectedPreset: (preset: string | null) => void;
  setErpConnection: (on: boolean) => void;
  clearAll: () => void;
}

export const useDemoStore = create<DemoState>((set) => ({
  selectedPreset: null,
  erpConnectionOn: false,
  setSelectedPreset: (preset) => set({ selectedPreset: preset }),
  setErpConnection: (on) => set({ erpConnectionOn: on }),
  clearAll: () => {
    set({ selectedPreset: null, erpConnectionOn: false });
    // 同步清 localStorage
    if (typeof window !== 'undefined') {
      try {
        Object.keys(localStorage)
          .filter((k) => k.startsWith('taxi:') || k.startsWith('tax_agent:'))
          .forEach((k) => localStorage.removeItem(k));
      } catch (e) {
        // localStorage 不可用，忽略
      }
    }
  },
}));
