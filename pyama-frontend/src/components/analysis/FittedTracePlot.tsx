import { useEffect, useRef } from "react";
import { FittingResult, TraceDataPoint } from "@/types/analysis";

interface FittedTracePlotProps {
  results: FittingResult[];
  traceData: TraceDataPoint[];
  selectedResultIdx: number;
  qualityFilter: boolean;
  width?: number;
  height?: number;
}

export function FittedTracePlot({
  results,
  traceData,
  selectedResultIdx,
  qualityFilter,
  width = 400,
  height = 300,
}: FittedTracePlotProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || results.length === 0 || traceData.length === 0) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const w = canvas.width;
    const h = canvas.height;

    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#171717";
    ctx.fillRect(0, 0, w, h);

    // Get filtered results
    const filtered = qualityFilter
      ? results.filter((r) => r.r_squared > 0.9)
      : results;

    if (filtered.length === 0) return;

    const result = filtered[selectedResultIdx % filtered.length];
    const cellId = `${result.fov}_${result.cell}`;

    // Get trace data for this cell
    const cellData = traceData.filter((d) => `${d.fov}_${d.cell}` === cellId);
    if (cellData.length === 0) return;

    cellData.sort((a, b) => a.time - b.time);

    // Find bounds
    const minTime = Math.min(...cellData.map((d) => d.time));
    const maxTime = Math.max(...cellData.map((d) => d.time));
    const minVal = Math.min(...cellData.map((d) => d.value));
    const maxVal = Math.max(...cellData.map((d) => d.value));

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

    // Draw raw data
    ctx.strokeStyle = "#60a5fa";
    ctx.lineWidth = 1.5;
    ctx.globalAlpha = 0.8;
    ctx.beginPath();

    for (let i = 0; i < cellData.length; i++) {
      const x =
        padding + ((cellData[i].time - minTime) / (maxTime - minTime)) * plotWidth;
      const y =
        h -
        padding -
        ((cellData[i].value - minVal) / (maxVal - minVal)) * plotHeight;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }

    ctx.stroke();
    ctx.globalAlpha = 1;

    // Labels
    ctx.fillStyle = "#a3a3a3";
    ctx.font = "11px sans-serif";
    ctx.fillText(`Cell ${result.fov}_${result.cell}`, padding, 20);
    ctx.fillText(`R² = ${result.r_squared.toFixed(3)}`, padding, 35);
    ctx.fillText(result.success ? "Success" : "Failed", padding + 100, 35);
  }, [results, traceData, selectedResultIdx, qualityFilter]);

  return (
    <div className="aspect-[4/3] w-full overflow-hidden rounded-lg border border-neutral-800">
      <canvas
        ref={canvasRef}
        width={width}
        height={height}
        className="h-full w-full"
      />
    </div>
  );
}
