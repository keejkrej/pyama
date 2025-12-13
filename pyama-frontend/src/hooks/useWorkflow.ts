import { useState, useRef, useEffect } from "react";
import { JobState } from "@/types/processing";

export function useWorkflow(apiBase: string) {
  const [currentJob, setCurrentJob] = useState<JobState | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [statusMessage, setStatusMessage] = useState("Ready");
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const stopPolling = () => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  };

  const startPolling = (jobId: string) => {
    stopPolling();

    pollIntervalRef.current = setInterval(async () => {
      try {
        const response = await fetch(
          `${apiBase}/processing/workflow/status/${jobId}`
        );
        const data = await response.json();

        setCurrentJob({
          job_id: data.job_id,
          status: data.status,
          progress: data.progress,
          message: data.message,
        });

        if (data.progress) {
          setStatusMessage(
            `Processing: ${data.progress.current}/${data.progress.total} FOVs (${data.progress.percentage.toFixed(
              1
            )}%)`
          );
        } else {
          setStatusMessage(data.message || `Status: ${data.status}`);
        }

        if (
          ["completed", "failed", "cancelled", "not_found"].includes(data.status)
        ) {
          stopPolling();
          setIsProcessing(false);
          if (data.status === "completed") {
            setStatusMessage("Workflow completed successfully!");
          } else if (data.status === "cancelled") {
            setStatusMessage("Workflow was cancelled");
          } else if (data.status === "failed") {
            setStatusMessage(`Workflow failed: ${data.message}`);
          }
        }
      } catch (err) {
        console.error("Failed to poll job status:", err);
      }
    }, 1000);
  };

  useEffect(() => {
    return () => stopPolling();
  }, []);

  const startWorkflow = async (payload: any) => {
    setIsProcessing(true);
    setStatusMessage("Starting workflow...");
    try {
      const response = await fetch(`${apiBase}/processing/workflow/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!data.success) {
        throw new Error(data.error || "Failed to start workflow");
      }
      setCurrentJob({
        job_id: data.job_id,
        status: "pending",
        progress: null,
        message: data.message || "Workflow started",
      });
      setStatusMessage(`Workflow started (Job: ${data.job_id})`);
      startPolling(data.job_id);
    } catch (err) {
      setIsProcessing(false);
      setStatusMessage(
        err instanceof Error ? err.message : "Failed to start workflow"
      );
    }
  };

  const cancelWorkflow = async () => {
    if (!currentJob) return;
    try {
      const response = await fetch(
        `${apiBase}/processing/workflow/cancel/${currentJob.job_id}`,
        {
          method: "POST",
        }
      );
      const data = await response.json();
      if (data.success) {
        setStatusMessage("Cancelling workflow...");
      } else {
        setStatusMessage(`Failed to cancel: ${data.message}`);
      }
    } catch (err) {
      setStatusMessage(
        err instanceof Error ? err.message : "Failed to cancel workflow"
      );
    }
  };

  return {
    currentJob,
    isProcessing,
    statusMessage,
    setStatusMessage,
    startWorkflow,
    cancelWorkflow,
  };
}
