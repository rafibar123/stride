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

export interface RatingBreakdown {
  pace_kmh: number;
  dist_per_min_m: number;
  sprints_per_min: number;
  att_third_pct: number;
  def_third_pct: number;
  mid_third_pct: number;
  duration_min: number;
  pass_total: number;
  pass_accurate: number;
  pass_accuracy_pct: number;
}

export interface PlayerRating {
  overall: number;
  physical: number;
  attacking: number;
  positioning: number;
  pressing: number;
  passing: number;
  breakdown: RatingBreakdown;
}

export interface PassEvent {
  frame: number;
  kick_frame: number;
  result: 'accurate' | 'failed' | 'unknown';
}

export interface PassStats {
  total: number;
  accurate: number;
  failed: number;
  unknown: number;
  accuracy_pct: number;
  events: PassEvent[];
  coach_note: string;
}

export interface ActionItem {
  type: string;
  label: string;
}

export interface ActionCounts {
  positive_count: number;
  negative_count: number;
  positive_items: ActionItem[];
  negative_items: ActionItem[];
}

export interface TrainingDrill {
  drill: string;
  duration: string;
  focus: string;
}

export interface MatchAnalysis {
  actions: ActionCounts;
  summary: [string, string, string];
  recommendations: [TrainingDrill, TrainingDrill, TrainingDrill];
  ai_generated: boolean;
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
  rating?: PlayerRating;
  pass_stats?: PassStats;
  match_analysis?: MatchAnalysis;
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
