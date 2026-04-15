import { create } from 'zustand';

interface MapStore {
  // Selected well for detail view
  selectedWellId: string | null;
  setSelectedWellId: (id: string | null) => void;

  // Detail panel visibility
  isPanelOpen: boolean;
  openPanel: () => void;
  closePanel: () => void;
  togglePanel: () => void;
}

export const useMapStore = create<MapStore>((set) => ({
  selectedWellId: null,
  isPanelOpen: false,

  setSelectedWellId: (id) =>
    set({ selectedWellId: id, isPanelOpen: id !== null }),

  openPanel: () => set({ isPanelOpen: true }),
  closePanel: () => set({ isPanelOpen: false, selectedWellId: null }),
  togglePanel: () =>
    set((state) => ({ isPanelOpen: !state.isPanelOpen })),
}));