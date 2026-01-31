import type { ElectronAPI, AgentAPI } from "../electron/preload";

declare global {
  interface Window {
    electronAPI: ElectronAPI;
    agentAPI: AgentAPI;
  }
}
