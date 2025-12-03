import { useState, useEffect } from "react";
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
  { key: "fov_end", label: "FOV End", type: "int" },
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
  // Local state to track raw input values (allows typing anything)
  const [inputValues, setInputValues] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {};
    parameterConfig.forEach(({ key }) => {
      initial[key] = parameters[key].toString();
    });
    return initial;
  });

  // Sync input values when parameters change externally (but preserve user's current typing)
  useEffect(() => {
    const newValues: Record<string, string> = {};
    parameterConfig.forEach(({ key }) => {
      // Only update if user hasn't modified this field (not in inputValues means it was reset)
      if (!(key in inputValues)) {
        newValues[key] = parameters[key].toString();
      }
    });
    if (Object.keys(newValues).length > 0) {
      setInputValues((prev) => ({ ...prev, ...newValues }));
    }
  }, [parameters]);

  const handleInputChange = (key: keyof WorkflowParameters, value: string) => {
    // Store whatever they type
    setInputValues((prev) => ({ ...prev, [key]: value }));
    // Try to parse and update parent, but don't block if invalid
    onChange(key, value);
  };

  return (
    <Card className="border-neutral-800 bg-neutral-900">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-semibold text-neutral-50">
            Parameters
          </CardTitle>
          <Button
            size="sm"
            onClick={() => onManualModeChange(!manualMode)}
            disabled={isProcessing}
            className="h-7 text-xs"
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
            <Input
              type="text"
              inputMode={type === "float" ? "decimal" : "numeric"}
              value={inputValues[key] ?? parameters[key].toString()}
              onChange={(e) => handleInputChange(key, e.target.value)}
              disabled={!manualMode || isProcessing}
              className="h-8 text-right"
            />
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
