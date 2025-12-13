import { FittingResult } from "@/types/analysis";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { HistogramPlot } from "./HistogramPlot";
import { ScatterPlot } from "./ScatterPlot";

interface ParameterPanelProps {
  fittingResults: FittingResult[];
  parameterNames: string[];
  selectedHistParam: string;
  onHistParamChange: (param: string) => void;
  selectedScatterX: string;
  onScatterXChange: (param: string) => void;
  selectedScatterY: string;
  onScatterYChange: (param: string) => void;
  qualityFilter: boolean;
  onQualityFilterChange: (checked: boolean) => void;
}

export function ParameterPanel({
  fittingResults,
  parameterNames,
  selectedHistParam,
  onHistParamChange,
  selectedScatterX,
  onScatterXChange,
  selectedScatterY,
  onScatterYChange,
  qualityFilter,
  onQualityFilterChange,
}: ParameterPanelProps) {
  const filteredResults = qualityFilter
    ? fittingResults.filter((r) => r.r_squared > 0.9)
    : fittingResults;

  return (
    <div className="rounded-2xl border border-neutral-900 bg-neutral-900 p-6 shadow-sm">
      <div className="pb-3 mb-4">
        <h3 className="text-lg font-semibold text-neutral-50">Parameter Analysis</h3>
      </div>
      <div className="space-y-4">
        {/* Histogram */}
        <div>
          <div className="mb-2 flex items-center justify-between">
            <Label className="text-xs text-neutral-400">Histogram</Label>
            <Select value={selectedHistParam} onValueChange={onHistParamChange}>
              <SelectTrigger className="h-7 w-[120px] text-xs">
                <SelectValue placeholder="Parameter" />
              </SelectTrigger>
              <SelectContent>
                {parameterNames.map((p) => (
                  <SelectItem key={p} value={p}>
                    {p}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <HistogramPlot data={filteredResults} param={selectedHistParam} />
        </div>

        {/* Scatter Plot */}
        <div>
          <div className="mb-2 flex items-center gap-2">
            <Label className="text-xs text-neutral-400 w-12">Scatter</Label>
            <Select value={selectedScatterX} onValueChange={onScatterXChange}>
              <SelectTrigger className="h-7 flex-1 text-xs">
                <SelectValue placeholder="X" />
              </SelectTrigger>
              <SelectContent>
                {parameterNames.map((p) => (
                  <SelectItem key={p} value={p}>
                    {p}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <span className="text-xs text-neutral-500">vs</span>
            <Select value={selectedScatterY} onValueChange={onScatterYChange}>
              <SelectTrigger className="h-7 flex-1 text-xs">
                <SelectValue placeholder="Y" />
              </SelectTrigger>
              <SelectContent>
                {parameterNames.map((p) => (
                  <SelectItem key={p} value={p}>
                    {p}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <ScatterPlot data={filteredResults} xParam={selectedScatterX} yParam={selectedScatterY} />
        </div>

        {/* Quality Filter (shared) */}
        <div className="flex items-center gap-2">
          <Checkbox
            id="param-quality-filter"
            checked={qualityFilter}
            onCheckedChange={(checked) => onQualityFilterChange(checked === true)}
            className="border-neutral-600"
          />
          <Label htmlFor="param-quality-filter" className="text-sm cursor-pointer">
            Good fits only (R² {">"} 0.9)
          </Label>
        </div>
      </div>
    </div>
  );
}
