import { create } from 'zustand';

interface DemoState {
  selectedPreset: string | null;
  setSelectedPreset: (preset: string | null) => void;
}

export const useDemoStore = create<DemoState>((set) => ({
  selectedPreset: null,
  setSelectedPreset: (preset) => set({ selectedPreset: preset }),
}));
