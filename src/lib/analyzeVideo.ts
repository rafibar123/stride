import { normalizeAnalysis, type NormalizedAnalysis, type RawEngineResponse } from "./normalizeAnalysis";

const STRIDE_API = "https://web-production-c4e3a.up.railway.app";
const POLL_INTERVAL_MS = 1500;
const POLL_TIMEOUT_MS = 22 * 60 * 1000; // 22 min — matches Railway's 15-min cap + buffer

// ── Map Stride pipeline result → RawEngineResponse ────────────────────────────
// Stride returns a full PipelineResult; we pick the fields Overball needs.

function strideToRaw(result: Record<string, unknown>): RawEngineResponse {
  const player = (result.per_player_metrics as unknown[])?.[0] as Record<string, unknown> ?? {};
  const ev     = (result.event_metrics as Record<string, unknown>) ?? {};
  const ps     = (result.pass_stats   as Record<string, unknown>) ?? {};
  const fps    = (result.fps as number) ?? 25;
  const frames = (result.frames_processed as number) ?? 0;

  // Passes: prefer detect_passes() output (more accurate) over EventEngine counters
  const totalPasses    = (ps.total    as number) ?? ((ev.pass_success as number ?? 0) + (ev.pass_fail as number ?? 0));
  const accuratePasses = (ps.accurate as number) ?? (ev.pass_success as number) ?? 0;
  const passAccuracy   = (ps.accuracy_pct as number) ?? null;

  // xG: sum of both teams (tracked-player team is usually team_1)
  const xg = ((ev.xG_team_1 as number) ?? 0) + ((ev.xG_team_2 as number) ?? 0);

  return {
    passes:          totalPasses,
    accurate_passes: accuratePasses,
    pass_accuracy:   passAccuracy,
    shots:           (ev.shot_count as number)    ?? 0,
    shots_on_target: null,                          // not tracked by Stride
    xg,
    distance_km:     player.distance_m != null
                       ? (player.distance_m as number) / 1000
                       : null,
    top_speed_kmh:   player.max_speed_mps != null
                       ? (player.max_speed_mps as number) * 3.6
                       : null,
    minutes:         frames > 0 ? frames / fps / 60 : null,
    heatmap_url:     null,                          // Stride returns points, not a URL
    events:          (result.events as unknown[]) ?? [],
    // keep the full raw dict for consumers that want deeper fields
    ...(result as RawEngineResponse),
  };
}

// ── Public API ─────────────────────────────────────────────────────────────────

export interface AnalyzeOptions {
  /** Normalised (0-1) click position of the player to track. Defaults to centre. */
  clickX?: number;
  clickY?: number;
  /** Process every Nth frame. Higher = faster but less detail. Default 10. */
  frameSkip?: number;
  /** Called with 0-100 progress while waiting for the GPU worker. */
  onProgress?: (pct: number, stage: string) => void;
}

export async function analyzeVideo(
  file: File,
  options: AnalyzeOptions = {},
): Promise<NormalizedAnalysis> {
  const { clickX = 0.5, clickY = 0.5, frameSkip = 10, onProgress } = options;

  onProgress?.(2, "uploading");

  // ── Step 1: upload video, get preview_id ─────────────────────────────────────
  const previewFd = new FormData();
  previewFd.append("video", file);

  const previewRes = await fetch(`${STRIDE_API}/preview`, {
    method: "POST",
    body: previewFd,
  });
  if (!previewRes.ok) {
    const text = await previewRes.text();
    throw new Error(`Preview upload failed (${previewRes.status}): ${text}`);
  }
  const { preview_id } = await previewRes.json() as { preview_id: string };

  onProgress?.(8, "starting");

  // ── Step 2: start analysis job ───────────────────────────────────────────────
  const analyzeFd = new FormData();
  analyzeFd.append("preview_id", preview_id);
  analyzeFd.append("frame_skip", String(frameSkip));
  analyzeFd.append("click_x",   String(clickX));
  analyzeFd.append("click_y",   String(clickY));

  const analyzeRes = await fetch(`${STRIDE_API}/analyze`, {
    method: "POST",
    body: analyzeFd,
  });
  if (!analyzeRes.ok) {
    const text = await analyzeRes.text();
    throw new Error(`Analysis start failed (${analyzeRes.status}): ${text}`);
  }
  const { job_id } = await analyzeRes.json() as { job_id: string };

  onProgress?.(10, "processing");

  // ── Step 3: poll /progress/{job_id} ─────────────────────────────────────────
  const deadline = Date.now() + POLL_TIMEOUT_MS;

  while (Date.now() < deadline) {
    await new Promise<void>((r) => setTimeout(r, POLL_INTERVAL_MS));

    let data: { pct?: number; stage?: string; result?: Record<string, unknown>; error?: string };
    try {
      const res = await fetch(`${STRIDE_API}/progress/${job_id}`);
      if (!res.ok) continue;
      data = await res.json();
    } catch {
      continue; // transient network hiccup — keep polling
    }

    onProgress?.(data.pct ?? 10, data.stage ?? "processing");

    if (data.stage === "done" && data.result) {
      return normalizeAnalysis(strideToRaw(data.result));
    }
    if (data.stage === "error") {
      throw new Error(data.error ?? "Analysis pipeline error");
    }
  }

  throw new Error("Analysis timed out after 22 minutes");
}
