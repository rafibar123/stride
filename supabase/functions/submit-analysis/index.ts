/**
 * submit-analysis — Supabase Edge Function
 *
 * Triggered with { analysis_id } in the JSON body.
 * Downloads the video from Supabase Storage, streams it to Railway (Stride),
 * polls for the result, then writes it back to the analyses row.
 *
 * This function is a thin bridge — all heavy work (YOLO, GPU) happens on
 * Railway → Modal (stride-ai). There is NO direct Modal call here.
 */

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const STRIDE_API   = "https://web-production-c4e3a.up.railway.app";
const POLL_MS      = 3000;
const POLL_TIMEOUT = 100 * 60 * 1000; // 100 min — covers 90-min match + server overhead

const corsHeaders = {
  "Access-Control-Allow-Origin":  "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

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
    const body = await req.json();
    analysisId = body.analysis_id as string | null;
    if (!analysisId) throw new Error("Missing analysis_id");

    // ── Fetch analysis row ────────────────────────────────────────
    const { data: analysis, error: fetchErr } = await supabase
      .from("analyses")
      .select("id, video_bucket, video_path, status")
      .eq("id", analysisId)
      .single();

    if (fetchErr || !analysis) throw new Error(`Analysis not found: ${fetchErr?.message}`);
    if (analysis.status === "completed") {
      return new Response(JSON.stringify({ ok: true, skipped: true }), {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const { error: markErr } = await supabase
      .from("analyses")
      .update({ status: "processing", ai_progress: 5 })
      .eq("id", analysisId);
    if (markErr) console.error("[submit-analysis] mark processing:", markErr.message);

    // ── Download video from Supabase Storage ──────────────────────
    const bucket = analysis.video_bucket ?? "match-videos";
    const { data: signed, error: signErr } = await supabase.storage
      .from(bucket)
      .createSignedUrl(analysis.video_path, 3600);

    if (signErr || !signed?.signedUrl) throw new Error(`Signed URL failed: ${signErr?.message}`);

    const videoRes = await fetch(signed.signedUrl);
    if (!videoRes.ok) throw new Error(`Video download failed: ${videoRes.status}`);
    const videoBlob = await videoRes.blob();

    // ── POST /preview → Railway ───────────────────────────────────
    const previewFd = new FormData();
    previewFd.append("video", videoBlob, "video.mp4");

    const previewRes = await fetch(`${STRIDE_API}/preview`, { method: "POST", body: previewFd });
    if (!previewRes.ok) throw new Error(`/preview failed: ${previewRes.status}`);
    const { preview_id } = await previewRes.json() as { preview_id: string };

    const { error: previewProgressErr } = await supabase
      .from("analyses")
      .update({ ai_progress: 10 })
      .eq("id", analysisId);
    if (previewProgressErr) console.error("[submit-analysis] progress 10:", previewProgressErr.message);

    // ── POST /analyze → Railway ───────────────────────────────────
    const analyzeFd = new FormData();
    analyzeFd.append("preview_id", preview_id);
    analyzeFd.append("frame_skip", "10");
    analyzeFd.append("click_x",   "0.5");
    analyzeFd.append("click_y",   "0.5");

    const analyzeRes = await fetch(`${STRIDE_API}/analyze`, { method: "POST", body: analyzeFd });
    if (!analyzeRes.ok) throw new Error(`/analyze failed: ${analyzeRes.status}`);
    const { job_id } = await analyzeRes.json() as { job_id: string };

    // ── Poll /progress/{job_id} ───────────────────────────────────
    const deadline = Date.now() + POLL_TIMEOUT;
    let strideResult: Record<string, unknown> | null = null;

    while (Date.now() < deadline) {
      await new Promise<void>((r) => setTimeout(r, POLL_MS));

      let progress: { pct?: number; stage?: string; result?: Record<string, unknown>; error?: string };
      try {
        const res = await fetch(`${STRIDE_API}/progress/${job_id}`);
        if (!res.ok) continue;
        progress = await res.json();
      } catch {
        continue;
      }

      if (typeof progress.pct === "number") {
        const { error: pollUpdateErr } = await supabase
          .from("analyses")
          .update({ ai_progress: Math.min(95, Math.round(progress.pct)) })
          .eq("id", analysisId);
        if (pollUpdateErr) console.warn("[submit-analysis] progress mirror:", pollUpdateErr.message);
      }

      if (progress.stage === "done" && progress.result) {
        strideResult = progress.result;
        break;
      }
      if (progress.stage === "error") throw new Error(progress.error ?? "Stride pipeline error");
    }

    if (!strideResult) throw new Error("Stride analysis timed out");

    // ── Write results back to Supabase ────────────────────────────
    const player  = (strideResult.per_player_metrics as Record<string, unknown>[])?.[0] ?? {};
    const ev      = (strideResult.event_metrics as Record<string, unknown>) ?? {};
    const ps      = (strideResult.pass_stats   as Record<string, unknown>) ?? {};
    const rating  = (strideResult.rating       as Record<string, unknown>) ?? {};
    const fps     = Number(strideResult.fps ?? 25);
    const frames  = Number(strideResult.frames_processed ?? 0);
    const overall = Number(rating.overall ?? 0);

    const analysisResult = {
      score:              overall > 0 ? overall : null,
      level:              overall >= 8.5 ? "elite" : overall >= 7.5 ? "advanced" : overall >= 6.0 ? "intermediate" : overall > 0 ? "beginner" : null,
      is_fallback:        false,
      data_source:        "stride_gpu",
      radar:              overall > 0 ? {
        pace:      Number(rating.physical ?? 0),
        shooting:  Number(rating.attacking ?? 0),
        passing:   Number(rating.passing ?? 0),
        dribbling: Number(rating.pressing ?? 0),
        defending: Number(rating.positioning ?? 0),
        physical:  Number(rating.physical ?? 0),
      } : null,
      completed_passes:   Number(ps.accurate ?? (ev.pass_success ?? 0)),
      failed_passes:      Number(ps.failed   ?? (ev.pass_fail   ?? 0)),
      shots:              Number(ev.shot_count ?? 0),
      shots_on_target:    null,
      xG:                 Number(ev.xG_team_1 ?? 0) + Number(ev.xG_team_2 ?? 0),
      total_distance_km:  Number(player.distance_m ?? 0) / 1000,
      avg_speed_kmh:      Number(player.avg_speed_mps ?? 0) * 3.6,
      top_speed_kmh:      Number(player.max_speed_mps ?? 0) * 3.6,
      goals:              Number(player.goals ?? 0),
      assists:            Number(player.assists ?? 0),
      minutes_played:     frames > 0 ? frames / fps / 60 : null,
      heatmap_url:        null,
    };

    const { error: writeErr } = await supabase
      .from("analyses")
      .update({
        status:          "completed",
        ai_progress:     100,
        metrics_json:    strideResult,
        analysis_result: analysisResult,
        completed_at:    new Date().toISOString(),
      })
      .eq("id", analysisId);
    if (writeErr) console.error("[submit-analysis] final write:", writeErr.message);

    return new Response(
      JSON.stringify({ ok: true, analysis_id: analysisId, result: analysisResult }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" } },
    );

  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error("[submit-analysis] error:", message);

    if (analysisId) {
      await supabase
        .from("analyses")
        .update({ status: "error", ai_progress: 0 })
        .eq("id", analysisId)
        .catch(() => {});
    }

    return new Response(
      JSON.stringify({ ok: false, error: message }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } },
    );
  }
});
