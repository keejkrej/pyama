"use client";

import { useState } from "react";
import { FilePicker } from "@/components/FilePicker";
import { ImageViewer } from "@/components/visualization/ImageViewer";
import { TraceViewer } from "@/components/visualization/TraceViewer";
import { useImageStack } from "@/hooks/useImageStack";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";

export default function VisualizationPage() {
  // Backend config
  const backendBase = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
  const apiBase = `${backendBase.replace(/\/$/, "")}/api/v1`;

  // Image Stack Hook
  const {
    availableFovs,
    availableChannels,
    loadingProject,
    statusMessage,
    discoverFovs,
    discoverChannels,
    startVisualization,
    channelsMeta,
    currentChannel,
    currentFrame,
    maxFrames,
    imageData,
    loadingFrame,
    changeFrame,
    changeChannel,
    traces,
    setTraces,
    overlayPositions,
  } = useImageStack(apiBase);

  // Local UI State
  const [showPicker, setShowPicker] = useState(false);
  const [outputDir, setOutputDir] = useState<string | null>(null);
  const [selectedFov, setSelectedFov] = useState<number>(0);
  const [selectedChannels, setSelectedChannels] = useState<string[]>([]);
  const [activeTraceId, setActiveTraceId] = useState<string | null>(null);
  const [tracePage, setTracePage] = useState(0);
  const tracesPerPage = 10;

  const handleOutputDirSelect = (path: string) => {
    setShowPicker(false);
    setOutputDir(path);
    discoverFovs(path).then((fovs) => {
      if (fovs.length > 0) {
        setSelectedFov(fovs[0]);
        discoverChannels(path, fovs[0]);
      }
    });
  };

  const handleStartVisualization = () => {
    if (outputDir && selectedChannels.length > 0) {
      startVisualization(outputDir, selectedFov, selectedChannels);
    }
  };

  const handleCanvasClick = (x: number, y: number) => {
    // Find closest overlay
    let closest = null;
    let minDist = 30;

    for (const overlay of overlayPositions) {
      const dist = Math.sqrt((overlay.x - x) ** 2 + (overlay.y - y) ** 2);
      if (dist < minDist) {
        minDist = dist;
        closest = overlay;
      }
    }

    if (closest) {
      setActiveTraceId(closest.id);
      // Find trace page
      const traceIdx = traces.findIndex((t) => t.cell_id === closest!.id);
      if (traceIdx >= 0) {
        setTracePage(Math.floor(traceIdx / tracesPerPage));
      }
    }
  };

  const toggleTraceQuality = (traceId: string) => {
    setTraces((prev) =>
      prev.map((t) => (t.cell_id === traceId ? { ...t, good: !t.good } : t))
    );
  };

  return (
    <div className="bg-neutral-950 text-neutral-50">
      <FilePicker
        isOpen={showPicker}
        onClose={() => setShowPicker(false)}
        config={{
          key: "processingOutput",
          title: "Select Output Directory",
          description: "Choose the workflow output folder",
          directory: true,
          mode: "select",
        }}
        initialPath={process.env.NEXT_PUBLIC_DEFAULT_BROWSE_PATH || "/home"}
        onSelect={handleOutputDirSelect}
      />

      <main className="mx-auto max-w-[1600px] px-6 py-8">
        {/* Header */}
        <div className="mb-6 flex flex-wrap items-start justify-between gap-6">
          <div className="space-y-3">
            <h1 className="text-4xl font-semibold leading-tight text-neutral-50 uppercase tracking-widest">
              Visualization
            </h1>
          </div>
          <div className="flex-1 max-w-md rounded-xl border border-neutral-800 bg-neutral-900 px-4 py-3 text-sm text-neutral-200 shadow-sm ml-auto">
            <p className="font-semibold text-neutral-50">Status</p>
            <p className="text-xs text-neutral-400 truncate" title={statusMessage}>
              {statusMessage}
            </p>
          </div>
        </div>

        {/* 3-Panel Layout */}
        <div className="grid gap-6 lg:grid-cols-[1fr_2fr_1fr]">
          {/* Load Panel */}
          <div className="rounded-2xl border border-neutral-900 bg-neutral-900 p-6 shadow-sm space-y-4">
              {/* Output Directory */}
              <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-xs text-neutral-300">
                    <span>Output Directory</span>
                    <Button
                      className="h-6 text-[10px]"
                      size="sm"
                      onClick={() => setShowPicker(true)}
                    >
                      Browse
                    </Button>
                  </div>
                  <div className="rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-neutral-300 truncate text-xs">
                    {outputDir ? outputDir.split("/").pop() : "unselected"}
                  </div>
                </div>
              </div>

              {/* FOV Selection */}
              {availableFovs.length > 0 && (
                <div>
                  <Label className="mb-1 text-xs text-neutral-400">FOV</Label>
                  <Select
                    value={selectedFov.toString()}
                    onValueChange={(val) => {
                      const fov = parseInt(val, 10);
                      setSelectedFov(fov);
                      if (outputDir) discoverChannels(outputDir, fov);
                    }}
                  >
                    <SelectTrigger className="h-9">
                      <SelectValue placeholder="Select FOV" />
                    </SelectTrigger>
                    <SelectContent>
                      {availableFovs.map((fov) => (
                        <SelectItem key={fov} value={fov.toString()}>
                          FOV {fov}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              {/* Channel Selection */}
              {availableChannels.length > 0 && (
                <div>
                  <Label className="mb-1 text-xs text-neutral-400">Channels</Label>
                  <div className="space-y-2">
                    {availableChannels.map((ch) => (
                      <div key={ch} className="flex items-center gap-2">
                        <Checkbox
                          id={`ch-${ch}`}
                          checked={selectedChannels.includes(ch)}
                          onCheckedChange={(checked) => {
                            if (checked) {
                              setSelectedChannels((prev) => [...prev, ch]);
                            } else {
                              setSelectedChannels((prev) => prev.filter((c) => c !== ch));
                            }
                          }}
                          className="border-neutral-600"
                        />
                        <Label htmlFor={`ch-${ch}`} className="text-sm cursor-pointer">
                          {ch === "pc" ? "Phase Contrast" : ch === "seg" ? "Segmentation" : `FL ${ch}`}
                        </Label>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <Button
                className="w-full"
                onClick={handleStartVisualization}
                disabled={loadingProject || !outputDir || selectedChannels.length === 0}
              >
                {loadingProject ? "Loading..." : "Start Visualization"}
              </Button>
          </div>

          {/* Image Panel */}
          <ImageViewer
            channelsMeta={channelsMeta}
            currentChannel={currentChannel}
            onChannelChange={changeChannel}
            imageData={imageData}
            overlayPositions={overlayPositions}
            activeTraceId={activeTraceId}
            onCanvasClick={handleCanvasClick}
            currentFrame={currentFrame}
            maxFrames={maxFrames}
            onFrameChange={changeFrame}
            loadingFrame={loadingFrame}
          />

          {/* Trace Panel */}
          <TraceViewer
            traces={traces}
            activeTraceId={activeTraceId}
            onTraceClick={setActiveTraceId}
            onTraceToggleQuality={toggleTraceQuality}
            tracePage={tracePage}
            onPageChange={setTracePage}
            tracesPerPage={tracesPerPage}
            currentFrame={currentFrame}
          />
        </div>
      </main>
    </div>
  );
}
