import { create } from 'zustand';

interface MapState {
  selectedWellId: string | null;
  panelOpen: boolean;

  selectWell: (wellId: string) => void;
  closePanel: () => void;
  openPanel: () => void;
  togglePanel: () => void;
}

export const useMapStore = create<MapState>((set) => ({
  selectedWellId: null,
  panelOpen: false,

  selectWell: (wellId) =>
    set({ selectedWellId: wellId, panelOpen: true }),

  closePanel: () =>
    set({ panelOpen: false }),

  openPanel: () =>
    set((state) =>
      state.selectedWellId ? { panelOpen: true } : {}
    ),

  togglePanel: () =>
    set((state) => ({ panelOpen: !state.panelOpen })),
}));
