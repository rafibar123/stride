/**
 * vision-worker-proxy — Supabase Edge Function
 *
 * Flow:
 *   1. Receive multipart request: video file + optional params
 *   2. POST /preview → Railway (Stride) → preview_id
 *   3. POST /analyze → Railway                → job_id
 *   4. Poll  GET /progress/{job_id}           → result
 *   5. Map result → Overball DB schema
 *   6. Update analyses row in Supabase + return JSON
 *
 * Expected request (multipart/form-data):
 *   video        — video file (required)
 *   analysis_id  — Supabase row ID to update (required)
 *   click_x      — float 0-1 (optional, default 0.5)
 *   click_y      — float 0-1 (optional, default 0.5)
 *   frame_skip   — int 1-10  (optional, default 10)
 */

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const STRIDE_API    = "https://web-production-c4e3a.up.railway.app";
const POLL_INTERVAL = 2000;   // ms between /progress polls
const POLL_TIMEOUT  = 20 * 60 * 1000; // 20 min hard cap

const corsHeaders = {
  "Access-Control-Allow-Origin":  "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function num(v: unknown, fallback = 0): number {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

function ratingToLevel(overall: number): string {
  if (overall >= 85) return "elite";
  if (overall >= 75) return "advanced";
  if (overall >= 60) return "intermediate";
  return "beginner";
}

/** Map Stride PipelineResult → Overball analysis_result schema */
function buildAnalysisResult(r: Record<string, unknown>) {
  const player = (r.per_player_metrics as Record<string, unknown>[])?.[0] ?? {};
  const ev     = (r.event_metrics as Record<string, unknown>) ?? {};
  const ps     = (r.pass_stats   as Record<string, unknown>) ?? {};
  const rating = (r.rating       as Record<string, unknown>) ?? {};
  const fps    = num(r.fps, 25);
  const frames = num(r.frames_processed, 0);

  const completedPasses = num(ps.accurate,   num(ev.pass_success));
  const failedPasses    = num(ps.failed,     num(ev.pass_fail));
  const xG              = num(ev.xG_team_1) + num(ev.xG_team_2);
  const overallScore    = num(rating.overall, 0);

  const radar = overallScore > 0 ? {
    pace:        num(rating.physical),
    shooting:    num(rating.attacking),
    passing:     num(rating.passing),
    dribbling:   num(rating.pressing),
    defending:   num(rating.positioning),
    physical:    num(rating.physical),
  } : null;

  return {
    score:             overallScore > 0 ? overallScore : null,
    level:             overallScore > 0 ? ratingToLevel(overallScore) : null,
    is_fallback:       false,
    data_source:       "stride_gpu",
    radar,
    completed_passes:  completedPasses,
    failed_passes:     failedPasses,
    shots:             num(ev.shot_count),
    shots_on_target:   null,
    xG,
    total_distance_m:  num(player.distance_m),
    top_speed_mps:     num(player.max_speed_mps),
    minutes_played:    frames > 0 ? frames / fps / 60 : null,
    heatmap_url:       null,
  };
}

// ── Main handler ──────────────────────────────────────────────────────────────

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
  );

  let analysisId: string | null = null;

  try {
    const form = await req.formData();

    const videoFile  = form.get("video") as File | null;
    analysisId       = form.get("analysis_id") as string | null;
    const clickX     = parseFloat((form.get("click_x") as string) ?? "0.5");
    const clickY     = parseFloat((form.get("click_y") as string) ?? "0.5");
    const frameSkip  = parseInt((form.get("frame_skip") as string) ?? "10", 10);

    if (!videoFile) throw new Error("Missing 'video' field");
    if (!analysisId) throw new Error("Missing 'analysis_id' field");

    // ── Mark as processing ────────────────────────────────────────────────────
    await supabase
      .from("analyses")
      .update({ status: "processing", ai_progress: 5 })
      .eq("id", analysisId);

    // ── Step 1: upload to Railway /preview ────────────────────────────────────
    const previewFd = new FormData();
    previewFd.append("video", videoFile);

    const previewRes = await fetch(`${STRIDE_API}/preview`, {
      method: "POST",
      body: previewFd,
    });
    if (!previewRes.ok) throw new Error(`/preview failed: ${previewRes.status}`);
    const { preview_id } = await previewRes.json() as { preview_id: string };

    await supabase
      .from("analyses")
      .update({ ai_progress: 10 })
      .eq("id", analysisId);

    // ── Step 2: start analysis job ────────────────────────────────────────────
    const analyzeFd = new FormData();
    analyzeFd.append("preview_id", preview_id);
    analyzeFd.append("frame_skip", String(Math.max(1, Math.min(10, frameSkip))));
    analyzeFd.append("click_x",   String(clickX));
    analyzeFd.append("click_y",   String(clickY));

    const analyzeRes = await fetch(`${STRIDE_API}/analyze`, {
      method: "POST",
      body: analyzeFd,
    });
    if (!analyzeRes.ok) throw new Error(`/analyze failed: ${analyzeRes.status}`);
    const { job_id } = await analyzeRes.json() as { job_id: string };

    // ── Step 3: poll /progress/{job_id} ──────────────────────────────────────
    const deadline = Date.now() + POLL_TIMEOUT;
    let strideResult: Record<string, unknown> | null = null;

    while (Date.now() < deadline) {
      await new Promise<void>((r) => setTimeout(r, POLL_INTERVAL));

      let progress: { pct?: number; stage?: string; result?: Record<string, unknown>; error?: string };
      try {
        const res = await fetch(`${STRIDE_API}/progress/${job_id}`);
        if (!res.ok) continue;
        progress = await res.json();
      } catch {
        continue;
      }

      // Mirror GPU progress into Supabase so the client can show a live bar
      if (typeof progress.pct === "number") {
        await supabase
          .from("analyses")
          .update({ ai_progress: Math.min(95, Math.round(progress.pct)) })
          .eq("id", analysisId);
      }

      if (progress.stage === "done" && progress.result) {
        strideResult = progress.result;
        break;
      }
      if (progress.stage === "error") {
        throw new Error(progress.error ?? "Stride pipeline error");
      }
    }

    if (!strideResult) throw new Error("Stride analysis timed out");

    // ── Step 4: write results to Supabase ────────────────────────────────────
    const analysisResult = buildAnalysisResult(strideResult);

    await supabase
      .from("analyses")
      .update({
        status:          "completed",
        ai_progress:     100,
        metrics_json:    strideResult,
        analysis_result: analysisResult,
        completed_at:    new Date().toISOString(),
      })
      .eq("id", analysisId);

    return new Response(
      JSON.stringify({ ok: true, analysis_id: analysisId, result: analysisResult }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" } },
    );

  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error("[vision-worker-proxy] error:", message);

    if (analysisId) {
      await supabase
        .from("analyses")
        .update({ status: "error", ai_progress: 0 })
        .eq("id", analysisId)
        .catch(() => {/* ignore secondary failure */});
    }

    return new Response(
      JSON.stringify({ ok: false, error: message }),
      {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      },
    );
  }
});
