import { useEffect, useRef } from "react";
import { TraceData } from "@/types/visualization";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface TraceViewerProps {
  traces: TraceData[];
  activeTraceId: string | null;
  onTraceClick: (id: string) => void;
  onTraceToggleQuality: (id: string) => void;
  tracePage: number;
  onPageChange: (page: number) => void;
  tracesPerPage: number;
  currentFrame: number;
  width?: number;
  height?: number;
}

export function TraceViewer({
  traces,
  activeTraceId,
  onTraceClick,
  onTraceToggleQuality,
  tracePage,
  onPageChange,
  tracesPerPage,
  currentFrame,
  width = 400,
  height = 300,
}: TraceViewerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const totalTracePages = Math.ceil(traces.length / tracesPerPage);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || traces.length === 0) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const w = canvas.width;
    const h = canvas.height;

    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#171717";
    ctx.fillRect(0, 0, w, h);

    // Get visible traces
    const startIdx = tracePage * tracesPerPage;
    const visibleTraces = traces.slice(startIdx, startIdx + tracesPerPage);

    if (visibleTraces.length === 0) return;

    // Find data bounds
    let minVal = Infinity;
    let maxVal = -Infinity;
    let maxFrame = 0;

    for (const trace of visibleTraces) {
      for (const v of trace.values) {
        minVal = Math.min(minVal, v);
        maxVal = Math.max(maxVal, v);
      }
      maxFrame = Math.max(maxFrame, ...trace.frames);
    }

    const padding = 40;
    const plotWidth = w - padding * 2;
    const plotHeight = h - padding * 2;

    // Draw axes
    ctx.strokeStyle = "#404040";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padding, padding);
    ctx.lineTo(padding, h - padding);
    ctx.lineTo(w - padding, h - padding);
    ctx.stroke();

    // Draw traces
    const colors = [
      "#60a5fa",
      "#f87171",
      "#4ade80",
      "#fbbf24",
      "#a78bfa",
      "#f472b6",
      "#22d3d8",
      "#fb923c",
    ];

    for (let i = 0; i < visibleTraces.length; i++) {
      const trace = visibleTraces[i];
      const color =
        trace.cell_id === activeTraceId ? "#ef4444" : colors[i % colors.length];
      const lineWidth = trace.cell_id === activeTraceId ? 2 : 1;
      const alpha = trace.cell_id === activeTraceId ? 1 : 0.6;

      ctx.strokeStyle = color;
      ctx.lineWidth = lineWidth;
      ctx.globalAlpha = alpha;
      ctx.beginPath();

      for (let j = 0; j < trace.frames.length; j++) {
        const x = padding + (trace.frames[j] / maxFrame) * plotWidth;
        const y =
          h -
          padding -
          ((trace.values[j] - minVal) / (maxVal - minVal)) * plotHeight;

        if (j === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }

      ctx.stroke();
    }

    ctx.globalAlpha = 1;

    // Draw current frame indicator
    const frameX = padding + (currentFrame / maxFrame) * plotWidth;
    ctx.strokeStyle = "#ef4444";
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(frameX, padding);
    ctx.lineTo(frameX, h - padding);
    ctx.stroke();
    ctx.setLineDash([]);

    // Labels
    ctx.fillStyle = "#a3a3a3";
    ctx.font = "11px sans-serif";
    ctx.fillText("Frame", w / 2, h - 10);
    ctx.save();
    ctx.translate(12, h / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText("Value", 0, 0);
    ctx.restore();
  }, [traces, tracePage, activeTraceId, currentFrame]);

  return (
    <Card className="border-neutral-800 bg-neutral-900">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-semibold text-neutral-50">
            Traces
          </CardTitle>
          <span className="text-xs text-neutral-400">{traces.length} cells</span>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Trace Canvas */}
        <div className="aspect-[4/3] w-full overflow-hidden rounded-lg border border-neutral-800">
          <canvas
            ref={canvasRef}
            width={width}
            height={height}
            className="h-full w-full"
          />
        </div>

        {/* Trace List */}
        <div className="rounded-md border border-neutral-800 bg-neutral-950/50 overflow-hidden">
          <div className="max-h-48 overflow-y-auto divide-y divide-neutral-800/50">
            {traces
              .slice(tracePage * tracesPerPage, (tracePage + 1) * tracesPerPage)
              .map((trace) => (
                <div
                  key={trace.cell_id}
                  className={`flex cursor-pointer items-center justify-between px-3 py-2 text-sm hover:bg-neutral-800 ${
                    trace.cell_id === activeTraceId ? "bg-neutral-800" : ""
                  }`}
                  onClick={() => onTraceClick(trace.cell_id)}
                >
                  <span
                    className={
                      trace.good ? "text-blue-400" : "text-green-400"
                    }
                  >
                    Cell {trace.cell}
                  </span>
                  <Button
                    variant="default"
                    size="sm"
                    className="h-6 px-2 text-xs text-neutral-500 hover:text-neutral-300"
                    onClick={(e) => {
                      e.stopPropagation();
                      onTraceToggleQuality(trace.cell_id);
                    }}
                  >
                    {trace.good ? "Good" : "Bad"}
                  </Button>
                </div>
              ))}
            {traces.length === 0 && (
              <div className="p-4 text-center text-sm text-neutral-500">
                No traces loaded
              </div>
            )}
          </div>
        </div>

        {/* Pagination */}
        {totalTracePages > 1 && (
          <div className="flex items-center justify-between text-xs">
            <Button
              variant="default"
              size="sm"
              className="h-7 px-2"
              onClick={() => onPageChange(Math.max(0, tracePage - 1))}
              disabled={tracePage === 0}
            >
              Previous
            </Button>
            <span className="text-neutral-400">
              Page {tracePage + 1} of {totalTracePages}
            </span>
            <Button
              variant="default"
              size="sm"
              className="h-7 px-2"
              onClick={() =>
                onPageChange(Math.min(totalTracePages - 1, tracePage + 1))
              }
              disabled={tracePage >= totalTracePages - 1}
            >
              Next
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
