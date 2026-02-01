import { createRoot } from "react-dom/client";
import "./index.css";
import { App } from "./app.tsx";
import { initializeTheme } from "./lib/theme";
import { initializeStorage } from "./lib/storage";

// Initialize storage (clears all persisted state for clean startup)
initializeStorage();

// Initialize theme before render to prevent flash
initializeTheme();

createRoot(document.getElementById("app")!).render(<App />);
