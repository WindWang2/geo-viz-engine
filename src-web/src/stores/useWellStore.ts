import { create } from "zustand";

export interface WellMetadata {
  well_id: string;
  well_name: string;
  depth_start: number;
  depth_end: number;
  curve_names: string[];
  longitude?: number | null;
  latitude?: number | null;
}

interface WellState {
  wells: WellMetadata[];
  isLoading: boolean;
  error: string | null;
  setWells: (wells: WellMetadata[]) => void;
  clearWells: () => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useWellStore = create<WellState>((set) => ({
  wells: [],
  isLoading: false,
  error: null,
  setWells: (wells) => set({ wells }),
  clearWells: () => set({ wells: [] }),
  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),
}));
