import { FittingResult, TraceDataPoint } from "@/types/analysis";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { FittedTracePlot } from "./FittedTracePlot";

interface QualityPanelProps {
  fittingResults: FittingResult[];
  traceData: TraceDataPoint[];
  selectedResultIdx: number;
  onSelectResultIdx: (idx: number) => void;
  qualityFilter: boolean;
  onQualityFilterChange: (checked: boolean) => void;
  qualityPage: number;
  onPageChange: (page: number) => void;
  resultsPerPage: number;
}

export function QualityPanel({
  fittingResults,
  traceData,
  selectedResultIdx,
  onSelectResultIdx,
  qualityFilter,
  onQualityFilterChange,
  qualityPage,
  onPageChange,
  resultsPerPage,
}: QualityPanelProps) {
  const filteredResults = qualityFilter
    ? fittingResults.filter((r) => r.r_squared > 0.9)
    : fittingResults;

  const totalQualityPages = Math.ceil(filteredResults.length / resultsPerPage);

  const stats = (() => {
    if (fittingResults.length === 0) return { good: 0, mid: 0, bad: 0 };
    const good = fittingResults.filter((r) => r.r_squared > 0.9).length;
    const mid = fittingResults.filter(
      (r) => r.r_squared > 0.7 && r.r_squared <= 0.9
    ).length;
    const bad = fittingResults.filter((r) => r.r_squared <= 0.7).length;
    const total = fittingResults.length;
    return {
      good: ((good / total) * 100).toFixed(1),
      mid: ((mid / total) * 100).toFixed(1),
      bad: ((bad / total) * 100).toFixed(1),
    };
  })();

  return (
    <div className="rounded-2xl border border-neutral-900 bg-neutral-900 p-6 shadow-sm">
      <div className="space-y-4">
        {/* Fitted trace canvas */}
        <FittedTracePlot
          results={fittingResults}
          traceData={traceData}
          selectedResultIdx={selectedResultIdx}
          qualityFilter={qualityFilter}
        />

        {/* Quality Stats */}
        <div className="flex gap-2 text-xs">
          <span className="rounded bg-green-500/20 px-2 py-1 text-green-400">
            Good: {stats.good}%
          </span>
          <span className="rounded bg-yellow-500/20 px-2 py-1 text-yellow-400">
            Mid: {stats.mid}%
          </span>
          <span className="rounded bg-red-500/20 px-2 py-1 text-red-400">
            Bad: {stats.bad}%
          </span>
        </div>

        {/* Results List */}
        <div className="rounded-md border border-neutral-800 bg-neutral-950/50 overflow-hidden">
          <div className="max-h-48 overflow-y-auto divide-y divide-neutral-800/50">
            {filteredResults
              .slice(
                qualityPage * resultsPerPage,
                (qualityPage + 1) * resultsPerPage
              )
              .map((result, idx) => {
                const globalIdx = qualityPage * resultsPerPage + idx;
                const color =
                  result.r_squared > 0.9
                    ? "text-green-400"
                    : result.r_squared > 0.7
                    ? "text-yellow-400"
                    : "text-red-400";

                return (
                  <div
                    key={`${result.fov}_${result.cell}`}
                    className={`cursor-pointer px-3 py-2 text-xs hover:bg-neutral-800 ${
                      globalIdx === selectedResultIdx ? "bg-neutral-800" : ""
                    }`}
                    onClick={() => onSelectResultIdx(globalIdx)}
                  >
                    <span className={color}>
                      Cell {result.fov}_{result.cell} — R²:{" "}
                      {result.r_squared.toFixed(3)}
                    </span>
                  </div>
                );
              })}
            {filteredResults.length === 0 && (
              <div className="p-4 text-center text-sm text-neutral-500">
                No results loaded
              </div>
            )}
          </div>
        </div>

        {/* Pagination */}
        {totalQualityPages > 1 && (
          <div className="flex items-center justify-between text-xs">
            <Button
              variant="default"
              size="sm"
              className="h-7 px-2"
              onClick={() => onPageChange(Math.max(0, qualityPage - 1))}
              disabled={qualityPage === 0}
            >
              Previous
            </Button>
            <span className="text-neutral-400">
              Page {qualityPage + 1} of {totalQualityPages}
            </span>
            <Button
              variant="default"
              size="sm"
              className="h-7 px-2"
              onClick={() =>
                onPageChange(Math.min(totalQualityPages - 1, qualityPage + 1))
              }
              disabled={qualityPage >= totalQualityPages - 1}
            >
              Next
            </Button>
          </div>
        )}

        {/* Quality Filter */}
        <div className="flex items-center gap-2">
          <Checkbox
            id="quality-filter"
            checked={qualityFilter}
            onCheckedChange={(checked) => onQualityFilterChange(checked === true)}
            className="border-neutral-600"
          />
          <Label htmlFor="quality-filter" className="text-sm cursor-pointer">
            Good fits only (R² {">"} 0.9)
          </Label>
        </div>
      </div>
    </div>
  );
}
