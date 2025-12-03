import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ArrowRight, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface ChannelConfigurationProps {
  channelNames: string[];
  availablePhaseFeatures: string[];
  availableFlFeatures: string[];
  phaseChannel: number | null;
  setPhaseChannel: (val: number | null) => void;
  pcFeaturesSelected: string[];
  togglePcFeature: (feature: string) => void;
  flChannelSelection: number | null;
  setFlChannelSelection: (val: number | null) => void;
  flFeatureSelection: string | null;
  setFlFeatureSelection: (val: string | null) => void;
  flMapping: Record<number, string[]>;
  addFlMapping: () => void;
  removeFlMapping: (channel: number, feature: string) => void;
  isProcessing: boolean;
}

export function ChannelConfiguration({
  channelNames,
  availablePhaseFeatures,
  availableFlFeatures,
  phaseChannel,
  setPhaseChannel,
  pcFeaturesSelected,
  togglePcFeature,
  flChannelSelection,
  setFlChannelSelection,
  flFeatureSelection,
  setFlFeatureSelection,
  flMapping,
  addFlMapping,
  removeFlMapping,
  isProcessing,
}: ChannelConfigurationProps) {
  return (
    <Card className="border-neutral-800 bg-neutral-900">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-semibold text-neutral-50">
            Channels
          </CardTitle>
          {channelNames.length > 0 && (
            <span className="text-xs text-neutral-400">
              {channelNames.length} available
            </span>
          )}
        </div>
        {channelNames.length > 0 && (
          <div className="flex flex-wrap gap-2 pt-2">
            {channelNames.map((name, idx) => (
              <Badge
                key={`${name}-${idx}`}
                variant="outline"
                className="border-neutral-700 text-neutral-300 font-normal text-[10px]"
              >
                {idx}: {name || "Channel"}
              </Badge>
            ))}
          </div>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Phase Contrast */}
        <div className="space-y-3 rounded-md border border-neutral-800 bg-neutral-950/50 p-3">
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-sm font-medium text-neutral-200">
              Phase Contrast
            </span>
            <Select
              value={phaseChannel?.toString() ?? ""}
              onValueChange={(val) => setPhaseChannel(val ? Number(val) : null)}
              disabled={isProcessing || channelNames.length === 0}
            >
              <SelectTrigger className="w-[180px] h-8 text-xs">
                <SelectValue placeholder="Select channel" />
              </SelectTrigger>
              <SelectContent>
                {channelNames.map((name, idx) => (
                  <SelectItem key={`${name}-${idx}`} value={idx.toString()}>
                    {idx}: {name || "Channel"}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-wrap gap-2">
            {availablePhaseFeatures.length > 0 ? (
              availablePhaseFeatures.map((feature) => {
                const active = pcFeaturesSelected.includes(feature);
                return (
                  <button
                    type="button"
                    key={feature}
                    onClick={() => togglePcFeature(feature)}
                    disabled={isProcessing}
                    className={cn(
                      "rounded-full border px-3 py-1 text-[11px] font-medium transition-colors disabled:opacity-50",
                      active
                        ? "border-neutral-500 bg-neutral-700 text-neutral-50"
                        : "border-neutral-800 bg-neutral-900 text-neutral-400 hover:border-neutral-700"
                    )}
                  >
                    {feature}
                  </button>
                );
              })
            ) : (
              <span className="text-[11px] text-neutral-500">
                Load a microscopy file to choose phase features.
              </span>
            )}
          </div>
        </div>

        {/* Fluorescence */}
        <div className="space-y-3 rounded-md border border-neutral-800 bg-neutral-950/50 p-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-neutral-200">
              Fluorescence
            </span>
          </div>

          <div className="flex flex-wrap gap-2">
            <Select
              value={flChannelSelection?.toString() ?? ""}
              onValueChange={(val) =>
                setFlChannelSelection(val ? Number(val) : null)
              }
              disabled={isProcessing || channelNames.length === 0}
            >
              <SelectTrigger className="w-[140px] h-8 text-xs">
                <SelectValue placeholder="Channel" />
              </SelectTrigger>
              <SelectContent>
                {channelNames.map((name, idx) => (
                  <SelectItem key={`${name}-${idx}`} value={idx.toString()}>
                    {idx}: {name || "Channel"}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select
              value={flFeatureSelection ?? ""}
              onValueChange={(val) => setFlFeatureSelection(val || null)}
              disabled={isProcessing || availableFlFeatures.length === 0}
            >
              <SelectTrigger className="w-[140px] h-8 text-xs">
                <SelectValue placeholder="Feature" />
              </SelectTrigger>
              <SelectContent>
                {availableFlFeatures.map((feature) => (
                  <SelectItem key={feature} value={feature}>
                    {feature}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Button
              size="sm"
              variant="secondary"
              onClick={addFlMapping}
              disabled={
                isProcessing ||
                flChannelSelection === null ||
                !flFeatureSelection
              }
              className="h-8 text-xs"
            >
              Add
            </Button>
          </div>

          {Object.keys(flMapping).length > 0 && (
            <div className="space-y-2">
              {Object.entries(flMapping)
                .sort(([a], [b]) => Number(a) - Number(b))
                .map(([channel, features]) =>
                  features.map((feature) => (
                    <div
                      key={`${channel}-${feature}`}
                      className="flex items-center justify-between rounded-md border border-neutral-800 bg-neutral-900 px-3 py-2"
                    >
                      <div className="flex items-center gap-2 text-xs text-neutral-300">
                        <span className="font-mono">
                          {channel}: {channelNames[Number(channel)] || "Channel"}
                        </span>
                        <ArrowRight className="h-3 w-3 text-neutral-500" />
                        <span className="font-semibold text-neutral-200">
                          {feature}
                        </span>
                      </div>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-6 w-6 hover:text-red-400"
                        onClick={() => removeFlMapping(Number(channel), feature)}
                        disabled={isProcessing}
                      >
                        <X className="h-3 w-3" />
                      </Button>
                    </div>
                  ))
                )}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
