/**
 * API client for pyama-core FastAPI server
 */

const API_BASE = "http://localhost:8765/api";

// Types matching FastAPI Pydantic schemas

export type TaskStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export interface MicroscopyMetadata {
  file_path: string;
  base_name: string;
  file_type: string;
  height: number;
  width: number;
  n_frames: number;
  n_fovs: number;
  n_channels: number;
  timepoints: number[];
  channel_names: string[];
  dtype: string;
}

export interface ProcessingConfigSchema {
  title: string;
  type: string;
  properties: Record<string, unknown>;
  required?: string[];
}

export interface AvailableFeatures {
  phase: string[];
  fluorescence: string[];
}

export interface TaskProgress {
  phase: string;
  current_fov: number;
  total_fovs: number;
  percent: number;
  message: string;
}

export interface TaskResult {
  output_dir: string;
  summary: Record<string, unknown>;
}

export interface TaskResponse {
  id: string;
  status: TaskStatus;
  file_path: string;
  config: Record<string, unknown>;
  progress: TaskProgress | null;
  result: TaskResult | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface TaskListResponse {
  tasks: TaskResponse[];
  total: number;
}

// Visualization types
export interface ProjectData {
  project_path: string;
  n_fov: number;
  fov_data: Record<number, Record<string, string>>;
  channels: Record<string, unknown> | null;
  base_name: string;
}

export interface TraceData {
  cell_id: string;
  quality: boolean;
  features: Record<string, number[]>;
  positions: {
    frames: number[];
    xc: number[];
    yc: number[];
  };
}

export interface TracesResponse {
  traces: TraceData[];
  total: number;
  page: number;
  page_size: number;
  features: string[];
}

// API client

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

export const api = {
  /**
   * Load microscopy file metadata
   */
  async loadMicroscopy(filePath: string): Promise<MicroscopyMetadata> {
    return fetchJson(`${API_BASE}/data/microscopy`, {
      method: "POST",
      body: JSON.stringify({ file_path: filePath }),
    });
  },

  /**
   * Get processing config JSON schema for dynamic form generation
   */
  async getConfigSchema(): Promise<ProcessingConfigSchema> {
    return fetchJson(`${API_BASE}/processing/config`);
  },

  /**
   * Get available feature extractors for phase contrast and fluorescence channels
   */
  async getFeatures(): Promise<AvailableFeatures> {
    return fetchJson(`${API_BASE}/processing/config/features`);
  },

  /**
   * Create a new processing task
   * @param fake - If true, runs a 60-second simulated task instead of real processing
   */
  async createTask(
    filePath: string,
    config: Record<string, unknown>,
    fake: boolean = false,
  ): Promise<TaskResponse> {
    return fetchJson(`${API_BASE}/processing/tasks`, {
      method: "POST",
      body: JSON.stringify({ file_path: filePath, config, fake }),
    });
  },

  /**
   * Get task status and progress
   */
  async getTask(taskId: string): Promise<TaskResponse> {
    return fetchJson(`${API_BASE}/processing/tasks/${taskId}`);
  },

  /**
   * List all tasks
   */
  async listTasks(): Promise<TaskListResponse> {
    return fetchJson(`${API_BASE}/processing/tasks`);
  },

  /**
   * Cancel a running task
   */
  async cancelTask(taskId: string): Promise<TaskResponse> {
    return fetchJson(`${API_BASE}/processing/tasks/${taskId}`, {
      method: "DELETE",
    });
  },

  /**
   * Load visualization project data
   */
  async loadVisualizationProject(projectPath: string): Promise<ProjectData> {
    return fetchJson(`${API_BASE}/visualization/project/load`, {
      method: "POST",
      body: JSON.stringify({ project_path: projectPath }),
    });
  },

  /**
   * Get paginated trace data for a FOV
   */
  async getTraces(
    projectPath: string,
    fov: number,
    page: number = 0,
    pageSize: number = 10,
  ): Promise<TracesResponse> {
    const params = new URLSearchParams({
      project_path: projectPath,
      fov: fov.toString(),
      page: page.toString(),
      page_size: pageSize.toString(),
    });
    return fetchJson(`${API_BASE}/visualization/traces?${params}`);
  },

  /**
   * Get available feature columns from traces CSV
   */
  async getTraceFeatures(
    projectPath: string,
    fov: number,
  ): Promise<{ features: string[] }> {
    const params = new URLSearchParams({
      project_path: projectPath,
      fov: fov.toString(),
    });
    return fetchJson(`${API_BASE}/visualization/traces/features?${params}`);
  },

  /**
   * Update trace quality flags
   */
  async updateTraceQuality(
    projectPath: string,
    fov: number,
    updates: Record<string, boolean>,
  ): Promise<{ success: boolean; saved_path: string }> {
    return fetchJson(`${API_BASE}/visualization/traces/quality`, {
      method: "POST",
      body: JSON.stringify({
        project_path: projectPath,
        fov,
        updates,
      }),
    });
  },
};
