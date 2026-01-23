/**
 * API client for pyama-core FastAPI server
 */

const API_BASE = 'http://localhost:8000';

// Types matching FastAPI Pydantic schemas

export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface MicroscopyMetadata {
  file_path: string;
  file_name: string;
  file_size_mb: number;
  num_fovs: number;
  num_timepoints: number;
  num_channels: number;
  channel_names: string[];
  dimensions: Record<string, number>;
  pixel_size_um: number | null;
  time_interval_ms: number | null;
}

export interface ProcessingConfigSchema {
  title: string;
  type: string;
  properties: Record<string, unknown>;
  required?: string[];
}

export interface TaskProgress {
  phase: string;
  current_fov: number;
  total_fovs: number;
  progress_percent: number;
  progress_message: string;
}

export interface TaskResult {
  output_path: string;
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

// API client

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
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
      method: 'POST',
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
   * Create a new processing task
   */
  async createTask(filePath: string, config: Record<string, unknown>): Promise<TaskResponse> {
    return fetchJson(`${API_BASE}/processing/tasks`, {
      method: 'POST',
      body: JSON.stringify({ file_path: filePath, config }),
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
      method: 'DELETE',
    });
  },
};
