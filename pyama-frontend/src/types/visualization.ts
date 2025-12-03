export type ChannelMeta = {
  channel: string;
  dtype: string;
  shape: number[];
  n_frames: number;
  vmin: number;
  vmax: number;
  path: string;
};

export type TraceData = {
  cell_id: string;
  fov: number;
  cell: number;
  frames: number[];
  values: number[];
  x_positions: number[];
  y_positions: number[];
  good: boolean;
};

export type OverlayPosition = {
  id: string;
  x: number;
  y: number;
  color: string;
};
