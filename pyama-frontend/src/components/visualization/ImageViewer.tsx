import { useEffect, useRef } from "react";
import { OverlayPosition, ChannelMeta } from "@/types/visualization";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from "lucide-react";

interface ImageViewerProps {
  channelsMeta: ChannelMeta[];
  currentChannel: string;
  onChannelChange: (channel: string) => void;
  imageData: number[][] | null;
  overlayPositions: OverlayPosition[];
  activeTraceId: string | null;
  onCanvasClick: (x: number, y: number) => void;
  currentFrame: number;
  maxFrames: number;
  onFrameChange: (delta: number) => void;
  loadingFrame: boolean;
}

export function ImageViewer({
  channelsMeta,
  currentChannel,
  onChannelChange,
  imageData,
  overlayPositions,
  activeTraceId,
  onCanvasClick,
  currentFrame,
  maxFrames,
  onFrameChange,
  loadingFrame,
}: ImageViewerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !imageData) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const height = imageData.length;
    const width = imageData[0]?.length || 0;

    canvas.width = width;
    canvas.height = height;

    const imgData = ctx.createImageData(width, height);

    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const idx = (y * width + x) * 4;
        const value = imageData[y][x] || 0;
        imgData.data[idx] = value;
        imgData.data[idx + 1] = value;
        imgData.data[idx + 2] = value;
        imgData.data[idx + 3] = 255;
      }
    }

    ctx.putImageData(imgData, 0, 0);

    // Draw overlays
    for (const overlay of overlayPositions) {
      ctx.beginPath();
      ctx.arc(overlay.x, overlay.y, 20, 0, 2 * Math.PI);
      ctx.strokeStyle = overlay.id === activeTraceId ? "red" : overlay.color;
      ctx.lineWidth = overlay.id === activeTraceId ? 3 : 2;
      ctx.stroke();
    }
  }, [imageData, overlayPositions, activeTraceId]);

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const x = (e.clientX - rect.left) * scaleX;
    const y = (e.clientY - rect.top) * scaleY;

    onCanvasClick(x, y);
  };

  return (
    <Card className="border-neutral-800 bg-neutral-900">
      <CardContent className="p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-neutral-50">Image</h2>
          {channelsMeta.length > 0 && (
            <Select value={currentChannel} onValueChange={onChannelChange}>
              <SelectTrigger className="h-8 w-[160px]">
                <SelectValue placeholder="Channel" />
              </SelectTrigger>
              <SelectContent>
                {channelsMeta.map((ch) => (
                  <SelectItem key={ch.channel} value={ch.channel}>
                    {ch.channel === "pc"
                      ? "Phase Contrast"
                      : ch.channel === "seg"
                      ? "Segmentation"
                      : `FL ${ch.channel}`}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>

        {/* Canvas */}
        <div className="relative aspect-square w-full overflow-hidden rounded-lg border border-neutral-800 bg-neutral-950">
          <canvas
            ref={canvasRef}
            className="h-full w-full object-contain cursor-crosshair"
            onClick={handleCanvasClick}
          />
          {loadingFrame && (
            <div className="absolute inset-0 flex items-center justify-center bg-neutral-950/50">
              <span className="text-sm text-neutral-400">Loading...</span>
            </div>
          )}
        </div>

        {/* Frame Controls */}
        <div className="mt-3 flex items-center justify-center gap-2">
          <Button
            variant="default"
            size="icon"
            className="h-8 w-8"
            onClick={() => onFrameChange(-10)}
            disabled={currentFrame < 10}
          >
            <ChevronsLeft className="h-4 w-4" />
          </Button>
          <Button
            variant="default"
            size="icon"
            className="h-8 w-8"
            onClick={() => onFrameChange(-1)}
            disabled={currentFrame === 0}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="min-w-[100px] text-center text-sm text-neutral-300 font-mono">
            Frame {currentFrame + 1} / {maxFrames || 1}
          </span>
          <Button
            variant="default"
            size="icon"
            className="h-8 w-8"
            onClick={() => onFrameChange(1)}
            disabled={currentFrame >= maxFrames - 1}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
          <Button
            variant="default"
            size="icon"
            className="h-8 w-8"
            onClick={() => onFrameChange(10)}
            disabled={currentFrame >= maxFrames - 10}
          >
            <ChevronsRight className="h-4 w-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
