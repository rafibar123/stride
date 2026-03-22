import { useEffect, useRef } from 'react';

interface Props {
  points: [number, number][];
  pitchLength?: number;
  pitchWidth?: number;
}

const PITCH_L = 105;
const PITCH_W = 68;
const GRID_COLS = 105;
const GRID_ROWS = 68;

// ── Gaussian blur (separable) ─────────────────────────────────────────────────

function gaussKernel(sigma: number, radius: number): Float32Array {
  const k = new Float32Array(radius * 2 + 1);
  let sum = 0;
  for (let i = -radius; i <= radius; i++) {
    k[i + radius] = Math.exp(-(i * i) / (2 * sigma * sigma));
    sum += k[i + radius];
  }
  for (let i = 0; i < k.length; i++) k[i] /= sum;
  return k;
}

function gaussianBlur2D(src: Float32Array, cols: number, rows: number, sigma: number): Float32Array {
  const radius = Math.ceil(sigma * 2.5);
  const k = gaussKernel(sigma, radius);
  const tmp = new Float32Array(cols * rows);
  for (let y = 0; y < rows; y++) {
    for (let x = 0; x < cols; x++) {
      let v = 0;
      for (let d = -radius; d <= radius; d++) {
        const nx = Math.max(0, Math.min(cols - 1, x + d));
        v += src[y * cols + nx] * k[d + radius];
      }
      tmp[y * cols + x] = v;
    }
  }
  const dst = new Float32Array(cols * rows);
  for (let y = 0; y < rows; y++) {
    for (let x = 0; x < cols; x++) {
      let v = 0;
      for (let d = -radius; d <= radius; d++) {
        const ny = Math.max(0, Math.min(rows - 1, y + d));
        v += tmp[ny * cols + x] * k[d + radius];
      }
      dst[y * cols + x] = v;
    }
  }
  return dst;
}

// ── Colormap: transparent → blue → cyan → yellow → red ───────────────────────

function colormap(t: number): [number, number, number, number] {
  if (t < 0.015) return [0, 0, 0, 0];
  const stops: [number, number, number, number, number][] = [
    [0.015,   0,  30, 220, 0.25],
    [0.18,    0,  90, 255, 0.46],
    [0.36,    0, 210, 230, 0.60],
    [0.54,   50, 225,  60, 0.70],
    [0.70,  255, 215,   0, 0.78],
    [0.85,  255,  80,   0, 0.86],
    [1.00,  255,   0,   0, 0.92],
  ];
  for (let i = 0; i < stops.length - 1; i++) {
    const [t0, r0, g0, b0, a0] = stops[i];
    const [t1, r1, g1, b1, a1] = stops[i + 1];
    if (t <= t1) {
      const s = (t - t0) / (t1 - t0);
      return [
        Math.round(r0 + (r1 - r0) * s),
        Math.round(g0 + (g1 - g0) * s),
        Math.round(b0 + (b1 - b0) * s),
        a0 + (a1 - a0) * s,
      ];
    }
  }
  return [255, 0, 0, 0.92];
}

function glowRgb(intensity: number): string {
  if (intensity > 0.82) return '255,30,30';
  if (intensity > 0.62) return '255,120,0';
  if (intensity > 0.42) return '255,210,0';
  if (intensity > 0.22) return '0,210,170';
  return '20,110,255';
}

// ── Pitch drawing ─────────────────────────────────────────────────────────────

