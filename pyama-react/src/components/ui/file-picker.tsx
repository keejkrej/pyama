import { Button } from "./button";

interface FilePickerProps {
  label?: string;
  accept?: string;
  multiple?: boolean;
  directory?: boolean;
  onFileSelect?: (paths: string[]) => void;
  buttonText?: string;
  className?: string;
}

// Access Electron API from preload
declare global {
  interface Window {
    electronAPI?: {
      showOpenDialog: (
        options: Electron.OpenDialogOptions,
      ) => Promise<Electron.OpenDialogReturnValue>;
    };
  }
}

export function FilePicker({
  label,
  accept,
  multiple = false,
  directory = false,
  onFileSelect,
  buttonText = "Browse...",
  className = "",
}: FilePickerProps) {
  const handleButtonClick = async () => {
    if (!window.electronAPI) {
      console.warn("Electron API not available");
      return;
    }

    // Convert accept string (e.g., ".nd2") to Electron filter format
    const filters: Electron.FileFilter[] = [];
    if (accept && !directory) {
      const extensions = accept
        .split(",")
        .map((ext) => ext.trim().replace(/^\./, ""));
      filters.push({ name: "Files", extensions });
    }

    const result = await window.electronAPI.showOpenDialog({
      properties: [
        directory ? "openDirectory" : "openFile",
        ...(multiple ? ["multiSelections" as const] : []),
      ],
      filters: filters.length > 0 ? filters : undefined,
    });

    if (!result.canceled && result.filePaths.length > 0 && onFileSelect) {
      onFileSelect(result.filePaths);
    }
  };

  return (
    <div className={className}>
      {label && (
        <label className="text-xs font-medium leading-tight peer-disabled:cursor-not-allowed peer-disabled:opacity-70 mb-1.5 block text-foreground-bright">
          {label}
        </label>
      )}
      <div className="flex items-center gap-2">
        <Button onClick={handleButtonClick} variant="outline">
          {buttonText}
        </Button>
      </div>
    </div>
  );
}
