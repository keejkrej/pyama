import { create } from "zustand";
import { persist } from "zustand/middleware";

interface VisualizationState {
  dataFolder: string;
  fov: number;
  selectedFeature: string;
  currentPage: number;

  setDataFolder: (folder: string) => void;
  setFov: (fov: number) => void;
  setSelectedFeature: (feature: string) => void;
  setCurrentPage: (page: number) => void;
  reset: () => void;
}

export const useVisualizationStore = create<VisualizationState>()(
  persist(
    (set) => ({
      dataFolder: "",
      fov: 0,
      selectedFeature: "",
      currentPage: 1,

      setDataFolder: (folder) => set({ dataFolder: folder }),
      setFov: (fov) => set({ fov }),
      setSelectedFeature: (feature) => set({ selectedFeature: feature }),
      setCurrentPage: (page) => set({ currentPage: page }),
      reset: () =>
        set({
          dataFolder: "",
          fov: 0,
          selectedFeature: "",
          currentPage: 1,
        }),
    }),
    { name: "pyama:visualization" }
  )
);
