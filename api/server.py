"""
Stride — FastAPI server

Endpoints
---------
POST /preview          Upload video → {preview_id, width, height}; stores file for analysis
GET  /frame/{preview_id} Returns JPEG of the first video frame for player selection
POST /analyze          {preview_id, click_x, click_y} → {job_id}; poll /progress/{job_id}
POST /analyze/report   Upload a video → PDF report download
GET  /progress/{job_id} Live progress; includes 'result' when stage=='done'
GET  /health           Liveness check
"""

import asyncio
import logging
import os
import sys
import time
import uuid
from functools import partial
from threading import Lock
from typing import Optional

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    import cv2
except ImportError as _cv2_err:
    cv2 = None  # type: ignore
    print(f"[server] WARNING: cv2 import failed: {_cv2_err}", flush=True)

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

try:
    from engine.pipeline import PipelineConfig, run_pipeline
    from engine.report import generate_pdf
    from engine.analysis import generate_match_analysis
    _ENGINE_OK = True
except Exception as _engine_err:
    _ENGINE_OK = False
    print(f"[server] WARNING: engine import failed: {_engine_err}", flush=True)

MODAL_ENDPOINT = os.environ.get("MODAL_ENDPOINT", "").strip() or None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("server")

app = FastAPI(
    title="Stride",
    version="2.0.0",
    description="Personal football performance tracker.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── stores ────────────────────────────────────────────────────────────────────

_jobs: dict = {}
_jobs_lock = Lock()

# Maps preview_id → {"video_path": str, "frame_path": str, "width": int, "height": int}
_previews: dict = {}
_previews_lock = Lock()


# ── cleanup helpers ───────────────────────────────────────────────────────────

def _cleanup(path: str) -> None:
    try:
        if path and os.path.exists(path):
            os.unlink(path)
    except OSError:
        pass


async def _schedule_job_cleanup(job_id: str, delay: int = 300) -> None:
    await asyncio.sleep(delay)
    with _jobs_lock:
        _jobs.pop(job_id, None)


async def _schedule_preview_cleanup(preview_id: str, delay: int = 1800) -> None:
    await asyncio.sleep(delay)
    with _previews_lock:
        info = _previews.pop(preview_id, None)
    if info:
        _cleanup(info.get("video_path", ""))
        _cleanup(info.get("frame_path", ""))


# ── upload helper ─────────────────────────────────────────────────────────────

def _save_upload_to_tmp(video: UploadFile, uid: str) -> str:
    tmp_path = f"/tmp/video_{uid}.mp4"
    with open(tmp_path, "wb") as f:
        for chunk in iter(lambda: video.file.read(1024 * 1024), b""):
            f.write(chunk)
    return tmp_path


# ── background pipeline task ──────────────────────────────────────────────────

_ANALYSIS_TIMEOUT_S = 15 * 60  # 15 minutes hard cap


async def _call_modal(
    job_id: str,
    video_path: str,
    frame_skip: int,
    click_x: Optional[float],
    click_y: Optional[float],
    jersey_color: Optional[str],
    max_duration_s: float = 300.0,
) -> dict:
    """Send video to Modal GPU worker and return the result dict."""

    def _set(pct: float, stage: str) -> None:
        with _jobs_lock:
            _jobs[job_id] = {"pct": pct, "stage": stage}

    _set(5, "uploading_to_gpu")
    file_size_mb = os.path.getsize(video_path) / 1024 / 1024
    log.info("[%s] sending to Modal GPU  endpoint=%s  size=%.1fMB  max_dur=%.0fs",
             job_id[:8], MODAL_ENDPOINT, file_size_mb, max_duration_s)

    # Bump progress every 10 s while we wait so the UI doesn't look frozen.
    async def _ticker() -> None:
        pct = 10.0
        while True:
            await asyncio.sleep(10)
            pct = min(pct + 3, 88)
            _set(pct, "gpu_processing")

    ticker = asyncio.create_task(_ticker())
    try:
        data = {
            "frame_skip":     str(frame_skip),
            "click_x":        str(click_x  if click_x   is not None else 0.5),
            "click_y":        str(click_y  if click_y   is not None else 0.5),
            "max_duration_s": str(max_duration_s),
        }
        if jersey_color:
            data["jersey_color"] = jersey_color

        with open(video_path, "rb") as fh:
            video_bytes = fh.read()

        # Timeout = video duration cap + 120s upload/cold-start buffer
        http_timeout = max_duration_s + 120
        async with httpx.AsyncClient(timeout=http_timeout) as client:
            resp = await client.post(
                MODAL_ENDPOINT,
                data=data,
                files={"video": ("video.mp4", video_bytes, "video/mp4")},
            )
        resp.raise_for_status()
        result = resp.json()

    finally:
        ticker.cancel()

    if result.get("status") == "error" or "error" in result:
        raise RuntimeError(result.get("error", "Modal worker returned an error"))

    log.info("[%s] Modal GPU done", job_id[:8])
    return result


_GPU_MAX_DURATION_S = 300.0   # 5-minute cap on Modal GPU
_CPU_MAX_DURATION_S  = 30.0   # 30-second cap on Railway CPU fallback


async def _run_analysis(job_id: str, video_path: str, frame_skip: int,
                        click_x: Optional[float] = None,
                        click_y: Optional[float] = None,
                        jersey_color: Optional[str] = None,
                        player_info: Optional[dict] = None) -> None:
    t0 = time.time()
    try:
        def on_progress(pct: float, stage: str) -> None:
            with _jobs_lock:
                _jobs[job_id] = {"pct": pct, "stage": stage}

        loop = asyncio.get_event_loop()

        if MODAL_ENDPOINT:
            # ── GPU path (Modal) ───────────────────────────────────────────
            try:
                result_dict = await asyncio.wait_for(
                    _call_modal(job_id, video_path, frame_skip, click_x, click_y,
                                jersey_color, max_duration_s=_GPU_MAX_DURATION_S),
                    timeout=_ANALYSIS_TIMEOUT_S,
                )
            except asyncio.TimeoutError:
                log.error("[%s] Modal timed out after %ds", job_id[:8], _ANALYSIS_TIMEOUT_S)
                with _jobs_lock:
                    _jobs[job_id] = {
                        "pct": 0, "stage": "error",
                        "error": f"Analysis timed out after {_ANALYSIS_TIMEOUT_S // 60} minutes.",
                    }
                return
        else:
            # ── CPU path (local fallback) ──────────────────────────────────
            config = PipelineConfig(frame_skip=frame_skip, max_duration_s=_CPU_MAX_DURATION_S)
            try:
                result_obj = await asyncio.wait_for(
                    loop.run_in_executor(
                        None, partial(run_pipeline, video_path, config, run_id=job_id,
                                      progress_cb=on_progress, click_x=click_x, click_y=click_y,
                                      jersey_color=jersey_color)
                    ),
                    timeout=_ANALYSIS_TIMEOUT_S,
                )
            except asyncio.TimeoutError:
                log.error("[%s] pipeline timed out after %ds", job_id[:8], _ANALYSIS_TIMEOUT_S)
                with _jobs_lock:
                    _jobs[job_id] = {
                        "pct": 0, "stage": "error",
                        "error": f"Analysis timed out after {_ANALYSIS_TIMEOUT_S // 60} minutes. "
                                 "Try a shorter clip (under 30 s) or increase frame skip.",
                    }
                return
            result_dict = result_obj.to_dict()
        if player_info:
            result_dict["player_info"] = player_info

        # ── AI match analysis (60-second cap) ─────────────────────────────
        with _jobs_lock:
            _jobs[job_id] = {"pct": 95, "stage": "ai_analysis"}

        try:
            match_analysis = await asyncio.wait_for(
                loop.run_in_executor(None, generate_match_analysis, result_dict),
                timeout=60.0,
            )
            result_dict["match_analysis"] = match_analysis
            log.info(
                "[%s] match analysis done  ai=%s  pos=%d  neg=%d",
                job_id[:8],
                match_analysis.get("ai_generated"),
                match_analysis.get("actions", {}).get("positive_count", 0),
                match_analysis.get("actions", {}).get("negative_count", 0),
            )
        except asyncio.TimeoutError:
            log.warning("[%s] AI analysis timed out after 60s — skipping", job_id[:8])
        except Exception as exc:
            log.warning("[%s] match analysis failed: %s", job_id[:8], exc)

        with _jobs_lock:
            _jobs[job_id] = {"pct": 100, "stage": "done", "result": result_dict}

        log.info("[%s] analysis done  %.2fs", job_id[:8], time.time() - t0)

    except Exception as exc:
        log.exception("[%s] analysis failed", job_id[:8])
        with _jobs_lock:
            _jobs[job_id] = {"pct": 0, "stage": "error", "error": str(exc)}
    finally:
        _cleanup(video_path)
        # create_task lives OUTSIDE the try so a failure here never corrupts job state
        try:
            asyncio.create_task(_schedule_job_cleanup(job_id, delay=300))
        except RuntimeError:
            pass  # event loop already closed (e.g. during shutdown)


# ── routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    import sys, platform
    return {
        "status": "ok",
        "python": sys.version,
        "platform": platform.platform(),
        "port": os.environ.get("PORT", "not set"),
        "cv2": cv2 is not None if cv2 else False,
        "engine": _ENGINE_OK,
    }


@app.post("/preview")
async def preview(video: UploadFile = File(...)):
    """
    Upload a video. Saves it to disk, extracts the first frame as JPEG,
    and returns {preview_id, width, height}. Use GET /frame/{preview_id}
    to display the frame for player selection, then POST /analyze with the
    preview_id and click coordinates.
    """
    preview_id = str(uuid.uuid4())
    video_path = _save_upload_to_tmp(video, preview_id)

    cap = cv2.VideoCapture(video_path)
    ok, frame = cap.read()
    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    if not ok or frame is None:
        _cleanup(video_path)
        raise HTTPException(status_code=422, detail="Could not read first frame from video")

    frame_path = f"/tmp/frame_{preview_id}.jpg"
    cv2.imwrite(frame_path, frame)

    with _previews_lock:
        _previews[preview_id] = {
            "video_path": video_path,
            "frame_path": frame_path,
            "width": width,
            "height": height,
        }

    log.info("[%s] preview saved  %dx%d  %.1f KB",
             preview_id[:8], width, height, os.path.getsize(video_path) / 1024)

    asyncio.create_task(_schedule_preview_cleanup(preview_id, delay=1800))

    return JSONResponse(content={"preview_id": preview_id, "width": width, "height": height})


@app.get("/frame/{preview_id}")
def get_frame(preview_id: str):
    """Return the JPEG first frame for a preview."""
    with _previews_lock:
        info = _previews.get(preview_id)
    if not info or not os.path.exists(info.get("frame_path", "")):
        raise HTTPException(status_code=404, detail="Preview not found or expired")
    return FileResponse(info["frame_path"], media_type="image/jpeg")


@app.post("/analyze")
async def analyze(
    background_tasks: BackgroundTasks,
    preview_id: str = Form(...),
    frame_skip: int = Form(10),
    click_x: float = Form(0.5),
    click_y: float = Form(0.5),
    jersey_color: Optional[str] = Form(None),
    player_name: Optional[str] = Form(None),
    player_number: Optional[str] = Form(None),
    team_name: Optional[str] = Form(None),
):
    """
    Start analysis for a previously uploaded preview.
    click_x / click_y are normalised 0-1 coordinates of the player the user
    selected in the frame. Returns {job_id}; poll GET /progress/{job_id}.
    """
    if frame_skip < 1 or frame_skip > 10:
        raise HTTPException(status_code=422, detail="frame_skip must be between 1 and 10")

    with _previews_lock:
        info = _previews.get(preview_id)

    if not info:
        raise HTTPException(status_code=404, detail="Preview not found or expired. Re-upload the video.")

    video_path = info["video_path"]
    job_id = str(uuid.uuid4())

    player_info: Optional[dict] = None
    if player_name:
        player_info = {
            "name": player_name,
            "number": player_number or "",
            "jerseyColor": jersey_color or "#ffffff",
            "teamName": team_name or "",
        }

    with _jobs_lock:
        _jobs[job_id] = {"pct": 0, "stage": "starting"}

    log.info("[%s] analyze  preview=%s  frame_skip=%d  click=(%.3f, %.3f)  jersey=%s  player=%s",
             job_id[:8], preview_id[:8], frame_skip, click_x, click_y,
             jersey_color, player_name)

    background_tasks.add_task(
        _run_analysis, job_id, video_path, frame_skip,
        click_x, click_y, jersey_color, player_info,
    )

    return JSONResponse(content={"job_id": job_id})


@app.get("/progress/{job_id}")
def get_progress(job_id: str):
    """Poll for progress. When stage=='done', response includes 'result'."""
    with _jobs_lock:
        info = _jobs.get(job_id)
    if info is None:
        return {"pct": 0, "stage": "queued"}
    return info


class ReanalyzeRequest(BaseModel):
    result: dict
    manual_stats: dict


@app.post("/reanalyze")
async def reanalyze(body: ReanalyzeRequest):
    """
    Re-run match analysis with combined AI-detected + player-reported stats.
    Returns an updated match_analysis dict.
    """
    loop = asyncio.get_event_loop()
    match_analysis = await loop.run_in_executor(
        None, generate_match_analysis, body.result, body.manual_stats
    )
    return match_analysis


@app.post("/report")
async def report_from_result(background_tasks: BackgroundTasks, request_data: dict):
    """
    Generate a PDF from an already-computed result dict.
    Accepts the JSON body returned by GET /progress/{job_id} under 'result'.
    Returns the PDF file immediately — no pipeline re-run needed.
    """
    job_id = str(uuid.uuid4())
    tmp_pdf = f"/tmp/report_{job_id}.pdf"
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, partial(generate_pdf, request_data, tmp_pdf))
        background_tasks.add_task(_cleanup, tmp_pdf)
        return FileResponse(
            path=tmp_pdf,
            media_type="application/pdf",
            filename=f"stride_report_{job_id[:8]}.pdf",
        )
    except RuntimeError as exc:
        _cleanup(tmp_pdf)
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        _cleanup(tmp_pdf)
        raise HTTPException(status_code=500, detail=f"Report generation error: {exc}")


