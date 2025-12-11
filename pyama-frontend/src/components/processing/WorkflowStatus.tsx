import { JobState } from '@/types/processing';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Card, CardContent } from '@/components/ui/card';

interface WorkflowStatusProps {
  currentJob: JobState | null;
  isProcessing: boolean;
  onStart: () => void;
  onCancel: () => void;
}

export function WorkflowStatus({
  currentJob,
  isProcessing,
  onStart,
  onCancel,
}: WorkflowStatusProps) {
  return (
    <Card>
      <CardContent className="p-4 space-y-4">
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <Button
              className="flex-1 font-semibold"
              onClick={onStart}
              disabled={isProcessing}
            >
              {isProcessing ? 'Processing...' : 'Start Complete Workflow'}
            </Button>
            <Button
              variant="default"
              className="border-border bg-muted hover:border-destructive/50 hover:text-destructive disabled:opacity-50"
              onClick={onCancel}
              disabled={!isProcessing}
            >
              Cancel
            </Button>
          </div>

          {/* Progress Bar */}
          <div className="space-y-2">
            <Progress
              value={currentJob?.progress?.percentage || 0}
              className="h-2 bg-muted"
              // indicatorClassName="bg-blue-500" // shadcn Progress handles this via class or utility
            />
            {currentJob?.progress && (
              <p className="text-xs text-muted-foreground text-center">
                {currentJob.progress.current}/{currentJob.progress.total} FOVs (
                {currentJob.progress.percentage.toFixed(1)}%)
              </p>
            )}
            {isProcessing && !currentJob?.progress && (
              <p className="text-xs text-muted-foreground text-center">
                Processing in progress...
              </p>
            )}
            {isProcessing && !currentJob?.progress && (
              <p className="text-xs text-muted-foreground text-center">
                Processing in progress...
              </p>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
