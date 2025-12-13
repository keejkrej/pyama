import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ArrowRight, X } from 'lucide-react';
import { cn } from '@/lib/utils';

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
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-semibold text-foreground">
            Channels
          </CardTitle>
          {channelNames.length > 0 && (
            <span className="text-xs text-muted-foreground">
              {channelNames.length} available
            </span>
          )}
        </div>
        {channelNames.length > 0 && (
          <div className="flex flex-wrap gap-2 pt-2">
            {channelNames.map((name, idx) => (
              <Badge
                key={`${name}-${idx}`}
                variant="default"
                className="border-border text-muted-foreground font-normal text-[10px]"
              >
                {idx}: {name || 'Channel'}
              </Badge>
            ))}
          </div>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Phase Contrast */}
        <div className="space-y-3 rounded-md border border-border bg-muted/50 p-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-foreground">
              Phase Contrast
            </span>
          </div>
          <Select
            value={phaseChannel?.toString() ?? ''}
            onValueChange={(val) => setPhaseChannel(val ? Number(val) : null)}
            disabled={isProcessing || channelNames.length === 0}
          >
            <SelectTrigger className="w-[180px] h-8 text-xs">
              <SelectValue placeholder="Channel" />
            </SelectTrigger>
            <SelectContent>
              {channelNames.map((name, idx) => (
                <SelectItem key={`${name}-${idx}`} value={idx.toString()}>
                  {idx}: {name || 'Channel'}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <div className="flex flex-wrap gap-2">
            {availablePhaseFeatures.length > 0
              ? availablePhaseFeatures.map((feature) => {
                  const active = pcFeaturesSelected.includes(feature);
                  return (
                    <button
                      type="button"
                      key={feature}
                      onClick={() => togglePcFeature(feature)}
                      disabled={isProcessing}
                      className={cn(
                        'rounded-full border px-3 py-1 text-[11px] font-medium transition-colors disabled:opacity-50',
                        active
                          ? 'border-border bg-primary text-primary-foreground'
                          : 'border-border bg-muted text-muted-foreground hover:border-border hover:bg-accent'
                      )}
                    >
                      {feature}
                    </button>
                  );
                })
              : null}
          </div>
        </div>

        {/* Fluorescence */}
        <div className="space-y-3 rounded-md border border-border bg-muted/50 p-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-foreground">
              Fluorescence
            </span>
          </div>

          <div className="flex flex-wrap gap-2">
            <Select
              value={flChannelSelection?.toString() ?? ''}
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
                    {idx}: {name || 'Channel'}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select
              value={flFeatureSelection ?? ''}
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
              variant="default"
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
                      className="flex items-center justify-between rounded-md border border-border bg-muted px-3 py-2"
                    >
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <span className="font-mono">
                          {channel}:{' '}
                          {channelNames[Number(channel)] || 'Channel'}
                        </span>
                        <ArrowRight className="h-3 w-3 text-muted-foreground" />
                        <span className="font-semibold text-foreground">
                          {feature}
                        </span>
                      </div>
                      <Button
                        size="icon"
                        variant="default"
                        className="h-6 w-6 hover:text-destructive"
                        onClick={() =>
                          removeFlMapping(Number(channel), feature)
                        }
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
