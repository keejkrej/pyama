import { useState } from 'preact/hooks';
import { Card, Button, NumberInput, FilePicker, Section, Input } from '../components/ui';
import { AnalysisWindow } from '../components/popups/analysis-window';

interface AnalysisPageProps {
  path?: string;
}

export function AnalysisPage(_props: AnalysisPageProps) {
  const [isAnalysisOpen, setIsAnalysisOpen] = useState(false);
  const [dataFolder, setDataFolder] = useState('');
  const [frameInterval, setFrameInterval] = useState(10);
  const [timeMapping, setTimeMapping] = useState<string>('none');
  const [samples, setSamples] = useState<string[]>([]);

  return (
    <div className="p-8 min-h-screen bg-background">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold mb-3" style={{ color: 'hsl(0 0% 95%)' }}>Analysis</h1>
        <p className="text-sm text-muted-foreground">Load samples and perform statistical analysis</p>
      </div>

      <div className="grid grid-cols-3 gap-6 items-stretch">
        {/* Left Column: Load Data */}
        <Card title="Load Data" className="h-full flex flex-col" bodyClassName="flex-1 flex flex-col">
          <div className="flex-1 flex flex-col">
            <Section title="Data Folder">
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <Input
                    placeholder="No folder selected"
                    value={dataFolder}
                    onChange={(e) => setDataFolder(e.currentTarget.value)}
                    className="flex-1"
                    readOnly
                  />
                  <FilePicker
                    onFileSelect={(files) => {
                      if (files && files.length > 0) {
                        const path = (files[0] as any).webkitRelativePath || files[0].name;
                        const dirPath = path.substring(0, path.lastIndexOf('/')) || files[0].name;
                        setDataFolder(dirPath || 'Selected');
                      }
                    }}
                    directory
                    buttonText="Browse"
                  />
                </div>
                <div className="mt-2 p-4 bg-card rounded-lg border border-dashed border-border min-h-[100px] flex items-center justify-center">
                  <p className="text-xs text-muted-foreground">Data Folder Metadata</p>
                </div>
              </div>
            </Section>

            <div className="my-6 border-t border-border"></div>

            <Section title="Time Configuration">
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-2 text-foreground">
                    Frame interval
                  </label>
                  <div className="flex items-center gap-2">
                    <NumberInput
                      value={frameInterval}
                      onChange={setFrameInterval}
                      min={0}
                      step={0.1}
                      className="flex-1"
                    />
                    <span className="text-sm text-muted-foreground whitespace-nowrap">
                      min
                    </span>
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2 text-foreground">
                    Time mapping
                  </label>
                  <div className="p-3 bg-card rounded-lg border border-dashed border-border">
                    <p className="text-xs text-muted-foreground">
                      {timeMapping === 'none' ? 'No time mapping file' : timeMapping}
                    </p>
                  </div>
                </div>
              </div>
            </Section>

            <div className="my-6 border-t border-border"></div>

            <div className="mt-6 flex gap-2">
              <Button variant="default" className="flex-1" onClick={() => { }}>
                Load
              </Button>
              <Button variant="secondary" className="flex-1" onClick={() => { }}>
                Clear
              </Button>
            </div>
          </div>
        </Card>

        {/* Middle Column: Samples */}
        <Card title="Samples" className="h-full flex flex-col" bodyClassName="flex-1 flex flex-col">
          <div className="flex-1 flex flex-col">
            <Section title="Loaded Samples">
              <div className="p-6 bg-card rounded-lg border border-dashed border-border min-h-[400px] flex flex-col">
                {samples.length === 0 ? (
                  <div className="flex-1 flex items-center justify-center">
                    <div className="text-center">
                      <svg
                        className="w-16 h-16 mx-auto text-muted-foreground/50 mb-4"
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
                      <p className="text-sm text-muted-foreground font-medium">
                        No samples loaded
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        Load data folder to see samples
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {samples.map((sample, idx) => (
                      <div
                        key={idx}
                        className="p-4 bg-background rounded-lg border border-border hover:border-foreground/20 hover:shadow-sm transition-all cursor-pointer"
                      >
                        <p className="text-sm font-medium text-foreground">{sample}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </Section>

            <div className="my-6 border-t border-border"></div>

            <Section title="Actions">
              <div className="space-y-2">
                <Button variant="secondary" className="w-full" onClick={() => { }} disabled={samples.length === 0}>
                  Select All
                </Button>
                <Button variant="secondary" className="w-full" onClick={() => { }} disabled={samples.length === 0}>
                  Deselect All
                </Button>
              </div>
            </Section>
          </div>
        </Card>

        {/* Right Column: Comparison */}
        <Card title="Comparison" className="h-full flex flex-col" bodyClassName="flex-1 flex flex-col">
          <div className="flex-1 flex flex-col">
            <Section title="Analysis">
              <div className="p-6 bg-card rounded-lg border border-dashed border-border min-h-[200px] flex items-center justify-center">
                <div className="text-center">
                  <svg
                    className="w-12 h-12 mx-auto text-muted-foreground/40 mb-3"
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

            <div className="my-6 border-t border-border"></div>

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
                <Button variant="secondary" className="w-full" onClick={() => { }} disabled={samples.length === 0}>
                  Export Results
                </Button>
                <Button variant="secondary" className="w-full" onClick={() => { }} disabled={samples.length === 0}>
                  Compare Samples
                </Button>
              </div>
            </Section>
          </div>
        </Card>
      </div>

      {/* Analysis Window Popup */}
      <AnalysisWindow isOpen={isAnalysisOpen} onClose={() => setIsAnalysisOpen(false)} />
    </div>
  );
}
