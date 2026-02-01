// IMPORTANT: Import this FIRST to clear localStorage before any Zustand stores are created
// This prevents stores from restoring old state from localStorage
import "./lib/clear-storage-init";

import { createRoot } from "react-dom/client";
import "./index.css";
import { App } from "./app.tsx";
import { initializeTheme } from "./lib/theme";
import { initializeStorage } from "./lib/storage";

// Initialize storage (resets all Zustand stores to initial state)
// localStorage is already cleared above, so this just resets in-memory store state
initializeStorage();

// Initialize theme before render to prevent flash
initializeTheme();

createRoot(document.getElementById("app")!).render(<App />);
