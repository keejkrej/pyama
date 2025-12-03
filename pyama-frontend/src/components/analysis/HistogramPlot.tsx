import { useEffect, useRef } from "react";
import { FittingResult } from "@/types/analysis";

interface HistogramPlotProps {
  data: FittingResult[];
  param: string;
  width?: number;
  height?: number;
}

export function HistogramPlot({
  data,
  param,
  width = 400,
  height = 300,
}: HistogramPlotProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || data.length === 0 || !param) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const w = canvas.width;
    const h = canvas.height;

    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#171717";
    ctx.fillRect(0, 0, w, h);

    const values = data
      .map((r) => r[param])
      .filter((v): v is number => typeof v === "number" && !isNaN(v));

    if (values.length === 0) return;

    // Calculate histogram
    const min = Math.min(...values);
    const max = Math.max(...values);
    const bins = 30;
    const binWidth = (max - min) / bins;
    const counts = new Array(bins).fill(0);

    for (const v of values) {
      const idx = Math.min(Math.floor((v - min) / binWidth), bins - 1);
      counts[idx]++;
    }

    const maxCount = Math.max(...counts);
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

    // Draw bars
    ctx.fillStyle = "#60a5fa";
    const barWidth = plotWidth / bins;

    for (let i = 0; i < bins; i++) {
      const barHeight = (counts[i] / maxCount) * plotHeight;
      ctx.fillRect(
        padding + i * barWidth + 1,
        h - padding - barHeight,
        barWidth - 2,
        barHeight
      );
    }

    // Stats
    const mean = values.reduce((a, b) => a + b, 0) / values.length;
    const std = Math.sqrt(
      values.reduce((a, b) => a + (b - mean) ** 2, 0) / values.length
    );

    ctx.fillStyle = "#a3a3a3";
    ctx.font = "11px sans-serif";
    ctx.fillText(param, w / 2, h - 8);
    ctx.fillText(`Mean: ${mean.toFixed(3)}`, w - 100, 20);
    ctx.fillText(`Std: ${std.toFixed(3)}`, w - 100, 35);
  }, [data, param]);

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
