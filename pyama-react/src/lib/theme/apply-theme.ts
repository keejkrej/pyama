import type { Theme } from "./types";

const COLOR_PROPERTY_PREFIX = "--color-";
const STORAGE_KEY = "pyama-theme";
const STORAGE_PREFERENCE_KEY = "pyama-theme-preference";

/**
 * Apply a theme to the document by setting CSS custom properties.
 */
export function applyTheme(theme: Theme): void {
  const root = document.documentElement;

  // Set color-scheme for native element styling (scrollbars, etc.)
  root.style.setProperty("color-scheme", theme.type);

  // Apply all color variables
  for (const [key, value] of Object.entries(theme.colors)) {
    if (value !== undefined) {
      root.style.setProperty(`${COLOR_PROPERTY_PREFIX}${key}`, value);
    }
  }

  // Apply non-color variables
  if (theme.variables) {
    for (const [key, value] of Object.entries(theme.variables)) {
      if (value !== undefined) {
        root.style.setProperty(`--${key}`, value);
      }
    }
  }

  // Update class for Tailwind dark mode selector
  if (theme.type === "dark") {
    root.classList.add("dark");
  } else {
    root.classList.remove("dark");
  }

  // Store the applied theme ID
  try {
    localStorage.setItem(STORAGE_KEY, theme.id);
  } catch {
    // localStorage might be unavailable
  }
}

/**
 * Get stored theme preference.
 */
export function getStoredPreference(): string | null {
  try {
    return localStorage.getItem(STORAGE_PREFERENCE_KEY);
  } catch {
    return null;
  }
}

/**
 * Store theme preference.
 */
export function storePreference(preference: string): void {
  try {
    localStorage.setItem(STORAGE_PREFERENCE_KEY, preference);
  } catch {
    // localStorage might be unavailable
  }
}

/**
 * Get stored theme ID.
 */
export function getStoredThemeId(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

/**
 * Detect system color scheme preference.
 */
export function getSystemPreference(): "dark" | "light" {
  if (typeof window === "undefined") return "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

/**
 * Subscribe to system color scheme changes.
 */
export function onSystemPreferenceChange(
  callback: (preference: "dark" | "light") => void,
): () => void {
  if (typeof window === "undefined") return () => {};

  const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
  const handler = (e: MediaQueryListEvent) => {
    callback(e.matches ? "dark" : "light");
  };

  mediaQuery.addEventListener("change", handler);
  return () => mediaQuery.removeEventListener("change", handler);
}
