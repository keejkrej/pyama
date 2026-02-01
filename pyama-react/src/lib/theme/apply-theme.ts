import type { Theme } from "./types";

const COLOR_PROPERTY_PREFIX = "--color-";

/**
 * Apply a theme to the document by setting CSS custom properties.
 * Note: Theme state is now managed by Zustand store, not localStorage.
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
