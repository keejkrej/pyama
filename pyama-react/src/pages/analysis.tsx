import { useState } from "react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  Button,
  NumberInput,
  FilePicker,
  Section,
  Input,
  Label,
} from "../components/ui";
import { AnalysisWindow } from "../components/popups/analysis-window";
import { useAnalysisStore } from "../stores";

export function AnalysisPage() {
  // Persisted state from zustand store
  const { dataFolder, setDataFolder, frameInterval, setFrameInterval } =
    useAnalysisStore();

  // Local state
  const [isAnalysisOpen, setIsAnalysisOpen] = useState(false);
  const [timeMapping] = useState<string>("none");
  const [samples] = useState<string[]>([]);

  return (
    <div className="p-5">
      <div className="mb-5">
        <h1 className="text-lg font-semibold mb-1.5 text-foreground-bright">
          Analysis
        </h1>
        <p className="text-xs text-muted-foreground">
          Load samples and perform statistical analysis
        </p>
      </div>

      <div className="grid grid-cols-3 gap-4 items-stretch">
        {/* Left Column: Load Data */}
        <Card className="h-full flex flex-col">
          <CardHeader>
            <CardTitle>Load Data</CardTitle>
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
                    folder
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

            <Section title="Time Configuration">
              <div className="space-y-2.5">
                <div className="space-y-1">
                  <Label>Frame interval</Label>
                  <div className="flex items-center gap-2">
                    <NumberInput
                      value={frameInterval}
                      onChange={setFrameInterval}
                      min={0}
                      step={0.1}
                      className="flex-1"
                    />
                    <span className="text-xs text-muted-foreground whitespace-nowrap">
                      min
                    </span>
                  </div>
                </div>
                <div className="space-y-1">
                  <Label>Time mapping</Label>
                  <div className="p-3 bg-card rounded-lg border border-dashed border-border">
                    <p className="text-xs text-muted-foreground">
                      {timeMapping === "none"
                        ? "No time mapping file"
                        : timeMapping}
                    </p>
                  </div>
                </div>
              </div>
            </Section>

            <div className="my-4 border-t border-border"></div>

            <div className="mt-4 flex gap-2">
              <Button variant="default" className="flex-1" onClick={() => {}}>
                Load
              </Button>
              <Button variant="secondary" className="flex-1" onClick={() => {}}>
                Clear
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Middle Column: Samples */}
        <Card className="h-full flex flex-col">
          <CardHeader>
            <CardTitle>Samples</CardTitle>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col">
            <Section title="Loaded Samples">
              <div className="p-4 bg-card rounded-lg border border-dashed border-border min-h-[180px] flex flex-col">
                {samples.length === 0 ? (
                  <div className="flex-1 flex items-center justify-center">
                    <div className="text-center">
                      <svg
                        className="w-10 h-10 mx-auto text-muted-foreground/50 mb-2"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={1.5}
                          d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                        />
                      </svg>
                      <p className="text-xs text-muted-foreground">
                        No samples loaded
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        Load data folder to see samples
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-1.5">
                    {samples.map((sample, idx) => (
                      <div
                        key={idx}
                        className="p-2.5 bg-background rounded-md border border-border hover:border-foreground/20 transition-all cursor-pointer"
                      >
                        <p className="text-xs text-foreground">{sample}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </Section>

            <div className="my-4 border-t border-border"></div>

            <Section title="Actions">
              <div className="space-y-2">
                <Button
                  variant="secondary"
                  className="w-full"
                  onClick={() => {}}
                  disabled={samples.length === 0}
                >
                  Select All
                </Button>
                <Button
                  variant="secondary"
                  className="w-full"
                  onClick={() => {}}
                  disabled={samples.length === 0}
                >
                  Deselect All
                </Button>
              </div>
            </Section>
          </CardContent>
        </Card>

        {/* Right Column: Comparison */}
        <Card className="h-full flex flex-col">
          <CardHeader>
            <CardTitle>Comparison</CardTitle>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col">
            <Section title="Analysis">
              <div className="p-4 bg-card rounded-lg border border-dashed border-border min-h-[100px] flex items-center justify-center">
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
                    Analysis results will appear here
                  </p>
                </div>
              </div>
            </Section>

            <div className="my-4 border-t border-border"></div>

            <Section title="Actions">
              <div className="space-y-2">
                <Button
                  variant="default"
                  className="w-full"
                  onClick={() => setIsAnalysisOpen(true)}
                  disabled={samples.length === 0}
                >
                  Open Analysis
                </Button>
                <Button
                  variant="secondary"
                  className="w-full"
                  onClick={() => {}}
                  disabled={samples.length === 0}
                >
                  Export Results
                </Button>
                <Button
                  variant="secondary"
                  className="w-full"
                  onClick={() => {}}
                  disabled={samples.length === 0}
                >
                  Compare Samples
                </Button>
              </div>
            </Section>
          </CardContent>
        </Card>
      </div>

      {/* Analysis Window Popup */}
      <AnalysisWindow
        isOpen={isAnalysisOpen}
        onClose={() => setIsAnalysisOpen(false)}
      />
    </div>
  );
}
