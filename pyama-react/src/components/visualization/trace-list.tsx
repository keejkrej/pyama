import { useState } from "react";
import { Button, Checkbox } from "../ui";
import type { TraceData } from "../../lib/api";

interface TraceListProps {
  traces: TraceData[];
  activeTraceId: string | null;
  onTraceSelect: (cellId: string) => void;
  onQualityToggle: (cellId: string) => void;
}

export function TraceList({
  traces,
  activeTraceId,
  onTraceSelect,
  onQualityToggle,
}: TraceListProps) {
  const [rightClickCellId, setRightClickCellId] = useState<string | null>(
    null
  );

  const handleContextMenu = (e: React.MouseEvent, cellId: string) => {
    e.preventDefault();
    setRightClickCellId(cellId);
    onQualityToggle(cellId);
  };

  if (traces.length === 0) {
    return (
      <div className="flex items-center justify-center h-full min-h-[200px] text-muted-foreground">
        <p className="text-xs">No traces available</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto space-y-1">
        {traces.map((trace) => {
          const isActive = trace.cell_id === activeTraceId;
          const isGood = trace.quality;

          // Color coding: Red (active+good), Blue (good), Green (bad)
          let textColor: string;
          if (!isGood) {
            textColor = "text-green-600 dark:text-green-400";
          } else if (isActive && isGood) {
            textColor = "text-red-600 dark:text-red-400";
          } else {
            textColor = "text-blue-600 dark:text-blue-400";
          }

          return (
            <div
              key={trace.cell_id}
              className={`
                flex items-center gap-2 p-2 rounded cursor-pointer
                hover:bg-accent transition-colors
                ${isActive ? "bg-accent" : ""}
                ${textColor}
              `}
              onClick={() => onTraceSelect(trace.cell_id)}
              onContextMenu={(e) => handleContextMenu(e, trace.cell_id)}
            >
              <Checkbox checked={isGood} readOnly />
              <span className="text-xs font-medium flex-1">
                Trace {trace.cell_id}
              </span>
              {isActive && (
                <span className="text-xs text-muted-foreground">●</span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
