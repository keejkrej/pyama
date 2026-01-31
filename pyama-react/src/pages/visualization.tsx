import { useState } from "react";
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
import { useVisualizationStore } from "../stores";

export function VisualizationPage() {
  // Persisted state from zustand store
  const {
    dataFolder,
    setDataFolder,
    fov,
    setFov,
    selectedFeature,
    setSelectedFeature,
    currentPage,
    setCurrentPage,
  } = useVisualizationStore();

  // Local state
  const [isViewerOpen, setIsViewerOpen] = useState(false);
  const [totalFovs] = useState(0);
  const [totalPages] = useState(1);

  const features = [
    { value: "intensity_total", label: "Intensity Total" },
    { value: "area", label: "Area" },
    { value: "circularity", label: "Circularity" },
  ];

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
                    onFileSelect={(paths) => {
                      if (paths.length > 0) {
                        setDataFolder(paths[0]);
                      }
                    }}
                    directory
                    buttonText="Browse"
                  />
                </div>
                <div className="mt-1.5 p-3 bg-card rounded-lg border border-dashed border-border min-h-[50px] flex items-center justify-center">
                  <p className="text-xs text-muted-foreground">
                    Data Folder Metadata
                  </p>
                </div>
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
                      max={Math.max(0, totalFovs - 1)}
                      className="flex-1"
                    />
                    {totalFovs > 0 && (
                      <span className="text-xs text-muted-foreground whitespace-nowrap">
                        / {totalFovs}
                      </span>
                    )}
                  </div>
                </div>
                <Button
                  variant="default"
                  className="w-full"
                  disabled={totalFovs === 0}
                  onClick={() => setIsViewerOpen(true)}
                >
                  Start
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
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select feature" />
                  </SelectTrigger>
                  <SelectContent>
                    {features.map((f) => (
                      <SelectItem key={f.value} value={f.value}>
                        {f.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </Section>

            <div className="my-4 border-t border-border"></div>

            <Section title="Plot">
              <div className="p-4 bg-card rounded-lg border border-dashed border-border min-h-[120px] flex items-center justify-center">
                <div className="text-center">
                  <svg
                    className="w-10 h-10 mx-auto text-muted-foreground/40 mb-2"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={1.5}
                      d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                    />
                  </svg>
                  <p className="text-xs text-muted-foreground">
                    Trace plot will appear here
                  </p>
                </div>
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
            <Section title="Traces">
              <div className="p-4 bg-card rounded-lg border border-dashed border-border min-h-[100px] flex items-center justify-center">
                <p className="text-xs text-muted-foreground">
                  No traces selected
                </p>
              </div>
            </Section>

            <div className="my-4 border-t border-border"></div>

            <Section title="Navigation">
              <div className="space-y-2.5">
                <div className="p-3 bg-card rounded-lg border border-dashed border-border min-h-[40px] flex items-center justify-center">
                  <p className="text-xs text-muted-foreground">
                    Navigation content
                  </p>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">
                    Page {currentPage} of {totalPages}
                  </span>
                  <div className="flex gap-2">
                    <Button
                      variant="secondary"
                      onClick={() =>
                        setCurrentPage(Math.max(1, currentPage - 1))
                      }
                      disabled={currentPage <= 1}
                    >
                      Previous
                    </Button>
                    <Button
                      variant="secondary"
                      onClick={() =>
                        setCurrentPage(Math.min(totalPages, currentPage + 1))
                      }
                      disabled={currentPage >= totalPages}
                    >
                      Next
                    </Button>
                    <Button variant="secondary" disabled>
                      Save
                    </Button>
                  </div>
                </div>
              </div>
            </Section>
          </CardContent>
        </Card>
      </div>

      {/* Image Viewer Popup */}
      <ImageViewer
        isOpen={isViewerOpen}
        onClose={() => setIsViewerOpen(false)}
      />
    </div>
  );
}
