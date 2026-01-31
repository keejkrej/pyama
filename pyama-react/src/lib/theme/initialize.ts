import type { Theme, ThemePreference } from "./types";
import {
  applyTheme,
  getStoredPreference,
  getStoredThemeId,
  getSystemPreference,
} from "./apply-theme";
import { getTheme, darkTheme, lightTheme } from "./themes";

interface InitOptions {
  defaultPreference?: ThemePreference;
  defaultDarkTheme?: string;
  defaultLightTheme?: string;
}

/**
 * Initialize theme on app startup (call before render).
 * This prevents flash of wrong theme.
 */
export function initializeTheme(options: InitOptions = {}): Theme {
  const {
    defaultPreference = "dark",
    defaultDarkTheme = "dark",
    defaultLightTheme = "light",
  } = options;

  // Determine preference
  const storedPreference = getStoredPreference() as ThemePreference | null;
  const preference = storedPreference ?? defaultPreference;

  // Resolve to dark or light
  let resolvedType: "dark" | "light";
  if (preference === "system") {
    resolvedType = getSystemPreference();
  } else {
    resolvedType = preference;
  }

  // Get theme
  const storedThemeId = getStoredThemeId();
  let theme: Theme | undefined;

  if (storedThemeId) {
    theme = getTheme(storedThemeId);
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
