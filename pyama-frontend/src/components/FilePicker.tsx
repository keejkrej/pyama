import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { FileText, Folder, ArrowUp, RefreshCw, AlertCircle } from "lucide-react";
import { FileItem, PickerConfig } from "@/types/processing";
import { cn } from "@/lib/utils";

interface FilePickerProps {
  isOpen: boolean;
  onClose: () => void;
  config: PickerConfig | null;
  initialPath: string;
  onSelect: (path: string) => void;
}

export function FilePicker({
  isOpen,
  onClose,
  config,
  initialPath,
  onSelect,
}: FilePickerProps) {
  const [currentPath, setCurrentPath] = useState(initialPath);
  const [items, setItems] = useState<FileItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveFileName, setSaveFileName] = useState("");

  // Reset state when opening with new config
  useEffect(() => {
    if (isOpen && config) {
      setCurrentPath(initialPath);
      setSaveFileName(config.defaultFileName || "");
      loadDirectory(initialPath, config);
    }
  }, [isOpen, config, initialPath]);

  const backendBase = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
  const apiBase = `${backendBase.replace(/\/$/, "")}/api/v1`;

  const loadDirectory = async (path: string, currentConfig: PickerConfig) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${apiBase}/processing/list-directory`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          directory_path: path,
          include_hidden: false,
          filter_extensions: currentConfig.filterExtensions ?? null,
        }),
      });

      if (!response.ok) {
        throw new Error(`Backend responded with ${response.status}`);
      }
      const data = await response.json();
      if (!data.success) {
        throw new Error(data.error || "Failed to list directory");
      }
      setItems(data.items || []);
      setCurrentPath(data.directory_path || path);
    } catch (err) {
      setItems([]);
      setError(err instanceof Error ? err.message : "Failed to list directory");
    } finally {
      setLoading(false);
    }
  };

  const goUp = () => {
    if (!currentPath || !config) return;
    const normalized = currentPath.replace(/\\/g, "/");
    const parent = normalized.split("/").slice(0, -1).join("/") || "/";
    setCurrentPath(parent);
    loadDirectory(parent, config);
  };

  const handleItemClick = (item: FileItem) => {
    if (!config) return;
    if (item.is_directory) {
      setCurrentPath(item.path);
      loadDirectory(item.path, config);
    } else if (!config.directory && config.mode !== "save") {
      onSelect(item.path);
    }
  };

  const handleConfirmSelection = () => {
    if (!config) return;

    if (config.mode === "save") {
      const fullPath = `${currentPath.replace(/\/$/, "")}/${saveFileName}`;
      onSelect(fullPath);
    } else {
      onSelect(currentPath);
    }
  };

  if (!config) return null;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-3xl max-h-[85vh] flex flex-col gap-0 p-0 bg-neutral-900 border-neutral-800 text-neutral-50">
        <DialogHeader className="px-6 py-4 border-b border-neutral-800">
          <div className="flex items-start justify-between">
            <div className="space-y-1">
              <DialogTitle className="text-lg font-semibold text-neutral-50">
                {config.title}
              </DialogTitle>
              <DialogDescription className="text-neutral-400">
                {config.description}
              </DialogDescription>
            </div>
            <div className="flex items-center gap-2">
              {(config.directory || config.mode === "save") && (
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={handleConfirmSelection}
                  disabled={loading || (config.mode === "save" && !saveFileName.trim())}
                >
                  {config.mode === "save" ? "Save here" : "Use this folder"}
                </Button>
              )}
              <Button size="sm" variant="ghost" onClick={onClose}>
                Close
              </Button>
            </div>
          </div>
        </DialogHeader>

        <div className="p-4 space-y-4 flex-1 overflow-hidden flex flex-col">
          {/* Navigation Bar */}
          <div className="flex items-center gap-2">
            <div className="flex-1 flex items-center gap-2 rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2">
              <span className="text-xs font-medium text-neutral-500">Path</span>
              <div className="truncate text-sm text-neutral-200 font-mono">
                {currentPath}
              </div>
            </div>
            <Button
              size="icon"
              variant="outline"
              onClick={goUp}
              disabled={!currentPath || currentPath === "/"}
              title="Go Up"
            >
              <ArrowUp className="h-4 w-4" />
            </Button>
            <Button
              size="icon"
              variant="outline"
              onClick={() => loadDirectory(currentPath, config)}
              disabled={loading}
              title="Refresh"
            >
              <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
            </Button>
          </div>

          {error && (
            <div className="flex items-center gap-2 rounded-md border border-red-900/50 bg-red-900/20 p-3 text-sm text-red-200">
              <AlertCircle className="h-4 w-4" />
              {error}
            </div>
          )}

          {/* File List */}
          <div className="flex-1 overflow-auto rounded-md border border-neutral-800 bg-neutral-950/50">
            <Table>
              <TableHeader className="bg-neutral-900 sticky top-0 z-10">
                <TableRow className="hover:bg-neutral-900 border-neutral-800">
                  <TableHead className="w-[60%] text-neutral-400">Name</TableHead>
                  <TableHead className="text-neutral-400">Type</TableHead>
                  <TableHead className="text-right text-neutral-400">Size</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.length === 0 && !loading ? (
                  <TableRow className="hover:bg-transparent">
                    <TableCell
                      colSpan={3}
                      className="h-32 text-center text-neutral-500"
                    >
                      No items found in this location
                    </TableCell>
                  </TableRow>
                ) : (
                  items.map((item) => (
                    <TableRow
                      key={item.path}
                      className="cursor-pointer hover:bg-neutral-800/50 border-neutral-800 transition-colors"
                      onClick={() => handleItemClick(item)}
                    >
                      <TableCell className="font-medium text-neutral-200">
                        <div className="flex items-center gap-2">
                          {item.is_directory ? (
                            <Folder className="h-4 w-4 text-blue-400" />
                          ) : (
                            <FileText className="h-4 w-4 text-neutral-400" />
                          )}
                          {item.name}
                        </div>
                      </TableCell>
                      <TableCell className="text-neutral-400 text-xs">
                        {item.is_directory
                          ? "Folder"
                          : item.extension?.toUpperCase() || "File"}
                      </TableCell>
                      <TableCell className="text-right text-neutral-400 text-xs font-mono">
                        {item.is_directory
                          ? "-"
                          : typeof item.size_bytes === "number"
                          ? `${(item.size_bytes / 1024 / 1024).toFixed(2)} MB`
                          : ""}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>

          {/* Save Mode Filename Input */}
          {config.mode === "save" && (
            <div className="flex items-center gap-3 pt-2 border-t border-neutral-800">
              <span className="text-sm font-medium text-neutral-400">
                Filename:
              </span>
              <Input
                value={saveFileName}
                onChange={(e) => setSaveFileName(e.target.value)}
                placeholder="samples.yaml"
                className="flex-1"
              />
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
