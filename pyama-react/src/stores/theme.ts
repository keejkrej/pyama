import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { ThemePreference } from "../lib/theme/types";

interface ThemeState {
  preference: ThemePreference;
  themeId: string | null;

  setPreference: (preference: ThemePreference) => void;
  setThemeId: (themeId: string | null) => void;
  reset: () => void;
}

const DEFAULT_PREFERENCE: ThemePreference = "dark";
const DEFAULT_THEME_ID: string | null = null; // Will be resolved from preference

export const useThemeStore = create<ThemeState>()(
  persist(
    (set) => ({
      preference: DEFAULT_PREFERENCE,
      themeId: DEFAULT_THEME_ID,

      setPreference: (preference) => set({ preference }),
      setThemeId: (themeId) => set({ themeId }),
      reset: () =>
        set({
          preference: DEFAULT_PREFERENCE,
          themeId: DEFAULT_THEME_ID,
        }),
    }),
    {
      name: "pyama:theme",
    }
  )
);
