import { useState, useEffect, useCallback, useMemo } from "react";
import type { Theme, ThemePreference, ThemeState } from "./types";
import {
  applyTheme,
  getSystemPreference,
  onSystemPreferenceChange,
} from "./apply-theme";
import { getTheme, getAllThemes, darkTheme, lightTheme } from "./themes";
import { useThemeStore } from "../../stores/theme";

interface UseThemeOptions {
  /** Default preference if none stored */
  defaultPreference?: ThemePreference;
  /** Default dark theme ID */
  defaultDarkTheme?: string;
  /** Default light theme ID */
  defaultLightTheme?: string;
}

interface UseThemeReturn extends ThemeState {
  /** Set theme preference ('light', 'dark', or 'system') */
  setPreference: (preference: ThemePreference) => void;
  /** Set a specific theme by ID */
  setTheme: (themeId: string) => void;
  /** Toggle between light and dark */
  toggle: () => void;
  /** All available themes */
  themes: Theme[];
  /** Check if a theme is the current one */
  isActive: (themeId: string) => boolean;
}

const DEFAULT_OPTIONS: Required<UseThemeOptions> = {
  defaultPreference: "dark",
  defaultDarkTheme: "dark",
  defaultLightTheme: "light",
};

export function useTheme(options: UseThemeOptions = {}): UseThemeReturn {
  const opts = { ...DEFAULT_OPTIONS, ...options };

  // Get theme state from Zustand store
  const { preference, themeId, setPreference: setStorePreference, setThemeId: setStoreThemeId } = useThemeStore();

  const [systemPreference, setSystemPreference] = useState<"dark" | "light">(
    getSystemPreference,
  );

  // Resolve current theme ID from store or preference
  const currentThemeId = useMemo(() => {
    if (themeId && getTheme(themeId)) {
      return themeId;
    }
    return preference === "light"
      ? opts.defaultLightTheme
      : opts.defaultDarkTheme;
  }, [themeId, preference, opts.defaultLightTheme, opts.defaultDarkTheme]);

  // Resolve the actual theme type
  const resolvedType = useMemo((): "dark" | "light" => {
    if (preference === "system") {
      return systemPreference;
    }
    return preference;
  }, [preference, systemPreference]);

  // Get the current theme object
  const theme = useMemo((): Theme => {
    const current = getTheme(currentThemeId);
    if (current && current.type === resolvedType) return current;

    // Fallback if theme type doesn't match preference
    if (resolvedType === "light") {
      return getTheme(opts.defaultLightTheme) ?? lightTheme;
    }
    return getTheme(opts.defaultDarkTheme) ?? darkTheme;
  }, [
    currentThemeId,
    resolvedType,
    opts.defaultDarkTheme,
    opts.defaultLightTheme,
  ]);

  // Apply theme on change
  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  // Listen for system preference changes
  useEffect(() => {
    return onSystemPreferenceChange(setSystemPreference);
  }, []);

  // When preference changes to system, auto-select matching theme
  useEffect(() => {
    if (preference === "system") {
      const matchingTheme =
        resolvedType === "light"
          ? opts.defaultLightTheme
          : opts.defaultDarkTheme;
      setStoreThemeId(matchingTheme);
    }
  }, [preference, resolvedType, opts.defaultDarkTheme, opts.defaultLightTheme, setStoreThemeId]);

  const setPreference = useCallback(
    (newPreference: ThemePreference) => {
      setStorePreference(newPreference);

      if (newPreference !== "system") {
        // Auto-select default theme for the preference
        const defaultThemeId =
          newPreference === "light"
            ? opts.defaultLightTheme
            : opts.defaultDarkTheme;
        setStoreThemeId(defaultThemeId);
      }
    },
    [opts.defaultDarkTheme, opts.defaultLightTheme, setStorePreference, setStoreThemeId],
  );

  const setTheme = useCallback(
    (themeId: string) => {
      const newTheme = getTheme(themeId);
      if (newTheme) {
        setStoreThemeId(themeId);
        // Update preference to match theme type (exit system mode)
        if (preference === "system") {
          setStorePreference(newTheme.type);
        }
      }
    },
    [preference, setStorePreference, setStoreThemeId],
  );

  const toggle = useCallback(() => {
    const newPreference = resolvedType === "dark" ? "light" : "dark";
    setPreference(newPreference);
  }, [resolvedType, setPreference]);

  const themes = useMemo(() => getAllThemes(), []);

  const isActive = useCallback(
    (themeId: string) => theme.id === themeId,
    [theme.id],
  );

  return {
    theme,
    preference,
    resolvedType,
    setPreference,
    setTheme,
    toggle,
    themes,
    isActive,
  };
}
