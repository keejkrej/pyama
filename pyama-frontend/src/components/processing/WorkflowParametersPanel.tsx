import { WorkflowParameters } from "@/types/processing";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface WorkflowParametersPanelProps {
  parameters: WorkflowParameters;
  onChange: (key: keyof WorkflowParameters, value: string) => void;
  manualMode: boolean;
  onManualModeChange: (mode: boolean) => void;
  isProcessing: boolean;
}

const parameterConfig: {
  key: keyof WorkflowParameters;
  label: string;
  type: "int" | "float";
}[] = [
  { key: "fov_start", label: "FOV Start", type: "int" },
  { key: "fov_end", label: "FOV End (-1 for all)", type: "int" },
  { key: "batch_size", label: "Batch Size", type: "int" },
  { key: "n_workers", label: "Workers", type: "int" },
  { key: "background_weight", label: "Background Weight", type: "float" },
];

export function WorkflowParametersPanel({
  parameters,
  onChange,
  manualMode,
  onManualModeChange,
  isProcessing,
}: WorkflowParametersPanelProps) {
  return (
    <Card className="border-neutral-800 bg-neutral-900">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-semibold text-neutral-50">
            Parameters
          </CardTitle>
          <Button
            variant={manualMode ? "secondary" : "outline"}
            size="sm"
            onClick={() => onManualModeChange(!manualMode)}
            disabled={isProcessing}
            className={
              manualMode
                ? "bg-blue-500/20 text-blue-200 hover:bg-blue-500/30 border-blue-500/50"
                : "border-neutral-700 bg-neutral-800 text-neutral-200"
            }
          >
            {manualMode ? "Manual Mode" : "Auto Mode"}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        {parameterConfig.map(({ key, label, type }) => (
          <div
            key={key}
            className="grid grid-cols-[1.2fr_1fr] items-center gap-3 text-sm"
          >
            <Label className="text-neutral-200 font-normal">{label}</Label>
            {manualMode ? (
              <Input
                type="number"
                step={type === "float" ? "0.1" : "1"}
                value={parameters[key]}
                onChange={(e) => onChange(key, e.target.value)}
                disabled={isProcessing}
                className="h-8 text-right"
              />
            ) : (
              <div className="rounded-md border border-neutral-800 bg-neutral-950 px-3 py-1.5 text-right text-neutral-200 text-sm">
                {parameters[key]}
              </div>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
