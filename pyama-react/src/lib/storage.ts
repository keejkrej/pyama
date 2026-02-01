/**
 * Storage utilities for managing persisted state.
 */

// Import stores for reset functionality
// These imports are safe because stores don't import from this module
import { useProcessingStore } from "../stores/processing";
import { useVisualizationStore } from "../stores/visualization";
import { useAnalysisStore } from "../stores/analysis";
import { useChatStore } from "../stores/chat";
import { useThemeStore } from "../stores/theme";

/**
 * Clear all PyAMA-related localStorage data.
 * Use this to reset the app to a clean state.
 */
export function clearAllStorage(): void {
  const keys = [
    // All Zustand stores (all state is managed by Zustand)
    "pyama:processing",
    "pyama:analysis",
    "pyama:visualization",
    "pyama:chat",
    "pyama:theme",
  ];

  keys.forEach((key) => {
    localStorage.removeItem(key);
  });
}

/**
 * Clear only file-related persisted data (file paths, metadata).
 * Keeps user preferences like frame intervals, parameters, etc.
 */
export function clearFileData(): void {
  // Clear processing store file data
  const processingData = localStorage.getItem("pyama:processing");
  if (processingData) {
    try {
      const parsed = JSON.parse(processingData);
      // Zustand persist format: { state: {...}, version: 0 }
      const state = parsed.state || parsed;
      const cleaned = {
        ...parsed,
        state: {
          ...state,
          microscopyFile: "",
          microscopyMetadata: null,
          outputDir: "",
        },
      };
      localStorage.setItem("pyama:processing", JSON.stringify(cleaned));
    } catch {
      // If parsing fails, remove the entire key
      localStorage.removeItem("pyama:processing");
    }
  }

  // Clear analysis store file data
  const analysisData = localStorage.getItem("pyama:analysis");
  if (analysisData) {
    try {
      const parsed = JSON.parse(analysisData);
      const state = parsed.state || parsed;
      const cleaned = {
        ...parsed,
        state: {
          ...state,
          dataFolder: "",
        },
      };
      localStorage.setItem("pyama:analysis", JSON.stringify(cleaned));
    } catch {
      localStorage.removeItem("pyama:analysis");
    }
  }

  // Clear visualization store file data
  const visualizationData = localStorage.getItem("pyama:visualization");
  if (visualizationData) {
    try {
      const parsed = JSON.parse(visualizationData);
      const state = parsed.state || parsed;
      const cleaned = {
        ...parsed,
        state: {
          ...state,
          dataFolder: "",
        },
      };
      localStorage.setItem("pyama:visualization", JSON.stringify(cleaned));
    } catch {
      localStorage.removeItem("pyama:visualization");
    }
  }
}

/**
 * Initialize storage on app start.
 * Clears all persisted state to ensure a clean startup.
 * Also resets all Zustand stores to their initial state.
 * 
 * IMPORTANT: This must be called BEFORE any stores are accessed to prevent
 * Zustand's persist middleware from restoring old state from localStorage.
 */
export function initializeStorage(): void {
  // Clear localStorage first
  clearAllStorage();
  
  // Reset stores synchronously after clearing localStorage
  // This ensures stores don't restore old state when they're first accessed
  // Note: Stores are created when imported, but persist middleware only
  // restores state when the store is first accessed via getState() or in a component.
  // By resetting here, we ensure the in-memory state matches the cleared localStorage.
  useProcessingStore.getState().resetProcessing();
  useVisualizationStore.getState().reset();
  useAnalysisStore.getState().reset();
  useChatStore.getState().clearChat();
  useThemeStore.getState().reset();
}