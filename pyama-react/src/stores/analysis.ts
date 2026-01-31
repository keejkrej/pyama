import { create } from "zustand";
import { persist } from "zustand/middleware";

interface AnalysisState {
  dataFolder: string;
  frameInterval: number;

  setDataFolder: (folder: string) => void;
  setFrameInterval: (interval: number) => void;
  reset: () => void;
}

export const useAnalysisStore = create<AnalysisState>()(
  persist(
    (set) => ({
      dataFolder: "",
      frameInterval: 10,

      setDataFolder: (folder) => set({ dataFolder: folder }),
      setFrameInterval: (interval) => set({ frameInterval: interval }),
      reset: () =>
        set({
          dataFolder: "",
          frameInterval: 10,
        }),
    }),
    { name: "pyama:analysis" }
  )
);
