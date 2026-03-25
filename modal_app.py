"""
Modal GPU worker for Stride — app: stride-ai

Deploy:
    modal deploy modal_app.py

Copy the printed endpoint URL → set MODAL_ENDPOINT in Railway env vars.
"""
from __future__ import annotations

import os
import sys
import tempfile
import uuid

import modal

app = modal.App("stride-ai")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "libgl1", "libglib2.0-0", "libsm6", "libxext6")
    .pip_install(
        "fastapi[standard]",
        "opencv-python-headless",
        "numpy",
        "torch",
        "ultralytics",
        "matplotlib",
        "pillow",
        "anthropic>=0.50.0",
    )
    # Pre-download YOLOv8x weights into the image — avoids cold-start download
    .run_commands("python -c \"from ultralytics import YOLO; YOLO('yolov8x.pt')\"")
    .add_local_dir("engine", remote_path="/root/engine")
)

# FastAPI's Request is only available inside the container image.
# `with image.imports()` defers the import to container runtime.
with image.imports():
    from fastapi import Request


@app.function(
    image=image,
    gpu="A10G",     # A10G: 3x faster than T4 — essential for yolov8x@1280
    timeout=7200,   # 120-minute hard cap — covers 90-min match + upload/overhead
    min_containers=0,
)
@modal.fastapi_endpoint(method="POST")
async def analyze_video(request: Request):
    """
    Accepts multipart/form-data:
      video       — .mp4 file (required)
      frame_skip  — int 1-10 (default 10)
      click_x     — float 0-1 (default 0.5)
      click_y     — float 0-1 (default 0.5)
      jersey_color — hex string (optional)

    Returns the full pipeline result dict or {"status":"error","error":"..."}.
    """
    sys.path.insert(0, "/root")
    from engine.pipeline import PipelineConfig, run_pipeline  # noqa: PLC0415

    form = await request.form()

    video_file = form.get("video")
    if video_file is None:
        return {"status": "error", "error": "missing 'video' field in form"}

    contents = await video_file.read()
    if not contents:
        return {"status": "error", "error": "video file is empty"}

    frame_skip       = int(form.get("frame_skip", 5))
    click_x          = float(form.get("click_x", 0.5))
    click_y          = float(form.get("click_y", 0.5))
    jersey_color     = form.get("jersey_color") or None
    max_duration_s   = float(form.get("max_duration_s", 3600))  # default: full video

    run_id = str(uuid.uuid4())
    fd, tmp_path = tempfile.mkstemp(suffix=".mp4", prefix=f"stride_{run_id}_")
    try:
        os.close(fd)
        with open(tmp_path, "wb") as fh:
            fh.write(contents)

        config = PipelineConfig(
            frame_skip=max(1, min(20, frame_skip)),
            max_duration_s=max(10, max_duration_s),  # no upper cap
        )
        result = run_pipeline(
            tmp_path, config,
            run_id=run_id,
            click_x=click_x,
            click_y=click_y,
            jersey_color=jersey_color,
        )
        return result.to_dict()

    except Exception as exc:
        return {"engine": "vision-v8", "status": "error", "error": str(exc)}

    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
