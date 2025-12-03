"use client";

import { useEffect, useState } from "react";
import { FilePicker } from "@/components/FilePicker";
import { ChannelConfiguration } from "@/components/processing/ChannelConfiguration";
import { WorkflowParametersPanel } from "@/components/processing/WorkflowParametersPanel";
import { SampleManager } from "@/components/processing/SampleManager";
import { WorkflowStatus } from "@/components/processing/WorkflowStatus";
import { useWorkflow } from "@/hooks/useWorkflow";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  PickerKey,
  PickerConfig,
  PickerSelections,
  MicroscopyMetadata,
  WorkflowParameters,
  Sample,
} from "@/types/processing";
import { Folder, ToggleLeft, ToggleRight } from "lucide-react";

export default function Home() {
  // Backend configuration
  const backendBase =
    process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
  const apiBase = `${backendBase.replace(/\/$/, "")}/api/v1`;

  // Workflow Hook
  const {
    currentJob,
    isProcessing,
    statusMessage,
    setStatusMessage,
    startWorkflow,
    cancelWorkflow,
  } = useWorkflow(apiBase);

  // File picker state
  const [activePicker, setActivePicker] = useState<PickerConfig | null>(null);
  const [selections, setSelections] = useState<PickerSelections>({
    microscopy: null,
    processingOutput: null,
    sampleYaml: null,
    inputDir: null,
    mergeOutput: null,
    loadSamplesYaml: null,
    saveSamplesYaml: null,
  });

  // Status and metadata
  const [metadata, setMetadata] = useState<MicroscopyMetadata | null>(null);
  const [loadingMetadata, setLoadingMetadata] = useState(false);
  const [channelNames, setChannelNames] = useState<string[]>([]);

  // Features
  const [availablePhaseFeatures, setAvailablePhaseFeatures] = useState<string[]>(
    []
  );
  const [availableFlFeatures, setAvailableFlFeatures] = useState<string[]>([]);

  // Phase contrast selection
  const [phaseChannel, setPhaseChannel] = useState<number | null>(null);
  const [pcFeaturesSelected, setPcFeaturesSelected] = useState<string[]>([]);

  // Fluorescence selection
  const [flChannelSelection, setFlChannelSelection] = useState<number | null>(
    null
  );
  const [flFeatureSelection, setFlFeatureSelection] = useState<string | null>(
    null
  );
  const [flMapping, setFlMapping] = useState<Record<number, string[]>>({});

  // Parameters
  const [parameters, setParameters] = useState<WorkflowParameters>({
    fov_start: 0,
    fov_end: -1,
    batch_size: 2,
    n_workers: 2,
    background_weight: 1.0,
  });
  const [manualMode, setManualMode] = useState(false);

  // Split mode
  const [splitMode, setSplitMode] = useState(false);

  // Samples for merge
  const [samples, setSamples] = useState<Sample[]>([
    { id: "1", name: "control", fovs: "0-5" },
    { id: "2", name: "drug_a", fovs: "6-11" },
    { id: "3", name: "rescue", fovs: "12-17" },
  ]);
  const [editingSampleId, setEditingSampleId] = useState<string | null>(null);

  // Merge state
  const [isMerging, setIsMerging] = useState(false);

  // =============================================================================
  // UTILITY FUNCTIONS
  // =============================================================================

  const formatName = (fullPath: string | null) => {
    if (!fullPath) return null;
    const normalized = fullPath.replace(/\\/g, "/");
    const parts = normalized.split("/").filter(Boolean);
    return parts[parts.length - 1] || fullPath;
  };

  const getStartPath = (config: PickerConfig) => {
    const prior = selections[config.key];
    if (prior) {
      const normalized = prior.replace(/\\/g, "/");
      if (config.directory) return normalized;
      const parent = normalized.split("/").slice(0, -1).join("/") || "/";
      return parent;
    }
    return process.env.NEXT_PUBLIC_DEFAULT_BROWSE_PATH || "/home";
  };

  const selectionLabel = (key: PickerKey, fallback: string) =>
    formatName(selections[key]) || fallback;

  const generateSampleId = () =>
    `sample_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

  // =============================================================================
  // FILE PICKER HANDLERS
  // =============================================================================

  const openPicker = (config: PickerConfig) => setActivePicker(config);
  const closePicker = () => setActivePicker(null);

  const handleSelect = async (path: string) => {
    if (!activePicker) return;
    const key = activePicker.key;

    setSelections((prev) => ({ ...prev, [key]: path }));
    setActivePicker(null);

    if (key === "microscopy") {
      setPhaseChannel(null);
      setPcFeaturesSelected([]);
      setFlChannelSelection(null);
      setFlFeatureSelection(null);
      setFlMapping({});
      loadMicroscopyMetadata(path);
    } else if (key === "loadSamplesYaml") {
      await loadSamplesFromServer(path);
    } else if (key === "saveSamplesYaml") {
      await saveSamplesToServer(path);
    }
  };

  // =============================================================================
  // FEATURES LOADING
  // =============================================================================

  const loadFeatures = async () => {
    let phase = availablePhaseFeatures;
    let fl = availableFlFeatures;
    try {
      const response = await fetch(`${apiBase}/processing/features`);
      if (!response.ok) return { phase, fl };
      const data = await response.json();
      if (Array.isArray(data.phase_features) && data.phase_features.length) {
        phase = data.phase_features;
        setAvailablePhaseFeatures(data.phase_features);
      }
      if (
        Array.isArray(data.fluorescence_features) &&
        data.fluorescence_features.length
      ) {
        fl = data.fluorescence_features;
        setAvailableFlFeatures(data.fluorescence_features);
      }
    } catch {
      // Keep defaults on failure
    }
    return { phase, fl };
  };

  useEffect(() => {
    (async () => {
      const { phase, fl } = await loadFeatures();
      if (!pcFeaturesSelected.length && phase.length) {
        setPcFeaturesSelected(phase.slice(0, Math.min(3, phase.length)));
      }
      if (!availableFlFeatures.length && fl.length) {
        setAvailableFlFeatures(fl);
      }
    })();
  }, []);

  // =============================================================================
  // MICROSCOPY METADATA
  // =============================================================================

  const loadMicroscopyMetadata = async (
    filePath: string,
    split = splitMode
  ) => {
    setLoadingMetadata(true);
    setStatusMessage("Loading microscopy metadata...");
    setMetadata(null);
    setChannelNames([]);
    try {
      const { phase, fl } = await loadFeatures();
      const response = await fetch(`${apiBase}/processing/load-metadata`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_path: filePath, split_mode: split }),
      });
      if (!response.ok) {
        throw new Error(`Backend responded with ${response.status}`);
      }
      const data = await response.json();
      if (!data.success) {
        throw new Error(data.error || "Failed to load metadata");
      }
      const meta = data.metadata || {};
      const names: string[] = Array.isArray(meta.channel_names)
        ? meta.channel_names
        : [];
      setMetadata(meta);
      setChannelNames(names);

      const phaseDefaults = phase.length
        ? phase.slice(0, Math.min(3, phase.length))
        : [];
      setPcFeaturesSelected(phaseDefaults);
      setPhaseChannel(names.length ? 0 : null);

      setFlMapping({});
      setFlChannelSelection(names.length ? 0 : null);
      setFlFeatureSelection(fl.length ? fl[0] : null);

      // Update fov_end based on metadata
      if (typeof meta.n_fovs === "number") {
        setParameters((prev) => ({
          ...prev,
          fov_end: meta.n_fovs - 1,
        }));
      }

      const fovsText =
        typeof meta.n_fovs === "number"
          ? `${meta.n_fovs} FOVs`
          : "FOVs unknown";
      setStatusMessage(
        `Loaded metadata for ${formatName(filePath)} (${fovsText})${
          split ? " [split]" : ""
        }`
      );
    } catch (err) {
      setStatusMessage(
        err instanceof Error ? err.message : "Failed to load metadata"
      );
    } finally {
      setLoadingMetadata(false);
    }
  };

  const toggleSplitMode = () => {
    const next = !splitMode;
    setSplitMode(next);
    if (selections.microscopy) {
      loadMicroscopyMetadata(selections.microscopy, next);
    }
  };

  // =============================================================================
  // CHANNEL SELECTION
  // =============================================================================

  const togglePcFeature = (feature: string) => {
    setPcFeaturesSelected((prev) =>
      prev.includes(feature)
        ? prev.filter((f) => f !== feature)
        : [...prev, feature]
    );
  };

  const addFlMapping = () => {
    if (flChannelSelection === null || !flFeatureSelection) return;
    setFlMapping((prev) => {
      const existing = prev[flChannelSelection] || [];
      if (existing.includes(flFeatureSelection)) return prev;
      return {
        ...prev,
        [flChannelSelection]: [...existing, flFeatureSelection],
      };
    });
  };

  const removeFlMapping = (channel: number, feature: string) => {
    setFlMapping((prev) => {
      const current = prev[channel] || [];
      const updated = current.filter((f) => f !== feature);
      const next = { ...prev };
      if (updated.length) {
        next[channel] = updated;
      } else {
        delete next[channel];
      }
      return next;
    });
  };

  // =============================================================================
  // PARAMETERS
  // =============================================================================

  const handleParameterChange = (
    key: keyof WorkflowParameters,
    value: string
  ) => {
    const numValue =
      key === "background_weight" ? parseFloat(value) : parseInt(value, 10);
    if (!isNaN(numValue)) {
      setParameters((prev) => ({ ...prev, [key]: numValue }));
    }
  };

  // =============================================================================
  // WORKFLOW EXECUTION
  // =============================================================================

  const validateWorkflow = (): string | null => {
    if (!selections.microscopy) return "Please select a microscopy file";
    if (!selections.processingOutput)
      return "Please select an output directory";
    if (phaseChannel === null && Object.keys(flMapping).length === 0) {
      return "Please configure at least one channel (phase or fluorescence)";
    }
    if (phaseChannel !== null && pcFeaturesSelected.length === 0) {
      return "Please select at least one phase feature";
    }
    if (parameters.batch_size < 1) return "Batch size must be at least 1";
    if (parameters.n_workers < 1) return "Number of workers must be at least 1";
    return null;
  };

  const handleStartWorkflow = async () => {
    const validationError = validateWorkflow();
    if (validationError) {
      setStatusMessage(`Error: ${validationError}`);
      return;
    }

    // Build channel configuration
    const phaseConfig =
      phaseChannel !== null && pcFeaturesSelected.length > 0
        ? { channel: phaseChannel, features: pcFeaturesSelected }
        : null;

    const flConfigs = Object.entries(flMapping).map(([channel, features]) => ({
      channel: parseInt(channel, 10),
      features,
    }));

    const payload = {
      microscopy_path: selections.microscopy,
      output_dir: selections.processingOutput,
      channels: {
        phase: phaseConfig,
        fluorescence: flConfigs,
      },
      parameters: {
        fov_start: parameters.fov_start,
        fov_end: parameters.fov_end,
        batch_size: parameters.batch_size,
        n_workers: parameters.n_workers,
      },
    };

    await startWorkflow(payload);
  };

  // =============================================================================
  // SAMPLES MANAGEMENT
  // =============================================================================

  const addSample = () => {
    const newSample: Sample = {
      id: generateSampleId(),
      name: "",
      fovs: "",
    };
    setSamples((prev) => [...prev, newSample]);
    setEditingSampleId(newSample.id);
  };

  const removeSample = (id: string) => {
    setSamples((prev) => prev.filter((s) => s.id !== id));
    if (editingSampleId === id) {
      setEditingSampleId(null);
    }
  };

  const updateSample = (id: string, field: "name" | "fovs", value: string) => {
    setSamples((prev) =>
      prev.map((s) => (s.id === id ? { ...s, [field]: value } : s))
    );
  };

  const saveSamplesToServer = async (filePath: string) => {
    const validSamples = samples.filter((s) => s.name && s.fovs);
    if (validSamples.length === 0) {
      setStatusMessage("No valid samples to save");
      return;
    }

    setStatusMessage("Saving samples...");

    try {
      const response = await fetch(`${apiBase}/processing/samples/save`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          file_path: filePath,
          samples: validSamples.map((s) => ({ name: s.name, fovs: s.fovs })),
        }),
      });

      const data = await response.json();

      if (!data.success) {
        throw new Error(data.error || "Failed to save samples");
      }

      setStatusMessage(
        data.message ||
          `Saved ${validSamples.length} samples to ${formatName(filePath)}`
      );
    } catch (err) {
      setStatusMessage(
        err instanceof Error ? err.message : "Failed to save samples"
      );
    }
  };

  const loadSamplesFromServer = async (filePath: string) => {
    setStatusMessage("Loading samples...");

    try {
      const response = await fetch(`${apiBase}/processing/samples/load`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_path: filePath }),
      });

      const data = await response.json();

      if (!data.success) {
        throw new Error(data.error || "Failed to load samples");
      }

      if (data.samples && data.samples.length > 0) {
        const loadedSamples: Sample[] = data.samples.map(
          (s: { name: string; fovs: string }) => ({
            id: generateSampleId(),
            name: s.name,
            fovs: s.fovs,
          })
        );
        setSamples(loadedSamples);
        setStatusMessage(
          `Loaded ${loadedSamples.length} samples from ${formatName(filePath)}`
        );
      } else {
        setStatusMessage("No samples found in YAML file");
      }
    } catch (err) {
      setStatusMessage(
        err instanceof Error ? err.message : "Failed to load samples"
      );
    }
  };

  const openSaveYamlPicker = () => {
    openPicker({
      key: "saveSamplesYaml",
      title: "Save Samples YAML",
      description: "Choose a directory to save the samples configuration",
      directory: true,
      mode: "save",
      defaultFileName: "samples.yaml",
    });
  };

  const openLoadYamlPicker = () => {
    openPicker({
      key: "loadSamplesYaml",
      title: "Load Samples YAML",
      description: "Select a samples YAML file to load",
      filterExtensions: [".yaml", ".yml"],
    });
  };

  // =============================================================================
  // MERGE EXECUTION
  // =============================================================================

  const validateMerge = (): string | null => {
    if (!selections.sampleYaml) return "Please select a sample YAML file";
    if (!selections.inputDir)
      return "Please select an input directory (folder of processed FOVs)";
    if (!selections.mergeOutput) return "Please select an output directory";
    return null;
  };

  const runMerge = async () => {
    const validationError = validateMerge();
    if (validationError) {
      setStatusMessage(`Error: ${validationError}`);
      return;
    }

    setIsMerging(true);
    setStatusMessage("Running merge...");

    try {
      const response = await fetch(`${apiBase}/processing/merge`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sample_yaml: selections.sampleYaml,
          input_dir: selections.inputDir,
          output_dir: selections.mergeOutput,
        }),
      });

      const data = await response.json();

      if (!data.success) {
        throw new Error(data.error || "Failed to merge results");
      }

      setStatusMessage(
        `Merge completed: ${data.merged_files?.length || 0} files created`
      );
    } catch (err) {
      setStatusMessage(
        err instanceof Error ? err.message : "Failed to merge results"
      );
    } finally {
      setIsMerging(false);
    }
  };

  // =============================================================================
  // RENDER
  // =============================================================================

  return (
    <div className="relative min-h-screen bg-neutral-950 text-neutral-50">
      <FilePicker
        isOpen={!!activePicker}
        onClose={closePicker}
        config={activePicker}
        initialPath={activePicker ? getStartPath(activePicker) : "/home"}
        onSelect={handleSelect}
      />

      {/* Main Content */}
      <main className="relative mx-auto max-w-7xl px-6 py-12">
        {/* Header */}
        <div className="mb-10 flex flex-wrap items-start justify-between gap-6">
          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-neutral-400">
              Processing
            </p>
            <h1 className="text-4xl font-semibold leading-tight text-neutral-50">
              PyAMA Processing Workspace
            </h1>
            <p className="max-w-3xl text-sm text-neutral-300">
              Configure and run microscopy image processing workflows with
              real-time progress tracking.
            </p>
          </div>
          <div className="rounded-xl border border-neutral-800 bg-neutral-900 px-4 py-3 text-sm text-neutral-200 shadow-sm">
            <p className="font-semibold text-neutral-50">Status</p>
            <p className="text-xs text-neutral-400">{statusMessage}</p>
          </div>
        </div>

        {/* Main Grid */}
        <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
          {/* Workflow Section */}
          <section className="rounded-2xl border border-neutral-900 bg-neutral-900 p-6 shadow-sm space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-2xl font-semibold uppercase tracking-[0.12em] text-neutral-50">
                Workflow
              </h2>
              {isProcessing && (
                <Badge
                  variant="secondary"
                  className="bg-blue-500/20 text-blue-200 hover:bg-blue-500/20"
                >
                  Processing...
                </Badge>
              )}
            </div>

            <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
              {/* Input Section */}
              <div className="space-y-5 rounded-xl border border-neutral-800 bg-neutral-900 p-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="space-y-1">
                    <p className="text-sm font-semibold text-neutral-50">
                      Input
                    </p>
                    <p className="text-xs text-neutral-400">
                      Microscopy file and channel selection
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={toggleSplitMode}
                    className="text-xs border-neutral-700 bg-neutral-800"
                  >
                    {splitMode ? (
                      <>
                        Split files <ToggleRight className="ml-2 h-4 w-4" />
                      </>
                    ) : (
                      <>
                        Split files <ToggleLeft className="ml-2 h-4 w-4" />
                      </>
                    )}
                  </Button>
                </div>

                {/* Microscopy File Selection */}
                <div className="rounded-lg border border-dashed border-neutral-700 bg-neutral-900 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <p className="text-xs uppercase tracking-[0.2em] text-neutral-400">
                        Microscopy File
                      </p>
                      <p
                        className="text-sm font-semibold text-neutral-50 truncate"
                        title={selectionLabel("microscopy", "No file selected")}
                      >
                        {selectionLabel("microscopy", "No file selected")}
                      </p>
                      <p className="text-xs text-neutral-400">
                        Supports ND2 / CZI / OME-TIFF
                      </p>
                      {loadingMetadata && (
                        <p className="text-xs text-neutral-500">
                          Loading metadata...
                        </p>
                      )}
                      {metadata && (
                        <div className="mt-2 grid grid-cols-2 gap-2 text-[11px] text-neutral-300">
                          <span>
                            Channels:{" "}
                            {metadata.n_channels ?? channelNames.length}
                          </span>
                          <span>FOVs: {metadata.n_fovs ?? "?"}</span>
                          <span>Frames: {metadata.n_frames ?? "?"}</span>
                          <span>Time: {metadata.time_units || "unknown"}</span>
                        </div>
                      )}
                    </div>
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={isProcessing}
                      onClick={() =>
                        openPicker({
                          key: "microscopy",
                          title: "Choose microscopy file",
                          description: "Select an ND2 / CZI / OME-TIFF file",
                          filterExtensions: [
                            ".nd2",
                            ".czi",
                            ".ome.tif",
                            ".ome.tiff",
                            ".tif",
                            ".tiff",
                          ],
                        })
                      }
                    >
                      <Folder className="mr-2 h-3 w-3" />
                      Browse
                    </Button>
                  </div>
                </div>

                {/* Channel Configuration */}
                <ChannelConfiguration
                  channelNames={channelNames}
                  availablePhaseFeatures={availablePhaseFeatures}
                  availableFlFeatures={availableFlFeatures}
                  phaseChannel={phaseChannel}
                  setPhaseChannel={setPhaseChannel}
                  pcFeaturesSelected={pcFeaturesSelected}
                  togglePcFeature={togglePcFeature}
                  flChannelSelection={flChannelSelection}
                  setFlChannelSelection={setFlChannelSelection}
                  flFeatureSelection={flFeatureSelection}
                  setFlFeatureSelection={setFlFeatureSelection}
                  flMapping={flMapping}
                  addFlMapping={addFlMapping}
                  removeFlMapping={removeFlMapping}
                  isProcessing={isProcessing}
                />
              </div>

              {/* Output Section */}
              <div className="space-y-6">
                <div className="rounded-xl border border-neutral-800 bg-neutral-900 p-4 space-y-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1">
                      <p className="text-sm font-semibold text-neutral-50">
                        Output
                      </p>
                      <p className="text-xs text-neutral-400">
                        Destination & Parameters
                      </p>
                    </div>
                  </div>

                  {/* Output Directory */}
                  <div className="rounded-lg border border-dashed border-neutral-700 bg-neutral-900 p-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <p className="text-xs uppercase tracking-[0.2em] text-neutral-400">
                          Save Directory
                        </p>
                        <p
                          className="text-sm font-semibold text-neutral-50 truncate"
                          title={selectionLabel(
                            "processingOutput",
                            "No directory selected"
                          )}
                        >
                          {selectionLabel(
                            "processingOutput",
                            "No directory selected"
                          )}
                        </p>
                      </div>
                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={isProcessing}
                        onClick={() =>
                          openPicker({
                            key: "processingOutput",
                            title: "Choose output directory",
                            description: "Select the processing output folder",
                            directory: true,
                          })
                        }
                      >
                        <Folder className="mr-2 h-3 w-3" />
                        Browse
                      </Button>
                    </div>
                  </div>

                  <WorkflowParametersPanel
                    parameters={parameters}
                    onChange={handleParameterChange}
                    manualMode={manualMode}
                    onManualModeChange={setManualMode}
                    isProcessing={isProcessing}
                  />

                  <WorkflowStatus
                    statusMessage={statusMessage}
                    currentJob={currentJob}
                    isProcessing={isProcessing}
                    onStart={handleStartWorkflow}
                    onCancel={cancelWorkflow}
                  />
                </div>
              </div>
            </div>
          </section>

          {/* Merge Section */}
          <section className="rounded-2xl border border-neutral-900 bg-neutral-900 p-6 shadow-sm space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-2xl font-semibold uppercase tracking-[0.12em] text-neutral-50">
                Merge
              </h2>
              {isMerging && (
                <Badge
                  variant="secondary"
                  className="bg-green-500/20 text-green-200 hover:bg-green-500/20"
                >
                  Merging...
                </Badge>
              )}
            </div>

            <div className="space-y-4">
              <SampleManager
                samples={samples}
                addSample={addSample}
                removeSample={removeSample}
                updateSample={updateSample}
                onLoadYaml={openLoadYamlPicker}
                onSaveYaml={openSaveYamlPicker}
              />

              {/* Merge Samples */}
              <div className="rounded-xl border border-neutral-800 bg-neutral-900 p-4 space-y-3">
                <div className="space-y-1">
                  <p className="text-sm font-semibold text-neutral-50">
                    Merge Samples
                  </p>
                  <p className="text-xs text-neutral-400">Combine results</p>
                </div>

                <div className="space-y-3 text-sm text-neutral-200">
                  <div className="space-y-1">
                    <div className="flex items-center justify-between text-xs text-neutral-400">
                      <span>Sample YAML</span>
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-6 text-[10px]"
                        disabled={isMerging}
                        onClick={() =>
                          openPicker({
                            key: "sampleYaml",
                            title: "Choose sample.yaml",
                            description:
                              "Select a samples YAML that defines FOV assignments",
                            filterExtensions: [".yaml", ".yml"],
                          })
                        }
                      >
                        Browse
                      </Button>
                    </div>
                    <div className="rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-neutral-300 truncate text-xs">
                      {selections.sampleYaml || "sample.yaml (unselected)"}
                    </div>
                  </div>

                  <div className="space-y-1">
                    <div className="flex items-center justify-between text-xs text-neutral-400">
                      <span>Processed FOVs Folder</span>
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-6 text-[10px]"
                        disabled={isMerging}
                        onClick={() =>
                          openPicker({
                            key: "inputDir",
                            title: "Choose folder of processed FOVs",
                            description:
                              "Select the folder containing fov_000, fov_001, etc.",
                            directory: true,
                          })
                        }
                      >
                        Browse
                      </Button>
                    </div>
                    <div className="rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-neutral-300 truncate text-xs">
                      {selections.inputDir || "Input directory (unselected)"}
                    </div>
                  </div>

                  <div className="space-y-1">
                    <div className="flex items-center justify-between text-xs text-neutral-400">
                      <span>Output Folder</span>
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-6 text-[10px]"
                        disabled={isMerging}
                        onClick={() =>
                          openPicker({
                            key: "mergeOutput",
                            title: "Choose merge output folder",
                            description:
                              "Select where merged CSVs should be written",
                            directory: true,
                          })
                        }
                      >
                        Browse
                      </Button>
                    </div>
                    <div className="rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-neutral-300 truncate text-xs">
                      {selections.mergeOutput || "/output/path (unselected)"}
                    </div>
                  </div>

                  <Button
                    className="w-full mt-2"
                    onClick={runMerge}
                    disabled={isMerging}
                  >
                    {isMerging ? "Merging..." : "Run Merge"}
                  </Button>
                </div>
              </div>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
