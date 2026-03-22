"""
Frame enhancement pre-processing: noise → contrast → sharpening.
Applied per-frame before YOLO detection to improve detection quality
on low-resolution or compressed video.
"""

from dataclasses import dataclass
import logging
import time

import cv2
import numpy as np

log = logging.getLogger("enhance")


@dataclass
class EnhanceConfig:
    enabled: bool = True

    # ── Bilateral denoising ──────────────────────────────────────────────────
    # Edge-preserving: keeps jersey/ball edges sharp while removing compression noise.
    # d=5 = neighbourhood diameter; sigma values control colour/spatial smoothing.
    denoise_d: int = 5
    denoise_sigma: float = 28.0

    # ── CLAHE contrast enhancement ────────────────────────────────────────────
    # Applied only to the L channel of LAB so colours are unchanged.
    # clip_limit=2.5 prevents over-amplifying noise in flat areas.
    clahe_clip: float = 2.5
    clahe_grid: int = 8

    # ── Unsharp masking (sharpening) ─────────────────────────────────────────
    # strength=0.55 means: output = 1.55 * frame − 0.55 * blurred
    # Increases high-frequency detail (jersey numbers, player outlines).
    sharpen_strength: float = 0.55
    sharpen_blur_sigma: float = 1.8


class FrameEnhancer:
    """
    Lightweight, single-frame enhancement pipeline.

    Pipeline:
        1. Bilateral filter  — removes compression artifacts, keeps edges
        2. CLAHE             — normalises local contrast per tile
        3. Unsharp mask      — sharpens player contours
    """

    def __init__(self, config: EnhanceConfig):
        self.config = config
        self._clahe = None
        self._frames_processed = 0
        self._total_ms = 0.0

        if config.enabled and config.clahe_clip > 0:
            self._clahe = cv2.createCLAHE(
                clipLimit=config.clahe_clip,
                tileGridSize=(config.clahe_grid, config.clahe_grid),
            )

    # ── Public API ────────────────────────────────────────────────────────────

    def enhance(self, frame: np.ndarray) -> np.ndarray:
        """Return an enhanced copy of *frame* (BGR uint8)."""
        if not self.config.enabled:
            return frame

        t0 = time.perf_counter()

        frame = self._bilateral_denoise(frame)
        frame = self._clahe_contrast(frame)
        frame = self._unsharp_mask(frame)

        elapsed_ms = (time.perf_counter() - t0) * 1000
        self._frames_processed += 1
        self._total_ms += elapsed_ms
        return frame

    def avg_ms(self) -> float:
        if self._frames_processed == 0:
            return 0.0
        return self._total_ms / self._frames_processed

    # ── Steps ─────────────────────────────────────────────────────────────────

    def _bilateral_denoise(self, frame: np.ndarray) -> np.ndarray:
        """Edge-preserving noise reduction."""
        d = self.config.denoise_d
        s = self.config.denoise_sigma
        return cv2.bilateralFilter(frame, d=d, sigmaColor=s, sigmaSpace=s)

    def _clahe_contrast(self, frame: np.ndarray) -> np.ndarray:
        """CLAHE on L channel — corrects flat/over-exposed shots."""
        if self._clahe is None:
            return frame
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l = self._clahe.apply(l)
        lab = cv2.merge([l, a, b])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    def _unsharp_mask(self, frame: np.ndarray) -> np.ndarray:
        """Unsharp masking to sharpen player edges."""
        s = self.config.sharpen_strength
        if s <= 0:
            return frame
        blurred = cv2.GaussianBlur(frame, (0, 0), self.config.sharpen_blur_sigma)
        return cv2.addWeighted(frame, 1.0 + s, blurred, -s, 0)
