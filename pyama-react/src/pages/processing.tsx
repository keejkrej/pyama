import { useState, useRef, useEffect } from "react";
import {
  Card,
  Button,
  Input,
  NumberInput,
  Checkbox,
  Select,
  Table,
  TableHeader,
  TableRow,
  TableCell,
  FilePicker,
  Section,
  Badge,
} from "../components/ui";
import { api } from "../lib/api";
import type { TaskResponse } from "../lib/api";

interface FlChannelEntry {
  channel: number;
  feature: string;
}

interface SchemaProperty {
  type: string;
  default?: unknown;
  description?: string;
}

export function ProcessingPage() {
  const [microscopyFile, setMicroscopyFile] = useState("");
  const [phaseContrastChannel, setPhaseContrastChannel] = useState(0);
  const [flEntries, setFlEntries] = useState<FlChannelEntry[]>([
    { channel: 1, feature: "intensity_total" },
  ]);
  const [outputDir, setOutputDir] = useState("");
  const [manualParams, setManualParams] = useState(true);
  const [paramsSchema, setParamsSchema] = useState<Record<
    string,
    SchemaProperty
  > | null>(null);
  const [schemaLoading, setSchemaLoading] = useState(true);
  const [params, setParams] = useState<Record<string, unknown>>({});
  const tooltipRef = useRef<HTMLDivElement>(null);
  const iconRef = useRef<SVGSVGElement>(null);

  // Task state - restore from localStorage on mount
  const [taskId, setTaskId] = useState<string | null>(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("pyama_current_task_id");
    }
    return null;
  });
  const [taskStatus, setTaskStatus] = useState<TaskResponse | null>(null);
  const [isPolling, setIsPolling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Persist taskId to localStorage
  useEffect(() => {
    if (taskId) {
      localStorage.setItem("pyama_current_task_id", taskId);
    } else {
      localStorage.removeItem("pyama_current_task_id");
    }
  }, [taskId]);

  // On mount, check if we have a task to resume
  useEffect(() => {
    if (taskId && !taskStatus) {
      // Fetch current status and resume polling if still running
      api
        .getTask(taskId)
        .then((task) => {
          setTaskStatus(task);
          if (task.status === "pending" || task.status === "running") {
            setIsPolling(true);
          }
        })
        .catch(() => {
          // Task not found, clear it
          setTaskId(null);
        });
    }
  }, []);

  // Fetch config schema on mount
  useEffect(() => {
    api
      .getConfigSchema()
      .then((schema) => {
        const schemaAny = schema as any;
        // Handle $ref - Pydantic uses $defs for nested models
        let paramsProps = schemaAny?.properties?.params?.properties;
        if (!paramsProps && schemaAny?.properties?.params?.$ref) {
          // Dereference: "$ref": "#/$defs/ProcessingParamsSchema"
          const refPath = schemaAny.properties.params.$ref;
          const refName = refPath.split("/").pop();
          paramsProps = schemaAny?.$defs?.[refName]?.properties;
        }
        if (paramsProps) {
          setParamsSchema(paramsProps);
          // Initialize params with schema defaults
          const defaults: Record<string, unknown> = {};
          for (const [key, prop] of Object.entries(paramsProps)) {
            if ((prop as SchemaProperty).default !== undefined) {
              defaults[key] = (prop as SchemaProperty).default;
            }
          }
          setParams(defaults);
        }
      })
      .catch((err) => console.warn("Failed to fetch config schema:", err))
      .finally(() => setSchemaLoading(false));
  }, []);

  // Poll for task updates
  useEffect(() => {
    if (!isPolling || !taskId) return;

    const interval = setInterval(async () => {
      try {
        const task = await api.getTask(taskId);
        setTaskStatus(task);
        if (
          task.status === "completed" ||
          task.status === "failed" ||
          task.status === "cancelled"
        ) {
          setIsPolling(false);
        }
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to fetch task status",
        );
        setIsPolling(false);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [isPolling, taskId]);

  const handleStart = async () => {
    setError(null);
    try {
      // Build config from current state
      const config = {
        channels: {
          pc: { [phaseContrastChannel]: ["area"] },
          fl: Object.fromEntries(
            flEntries.map((entry) => [entry.channel, [entry.feature]]),
          ),
        },
        params: manualParams ? params : {},
      };

      // Create fake task for testing (set to true for 60-second simulation)
      const task = await api.createTask(microscopyFile, config, true);
      setTaskId(task.id);
      setTaskStatus(task);
      setIsPolling(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create task");
    }
  };

  const handleCancel = async () => {
    if (!taskId) return;
    try {
      await api.cancelTask(taskId);
      setIsPolling(false);
      setTaskId(null);
      setTaskStatus(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to cancel task");
    }
  };

  const handleAddFluorescence = () => {
    setFlEntries([...flEntries, { channel: 0, feature: "intensity_total" }]);
  };

  const handleRemoveFluorescence = () => {
    if (flEntries.length > 0) {
      setFlEntries(flEntries.slice(0, -1));
    }
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
        <Card
          title="Input"
          className="h-full flex flex-col"
          bodyClassName="flex-1 flex flex-col"
        >
          <div className="flex-1 flex flex-col">
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
                    onFileSelect={(files) => {
                      if (files && files.length > 0) {
                        setMicroscopyFile(files[0].name);
                      }
                    }}
                    accept=".nd2"
                    buttonText="Browse"
                  />
                </div>
                <div className="mt-1.5 p-3 bg-card rounded-lg border border-dashed border-border min-h-[50px] flex items-center justify-center">
                  <p className="text-xs text-muted-foreground">
                    Microscopy Metadata
                  </p>
                </div>
              </div>
            </Section>

            <div className="my-4 border-t border-border"></div>

            <Section title="Channels">
              <div className="space-y-2.5">
                <div>
                  <label className="block text-xs font-medium mb-1.5 text-foreground">
                    Phase Contrast
                  </label>
                  <NumberInput
                    value={phaseContrastChannel}
                    onChange={setPhaseContrastChannel}
                    min={0}
                    className="w-full"
                  />
                  <div className="mt-1.5 p-3 bg-card rounded-lg border border-dashed border-border min-h-[50px] flex items-center justify-center">
                    <p className="text-xs text-muted-foreground">
                      Phase Contrast Features
                    </p>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium mb-1.5 text-foreground">
                    Fluorescence
                  </label>
                  <div className="space-y-2 mb-2">
                    {flEntries.map((entry, idx) => (
                      <div key={idx} className="flex gap-2">
                        <NumberInput
                          value={entry.channel}
                          onChange={(v) => {
                            const updated = [...flEntries];
                            updated[idx] = { ...entry, channel: v };
                            setFlEntries(updated);
                          }}
                          min={0}
                          className="w-20"
                        />
                        <Select
                          value={entry.feature}
                          onChange={(e) => {
                            const updated = [...flEntries];
                            updated[idx] = {
                              ...entry,
                              feature: e.currentTarget.value,
                            };
                            setFlEntries(updated);
                          }}
                          options={[
                            {
                              value: "intensity_total",
                              label: "Intensity Total",
                            },
                            { value: "particle_num", label: "Particle Num" },
                          ]}
                          className="flex-1"
                        />
                      </div>
                    ))}
                  </div>
                  <div className="mt-1.5 p-3 bg-card rounded-lg border border-dashed border-border min-h-[50px] flex items-center justify-center">
                    <p className="text-xs text-muted-foreground">
                      Fluorescence Features
                    </p>
                  </div>
                </div>
              </div>
            </Section>

            <div className="mt-4 grid grid-cols-2 gap-2">
              <Button onClick={handleAddFluorescence} variant="secondary">
                Add
              </Button>
              <Button
                variant="secondary"
                onClick={handleRemoveFluorescence}
                disabled={flEntries.length === 0}
              >
                Remove
              </Button>
            </div>
          </div>
        </Card>

        {/* Middle Column: Output */}
        <Card
          title="Output"
          className="h-full flex flex-col"
          bodyClassName="flex-1 flex flex-col"
        >
          <div className="flex-1 flex flex-col">
            <Section title="Save Directory">
              <div className="flex items-center gap-2">
                <Input
                  placeholder="Select output directory"
                  value={outputDir}
                  onChange={(e) => setOutputDir(e.currentTarget.value)}
                  className="flex-1"
                  readOnly
                />
                <FilePicker
                  onFileSelect={(files) => {
                    if (files && files.length > 0) {
                      // Extract directory path from file path
                      const path =
                        (files[0] as any).webkitRelativePath || files[0].name;
                      const dirPath = path.substring(0, path.lastIndexOf("/"));
                      setOutputDir(dirPath || "Selected");
                    }
                  }}
                  directory
                  buttonText="Browse"
                />
              </div>
            </Section>

            <div className="my-4 border-t border-border"></div>

            <Section title="Parameters">
              <div className="mb-3">
                <Checkbox
                  label="Set parameters manually"
                  checked={manualParams}
                  onChange={(e) => setManualParams(e.currentTarget.checked)}
                />
              </div>

              <Table className="table-fixed">
                <TableHeader>
                  <TableRow>
                    <TableCell header className="border-r border-border w-1/2">
                      Name
                    </TableCell>
                    <TableCell header className="w-1/2">
                      Value
                    </TableCell>
                  </TableRow>
                </TableHeader>
                <tbody>
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
                </tbody>
              </Table>
            </Section>

            <div className="my-4 border-t border-border"></div>

            {/* Task Status Display */}
            {(taskStatus || error) && (
              <Section title="Status">
                <div className="space-y-2">
                  {error && (
                    <div className="p-2 bg-destructive/10 border border-destructive rounded text-sm text-destructive">
                      {error}
                    </div>
                  )}
                  {taskStatus && (
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-muted-foreground">
                          Status:
                        </span>
                        <Badge
                          variant={
                            taskStatus.status === "completed"
                              ? "success"
                              : taskStatus.status === "failed"
                                ? "destructive"
                                : taskStatus.status === "running"
                                  ? "info"
                                  : "muted"
                          }
                        >
                          {taskStatus.status}
                        </Badge>
                      </div>
                      {taskStatus.progress && (
                        <>
                          <div className="w-full bg-muted rounded-full h-2">
                            <div
                              className="bg-primary h-2 rounded-full transition-all duration-300"
                              style={{
                                width: `${taskStatus.progress.percent || 0}%`,
                              }}
                            />
                          </div>
                          <p className="text-xs text-muted-foreground">
                            {taskStatus.progress.message ||
                              `${taskStatus.progress.percent?.toFixed(0) || 0}%`}
                          </p>
                        </>
                      )}
                      {taskStatus.error_message && (
                        <p className="text-xs text-destructive">
                          {taskStatus.error_message}
                        </p>
                      )}
                      {taskStatus.status === "completed" &&
                        taskStatus.result && (
                          <p className="text-xs text-success">
                            Output: {taskStatus.result.output_dir}
                          </p>
                        )}
                    </div>
                  )}
                </div>
              </Section>
            )}

            {(taskStatus || error) && (
              <div className="my-4 border-t border-border"></div>
            )}

            <div className="mt-4 flex gap-2">
              <Button
                variant="default"
                className="flex-1"
                onClick={handleStart}
                disabled={isPolling || !microscopyFile}
              >
                {isPolling ? "Processing..." : "Start"}
              </Button>
              <Button
                variant="secondary"
                className="flex-1"
                onClick={handleCancel}
                disabled={!isPolling}
              >
                Cancel
              </Button>
            </div>
          </div>
        </Card>

        {/* Right Column: Samples */}
        <Card
          title="Samples"
          className="h-full flex flex-col"
          bodyClassName="flex-1 flex flex-col"
        >
          <div className="flex-1 flex flex-col">
            <Section title="Assign FOVs">
              <div className="relative">
                <Table className="table-fixed">
                  <TableHeader>
                    <TableRow>
                      <TableCell
                        header
                        className="border-r border-border w-1/2"
                      >
                        Name
                      </TableCell>
                      <TableCell header className="w-1/2">
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
                      </TableCell>
                    </TableRow>
                  </TableHeader>
                  <tbody>
                    <TableRow>
                      <TableCell
                        colSpan={2}
                        className="text-center py-6 text-muted-foreground border-r-0"
                      >
                        No samples assigned
                      </TableCell>
                    </TableRow>
                  </tbody>
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
                <div>
                  <label className="block text-xs font-medium mb-1.5 text-foreground">
                    Sample YAML
                  </label>
                  <div className="flex items-center gap-2">
                    <Input
                      placeholder="Select sample YAML file"
                      className="flex-1"
                    />
                    <FilePicker onFileSelect={() => {}} buttonText="Browse" />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium mb-1.5 text-foreground">
                    Folder of processed FOVs
                  </label>
                  <div className="flex items-center gap-2">
                    <Input placeholder="Select folder" className="flex-1" />
                    <FilePicker onFileSelect={() => {}} buttonText="Browse" />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium mb-1.5 text-foreground">
                    Output folder
                  </label>
                  <div className="flex items-center gap-2">
                    <Input
                      placeholder="Select output folder"
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
          </div>
        </Card>
      </div>
    </div>
  );
}
