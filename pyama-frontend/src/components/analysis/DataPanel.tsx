import { TraceDataPoint, ModelInfo, JobProgress, ModelParamState } from "@/types/analysis";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Progress } from "@/components/ui/progress";
import { TracePlot } from "./TracePlot";

interface DataPanelProps {
  csvPath: string | null;
  onBrowse: () => void;
  traceData: TraceDataPoint[];
  availableModels: ModelInfo[];
  selectedModel: string;
  onModelChange: (model: string) => void;
  modelParams: Record<string, ModelParamState>;
  onParamChange: (name: string, field: keyof ModelParamState, value: number) => void;
  manualMode: boolean;
  onManualModeChange: (checked: boolean) => void;
  isFitting: boolean;
  fittingProgress: JobProgress | null;
  onStartFitting: () => void;
  onCancelFitting: () => void;
  onLoadResults: () => void;
}

export function DataPanel({
  csvPath,
  onBrowse,
  traceData,
  availableModels,
  selectedModel,
  onModelChange,
  modelParams,
  onParamChange,
  manualMode,
  onManualModeChange,
  isFitting,
  fittingProgress,
  onStartFitting,
  onCancelFitting,
  onLoadResults,
}: DataPanelProps) {
  return (
    <Card className="border-neutral-800 bg-neutral-900">
      <CardContent className="space-y-4 pt-6">
        {/* Load CSV */}
        <div>
          <Label className="mb-1 text-xs text-neutral-400">Trace CSV</Label>
          <div className="flex gap-2">
            <div className="flex-1 truncate rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm text-neutral-300">
              {csvPath ? csvPath.split("/").pop() : "Not selected"}
            </div>
            <Button variant="default" size="sm" onClick={onBrowse}>
              Browse
            </Button>
          </div>
        </div>

        {/* Trace Plot */}
        <TracePlot data={traceData} />

        {/* Model Selection */}
        <div>
          <Label className="mb-1 text-xs text-neutral-400">Model</Label>
          <Select value={selectedModel} onValueChange={onModelChange} disabled={availableModels.length === 0}>
            <SelectTrigger className="h-9">
              <SelectValue placeholder="Select model" />
            </SelectTrigger>
            <SelectContent>
              {availableModels.map((m) => (
                <SelectItem key={m.name} value={m.name}>
                  {m.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Parameters */}
        <div>
          <div className="mb-2 flex items-center justify-between">
            <Label className="text-xs text-neutral-400">Parameters</Label>
            <div className="flex items-center gap-2">
              <Checkbox
                id="manual-mode"
                checked={manualMode}
                onCheckedChange={(checked) => onManualModeChange(checked === true)}
                className="border-neutral-600"
              />
              <Label htmlFor="manual-mode" className="text-xs cursor-pointer">
                Manual
              </Label>
            </div>
          </div>
          <div className="rounded-md border border-neutral-800 bg-neutral-950/50 overflow-hidden">
            <div className="max-h-40 overflow-y-auto p-2">
              <table className="w-full text-xs">
                <thead className="text-neutral-500">
                  <tr>
                    <th className="px-2 py-1 text-left font-medium">Name</th>
                    <th className="px-2 py-1 text-right font-medium">Value</th>
                    <th className="px-2 py-1 text-right font-medium">Min</th>
                    <th className="px-2 py-1 text-right font-medium">Max</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-800/50">
                  {Object.entries(modelParams).map(([name, p]) => (
                    <tr key={name}>
                      <td className="px-2 py-1.5 text-neutral-300">{name}</td>
                      <td className="px-2 py-1">
                        <Input
                          type="number"
                          step="0.01"
                          value={p.value}
                          disabled={!manualMode}
                          onChange={(e) => onParamChange(name, "value", parseFloat(e.target.value))}
                          className="h-6 text-right px-1"
                        />
                      </td>
                      <td className="px-2 py-1">
                        <Input
                          type="number"
                          step="0.01"
                          value={p.min}
                          disabled={!manualMode}
                          onChange={(e) => onParamChange(name, "min", parseFloat(e.target.value))}
                          className="h-6 text-right px-1"
                        />
                      </td>
                      <td className="px-2 py-1">
                        <Input
                          type="number"
                          step="0.01"
                          value={p.max}
                          disabled={!manualMode}
                          onChange={(e) => onParamChange(name, "max", parseFloat(e.target.value))}
                          className="h-6 text-right px-1"
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <Button variant="default" className="w-full" onClick={onLoadResults}>
          Load Fitted Results
        </Button>

        {/* Actions */}
        <div className="flex gap-2 pt-2">
          <Button className="flex-1" onClick={onStartFitting} disabled={isFitting || !csvPath}>
            {isFitting ? "Fitting..." : "Start Fitting"}
          </Button>
          <Button variant="default" onClick={onCancelFitting} disabled={!isFitting}>
            Cancel
          </Button>
        </div>

        {isFitting && (
          <div className="space-y-1">
            <Progress value={fittingProgress?.percentage || 0} className="h-1.5" />
            <p className="text-[10px] text-neutral-500 text-center">
              {fittingProgress ? `${fittingProgress.percentage.toFixed(1)}%` : "Starting..."}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
