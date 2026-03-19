export interface ZoneFrames {
  defensive_third: number;
  middle_third: number;
  attacking_third: number;
}

export interface PlayerStats {
  track_id: number;
  distance_m: number;
  avg_speed_mps: number;
  max_speed_mps: number;
  sprint_count: number;
  zone_frames: ZoneFrames;
  total_frames: number;
}

export interface PitchMeta {
  ready: boolean;
  pitch_length_m: number;
  pitch_width_m: number;
}

export interface VideoMeta {
  width: number;
  height: number;
  fps: number;
  frames_processed: number;
}

export interface AnalysisResult {
  run_id: string;
  engine: string;
  status: string;
  frames_processed: number;
  fps: number;
  per_player_metrics: PlayerStats[];
  heatmap_points: [number, number][];
  pitch: PitchMeta;
  video: VideoMeta;
  modules_completed: string[];
  errors: string[];
}

export interface PlayerProfile {
  name: string;
  number: string;   // jersey number string (could be "10", "99", etc.)
  jerseyColor: string; // hex, e.g. "#e53935"
  teamName: string;
}

export type AnalysisStage =
  | 'idle'
  | 'profiling'
  | 'selecting'
  | 'uploading'
  | 'processing'
  | 'done'
  | 'error';
