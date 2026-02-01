/**
 * Storage utilities for managing persisted state.
 */

/**
 * Clear all PyAMA-related localStorage data.
 * Use this to reset the app to a clean state.
 */
export function clearAllStorage(): void {
  const keys = [
    "pyama:processing",
    "pyama:analysis",
    "pyama:visualization",
    "pyama:chat",
    "pyama_current_task_id",
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

  // Clear task ID
  localStorage.removeItem("pyama_current_task_id");
}

/**
 * Initialize storage on app start.
 * Clears all persisted state to ensure a clean startup.
 */
export function initializeStorage(): void {
  clearAllStorage();
}