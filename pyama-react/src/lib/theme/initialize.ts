import type { Theme, ThemePreference } from "./types";
import {
  applyTheme,
  getSystemPreference,
} from "./apply-theme";
import { getTheme, darkTheme, lightTheme } from "./themes";
import { useThemeStore } from "../../stores/theme";

interface InitOptions {
  defaultPreference?: ThemePreference;
  defaultDarkTheme?: string;
  defaultLightTheme?: string;
}

/**
 * Initialize theme on app startup (call before render).
 * This prevents flash of wrong theme.
 * 
 * Note: Since we clear localStorage on startup, this uses defaults.
 * The Zustand store will be initialized with defaults as well.
 */
export function initializeTheme(options: InitOptions = {}): Theme {
  const {
    defaultPreference = "dark",
    defaultDarkTheme = "dark",
    defaultLightTheme = "light",
  } = options;

  // Get preference from Zustand store (will be default since localStorage is cleared)
  const store = useThemeStore.getState();
  const preference = store.preference || defaultPreference;

  // Resolve to dark or light
  let resolvedType: "dark" | "light";
  if (preference === "system") {
    resolvedType = getSystemPreference();
  } else {
    resolvedType = preference;
  }

  // Get theme from store or use default
  let theme: Theme | undefined;

  if (store.themeId) {
    theme = getTheme(store.themeId);
    // Validate theme type matches resolved preference
    if (theme && theme.type !== resolvedType) {
      theme = undefined; // Reset to default
    }
  }

  if (!theme) {
    theme =
      resolvedType === "light"
        ? (getTheme(defaultLightTheme) ?? lightTheme)
        : (getTheme(defaultDarkTheme) ?? darkTheme);
  }

  applyTheme(theme);
  return theme;
}
