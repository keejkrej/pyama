import { useEffect, useRef } from "react";
import { FittingResult } from "@/types/analysis";

interface ScatterPlotProps {
  data: FittingResult[];
  xParam: string;
  yParam: string;
  width?: number;
  height?: number;
}

export function ScatterPlot({
  data,
  xParam,
  yParam,
  width = 400,
  height = 300,
}: ScatterPlotProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || data.length === 0 || !xParam || !yParam) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const w = canvas.width;
    const h = canvas.height;

    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#171717";
    ctx.fillRect(0, 0, w, h);

    const points = data
      .map((r) => ({
        x: r[xParam] as number,
        y: r[yParam] as number,
      }))
      .filter(
        (p) =>
          typeof p.x === "number" &&
          typeof p.y === "number" &&
          !isNaN(p.x) &&
          !isNaN(p.y)
      );

    if (points.length === 0) return;

    const minX = Math.min(...points.map((p) => p.x));
    const maxX = Math.max(...points.map((p) => p.x));
    const minY = Math.min(...points.map((p) => p.y));
    const maxY = Math.max(...points.map((p) => p.y));

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

    // Draw points
    ctx.fillStyle = "#60a5fa";
    ctx.globalAlpha = 0.6;

    for (const p of points) {
      const x = padding + ((p.x - minX) / (maxX - minX || 1)) * plotWidth;
      const y = h - padding - ((p.y - minY) / (maxY - minY || 1)) * plotHeight;
      ctx.beginPath();
      ctx.arc(x, y, 4, 0, 2 * Math.PI);
      ctx.fill();
    }

    ctx.globalAlpha = 1;

    // Labels
    ctx.fillStyle = "#a3a3a3";
    ctx.font = "11px sans-serif";
    ctx.fillText(xParam, w / 2, h - 8);
    ctx.save();
    ctx.translate(12, h / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText(yParam, 0, 0);
    ctx.restore();
  }, [data, xParam, yParam]);

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
