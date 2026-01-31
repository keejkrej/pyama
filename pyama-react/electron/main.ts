import { app, BrowserWindow, shell, ipcMain, dialog, session } from "electron";
import { join } from "path";
import { is } from "@electron-toolkit/utils";
import { agentQuery, type AgentMessage } from "./agent";

function createWindow(): void {
  const mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    title: "PyAMA",
    webPreferences: {
      preload: join(__dirname, "../preload/index.mjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  // Open external links in browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  // Load the app
  if (is.dev && process.env["ELECTRON_RENDERER_URL"]) {
    mainWindow.loadURL(process.env["ELECTRON_RENDERER_URL"]);
  } else {
    mainWindow.loadFile(join(__dirname, "../renderer/index.html"));
  }
}

// Track active query to allow cancellation
let activeQueryAbortController: AbortController | null = null;

function registerIpcHandlers(): void {
  ipcMain.handle("dialog:open", async (_, options) => {
    const win = BrowserWindow.getFocusedWindow();
    return dialog.showOpenDialog(win!, options);
  });

  ipcMain.handle("dialog:save", async (_, options) => {
    const win = BrowserWindow.getFocusedWindow();
    return dialog.showSaveDialog(win!, options);
  });

  // Agent query handler - streams messages back to renderer
  ipcMain.handle("agent:query", async (event, prompt: string) => {
    const win = BrowserWindow.fromWebContents(event.sender);
    if (!win) return;

    activeQueryAbortController = new AbortController();
    const messages: AgentMessage[] = [];

    try {
      for await (const message of agentQuery(prompt)) {
        // Check if query was cancelled
        if (activeQueryAbortController?.signal.aborted) {
          break;
        }

        messages.push(message);
        // Send each message to renderer as it arrives
        win.webContents.send("agent:message", message);
      }
    } catch (error) {
      const errorMessage: AgentMessage = {
        type: "error",
        content: error instanceof Error ? error.message : "Query failed",
        isError: true,
      };
      win.webContents.send("agent:message", errorMessage);
      messages.push(errorMessage);
    } finally {
      activeQueryAbortController = null;
      win.webContents.send("agent:done");
    }

    return messages;
  });

  // Cancel active query
  ipcMain.handle("agent:cancel", async () => {
    if (activeQueryAbortController) {
      activeQueryAbortController.abort();
      activeQueryAbortController = null;
    }
  });
}

app.whenReady().then(() => {
  registerIpcHandlers();
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

// Clear localStorage on app quit so session state doesn't persist
app.on("before-quit", () => {
  session.defaultSession.clearStorageData({ storages: ["localstorage"] });
});
