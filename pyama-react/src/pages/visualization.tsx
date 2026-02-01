import { useState, useEffect } from "react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  Button,
  NumberInput,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  FilePicker,
  Section,
  Input,
  Label,
} from "../components/ui";
import { ImageViewer } from "../components/popups/image-viewer";
import { TracePlot } from "../components/visualization/trace-plot";
import { TraceList } from "../components/visualization/trace-list";
import { useVisualizationStore } from "../stores";

export function VisualizationPage() {
  const {
    dataFolder,
    setDataFolder,
    fov,
    setFov,
    selectedFeature,
    setSelectedFeature,
    currentPage,
    setCurrentPage,
    projectData,
    traces,
    totalTraces,
    availableFeatures,
    loading,
    error,
    loadProject,
    loadTraces,
    toggleTraceQuality,
    saveQualityUpdates,
    clear,
  } = useVisualizationStore();

  const [isViewerOpen, setIsViewerOpen] = useState(false);
  const [activeTraceId, setActiveTraceId] = useState<string | null>(null);
  const [selectedChannels, setSelectedChannels] = useState<string[]>([]);

  // Calculate pagination
  const pageSize = 10;
  const totalPages = Math.max(1, Math.ceil(totalTraces / pageSize));

  // Load project when dataFolder changes (if different from current project)
  useEffect(() => {
    if (dataFolder && (!projectData || projectData.project_path !== dataFolder)) {
      loadProject(dataFolder).catch(console.error);
    }
  }, [dataFolder]);

  // Load traces when FOV or page changes
  useEffect(() => {
    if (projectData) {
      loadTraces(currentPage).catch(console.error);
    }
  }, [projectData, fov, currentPage]);

  // Extract available channels from project data
  const availableChannels = projectData
    ? Object.keys(projectData.fov_data[fov] || {}).filter(
        (k) => !k.startsWith("traces")
      )
    : [];

  const handleLoadFolder = (paths: string[]) => {
    if (paths.length > 0) {
      clear();
      setDataFolder(paths[0]);
    }
  };

  const handleStartVisualization = () => {
    if (!projectData || selectedChannels.length === 0) {
      return;
    }
    setIsViewerOpen(true);
  };

  const handleTraceSelect = (cellId: string) => {
    setActiveTraceId(cellId === activeTraceId ? null : cellId);
  };

  const handlePreviousPage = () => {
    if (currentPage > 0) {
      setCurrentPage(currentPage - 1);
      setActiveTraceId(null);
    }
  };

  const handleNextPage = () => {
    if (currentPage < totalPages - 1) {
      setCurrentPage(currentPage + 1);
      setActiveTraceId(null);
    }
  };

  const handleSave = async () => {
    await saveQualityUpdates();
  };

  return (
    <div className="p-5">
      <div className="mb-5">
        <h1 className="text-lg font-semibold mb-1.5 text-foreground-bright">
          Visualization
        </h1>
        <p className="text-xs text-muted-foreground">
          Load and visualize processed microscopy data
        </p>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-destructive/10 border border-destructive/20 rounded text-destructive text-xs">
          {error}
        </div>
      )}

      <div className="grid grid-cols-3 gap-4 items-stretch">
        {/* Left Column: Load Data Folder */}
        <Card className="h-full flex flex-col">
          <CardHeader>
            <CardTitle>Load Data Folder</CardTitle>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col">
            <Section title="Data Folder">
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Input
                    placeholder="No folder selected"
                    value={dataFolder}
                    onChange={(e) => setDataFolder(e.currentTarget.value)}
                    className="flex-1"
                    readOnly
                  />
                  <FilePicker
                    onFileSelect={handleLoadFolder}
                    folder
                    buttonText="Browse"
                  />
                </div>
                {projectData && (
                  <div className="mt-1.5 p-3 bg-card rounded-lg border border-border text-xs">
                    <div className="space-y-1">
                      <p>
                        <span className="font-medium">Project:</span>{" "}
                        {projectData.base_name || "Unknown"}
                      </p>
                      <p>
                        <span className="font-medium">FOVs:</span>{" "}
                        {projectData.n_fov}
                      </p>
                      {projectData.channels && (
                        <p>
                          <span className="font-medium">Channels:</span>{" "}
                          {Object.keys(projectData.channels).length}
                        </p>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </Section>

            <div className="my-4 border-t border-border"></div>

            <Section title="Visualization">
              <div className="space-y-2.5">
                <div className="space-y-1">
                  <Label>FOV</Label>
                  <div className="flex items-center gap-2">
                    <NumberInput
                      value={fov}
                      onChange={setFov}
                      min={0}
                      max={Math.max(0, (projectData?.n_fov || 1) - 1)}
                      className="flex-1"
                      disabled={!projectData}
                    />
                    {projectData && projectData.n_fov > 0 && (
                      <span className="text-xs text-muted-foreground whitespace-nowrap">
                        / {projectData.n_fov - 1}
                      </span>
                    )}
                  </div>
                </div>

                {availableChannels.length > 0 && (
                  <div className="space-y-1">
                    <Label>Channels</Label>
                    <div className="space-y-1 max-h-32 overflow-y-auto">
                      {availableChannels.map((channel) => (
                        <label
                          key={channel}
                          className="flex items-center gap-2 text-xs cursor-pointer hover:bg-accent p-1 rounded"
                        >
                          <input
                            type="checkbox"
                            checked={selectedChannels.includes(channel)}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setSelectedChannels([...selectedChannels, channel]);
                              } else {
                                setSelectedChannels(
                                  selectedChannels.filter((c) => c !== channel)
                                );
                              }
                            }}
                            className="w-3 h-3"
                          />
                          <span>{channel}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                )}

                <Button
                  variant="default"
                  className="w-full"
                  disabled={!projectData || selectedChannels.length === 0 || loading}
                  onClick={handleStartVisualization}
                >
                  {loading ? "Loading..." : "Start Visualization"}
                </Button>
              </div>
            </Section>
          </CardContent>
        </Card>

        {/* Middle Column: Trace Plot */}
        <Card className="h-full flex flex-col">
          <CardHeader>
            <CardTitle>Trace Plot</CardTitle>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col">
            <Section title="Feature Selection">
              <div className="space-y-1">
                <Label>Feature</Label>
                <Select
                  value={selectedFeature}
                  onValueChange={setSelectedFeature}
                  disabled={availableFeatures.length === 0}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select feature" />
                  </SelectTrigger>
                  <SelectContent>
                    {availableFeatures.map((feature) => (
                      <SelectItem key={feature} value={feature}>
                        {feature}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </Section>

            <div className="my-4 border-t border-border"></div>

            <Section title="Plot" className="flex-1 flex flex-col min-h-0">
              <div className="flex-1 min-h-0">
                <TracePlot
                  traces={traces}
                  selectedFeature={selectedFeature}
                  activeTraceId={activeTraceId}
                />
              </div>
            </Section>
          </CardContent>
        </Card>

        {/* Right Column: Trace Selection */}
        <Card className="h-full flex flex-col">
          <CardHeader>
            <CardTitle>Trace Selection</CardTitle>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col">
            <Section title="Traces" className="flex-1 flex flex-col min-h-0">
              <div className="flex-1 min-h-0">
                <TraceList
                  traces={traces}
                  activeTraceId={activeTraceId}
                  onTraceSelect={handleTraceSelect}
                  onQualityToggle={toggleTraceQuality}
                />
              </div>
            </Section>

            <div className="my-4 border-t border-border"></div>

            <Section title="Navigation">
              <div className="space-y-2.5">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>
                    Page {currentPage + 1} of {totalPages}
                  </span>
                  <span>{totalTraces} total traces</span>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="secondary"
                    onClick={handlePreviousPage}
                    disabled={currentPage <= 0 || loading}
                    className="flex-1"
                  >
                    Previous
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={handleNextPage}
                    disabled={currentPage >= totalPages - 1 || loading}
                    className="flex-1"
                  >
                    Next
                  </Button>
                </div>
                <Button
                  variant="secondary"
                  onClick={handleSave}
                  disabled={loading}
                  className="w-full"
                >
                  Save Inspected CSV
                </Button>
              </div>
            </Section>
          </CardContent>
        </Card>
      </div>

      {/* Image Viewer Popup */}
      <ImageViewer
        isOpen={isViewerOpen}
        onClose={() => setIsViewerOpen(false)}
        projectData={projectData}
        fov={fov}
        selectedChannels={selectedChannels}
      />
    </div>
  );
}