@app.post("/analyze/report")
async def analyze_report(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    frame_skip: int = 10,
):
    """Upload a video and receive a personal performance PDF report."""
    if frame_skip < 1 or frame_skip > 10:
        raise HTTPException(status_code=422, detail="frame_skip must be between 1 and 10")

    job_id = str(uuid.uuid4())
    tmp_video = None
    tmp_pdf = f"/tmp/report_{job_id}.pdf"
    try:
        t0 = time.time()
        tmp_video = _save_upload_to_tmp(video, job_id)
        config = PipelineConfig(frame_skip=frame_skip)

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, partial(run_pipeline, tmp_video, config, run_id=job_id)
        )
        await loop.run_in_executor(None, partial(generate_pdf, result.to_dict(), tmp_pdf))
        log.info("[%s] /analyze/report done  %.2fs", job_id[:8], time.time() - t0)

        background_tasks.add_task(_cleanup, tmp_pdf)
        return FileResponse(
            path=tmp_pdf,
            media_type="application/pdf",
            filename=f"stride_report_{job_id[:8]}.pdf",
        )

    except RuntimeError as exc:
        _cleanup(tmp_pdf)
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        _cleanup(tmp_pdf)
        raise HTTPException(status_code=500, detail=f"Report generation error: {exc}")
    finally:
        _cleanup(tmp_video)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("api.server:app", host="0.0.0.0", port=port, reload=False)
