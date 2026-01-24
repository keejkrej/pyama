import { useState, useRef } from 'preact/hooks';
import { Card, Button, Input, NumberInput, Checkbox, Table, TableHeader, TableRow, TableCell, FilePicker, Section } from '../components/ui';

interface ProcessingPageProps {
  path?: string;
}

interface ProcessingParams {
  fov_start: number;
  fov_end: number;
  batch_size: number;
  n_workers: number;
  background_weight: number;
}

export function ProcessingPage(_props: ProcessingPageProps) {
  const [microscopyFile, setMicroscopyFile] = useState('');
  const [phaseContrastChannel, setPhaseContrastChannel] = useState(0);
  const [fluorescenceChannels, setFluorescenceChannels] = useState<number[]>([]);
  const [flChannel1, setFlChannel1] = useState(0);
  const [flChannel2, setFlChannel2] = useState(0);
  const [outputDir, setOutputDir] = useState('');
  const [manualParams, setManualParams] = useState(true);
  const [params, setParams] = useState<ProcessingParams>({
    fov_start: 0,
    fov_end: -1,
    batch_size: 2,
    n_workers: 2,
    background_weight: 1,
  });
  const tooltipRef = useRef<HTMLDivElement>(null);
  const iconRef = useRef<SVGSVGElement>(null);

  const handleAddFluorescence = () => {
    if (flChannel1 > 0 && !fluorescenceChannels.includes(flChannel1)) {
      setFluorescenceChannels([...fluorescenceChannels, flChannel1]);
    }
  };

  const updateParam = (key: keyof ProcessingParams, value: number) => {
    setParams({ ...params, [key]: value });
  };

  return (
    <div className="p-5">
      <div className="mb-5">
        <h1 className="text-lg font-semibold mb-1.5 text-foreground-bright">Processing</h1>
        <p className="text-xs text-muted-foreground">Configure microscopy file processing and workflow parameters</p>
      </div>

      <div className="grid grid-cols-3 gap-4 items-stretch">
        {/* Left Column: Input */}
        <Card title="Input" className="h-full flex flex-col" bodyClassName="flex-1 flex flex-col">
          <div className="flex-1 flex flex-col">
            <Section title="Microscopy">
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Input
                    placeholder="No microscopy selected"
                    value={microscopyFile}
                    onChange={(e) => setMicroscopyFile(e.currentTarget.value)}
                    className="flex-1"
                    readOnly
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
                  <p className="text-xs text-muted-foreground">Microscopy Metadata</p>
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
                    <p className="text-xs text-muted-foreground">Phase Contrast Features</p>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium mb-1.5 text-foreground">
                    Fluorescence
                  </label>
                  <div className="space-y-2 mb-2">
                    <NumberInput
                      value={flChannel1}
                      onChange={setFlChannel1}
                      min={0}
                    />
                    <NumberInput
                      value={flChannel2}
                      onChange={setFlChannel2}
                      min={0}
                    />
                  </div>
                  {fluorescenceChannels.length > 0 && (
                    <div className="mb-2">
                      <p className="text-xs text-muted-foreground mb-1">Channels: {fluorescenceChannels.join(', ')}</p>
                    </div>
                  )}
                  <div className="mt-1.5 p-3 bg-card rounded-lg border border-dashed border-border min-h-[50px] flex items-center justify-center">
                    <p className="text-xs text-muted-foreground">Fluorescence Features</p>
                  </div>
                </div>
              </div>
            </Section>

            <div className="mt-4 grid grid-cols-2 gap-2">
              <Button onClick={handleAddFluorescence} variant="secondary">
                Add
              </Button>
              <Button variant="secondary" disabled onClick={() => { }}>
                Remove
              </Button>
            </div>
          </div>
        </Card>

        {/* Middle Column: Output */}
        <Card title="Output" className="h-full flex flex-col" bodyClassName="flex-1 flex flex-col">
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
                      const path = (files[0] as any).webkitRelativePath || files[0].name;
                      const dirPath = path.substring(0, path.lastIndexOf('/'));
                      setOutputDir(dirPath || 'Selected');
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
                    <TableCell header className="border-r border-border w-1/2">Name</TableCell>
                    <TableCell header className="w-1/2">Value</TableCell>
                  </TableRow>
                </TableHeader>
                <tbody>
                  {manualParams ? (
                    <>
                      <TableRow>
                        <TableCell className="border-r border-border">fov_start</TableCell>
                        <TableCell>
                          <NumberInput
                            value={params.fov_start}
                            onChange={(v) => updateParam('fov_start', v)}
                          />
                        </TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell className="border-r border-border">fov_end</TableCell>
                        <TableCell>
                          <NumberInput
                            value={params.fov_end}
                            onChange={(v) => updateParam('fov_end', v)}
                          />
                        </TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell className="border-r border-border">batch_size</TableCell>
                        <TableCell>
                          <NumberInput
                            value={params.batch_size}
                            onChange={(v) => updateParam('batch_size', v)}
                            min={1}
                          />
                        </TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell className="border-r border-border">n_workers</TableCell>
                        <TableCell>
                          <NumberInput
                            value={params.n_workers}
                            onChange={(v) => updateParam('n_workers', v)}
                            min={1}
                          />
                        </TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell className="border-r border-border">background_weight</TableCell>
                        <TableCell>
                          <NumberInput
                            value={params.background_weight}
                            onChange={(v) => updateParam('background_weight', v)}
                            min={0}
                            step={0.1}
                          />
                        </TableCell>
                      </TableRow>
                    </>
                  ) : (
                    <TableRow>
                      <TableCell colSpan={2} className="text-center py-6 text-muted-foreground border-r-0">
                        Parameters by default
                      </TableCell>
                    </TableRow>
                  )}
                </tbody>
              </Table>
            </Section>

            <div className="my-4 border-t border-border"></div>

            <div className="mt-4 flex gap-2">
              <Button variant="default" className="flex-1" onClick={() => { }}>
                Start
              </Button>
              <Button variant="secondary" className="flex-1" onClick={() => { }}>
                Cancel
              </Button>
            </div>
          </div>
        </Card>

        {/* Right Column: Samples */}
        <Card title="Samples" className="h-full flex flex-col" bodyClassName="flex-1 flex flex-col">
          <div className="flex-1 flex flex-col">
            <Section title="Assign FOVs">
              <div className="relative">
                <Table className="table-fixed">
                  <TableHeader>
                    <TableRow>
                      <TableCell header className="border-r border-border w-1/2">Name</TableCell>
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
                                  const iconRect = iconRef.current.getBoundingClientRect();
                                  tooltipRef.current.style.left = `${iconRect.left + iconRect.width / 2}px`;
                                  tooltipRef.current.style.top = `${iconRect.top - 8}px`;
                                  tooltipRef.current.style.transform = 'translate(-50%, -100%)';
                                  tooltipRef.current.classList.remove('opacity-0', 'invisible');
                                  tooltipRef.current.classList.add('opacity-100', 'visible');
                                }
                              }}
                              onMouseLeave={() => {
                                if (tooltipRef.current) {
                                  tooltipRef.current.classList.add('opacity-0', 'invisible');
                                  tooltipRef.current.classList.remove('opacity-100', 'visible');
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
                      <TableCell colSpan={2} className="text-center py-6 text-muted-foreground border-r-0">
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
                    backgroundColor: 'var(--color-popover)',
                    color: 'var(--color-popover-foreground)',
                    border: '1px solid var(--color-border)',
                    zIndex: 9999,
                  }}
                >
                  Format: 0-5, 7, 9-11
                  <div
                    className="absolute left-1/2 -translate-x-1/2 top-full w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent"
                    style={{ borderTopColor: 'var(--color-border)' }}
                  ></div>
                </div>
              </div>
              <div className="mt-4 grid grid-cols-2 gap-2">
                <Button variant="secondary" onClick={() => { }}>Add</Button>
                <Button variant="secondary" onClick={() => { }} disabled>Remove</Button>
                <Button variant="secondary" onClick={() => { }}>Load</Button>
                <Button variant="secondary" onClick={() => { }}>Save</Button>
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
                    <Input placeholder="Select sample YAML file" className="flex-1" />
                    <FilePicker onFileSelect={() => { }} buttonText="Browse" />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium mb-1.5 text-foreground">
                    Folder of processed FOVs
                  </label>
                  <div className="flex items-center gap-2">
                    <Input placeholder="Select folder" className="flex-1" />
                    <FilePicker onFileSelect={() => { }} buttonText="Browse" />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium mb-1.5 text-foreground">
                    Output folder
                  </label>
                  <div className="flex items-center gap-2">
                    <Input placeholder="Select output folder" className="flex-1" />
                    <FilePicker onFileSelect={() => { }} buttonText="Browse" />
                  </div>
                </div>

                <div className="mt-4">
                  <Button variant="default" className="w-full" onClick={() => { }}>
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