function drawPitch(ctx: CanvasRenderingContext2D, W: number, H: number) {
  const px = (x: number) => (x / PITCH_L) * W;
  const py = (y: number) => (y / PITCH_W) * H;
  const scale = W / 840;

  // Grass background
  const bg = ctx.createLinearGradient(0, 0, 0, H);
  bg.addColorStop(0,   '#0d1f0e');
  bg.addColorStop(0.5, '#112511');
  bg.addColorStop(1,   '#0d1f0e');
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, W, H);

  // Alternating mowing stripes
  const stripes = 10;
  for (let i = 0; i < stripes; i++) {
    if (i % 2 === 0) {
      ctx.fillStyle = 'rgba(255,255,255,0.024)';
      ctx.fillRect(px((PITCH_L / stripes) * i), 0, px(PITCH_L / stripes) + 0.5, H);
    }
  }

  const lw = Math.max(1.2, W * 0.002);
  ctx.strokeStyle = 'rgba(255,255,255,0.82)';
  ctx.lineWidth = lw;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  const line = (x1: number, y1: number, x2: number, y2: number) => {
    ctx.beginPath(); ctx.moveTo(px(x1), py(y1)); ctx.lineTo(px(x2), py(y2)); ctx.stroke();
  };
  const rect = (x: number, y: number, w: number, h: number) => {
    ctx.strokeRect(px(x), py(y), px(x + w) - px(x), py(y + h) - py(y));
  };
  // Arc uses W-based radius because canvas aspect ratio = pitch aspect ratio
  const mArc = (cx: number, cy: number, rM: number, a0 = 0, a1 = Math.PI * 2) => {
    const rPx = (rM / PITCH_L) * W;
    ctx.beginPath(); ctx.arc(px(cx), py(cy), rPx, a0, a1); ctx.stroke();
  };
  const dot = (x: number, y: number, r = 2.8) => {
    ctx.fillStyle = 'rgba(255,255,255,0.78)';
    ctx.beginPath(); ctx.arc(px(x), py(y), r * scale, 0, Math.PI * 2); ctx.fill();
  };

  // Outer boundary
  rect(0, 0, PITCH_L, PITCH_W);
  // Halfway line + centre circle + kick-off spot
  line(PITCH_L / 2, 0, PITCH_L / 2, PITCH_W);
  mArc(PITCH_L / 2, PITCH_W / 2, 9.15);
  dot(PITCH_L / 2, PITCH_W / 2);

  // Penalty areas
  const paW = 16.5, paH = 40.32, paY = (PITCH_W - paH) / 2;
  rect(0, paY, paW, paH);
  rect(PITCH_L - paW, paY, paW, paH);

  // Goal areas (6-yard boxes)
  const gaW = 5.5, gaH = 18.32, gaY = (PITCH_W - gaH) / 2;
  rect(0, gaY, gaW, gaH);
  rect(PITCH_L - gaW, gaY, gaW, gaH);

  // Goals (lighter)
  ctx.strokeStyle = 'rgba(255,255,255,0.35)';
  const goalH = 7.32, goalD = 2.44, goalY = (PITCH_W - goalH) / 2;
  rect(-goalD, goalY, goalD, goalH);
  rect(PITCH_L, goalY, goalD, goalH);
  ctx.strokeStyle = 'rgba(255,255,255,0.82)';

  // Penalty spots + D arcs
  dot(11, PITCH_W / 2);
  dot(PITCH_L - 11, PITCH_W / 2);
  const aR = 9.15;
  const aOff = Math.acos((paW - 11) / aR);
  mArc(11, PITCH_W / 2, aR, -aOff, aOff);
  mArc(PITCH_L - 11, PITCH_W / 2, aR, Math.PI - aOff, Math.PI + aOff);

  // Corner arcs (1 m)
  const crPx = (1 / PITCH_L) * W;
  const cornerArc = (cx: number, cy: number, startA: number) => {
    ctx.beginPath(); ctx.arc(px(cx), py(cy), crPx, startA, startA + Math.PI / 2); ctx.stroke();
  };
  cornerArc(0,       0,       0);
  cornerArc(PITCH_L, 0,       Math.PI / 2);
  cornerArc(PITCH_L, PITCH_W, Math.PI);
  cornerArc(0,       PITCH_W, -Math.PI / 2);

  // Zone-third dashed lines
  ctx.strokeStyle = 'rgba(255,255,255,0.14)';
  ctx.setLineDash([5, 8]);
  line(35, 0, 35, PITCH_W);
  line(70, 0, 70, PITCH_W);
  ctx.setLineDash([]);
}

// ── Build static heatmap layer ────────────────────────────────────────────────

interface HeatLayer {
  canvas: HTMLCanvasElement;
  blurred: Float32Array;
  maxVal: number;
  dots: GlowDot[];
}

function buildHeatLayer(points: [number, number][]): HeatLayer | null {
  if (points.length < 3) return null;

  const raw = new Float32Array(GRID_COLS * GRID_ROWS);
  for (const [x, y] of points) {
    const gx = Math.max(0, Math.min(GRID_COLS - 1, Math.floor((x / PITCH_L) * GRID_COLS)));
    const gy = Math.max(0, Math.min(GRID_ROWS - 1, Math.floor((y / PITCH_W) * GRID_ROWS)));
    raw[gy * GRID_COLS + gx] += 1;
  }
  const blurred = gaussianBlur2D(raw, GRID_COLS, GRID_ROWS, 4.5);

  let maxVal = 0;
  for (let i = 0; i < blurred.length; i++) if (blurred[i] > maxVal) maxVal = blurred[i];
  if (maxVal === 0) return null;

  const off = document.createElement('canvas');
  off.width = GRID_COLS;
  off.height = GRID_ROWS;
  const octx = off.getContext('2d')!;
  const img = octx.createImageData(GRID_COLS, GRID_ROWS);
  for (let i = 0; i < blurred.length; i++) {
    const t = blurred[i] / maxVal;
    const [r, g, b, a] = colormap(t);
    img.data[i * 4]     = r;
    img.data[i * 4 + 1] = g;
    img.data[i * 4 + 2] = b;
    img.data[i * 4 + 3] = Math.round(a * 255);
  }
  octx.putImageData(img, 0, 0);

  return { canvas: off, blurred, maxVal, dots: extractGlowDots(blurred, maxVal) };
}

