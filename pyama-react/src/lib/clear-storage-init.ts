/**
 * This module clears localStorage immediately when imported.
 * Import this FIRST in main.tsx before any other imports that might create Zustand stores.
 * 
 * This ensures localStorage is cleared before Zustand's persist middleware
 * tries to restore state from localStorage.
 */

// Clear all PyAMA-related localStorage keys immediately
// Only Zustand stores are cleared (all state is managed by Zustand)
const keys = [
  "pyama:processing",
  "pyama:analysis",
  "pyama:visualization",
  "pyama:chat",
  "pyama:theme",
];

keys.forEach((key) => {
  localStorage.removeItem(key);
});
