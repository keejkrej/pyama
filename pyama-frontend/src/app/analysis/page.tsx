"use client";

import { useState, useEffect } from "react";
import { FilePicker } from "@/components/FilePicker";
import { DataPanel } from "@/components/analysis/DataPanel";
import { QualityPanel } from "@/components/analysis/QualityPanel";
import { ParameterPanel } from "@/components/analysis/ParameterPanel";
import { useAnalysis } from "@/hooks/useAnalysis";
import { ModelParamState } from "@/types/analysis";

export default function AnalysisPage() {
  // Backend config
  const backendBase =
    process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
  const apiBase = `${backendBase.replace(/\/$/, "")}/api/v1`;

  // Analysis Hook
  const {
    traceData,
    cellIds,
    loadingData,
    loadTraceData,
    availableModels,
    selectedModel,
    setSelectedModel,
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
  } = useAnalysis(apiBase);

  // Local UI State
  const [csvPath, setCsvPath] = useState<string | null>(null);
  const [showPicker, setShowPicker] = useState(false);
  const [pickerMode, setPickerMode] = useState<"csv" | "results">("csv");
  const [manualMode, setManualMode] = useState(false);

  // Quality Panel State
  const [selectedResultIdx, setSelectedResultIdx] = useState(0);
  const [qualityFilter, setQualityFilter] = useState(false);
  const [qualityPage, setQualityPage] = useState(0);
  const resultsPerPage = 10;

  // Parameter Panel State
  const [selectedHistParam, setSelectedHistParam] = useState<string>("");
  const [selectedScatterX, setSelectedScatterX] = useState<string>("");
  const [selectedScatterY, setSelectedScatterY] = useState<string>("");

  // Update default parameter selections when params change
  useEffect(() => {
    if (parameterNames.length > 0) {
      if (!selectedHistParam) setSelectedHistParam(parameterNames[0]);
      if (!selectedScatterX) setSelectedScatterX(parameterNames[0]);
      if (!selectedScatterY)
        setSelectedScatterY(
          parameterNames.length > 1 ? parameterNames[1] : parameterNames[0]
        );
    }
  }, [parameterNames, selectedHistParam, selectedScatterX, selectedScatterY]);

  const handleFileSelect = (path: string) => {
    setShowPicker(false);
    if (pickerMode === "csv") {
      setCsvPath(path);
      loadTraceData(path);
    } else {
      loadFittedResults(path);
    }
  };

  const handleParamChange = (
    name: string,
    field: keyof ModelParamState,
    value: number
  ) => {
    setModelParams((prev) => ({
      ...prev,
      [name]: { ...prev[name], [field]: value },
    }));
  };

  const handleStartFitting = () => {
    if (!csvPath) return;

    const params: Record<string, number> = {};
    const bounds: Record<string, [number, number]> = {};

    if (manualMode) {
      for (const [name, p] of Object.entries(modelParams)) {
        params[name] = p.value;
        bounds[name] = [p.min, p.max];
      }
    }

    startFitting(csvPath, manualMode, params, bounds);
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-50">
      <FilePicker
        isOpen={showPicker}
        onClose={() => setShowPicker(false)}
        config={{
          key: pickerMode === "csv" ? "inputDir" : "mergeOutput", // Reusing keys for simplicity
          title:
            pickerMode === "csv"
              ? "Select Trace CSV"
              : "Select Fitted Results CSV",
          description: "Choose a CSV file",
          filterExtensions: [".csv"],
          directory: false,
          mode: "select",
        }}
        initialPath={process.env.NEXT_PUBLIC_DEFAULT_BROWSE_PATH || "/home"}
        onSelect={handleFileSelect}
      />

      <main className="mx-auto max-w-[1600px] px-6 py-8">
        {/* Header */}
        <div className="mb-6 flex flex-wrap items-start justify-between gap-6">
          <div className="space-y-3">
            <h1 className="text-4xl font-semibold leading-tight text-neutral-50 uppercase tracking-widest">
              Analysis
            </h1>
          </div>
          <div className="flex-1 max-w-md rounded-xl border border-neutral-800 bg-neutral-900 px-4 py-3 text-sm text-neutral-200 shadow-sm">
            <p className="font-semibold text-neutral-50">Status</p>
            <p className="text-xs text-neutral-400 truncate" title={statusMessage}>
              {statusMessage}
            </p>
          </div>
        </div>

        {/* 3-Panel Layout */}
        <div className="grid gap-4 lg:grid-cols-3">
          {/* Data Panel */}
          <DataPanel
            csvPath={csvPath}
            onBrowse={() => {
              setPickerMode("csv");
              setShowPicker(true);
            }}
            traceData={traceData}
            availableModels={availableModels}
            selectedModel={selectedModel}
            onModelChange={setSelectedModel}
            modelParams={modelParams}
            onParamChange={handleParamChange}
            manualMode={manualMode}
            onManualModeChange={setManualMode}
            isFitting={isFitting}
            fittingProgress={fittingProgress}
            onStartFitting={handleStartFitting}
            onCancelFitting={cancelFitting}
            onLoadResults={() => {
              setPickerMode("results");
              setShowPicker(true);
            }}
          />

          {/* Quality Panel */}
          <QualityPanel
            fittingResults={fittingResults}
            traceData={traceData}
            selectedResultIdx={selectedResultIdx}
            onSelectResultIdx={setSelectedResultIdx}
            qualityFilter={qualityFilter}
            onQualityFilterChange={(c) => {
              setQualityFilter(c);
              setQualityPage(0);
              setSelectedResultIdx(0);
            }}
            qualityPage={qualityPage}
            onPageChange={setQualityPage}
            resultsPerPage={resultsPerPage}
          />

          {/* Parameter Panel */}
          <ParameterPanel
            fittingResults={fittingResults}
            parameterNames={parameterNames}
            selectedHistParam={selectedHistParam}
            onHistParamChange={setSelectedHistParam}
            selectedScatterX={selectedScatterX}
            onScatterXChange={setSelectedScatterX}
            selectedScatterY={selectedScatterY}
            onScatterYChange={setSelectedScatterY}
            qualityFilter={qualityFilter}
            onQualityFilterChange={setQualityFilter}
          />
        </div>
      </main>
    </div>
  );
}
