export type ModelParameter = {
  name: string;
  default: number;
  bounds: [number, number];
};

export type ModelInfo = {
  name: string;
  description: string;
  parameters: ModelParameter[];
};

export type TraceDataPoint = {
  fov: number;
  cell: number;
  time: number;
  value: number;
  frame: number;
};

export type FittingResult = {
  fov: number;
  cell: number;
  model_type: string;
  success: boolean;
  r_squared: number;
  [key: string]: number | string | boolean;
};

export type JobProgress = {
  current: number;
  total: number;
  percentage: number;
};

export type ModelParamState = {
  value: number;
  min: number;
  max: number;
};
