import { useState, useRef, useEffect, useCallback } from "react";
import {
  ModelInfo,
  TraceDataPoint,
  FittingResult,
  JobProgress,
  ModelParamState,
} from "@/types/analysis";

export function useAnalysis(apiBase: string) {
  // Data state
  const [traceData, setTraceData] = useState<TraceDataPoint[]>([]);
  const [cellIds, setCellIds] = useState<string[]>([]);
  const [loadingData, setLoadingData] = useState(false);
  const [statusMessage, setStatusMessage] = useState("Ready");

  // Model state
  const [availableModels, setAvailableModels] = useState<ModelInfo[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [modelParams, setModelParams] = useState<
    Record<string, ModelParamState>
  >({});

  // Fitting state
  const [fittingJobId, setFittingJobId] = useState<string | null>(null);
  const [fittingProgress, setFittingProgress] = useState<JobProgress | null>(
    null
  );
  const [isFitting, setIsFitting] = useState(false);
  const [fittingResults, setFittingResults] = useState<FittingResult[]>([]);
  const [resultsFile, setResultsFile] = useState<string | null>(null);
  const [parameterNames, setParameterNames] = useState<string[]>([]);

  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const loadModels = async () => {
    try {
      const response = await fetch(`${apiBase}/analysis/models`);
      const data = await response.json();
      if (data.models && data.models.length > 0) {
        setAvailableModels(data.models);
        setSelectedModel(data.models[0].name);
        initModelParams(data.models[0]);
      }
    } catch (err) {
      console.error("Failed to load models:", err);
    }
  };

  const initModelParams = (model: ModelInfo) => {
    const params: Record<string, ModelParamState> = {};
    for (const param of model.parameters) {
      params[param.name] = {
        value: param.default,
        min: param.bounds[0],
        max: param.bounds[1],
      };
    }
    setModelParams(params);
  };

  const loadTraceData = async (path: string) => {
    setLoadingData(true);
    setStatusMessage("Loading trace data...");

    try {
      // First, get info about the file
      const infoResponse = await fetch(`${apiBase}/analysis/load-traces`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ csv_path: path }),
      });

      const infoData = await infoResponse.json();
      if (!infoData.success) {
        throw new Error(infoData.error || "Failed to load traces");
      }

      // Read the actual CSV content
      const contentResponse = await fetch(`${apiBase}/processing/file/read`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_path: path }),
      });

      const contentData = await contentResponse.json();
      if (contentData.success && contentData.content) {
        const parsed = parseTraceCsv(contentData.content);
        setTraceData(parsed.data);
        setCellIds(parsed.cellIds);
        setStatusMessage(
          `Loaded ${parsed.cellIds.length} cells, ${
            infoData.data?.n_timepoints || 0
          } timepoints`
        );
      }
    } catch (err) {
      setStatusMessage(
        err instanceof Error ? err.message : "Failed to load traces"
      );
    } finally {
      setLoadingData(false);
    }
  };

  const parseTraceCsv = (
    content: string
  ): { data: TraceDataPoint[]; cellIds: string[] } => {
    const lines = content.trim().split("\n");
    if (lines.length < 2) return { data: [], cellIds: [] };

    const header = lines[0].split(",");
    const fovIdx = header.indexOf("fov");
    const cellIdx = header.indexOf("cell");
    const timeIdx = header.indexOf("time");
    const valueIdx = header.indexOf("value");
    const frameIdx = header.indexOf("frame");

    const data: TraceDataPoint[] = [];
    const cellSet = new Set<string>();

    for (let i = 1; i < lines.length; i++) {
      const cols = lines[i].split(",");
      const fov = parseInt(cols[fovIdx], 10);
      const cell = parseInt(cols[cellIdx], 10);
      const time = parseFloat(cols[timeIdx]);
      const value = parseFloat(cols[valueIdx]);
      const frame = frameIdx >= 0 ? parseInt(cols[frameIdx], 10) : i - 1;

      data.push({ fov, cell, time, value, frame });
      cellSet.add(`${fov}_${cell}`);
    }

    return { data, cellIds: Array.from(cellSet) };
  };

  const loadFittedResults = async (path: string) => {
    setStatusMessage("Loading fitted results...");

    try {
      const response = await fetch(`${apiBase}/processing/file/read`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_path: path }),
      });

      const data = await response.json();

      if (data.success && data.content) {
        const results = parseFittedCsv(data.content);
        setFittingResults(results);
        setResultsFile(path);

        // Extract parameter names
        if (results.length > 0) {
          const excluded = [
            "fov",
            "cell",
            "model_type",
            "success",
            "r_squared",
            "residual_sum_squares",
            "message",
            "n_function_calls",
          ];
          const params = Object.keys(results[0]).filter(
            (k) => !excluded.includes(k) && typeof results[0][k] === "number"
          );
          setParameterNames(params);
        }

        setStatusMessage(`Loaded ${results.length} fitted results`);
      }
    } catch (err) {
      setStatusMessage(
        err instanceof Error ? err.message : "Failed to load results"
      );
    }
  };

  const parseFittedCsv = (content: string): FittingResult[] => {
    const lines = content.trim().split("\n");
    if (lines.length < 2) return [];

    const header = lines[0].split(",");
    const results: FittingResult[] = [];

    for (let i = 1; i < lines.length; i++) {
      const cols = lines[i].split(",");
      const row: Record<string, number | string | boolean> = {};

      for (let j = 0; j < header.length; j++) {
        const key = header[j];
        const val = cols[j];

        if (key === "success") {
          row[key] = val.toLowerCase() === "true";
        } else if (key === "model_type") {
          row[key] = val;
        } else {
          const num = parseFloat(val);
          row[key] = isNaN(num) ? val : num;
        }
      }

      results.push(row as FittingResult);
    }

    return results;
  };

  const startFitting = async (
    csvPath: string,
    manualMode: boolean,
    params: Record<string, number>,
    bounds: Record<string, [number, number]>
  ) => {
    setIsFitting(true);
    setStatusMessage("Starting fitting...");

    try {
      const response = await fetch(`${apiBase}/analysis/fitting/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          csv_path: csvPath,
          model_type: selectedModel,
          model_params: manualMode ? params : null,
          model_bounds: manualMode ? bounds : null,
        }),
      });

      const data = await response.json();

      if (!data.success) {
        throw new Error(data.error || "Failed to start fitting");
      }

      setFittingJobId(data.job_id);
      setStatusMessage(`Fitting started (Job: ${data.job_id})`);
      startPolling(data.job_id);
    } catch (err) {
      setIsFitting(false);
      setStatusMessage(
        err instanceof Error ? err.message : "Failed to start fitting"
      );
    }
  };

  const startPolling = (jobId: string) => {
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);

    pollIntervalRef.current = setInterval(async () => {
      try {
        const response = await fetch(
          `${apiBase}/analysis/fitting/status/${jobId}`
        );
        const data = await response.json();

        if (data.progress) {
          setFittingProgress(data.progress);
          setStatusMessage(
            `Fitting: ${data.progress.current}/${data.progress.total} (${data.progress.percentage.toFixed(
              1
            )}%)`
          );
        }

        if (
          ["completed", "failed", "cancelled", "not_found"].includes(
            data.status
          )
        ) {
          stopPolling();
          setIsFitting(false);

          if (data.status === "completed") {
            const resultsResponse = await fetch(
              `${apiBase}/analysis/fitting/results/${jobId}`
            );
            const resultsData = await resultsResponse.json();

            if (resultsData.success && resultsData.results_file) {
              loadFittedResults(resultsData.results_file);
              setStatusMessage(
                `Fitting completed! ${
                  resultsData.summary?.successful_fits || 0
                } successful fits`
              );
            }
          } else {
            setStatusMessage(`Fitting ${data.status}: ${data.message}`);
          }
        }
      } catch (err) {
        console.error("Polling error:", err);
      }
    }, 1000);
  };

  const stopPolling = () => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  };

  const cancelFitting = async () => {
    if (!fittingJobId) return;
    try {
      await fetch(`${apiBase}/analysis/fitting/cancel/${fittingJobId}`, {
        method: "POST",
      });
      setStatusMessage("Cancelling fitting...");
    } catch (err) {
      console.error("Failed to cancel:", err);
    }
  };

  useEffect(() => {
    loadModels();
    return () => stopPolling();
  }, []);

  return {
    traceData,
    cellIds,
    loadingData,
    loadTraceData,
    availableModels,
    selectedModel,
    setSelectedModel: (model: string) => {
        setSelectedModel(model);
        const m = availableModels.find((m) => m.name === model);
        if (m) initModelParams(m);
    },
    modelParams,
    setModelParams,
    isFitting,
    fittingProgress,
    startFitting,
    cancelFitting,
    fittingResults,
    loadFittedResults,
    parameterNames,
    statusMessage,
    setStatusMessage
  };
}