// ── Animated glow dots ────────────────────────────────────────────────────────

interface GlowDot {
  pitchX: number;
  pitchY: number;
  intensity: number;
  phase: number;
}

function extractGlowDots(blurred: Float32Array, maxVal: number, topN = 28): GlowDot[] {
  const threshold = maxVal * 0.20;
  const candidates: { i: number; v: number }[] = [];
  for (let i = 0; i < blurred.length; i++) {
    if (blurred[i] >= threshold) candidates.push({ i, v: blurred[i] });
  }
  candidates.sort((a, b) => b.v - a.v);

  const selected: GlowDot[] = [];
  const minGap = 4.5;

  for (const { i, v } of candidates) {
    if (selected.length >= topN) break;
    const cx = (i % GRID_COLS) + 0.5;
    const cy = Math.floor(i / GRID_COLS) + 0.5;

    let tooClose = false;
    for (const s of selected) {
      const dx = cx - (s.pitchX / PITCH_L) * GRID_COLS;
      const dy = cy - (s.pitchY / PITCH_W) * GRID_ROWS;
      if (dx * dx + dy * dy < minGap * minGap) { tooClose = true; break; }
    }
    if (tooClose) continue;

    selected.push({
      pitchX:    (cx / GRID_COLS) * PITCH_L,
      pitchY:    (cy / GRID_ROWS) * PITCH_W,
      intensity: v / maxVal,
      phase:     Math.random() * Math.PI * 2,
    });
  }
  return selected;
}

