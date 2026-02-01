import { useMemo } from "react";
import Plot from "react-plotly.js";
import type { TraceData } from "../../lib/api";

interface TracePlotProps {
  traces: TraceData[];
  selectedFeature: string;
  activeTraceId: string | null;
}

export function TracePlot({
  traces,
  selectedFeature,
  activeTraceId,
}: TracePlotProps) {
  const plotData = useMemo(() => {
    if (!selectedFeature || traces.length === 0) {
      return [];
    }

    return traces.map((trace) => {
      const featureValues = trace.features[selectedFeature];
      // Frame array is stored in features.frame (matching TracePanel behavior)
      const frames = trace.features.frame || trace.positions.frames || [];

      if (!featureValues || frames.length === 0) {
        return null;
      }

      // Ensure arrays are the same length
      const minLength = Math.min(frames.length, featureValues.length);
      const x = frames.slice(0, minLength);
      const y = featureValues.slice(0, minLength);

      // Determine color based on quality and active state
      // Red: active+good, Blue: good, Green: bad
      const isGood = trace.quality;
      const isActive = trace.cell_id === activeTraceId;

      let color: string;
      let opacity: number;
      let width: number;

      if (!isGood) {
        color = "green";
        opacity = 0.5;
        width = 1;
      } else if (isActive && isGood) {
        color = "red";
        opacity = 1.0;
        width = 2;
      } else {
        color = "blue";
        opacity = 0.5;
        width = 1;
      }

      return {
        x,
        y,
        type: "scattergl" as const, // Use WebGL for performance
        mode: "lines" as const,
        name: `Trace ${trace.cell_id}`,
        line: {
          color,
          width,
        },
        opacity,
        hovertemplate: `Trace ${trace.cell_id}<br>Frame: %{x}<br>${selectedFeature}: %{y}<extra></extra>`,
        showlegend: false,
      };
    }).filter((trace) => trace !== null);
  }, [traces, selectedFeature, activeTraceId]);

  const layout = useMemo(
    () => ({
      autosize: true,
      margin: { l: 50, r: 20, t: 20, b: 50 },
      xaxis: {
        title: "Frame",
        showgrid: true,
        gridcolor: "rgba(128, 128, 128, 0.2)",
      },
      yaxis: {
        title: selectedFeature || "Feature",
        showgrid: true,
        gridcolor: "rgba(128, 128, 128, 0.2)",
      },
      plot_bgcolor: "transparent",
      paper_bgcolor: "transparent",
      font: {
        color: "var(--color-foreground)",
        size: 11,
      },
      modebar: {
        orientation: "v",
        remove: ["lasso2d", "select2d"], // Remove interactive selection tools for performance
      },
    }),
    [selectedFeature]
  );

  const config = useMemo(
    () => ({
      displayModeBar: true,
      displaylogo: false,
      modeBarButtonsToRemove: ["lasso2d", "select2d"],
      responsive: true,
      toImageButtonOptions: {
        format: "png",
        filename: `trace_plot_${selectedFeature}`,
        height: 600,
        width: 800,
        scale: 1,
      },
    }),
    [selectedFeature]
  );

  if (!selectedFeature || traces.length === 0) {
    return (
      <div className="flex items-center justify-center h-full min-h-[400px] text-muted-foreground">
        <div className="text-center">
          <svg
            className="w-10 h-10 mx-auto mb-2 text-muted-foreground/40"
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
          <p className="text-xs">
            {!selectedFeature
              ? "Select a feature to plot"
              : "No traces available"}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full h-full min-h-[400px]">
      <Plot
        data={plotData}
        layout={layout}
        config={config}
        style={{ width: "100%", height: "100%" }}
        useResizeHandler={true}
      />
    </div>
  );
}
