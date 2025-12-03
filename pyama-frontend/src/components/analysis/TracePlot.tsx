import { useEffect, useRef } from "react";
import { TraceDataPoint } from "@/types/analysis";

interface TracePlotProps {
  data: TraceDataPoint[];
  width?: number;
  height?: number;
}

export function TracePlot({ data, width = 400, height = 300 }: TracePlotProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || data.length === 0) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const w = canvas.width;
    const h = canvas.height;

    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#171717";
    ctx.fillRect(0, 0, w, h);

    // Group by cell
    const cellMap = new Map<string, TraceDataPoint[]>();
    for (const point of data) {
      const id = `${point.fov}_${point.cell}`;
      if (!cellMap.has(id)) cellMap.set(id, []);
      cellMap.get(id)!.push(point);
    }

    // Find bounds
    let minTime = Infinity,
      maxTime = -Infinity;
    let minVal = Infinity,
      maxVal = -Infinity;

    for (const point of data) {
      minTime = Math.min(minTime, point.time);
      maxTime = Math.max(maxTime, point.time);
      minVal = Math.min(minVal, point.value);
      maxVal = Math.max(maxVal, point.value);
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

    // Draw all traces in gray
    ctx.strokeStyle = "#6b7280";
    ctx.lineWidth = 0.5;
    ctx.globalAlpha = 0.3;

    for (const [, points] of cellMap) {
      points.sort((a, b) => a.time - b.time);
      ctx.beginPath();
      for (let i = 0; i < points.length; i++) {
        const x =
          padding + ((points[i].time - minTime) / (maxTime - minTime)) * plotWidth;
        const y =
          h -
          padding -
          ((points[i].value - minVal) / (maxVal - minVal)) * plotHeight;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }

    // Calculate and draw mean
    const timePoints = Array.from(new Set(data.map((d) => d.time))).sort(
      (a, b) => a - b
    );
    const meanValues: number[] = [];

    for (const t of timePoints) {
      const vals = data.filter((d) => d.time === t).map((d) => d.value);
      meanValues.push(vals.reduce((a, b) => a + b, 0) / vals.length);
    }

    ctx.globalAlpha = 1;
    ctx.strokeStyle = "#ef4444";
    ctx.lineWidth = 2;
    ctx.beginPath();

    for (let i = 0; i < timePoints.length; i++) {
      const x =
        padding + ((timePoints[i] - minTime) / (maxTime - minTime)) * plotWidth;
      const y =
        h - padding - ((meanValues[i] - minVal) / (maxVal - minVal)) * plotHeight;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }

    ctx.stroke();

    // Labels
    ctx.fillStyle = "#a3a3a3";
    ctx.font = "11px sans-serif";
    ctx.fillText("Time (hours)", w / 2, h - 8);
    ctx.save();
    ctx.translate(12, h / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText("Intensity", 0, 0);
    ctx.restore();

    // Legend
    ctx.fillStyle = "#ef4444";
    ctx.fillRect(w - 100, 10, 12, 12);
    ctx.fillStyle = "#a3a3a3";
    ctx.fillText(`Mean (n=${cellMap.size})`, w - 85, 20);
  }, [data]);

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