function drawGlowDots(
  ctx: CanvasRenderingContext2D,
  W: number,
  H: number,
  dots: GlowDot[],
  t: number,
) {
  const toPx = (x: number) => (x / PITCH_L) * W;
  const toPy = (y: number) => (y / PITCH_W) * H;

  for (const dot of dots) {
    const cx = toPx(dot.pitchX);
    const cy = toPy(dot.pitchY);
    const pulse = 0.72 + 0.28 * (0.5 + 0.5 * Math.sin(t * 1.6 + dot.phase));
    const baseR  = W * 0.019 * (0.45 + 0.8 * dot.intensity) * pulse;
    const outerR = baseR * 2.4;
    const rgb    = glowRgb(dot.intensity);
    const alpha  = dot.intensity * 0.28 * pulse;

    // Wide soft glow
    const gOuter = ctx.createRadialGradient(cx, cy, 0, cx, cy, outerR);
    gOuter.addColorStop(0,   `rgba(${rgb},${alpha.toFixed(3)})`);
    gOuter.addColorStop(0.5, `rgba(${rgb},${(alpha * 0.5).toFixed(3)})`);
    gOuter.addColorStop(1,   `rgba(${rgb},0)`);
    ctx.fillStyle = gOuter;
    ctx.beginPath(); ctx.arc(cx, cy, outerR, 0, Math.PI * 2); ctx.fill();

    // Bright core
    const gCore = ctx.createRadialGradient(cx, cy, 0, cx, cy, baseR);
    gCore.addColorStop(0,   `rgba(255,255,255,${(0.52 * pulse).toFixed(3)})`);
    gCore.addColorStop(0.25, `rgba(${rgb},${(0.72 * pulse).toFixed(3)})`);
    gCore.addColorStop(1,   `rgba(${rgb},0)`);
    ctx.fillStyle = gCore;
    ctx.beginPath(); ctx.arc(cx, cy, baseR, 0, Math.PI * 2); ctx.fill();
  }
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function HeatmapPitch({ points }: Props) {
  const canvasRef  = useRef<HTMLCanvasElement>(null);
  const layerRef   = useRef<HeatLayer | null>(null);
  const rafRef     = useRef<number>(0);
  const startRef   = useRef<number>(performance.now());

  // Recompute static layer whenever points change
  useEffect(() => {
    layerRef.current = buildHeatLayer(points);
    startRef.current = performance.now();
  }, [points]);

  // Continuous animation loop (mounted once, reads layerRef via closure)
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const W = canvas.width;
    const H = canvas.height;

    const frame = () => {
      const t = (performance.now() - startRef.current) / 1000;
      ctx.clearRect(0, 0, W, H);
      drawPitch(ctx, W, H);

      const layer = layerRef.current;
      if (layer) {
        ctx.save();
        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = 'high';
        ctx.drawImage(layer.canvas, 0, 0, W, H);
        ctx.restore();
        drawGlowDots(ctx, W, H, layer.dots, t);
      }

      rafRef.current = requestAnimationFrame(frame);
    };

    rafRef.current = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(rafRef.current);
  }, []);

  const hasData = points.length >= 3;

  return (
    <div className="hm-wrap">
      <div className="hm-header">
        <div className="hm-title-group">
          <span className="section-title">Movement Heatmap</span>
          <span className="hm-subtitle">{points.length} position samples</span>
        </div>
        <div className="hm-legend">
          <span className="hm-leg-label">Low</span>
          <div className="hm-leg-bar" />
          <span className="hm-leg-label">High</span>
        </div>
      </div>

      <div className="hm-canvas-wrap">
        <canvas ref={canvasRef} width={840} height={544} className="hm-canvas" />

        {!hasData && (
          <div className="hm-empty">
            <span>Not enough tracking data to generate heatmap</span>
          </div>
        )}

        <div className="hm-y-labels">
          <span>Left</span>
          <span>Center</span>
          <span>Right</span>
        </div>
      </div>

      <div className="hm-x-labels">
        <div className="hm-zone-block hm-zone-def">
          <span className="hm-zone-name">Defensive Third</span>
          <span className="hm-zone-range">0 – 35 m</span>
        </div>
        <div className="hm-zone-block hm-zone-mid">
          <span className="hm-zone-name">Middle Third</span>
          <span className="hm-zone-range">35 – 70 m</span>
        </div>
        <div className="hm-zone-block hm-zone-att">
          <span className="hm-zone-name">Attacking Third</span>
          <span className="hm-zone-range">70 – 105 m</span>
        </div>
      </div>

      <style>{`
        .hm-wrap {
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: var(--radius);
          overflow: hidden;
          display: flex;
          flex-direction: column;
        }
        .hm-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 14px 20px;
          border-bottom: 1px solid var(--border);
        }
        .hm-title-group { display: flex; flex-direction: column; gap: 2px; }
        .hm-subtitle { font-size: 11px; color: var(--text-muted); }

        .hm-legend {
          display: flex; align-items: center; gap: 8px;
          font-size: 11px; color: var(--text-muted);
        }
        .hm-leg-label { font-size: 10px; }
        .hm-leg-bar {
          width: 110px; height: 8px; border-radius: 4px;
          background: linear-gradient(90deg,
            rgba(20,110,255,.50)  0%,
            rgba(0,210,170,.65)  28%,
            rgba(255,210,0,.80)  58%,
            rgba(255,80,0,.88)   78%,
            rgba(255,0,0,.94)   100%);
          border: 1px solid rgba(255,255,255,.08);
        }

        .hm-canvas-wrap {
          position: relative;
          background: #0d1f0e;
          padding: 10px 10px 0;
        }
        .hm-canvas {
          width: 100%; height: auto;
          display: block; border-radius: 4px;
        }
        .hm-empty {
          position: absolute; inset: 0;
          display: flex; align-items: center; justify-content: center;
          font-size: 13px; color: var(--text-muted);
          background: rgba(13,31,14,.88);
        }

        .hm-y-labels {
          position: absolute;
          right: 14px; top: 10px; bottom: 0;
          display: flex; flex-direction: column;
          justify-content: space-between;
          padding: 6px 0;
          pointer-events: none;
        }
        .hm-y-labels span {
          font-size: 9px; font-weight: 600;
          text-transform: uppercase; letter-spacing: .06em;
          color: rgba(255,255,255,.20);
          writing-mode: vertical-rl;
          transform: rotate(180deg);
        }

        .hm-x-labels {
          display: grid;
          grid-template-columns: 1fr 1fr 1fr;
          background: #0d1f0e;
          padding: 0 10px 8px;
        }
        .hm-zone-block {
          display: flex; flex-direction: column; align-items: center;
          gap: 2px; padding: 6px 4px 2px;
          border-top: 2px solid transparent;
        }
        .hm-zone-def { border-color: rgba(56,189,248,.45); }
        .hm-zone-mid { border-color: rgba(0,230,118,.45); }
        .hm-zone-att { border-color: rgba(251,191,36,.45); }
        .hm-zone-name {
          font-size: 10px; font-weight: 700;
          text-transform: uppercase; letter-spacing: .07em;
          color: rgba(255,255,255,.32);
        }
        .hm-zone-range { font-size: 9px; color: rgba(255,255,255,.16); }
      `}</style>
    </div>
  );
}
