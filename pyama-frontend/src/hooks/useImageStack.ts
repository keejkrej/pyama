import { useState, useEffect } from "react";
import { ChannelMeta, TraceData, OverlayPosition } from "@/types/visualization";

export function useImageStack(apiBase: string) {
  // Load state
  const [availableFovs, setAvailableFovs] = useState<number[]>([]);
  const [availableChannels, setAvailableChannels] = useState<string[]>([]);
  const [loadingProject, setLoadingProject] = useState(false);
  const [statusMessage, setStatusMessage] = useState("Ready");

  // Visualization state
  const [channelsMeta, setChannelsMeta] = useState<ChannelMeta[]>([]);
  const [currentChannel, setCurrentChannel] = useState<string>("");
  const [currentFrame, setCurrentFrame] = useState(0);
  const [maxFrames, setMaxFrames] = useState(0);
  const [imageData, setImageData] = useState<number[][] | null>(null);
  const [loadingFrame, setLoadingFrame] = useState(false);

  // Trace state
  const [traces, setTraces] = useState<TraceData[]>([]);
  const [overlayPositions, setOverlayPositions] = useState<OverlayPosition[]>([]);

  const discoverFovs = async (dir: string) => {
    setLoadingProject(true);
    setStatusMessage("Discovering FOVs...");
    try {
      const response = await fetch(`${apiBase}/processing/list-directory`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ directory_path: dir, include_hidden: false }),
      });
      const data = await response.json();
      if (data.success) {
        const fovDirs = (data.items || [])
          .filter((item: { name: string; is_directory: boolean }) =>
            item.is_directory && item.name.startsWith("fov_"))
          .map((item: { name: string }) => parseInt(item.name.replace("fov_", ""), 10))
          .filter((n: number) => !isNaN(n))
          .sort((a: number, b: number) => a - b);

        setAvailableFovs(fovDirs);
        setStatusMessage(`Found ${fovDirs.length} FOVs`);
        return fovDirs;
      }
    } catch (err) {
      setStatusMessage("Failed to discover FOVs");
    } finally {
      setLoadingProject(false);
    }
    return [];
  };

  const discoverChannels = async (dir: string, fov: number) => {
    try {
      const fovDir = `${dir}/fov_${fov.toString().padStart(3, "0")}`;
      const response = await fetch(`${apiBase}/processing/list-directory`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ directory_path: fovDir, include_hidden: false }),
      });
      const data = await response.json();
      if (data.success) {
        const channels: string[] = [];
        for (const item of data.items || []) {
          if (item.name === "pc.npy") channels.push("pc");
          else if (item.name === "seg.npy") channels.push("seg");
          else if (item.name.startsWith("fl_") && item.name.endsWith(".npy")) {
            const ch = item.name.replace("fl_", "").replace(".npy", "");
            channels.push(ch);
          }
        }
        setAvailableChannels(channels);
        return channels;
      }
    } catch (err) {
      console.error("Failed to discover channels:", err);
    }
    return [];
  };

  const startVisualization = async (outputDir: string, fov: number, channels: string[]) => {
    setLoadingProject(true);
    setStatusMessage("Initializing visualization...");

    try {
      const response = await fetch(`${apiBase}/visualization/init`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          output_dir: outputDir,
          fov_id: fov,
          channels: channels,
          data_types: ["image", "seg"],
        }),
      });

      const data = await response.json();

      if (!data.success) {
        throw new Error(data.error || "Failed to initialize visualization");
      }

      setChannelsMeta(data.channels);
      if (data.channels.length > 0) {
        const firstChannel = data.channels[0];
        setCurrentChannel(firstChannel.channel);
        setMaxFrames(firstChannel.n_frames);
        setCurrentFrame(0);
        loadFrame(firstChannel.path, firstChannel.channel, 0);
      }

      // Load traces if available
      if (data.traces_csv) {
        loadTraces(data.traces_csv);
      }

      setStatusMessage(`Loaded FOV ${fov} with ${data.channels.length} channels`);
    } catch (err) {
      setStatusMessage(err instanceof Error ? err.message : "Failed to initialize");
    } finally {
      setLoadingProject(false);
    }
  };

  const loadFrame = async (cachedPath: string, channel: string, frame: number) => {
    setLoadingFrame(true);
    try {
      const response = await fetch(`${apiBase}/visualization/frame`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          cached_path: cachedPath,
          channel,
          frame,
        }),
      });

      const data = await response.json();

      if (data.success && data.frames.length > 0) {
        setImageData(data.frames[0]);
      }
    } catch (err) {
      console.error("Failed to load frame:", err);
    } finally {
      setLoadingFrame(false);
    }
  };

  const loadTraces = async (csvPath: string) => {
    try {
      const response = await fetch(`${apiBase}/processing/file/read`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_path: csvPath }),
      });

      const data = await response.json();
      if (data.success && data.content) {
        const parsed = parseTracesCsv(data.content);
        setTraces(parsed);
        updateOverlaysFromTraces(parsed, 0);
      }
    } catch (err) {
      console.error("Failed to load traces:", err);
    }
  };

  const parseTracesCsv = (content: string): TraceData[] => {
    const lines = content.trim().split("\n");
    if (lines.length < 2) return [];

    const header = lines[0].split(",");
    const fovIdx = header.indexOf("fov");
    const cellIdx = header.indexOf("cell");
    const frameIdx = header.indexOf("frame");
    const valueIdx = header.indexOf("value");
    const xIdx = header.indexOf("x");
    const yIdx = header.indexOf("y");
    const goodIdx = header.indexOf("good");

    if (fovIdx < 0 || cellIdx < 0 || frameIdx < 0 || valueIdx < 0) {
      return [];
    }

    const traceMap = new Map<string, TraceData>();

    for (let i = 1; i < lines.length; i++) {
      const cols = lines[i].split(",");
      const fov = parseInt(cols[fovIdx], 10);
      const cell = parseInt(cols[cellIdx], 10);
      const frame = parseInt(cols[frameIdx], 10);
      const value = parseFloat(cols[valueIdx]);
      const x = xIdx >= 0 ? parseFloat(cols[xIdx]) : 0;
      const y = yIdx >= 0 ? parseFloat(cols[yIdx]) : 0;
      const good = goodIdx >= 0 ? cols[goodIdx].toLowerCase() === "true" : true;

      const cellId = `${fov}_${cell}`;

      if (!traceMap.has(cellId)) {
        traceMap.set(cellId, {
          cell_id: cellId,
          fov,
          cell,
          frames: [],
          values: [],
          x_positions: [],
          y_positions: [],
          good,
        });
      }

      const trace = traceMap.get(cellId)!;
      trace.frames.push(frame);
      trace.values.push(value);
      trace.x_positions.push(x);
      trace.y_positions.push(y);
    }

    return Array.from(traceMap.values());
  };

  const updateOverlaysFromTraces = (traceData: TraceData[], frame: number) => {
    const positions: OverlayPosition[] = [];

    for (const trace of traceData) {
      const frameIdx = trace.frames.indexOf(frame);
      if (frameIdx >= 0) {
        positions.push({
          id: trace.cell_id,
          x: trace.x_positions[frameIdx] || 0,
          y: trace.y_positions[frameIdx] || 0,
          color: trace.good ? "blue" : "green",
        });
      }
    }

    setOverlayPositions(positions);
  };

  const changeFrame = (delta: number) => {
    const newFrame = Math.max(0, Math.min(maxFrames - 1, currentFrame + delta));
    if (newFrame !== currentFrame) {
      setCurrentFrame(newFrame);
      const meta = channelsMeta.find((c) => c.channel === currentChannel);
      if (meta) {
        loadFrame(meta.path, meta.channel, newFrame);
      }
      updateOverlaysFromTraces(traces, newFrame);
    }
  };

  const changeChannel = (channel: string) => {
    setCurrentChannel(channel);
    const meta = channelsMeta.find((c) => c.channel === channel);
    if (meta) {
      setMaxFrames(meta.n_frames);
      const frame = Math.min(currentFrame, meta.n_frames - 1);
      setCurrentFrame(frame);
      loadFrame(meta.path, channel, frame);
    }
  };

  return {
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
    overlayPositions
  };
}
