export type PickerKey =
  | "microscopy"
  | "processingOutput"
  | "sampleYaml"
  | "inputDir"
  | "mergeOutput"
  | "loadSamplesYaml"
  | "saveSamplesYaml";

export type PickerMode = "select" | "save";

export type PickerConfig = {
  key: PickerKey;
  title: string;
  description: string;
  accept?: string;
  directory?: boolean;
  filterExtensions?: string[];
  mode?: PickerMode;
  defaultFileName?: string;
};

export type PickerSelections = Record<PickerKey, string | null>;

export type FileItem = {
  name: string;
  path: string;
  is_directory: boolean;
  is_file: boolean;
  size_bytes?: number | null;
  extension?: string | null;
};

export type MicroscopyMetadata = {
  n_fovs?: number;
  n_frames?: number;
  n_channels?: number;
  channel_names?: string[];
  time_units?: string;
  pixel_size_um?: number;
};

export type WorkflowParameters = {
  fov_start: number;
  fov_end: number;
  batch_size: number;
  n_workers: number;
  background_weight: number;
};

export type Sample = {
  id: string;
  name: string;
  fovs: string;
};

export type JobStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelled"
  | "not_found";

export type JobProgress = {
  current: number;
  total: number;
  percentage: number;
};

export type JobState = {
  job_id: string;
  status: JobStatus;
  progress: JobProgress | null;
  message: string;
};
