import { useState, useRef, useEffect } from "react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  Button,
  Input,
  Label,
  NumberInput,
  Checkbox,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
  FilePicker,
  Section,
} from "../components/ui";
import { api } from "../lib/api";
import { useProcessingStore, type SchemaProperty } from "../stores";

export function ProcessingPage() {
  // Get persisted state from zustand store
  const {
    microscopyFile,
    setMicroscopyFile,
    microscopyMetadata,
    setMicroscopyMetadata,
    metadataLoading,
    setMetadataLoading,
    pcEntries,
    setPcEntries,
    flEntries,
    setFlEntries,
    availableFeatures,
    featuresLoading,
    outputDir,
    setOutputDir,
    manualParams,
    setManualParams,
    params,
    setParams,
    paramsSchema,
    schemaLoading,
    fetchFeatures,
    fetchSchema,
  } = useProcessingStore();

  // Local state (not persisted across tab changes)
  const tooltipRef = useRef<HTMLDivElement>(null);
  const iconRef = useRef<SVGSVGElement>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Fetch features and schema on mount (cached in store)
  useEffect(() => {
    fetchFeatures();
    fetchSchema();
  }, []);

  // Clear metadata when file path changes (but don't auto-load)
  useEffect(() => {
    if (microscopyMetadata && microscopyMetadata.file_path !== microscopyFile) {
      setMicroscopyMetadata(null);
    }
  }, [microscopyFile, microscopyMetadata]);

  // Auto-clear success message after 5 seconds
  useEffect(() => {
    if (successMessage) {
      const timer = setTimeout(() => {
        setSuccessMessage(null);
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [successMessage]);

  // Handle manual loading of microscopy metadata
  const handleLoadMicroscopy = async () => {
    if (!microscopyFile) {
      return;
    }
    setMetadataLoading(true);
    setMicroscopyMetadata(null); // Clear previous metadata
    try {
      const metadata = await api.loadMicroscopy(microscopyFile);
      setMicroscopyMetadata(metadata);
    } catch (err) {
      console.warn("Failed to load microscopy metadata:", err);
      setMicroscopyMetadata(null);
    } finally {
      setMetadataLoading(false);
    }
  };

  const handleStart = async () => {
    setSuccessMessage(null);
    try {
      // Build config from current state
      const config = {
        channels: {
          pc: Object.fromEntries(
            pcEntries.map((entry) => [entry.channel, [entry.feature]]),
          ),
          fl: Object.fromEntries(
            flEntries.map((entry) => [entry.channel, [entry.feature]]),
          ),
        },
        params: manualParams ? params : {},
      };

      // Create fake task for testing (set to true for 60-second simulation)
      await api.createTask(microscopyFile, config, true);
      setSuccessMessage("Task created successfully! Check the Dashboard to monitor progress.");
    } catch (err) {
      setSuccessMessage(
        `Failed to create task: ${err instanceof Error ? err.message : "Unknown error"}`,
      );
    }
  };

  const handleAddPhaseContrast = () => {
    const defaultFeature = availableFeatures?.phase[0];
    if (!defaultFeature) return;
    setPcEntries([...pcEntries, { channel: 0, feature: defaultFeature }]);
  };

  const handleRemovePhaseContrast = (idx: number) => {
    setPcEntries(pcEntries.filter((_, i) => i !== idx));
  };

  const handleAddFluorescence = () => {
    const defaultFeature = availableFeatures?.fluorescence[0];
    if (!defaultFeature) return;
    setFlEntries([...flEntries, { channel: 0, feature: defaultFeature }]);
  };

  const handleRemoveFluorescence = (idx: number) => {
    setFlEntries(flEntries.filter((_, i) => i !== idx));
  };

  const renderParamInput = (
    key: string,
    prop: SchemaProperty,
    value: unknown,
  ) => {
    if (prop.type === "integer" || prop.type === "number") {
      return (
        <NumberInput
          value={typeof value === "number" ? value : 0}
          onChange={(v) => setParams({ ...params, [key]: v })}
          step={prop.type === "number" ? 0.1 : 1}
        />
      );
    }
    // String (including fovs)
    return (
      <Input
        value={typeof value === "string" ? value : ""}
        onChange={(e) => setParams({ ...params, [key]: e.currentTarget.value })}
        placeholder={prop.description || ""}
      />
    );
  };

  return (
    <div className="p-5">
      <div className="mb-5">
        <h1 className="text-lg font-semibold mb-1.5 text-foreground-bright">
          Processing
        </h1>
        <p className="text-xs text-muted-foreground">
          Configure microscopy file processing and workflow parameters
        </p>
      </div>

      <div className="grid grid-cols-3 gap-4 items-stretch">
        {/* Left Column: Input */}
        <Card className="h-full flex flex-col">
          <CardHeader>
            <CardTitle>Input</CardTitle>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col">
            <Section title="Microscopy">
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Input
                    placeholder="Enter file path or browse..."
                    value={microscopyFile}
                    onChange={(e) => setMicroscopyFile(e.currentTarget.value)}
                    className="flex-1"
                  />
                  <FilePicker
                    onFileSelect={(paths) => {
                      if (paths.length > 0) {
                        setMicroscopyFile(paths[0]);
                      }
                    }}
                    accept=".nd2"
                    buttonText="Browse"
                  />
                  <Button
                    onClick={handleLoadMicroscopy}
                    disabled={!microscopyFile || metadataLoading}
                    variant="default"
                  >
                    {metadataLoading ? "Loading..." : "Load"}
                  </Button>
                </div>
                <div className="mt-1.5 p-3 bg-card rounded-lg border border-dashed border-border min-h-[50px]">
                  {metadataLoading ? (
                    <p className="text-xs text-muted-foreground text-center">
                      Loading metadata...
                    </p>
                  ) : microscopyMetadata ? (
                    <div className="text-xs space-y-1">
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">File:</span>
                        <span className="text-foreground font-medium truncate ml-2">
                          {microscopyMetadata.base_name}.{microscopyMetadata.file_type}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Dimensions:</span>
                        <span className="text-foreground">
                          {microscopyMetadata.width} × {microscopyMetadata.height}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">FOVs:</span>
                        <span className="text-foreground">
                          {microscopyMetadata.n_fovs}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Timepoints:</span>
                        <span className="text-foreground">
                          {microscopyMetadata.n_frames}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Channels:</span>
                        <span className="text-foreground">
                          {microscopyMetadata.n_channels}
                        </span>
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-muted-foreground text-center">
                      Microscopy Metadata
                    </p>
                  )}
                </div>
              </div>
            </Section>

            <div className="my-4 border-t border-border"></div>

            <Section title="Channels">
              <div className="space-y-3">
                {/* Phase Contrast Cards */}
                {pcEntries.map((entry, idx) => (
                  <div
                    key={`pc-${idx}`}
                    className="p-3 bg-card rounded-lg border border-border"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-medium text-foreground">
                        Phase Contrast
                      </span>
                      <button
                        onClick={() => handleRemovePhaseContrast(idx)}
                        className="text-muted-foreground hover:text-foreground transition-colors"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                    <div className="flex gap-2 items-start">
                      <div className="flex-1">
                        <Label className="block text-xs text-muted-foreground mb-1">Channel</Label>
                        {microscopyMetadata?.channel_names?.length ? (
                          <Select
                            value={String(entry.channel)}
                            onValueChange={(value) => {
                              const updated = [...pcEntries];
                              updated[idx] = { ...entry, channel: Number(value) };
                              setPcEntries(updated);
                            }}
                          >
                            <SelectTrigger className="w-full">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {microscopyMetadata.channel_names.map((name, i) => (
                                <SelectItem key={i} value={String(i)}>
                                  {name || `Channel ${i}`}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        ) : (
                          <NumberInput
                            value={entry.channel}
                            onChange={(v) => {
                              const updated = [...pcEntries];
                              updated[idx] = { ...entry, channel: v };
                              setPcEntries(updated);
                            }}
                            min={0}
                            className="w-full"
                          />
                        )}
                      </div>
                      <div className="flex-1">
                        <Label className="block text-xs text-muted-foreground mb-1">Feature</Label>
                        <Select
                          value={entry.feature}
                          onValueChange={(value) => {
                            const updated = [...pcEntries];
                            updated[idx] = { ...entry, feature: value };
                            setPcEntries(updated);
                          }}
                        >
                          <SelectTrigger className="w-full">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {availableFeatures?.phase.map((f) => (
                              <SelectItem key={f} value={f}>
                                {f.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                  </div>
                ))}

                {/* Fluorescence Cards */}
                {flEntries.map((entry, idx) => (
                  <div
                    key={`fl-${idx}`}
                    className="p-3 bg-card rounded-lg border border-border"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-medium text-foreground">
                        Fluorescence
                      </span>
                      <button
                        onClick={() => handleRemoveFluorescence(idx)}
                        className="text-muted-foreground hover:text-foreground transition-colors"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                    <div className="flex gap-2 items-start">
                      <div className="flex-1">
                        <Label className="block text-xs text-muted-foreground mb-1">Channel</Label>
                        {microscopyMetadata?.channel_names?.length ? (
                          <Select
                            value={String(entry.channel)}
                            onValueChange={(value) => {
                              const updated = [...flEntries];
                              updated[idx] = { ...entry, channel: Number(value) };
                              setFlEntries(updated);
                            }}
                          >
                            <SelectTrigger className="w-full">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {microscopyMetadata.channel_names.map((name, i) => (
                                <SelectItem key={i} value={String(i)}>
                                  {name || `Channel ${i}`}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        ) : (
                          <NumberInput
                            value={entry.channel}
                            onChange={(v) => {
                              const updated = [...flEntries];
                              updated[idx] = { ...entry, channel: v };
                              setFlEntries(updated);
                            }}
                            min={0}
                            className="w-full"
                          />
                        )}
                      </div>
                      <div className="flex-1">
                        <Label className="block text-xs text-muted-foreground mb-1">Feature</Label>
                        <Select
                          value={entry.feature}
                          onValueChange={(value) => {
                            const updated = [...flEntries];
                            updated[idx] = { ...entry, feature: value };
                            setFlEntries(updated);
                          }}
                        >
                          <SelectTrigger className="w-full">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {availableFeatures?.fluorescence.map((f) => (
                              <SelectItem key={f} value={f}>
                                {f.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                  </div>
                ))}

                {/* Empty state */}
                {pcEntries.length === 0 && flEntries.length === 0 && (
                  <div className="p-4 bg-card rounded-lg border border-dashed border-border text-center">
                    <p className="text-xs text-muted-foreground">
                      No channels configured. Add a channel to get started.
                    </p>
                  </div>
                )}
              </div>
            </Section>

            <div className="mt-4 grid grid-cols-2 gap-2">
              <Button
                onClick={handleAddPhaseContrast}
                variant="secondary"
                disabled={featuresLoading || !availableFeatures?.phase.length}
              >
                Add PC
              </Button>
              <Button
                onClick={handleAddFluorescence}
                variant="secondary"
                disabled={featuresLoading || !availableFeatures?.fluorescence.length}
              >
                Add FL
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Middle Column: Output */}
        <Card className="h-full flex flex-col">
          <CardHeader>
            <CardTitle>Output</CardTitle>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col">
            <Section title="Save Folder">
              <div className="flex items-center gap-2">
                <Input
                  placeholder="Select folder"
                  value={outputDir}
                  onChange={(e) => setOutputDir(e.currentTarget.value)}
                  className="flex-1"
                  readOnly
                />
                <FilePicker
                  onFileSelect={(paths) => {
                    if (paths.length > 0) {
                      setOutputDir(paths[0]);
                    }
                  }}
                  folder
                  buttonText="Browse"
                />
              </div>
            </Section>

            <div className="my-4 border-t border-border"></div>

            <Section title="Parameters">
              <div className="mb-3 flex items-center gap-2">
                <Checkbox
                  id="manual-params"
                  checked={manualParams}
                  onCheckedChange={(checked) => setManualParams(checked === true)}
                />
                <Label htmlFor="manual-params">Set parameters manually</Label>
              </div>

              <Table className="table-fixed">
                <TableHeader>
                  <TableRow>
                    <TableHead className="border-r border-border w-1/2">
                      Name
                    </TableHead>
                    <TableHead className="w-1/2">
                      Value
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {!manualParams ? (
                    <TableRow>
                      <TableCell
                        colSpan={2}
                        className="text-center py-6 text-muted-foreground border-r-0"
                      >
                        Parameters by default
                      </TableCell>
                    </TableRow>
                  ) : schemaLoading ? (
                    <TableRow>
                      <TableCell
                        colSpan={2}
                        className="text-center py-6 text-muted-foreground border-r-0"
                      >
                        Loading...
                      </TableCell>
                    </TableRow>
                  ) : !paramsSchema ? (
                    <TableRow>
                      <TableCell
                        colSpan={2}
                        className="text-center py-6 text-muted-foreground border-r-0"
                      >
                        No parameters available
                      </TableCell>
                    </TableRow>
                  ) : (
                    Object.entries(paramsSchema).map(([key, prop]) => (
                      <TableRow key={key}>
                        <TableCell className="border-r border-border">
                          {key}
                        </TableCell>
                        <TableCell>
                          {renderParamInput(key, prop, params[key])}
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </Section>

            <div className="my-4 border-t border-border"></div>

            {/* Success Message */}
            {successMessage && (
              <Section title="Status">
                <div
                  className={`p-3 rounded text-sm ${
                    successMessage.startsWith("Failed")
                      ? "bg-destructive/10 border border-destructive text-destructive"
                      : "bg-success/10 border border-success text-success"
                  }`}
                >
                  {successMessage}
                </div>
              </Section>
            )}

            {successMessage && (
              <div className="my-4 border-t border-border"></div>
            )}

            <div className="mt-4">
              <Button
                variant="default"
                className="w-full"
                onClick={handleStart}
                disabled={!microscopyFile}
              >
                Start
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Right Column: Samples */}
        <Card className="h-full flex flex-col">
          <CardHeader>
            <CardTitle>Samples</CardTitle>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col">
            <Section title="Assign FOVs">
              <div className="relative">
                <Table className="table-fixed">
                  <TableHeader>
                    <TableRow>
                      <TableHead className="border-r border-border w-1/2">
                        Name
                      </TableHead>
                      <TableHead className="w-1/2">
                        <div className="flex items-center gap-1.5">
                          <span>FOV</span>
                          <div className="relative group">
                            <svg
                              ref={iconRef}
                              className="w-4 h-4 text-muted-foreground cursor-help"
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                              onMouseEnter={() => {
                                if (tooltipRef.current && iconRef.current) {
                                  const iconRect =
                                    iconRef.current.getBoundingClientRect();
                                  tooltipRef.current.style.left = `${iconRect.left + iconRect.width / 2}px`;
                                  tooltipRef.current.style.top = `${iconRect.top - 8}px`;
                                  tooltipRef.current.style.transform =
                                    "translate(-50%, -100%)";
                                  tooltipRef.current.classList.remove(
                                    "opacity-0",
                                    "invisible",
                                  );
                                  tooltipRef.current.classList.add(
                                    "opacity-100",
                                    "visible",
                                  );
                                }
                              }}
                              onMouseLeave={() => {
                                if (tooltipRef.current) {
                                  tooltipRef.current.classList.add(
                                    "opacity-0",
                                    "invisible",
                                  );
                                  tooltipRef.current.classList.remove(
                                    "opacity-100",
                                    "visible",
                                  );
                                }
                              }}
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                              />
                            </svg>
                          </div>
                        </div>
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    <TableRow>
                      <TableCell
                        colSpan={2}
                        className="text-center py-6 text-muted-foreground border-r-0"
                      >
                        No samples assigned
                      </TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
                {/* Tooltip positioned outside table overflow using fixed positioning */}
                <div
                  ref={tooltipRef}
                  className="fixed px-3 py-2 rounded-lg shadow-lg text-sm whitespace-nowrap opacity-0 invisible pointer-events-none transition-all duration-200"
                  style={{
                    backgroundColor: "var(--color-popover)",
                    color: "var(--color-popover-foreground)",
                    border: "1px solid var(--color-border)",
                    zIndex: 9999,
                  }}
                >
                  Format: 0-5, 7, 9-11
                  <div
                    className="absolute left-1/2 -translate-x-1/2 top-full w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent"
                    style={{ borderTopColor: "var(--color-border)" }}
                  ></div>
                </div>
              </div>
              <div className="mt-4 grid grid-cols-2 gap-2">
                <Button variant="secondary" onClick={() => {}}>
                  Add
                </Button>
                <Button variant="secondary" onClick={() => {}} disabled>
                  Remove
                </Button>
                <Button variant="secondary" onClick={() => {}}>
                  Load
                </Button>
                <Button variant="secondary" onClick={() => {}}>
                  Save
                </Button>
              </div>
            </Section>

            <div className="my-4 border-t border-border"></div>

            <Section title="Merge Samples">
              <div className="space-y-2.5">
                <div className="space-y-1">
                  <Label>Sample YAML</Label>
                  <div className="flex items-center gap-2">
                    <Input
                      placeholder="Select file"
                      className="flex-1"
                    />
                    <FilePicker onFileSelect={() => {}} buttonText="Browse" />
                  </div>
                </div>

                <div className="space-y-1">
                  <Label>Folder of processed FOVs</Label>
                  <div className="flex items-center gap-2">
                    <Input placeholder="Select folder" className="flex-1" />
                    <FilePicker onFileSelect={() => {}} buttonText="Browse" />
                  </div>
                </div>

                <div className="space-y-1">
                  <Label>Output folder</Label>
                  <div className="flex items-center gap-2">
                    <Input
                      placeholder="Select folder"
                      className="flex-1"
                    />
                    <FilePicker onFileSelect={() => {}} buttonText="Browse" />
                  </div>
                </div>

                <div className="mt-4">
                  <Button
                    variant="default"
                    className="w-full"
                    onClick={() => {}}
                  >
                    Merge
                  </Button>
                </div>
              </div>
            </Section>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
