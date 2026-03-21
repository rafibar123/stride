"""
Modal GPU worker for Stride.

Deploy:
    modal deploy modal_app.py

After deploying, copy the printed endpoint URL and set it as the
MODAL_ENDPOINT environment variable in Railway.
"""
import os
import sys
import tempfile
import uuid
from typing import Optional

import modal
from fastapi import File, Form, UploadFile

app = modal.App("stride")

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
    .add_local_dir("engine", remote_path="/root/engine")
)


@app.function(
    image=image,
    gpu="T4",
    timeout=600,
    min_containers=0,
)
@modal.fastapi_endpoint(method="POST")
async def analyze_video(
    video: UploadFile = File(...),
    frame_skip: int = Form(10),
    click_x: float = Form(0.5),
    click_y: float = Form(0.5),
    jersey_color: Optional[str] = Form(None),
):
    sys.path.insert(0, "/root")
    from engine.pipeline import PipelineConfig, run_pipeline  # noqa: PLC0415

    run_id = str(uuid.uuid4())
    fd, tmp_path = tempfile.mkstemp(suffix=".mp4", prefix=f"stride_{run_id}_")
    try:
        os.close(fd)
        contents = await video.read()
        with open(tmp_path, "wb") as f:
            f.write(contents)

        config = PipelineConfig(frame_skip=max(1, min(10, frame_skip)))
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
