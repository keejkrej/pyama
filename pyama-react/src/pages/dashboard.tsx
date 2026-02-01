import { useState, useEffect, useRef } from "react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  Button,
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
  Badge,
} from "../components/ui";
import { api, type TaskResponse } from "../lib/api";

function formatTimestamp(timestamp: string | null): string {
  if (!timestamp) return "—";
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins} minute${diffMins > 1 ? "s" : ""} ago`;
  if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? "s" : ""} ago`;
  if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? "s" : ""} ago`;
  return date.toLocaleDateString();
}

function getStatusBadgeVariant(
  status: TaskResponse["status"],
): "success" | "destructive" | "info" | "muted" {
  switch (status) {
    case "completed":
      return "success";
    case "failed":
      return "destructive";
    case "running":
    case "pending":
      return "info";
    case "cancelled":
    default:
      return "muted";
  }
}

function truncatePath(path: string, maxLength: number = 50): string {
  if (path.length <= maxLength) return path;
  const start = path.substring(0, maxLength / 2 - 3);
  const end = path.substring(path.length - maxLength / 2 + 3);
  return `${start}...${end}`;
}

export function DashboardPage() {
  const [tasks, setTasks] = useState<TaskResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState<Set<string>>(new Set());
  const pollingIntervalRef = useRef<number | null>(null);

  // Fetch all tasks
  const fetchTasks = async () => {
    try {
      setError(null);
      const response = await api.listTasks();
      // Sort by created_at descending (newest first)
      const sorted = [...response.tasks].sort(
        (a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
      );
      setTasks(sorted);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to fetch tasks",
      );
    } finally {
      setLoading(false);
    }
  };

  // Initial fetch on mount
  useEffect(() => {
    fetchTasks();
  }, []);

  // Poll for updates on running/pending tasks
  useEffect(() => {
    const hasActiveTasks = tasks.some(
      (task) => task.status === "pending" || task.status === "running",
    );

    if (!hasActiveTasks) {
      // Clear polling if no active tasks
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
      return;
    }

    // Start polling every 2 seconds
    pollingIntervalRef.current = window.setInterval(() => {
      fetchTasks();
    }, 2000);

    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    };
  }, [tasks]);

  const handleCancel = async (taskId: string) => {
    if (cancelling.has(taskId)) return;
    setCancelling((prev) => new Set(prev).add(taskId));
    try {
      await api.cancelTask(taskId);
      // Refresh tasks after cancellation
      await fetchTasks();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to cancel task",
      );
    } finally {
      setCancelling((prev) => {
        const next = new Set(prev);
        next.delete(taskId);
        return next;
      });
    }
  };

  const activeTasksCount = tasks.filter(
    (task) => task.status === "pending" || task.status === "running",
  ).length;

  return (
    <div className="p-5">
      <div className="mb-5">
        <h1 className="text-lg font-semibold mb-1.5 text-foreground-bright">
          Task Dashboard
        </h1>
        <p className="text-xs text-muted-foreground">
          Monitor and manage all processing tasks
          {activeTasksCount > 0 && (
            <span className="ml-2">
              ({activeTasksCount} active)
            </span>
          )}
        </p>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Tasks</CardTitle>
            <Button
              variant="secondary"
              onClick={fetchTasks}
              disabled={loading}
            >
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {error && (
            <div className="mb-4 p-3 bg-destructive/10 border border-destructive rounded text-sm text-destructive">
              {error}
            </div>
          )}

          {loading ? (
            <div className="text-center py-8 text-muted-foreground">
              Loading tasks...
            </div>
          ) : tasks.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No tasks found
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[100px]">Status</TableHead>
                    <TableHead className="min-w-[200px]">File</TableHead>
                    <TableHead className="w-[200px]">Progress</TableHead>
                    <TableHead className="w-[120px]">Created</TableHead>
                    <TableHead className="w-[100px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {tasks.map((task) => (
                    <TableRow key={task.id}>
                      <TableCell>
                        <Badge variant={getStatusBadgeVariant(task.status)}>
                          {task.status}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div
                          className="text-sm"
                          title={task.file_path}
                        >
                          {truncatePath(task.file_path)}
                        </div>
                      </TableCell>
                      <TableCell>
                        {task.progress ? (
                          <div className="space-y-1">
                            <div className="w-full bg-muted rounded-full h-2">
                              <div
                                className="bg-primary h-2 rounded-full transition-all duration-300"
                                style={{
                                  width: `${task.progress.percent || 0}%`,
                                }}
                              />
                            </div>
                            <p className="text-xs text-muted-foreground">
                              {task.progress.message ||
                                `${task.progress.percent?.toFixed(0) || 0}%`}
                            </p>
                          </div>
                        ) : (
                          <span className="text-xs text-muted-foreground">
                            —
                          </span>
                        )}
                      </TableCell>
                      <TableCell>
                        <span className="text-xs text-muted-foreground">
                          {formatTimestamp(task.created_at)}
                        </span>
                      </TableCell>
                      <TableCell>
                        {(task.status === "pending" ||
                          task.status === "running") && (
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => handleCancel(task.id)}
                            disabled={cancelling.has(task.id)}
                          >
                            {cancelling.has(task.id) ? "Cancelling..." : "Cancel"}
                          </Button>
                        )}
                        {task.status === "failed" && task.error_message && (
                          <div
                            className="text-xs text-destructive"
                            title={task.error_message}
                          >
                            Error
                          </div>
                        )}
                        {task.status === "completed" && task.result && (
                          <div
                            className="text-xs text-success"
                            title={task.result.output_dir}
                          >
                            Complete
                          </div>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
