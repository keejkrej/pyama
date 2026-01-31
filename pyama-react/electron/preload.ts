import { contextBridge, ipcRenderer } from "electron";

export interface AgentMessage {
  type: "assistant" | "tool_use" | "tool_result" | "result" | "error";
  content?: string;
  toolName?: string;
  toolInput?: unknown;
  toolResult?: unknown;
  isError?: boolean;
}

export interface ElectronAPI {
  showOpenDialog: (
    options: Electron.OpenDialogOptions,
  ) => Promise<Electron.OpenDialogReturnValue>;
  showSaveDialog: (
    options: Electron.SaveDialogOptions,
  ) => Promise<Electron.SaveDialogReturnValue>;
}

export interface AgentAPI {
  query: (prompt: string) => Promise<AgentMessage[]>;
  cancel: () => Promise<void>;
  onMessage: (callback: (message: AgentMessage) => void) => () => void;
  onDone: (callback: () => void) => () => void;
}

contextBridge.exposeInMainWorld("electronAPI", {
  showOpenDialog: (options: Electron.OpenDialogOptions) =>
    ipcRenderer.invoke("dialog:open", options),
  showSaveDialog: (options: Electron.SaveDialogOptions) =>
    ipcRenderer.invoke("dialog:save", options),
});

contextBridge.exposeInMainWorld("agentAPI", {
  query: (prompt: string) => ipcRenderer.invoke("agent:query", prompt),
  cancel: () => ipcRenderer.invoke("agent:cancel"),
  onMessage: (callback: (message: AgentMessage) => void) => {
    const handler = (
      _event: Electron.IpcRendererEvent,
      message: AgentMessage,
    ) => callback(message);
    ipcRenderer.on("agent:message", handler);
    // Return cleanup function
    return () => ipcRenderer.removeListener("agent:message", handler);
  },
  onDone: (callback: () => void) => {
    const handler = () => callback();
    ipcRenderer.on("agent:done", handler);
    return () => ipcRenderer.removeListener("agent:done", handler);
  },
});
