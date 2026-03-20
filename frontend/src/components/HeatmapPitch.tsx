import { useEffect, useRef } from 'react';

interface Props {
  points: [number, number][];
  pitchLength?: number;
  pitchWidth?: number;
}

// Pitch dimensions in metres
const PITCH_L = 105;
const PITCH_W = 68;

// ── Separable Gaussian blur ───────────────────────────────────────────────────

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

function gaussianBlur2D(
  src: Float32Array,
  cols: number,
  rows: number,
  sigma: number,
): Float32Array {
  const radius = Math.ceil(sigma * 2.5);
  const k = gaussKernel(sigma, radius);
  const tmp = new Float32Array(cols * rows);

  // horizontal pass
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

  // vertical pass
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

// ── Colormap: transparent → green → yellow-green → yellow → orange → red ─────

function colormap(t: number): [number, number, number, number] {
  if (t < 0.02) return [0, 0, 0, 0];

  // [threshold, r, g, b, alpha]
  const stops: [number, number, number, number, number][] = [
    [0.02, 0,   210,  90, 0.28],
    [0.18, 0,   230, 100, 0.52],
    [0.38, 140, 230,   0, 0.66],
    [0.58, 255, 200,   0, 0.76],
    [0.78, 255,  70,   0, 0.83],
    [1.00, 255,   0,   0, 0.90],
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
  return [255, 0, 0, 0.90];
}

// ── Pitch drawing ─────────────────────────────────────────────────────────────

function drawPitch(ctx: CanvasRenderingContext2D, W: number, H: number) {
  const px = (x: number) => (x / PITCH_L) * W;
  const py = (y: number) => (y / PITCH_W) * H;

  // Grass gradient
  const grad = ctx.createLinearGradient(0, 0, 0, H);
  grad.addColorStop(0,   '#163516');
  grad.addColorStop(0.5, '#1a3f1a');
  grad.addColorStop(1,   '#163516');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, W, H);

  // Subtle pitch stripes
  for (let i = 0; i < 10; i++) {
    if (i % 2 === 0) {
      ctx.fillStyle = 'rgba(255,255,255,0.025)';
      ctx.fillRect(px((PITCH_L / 10) * i), 0, px(PITCH_L / 10), H);
    }
  }

  ctx.strokeStyle = 'rgba(255,255,255,0.70)';
  ctx.lineWidth = Math.max(1, W * 0.0025);
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  const line = (x1: number, y1: number, x2: number, y2: number) => {
    ctx.beginPath(); ctx.moveTo(px(x1), py(y1)); ctx.lineTo(px(x2), py(y2)); ctx.stroke();
  };

  const strokeRect = (x: number, y: number, w: number, h: number) => {
    ctx.strokeRect(px(x), py(y), px(x + w) - px(x), py(y + h) - py(y));
  };

  const arc = (cx: number, cy: number, r: number, a0 = 0, a1 = Math.PI * 2) => {
    ctx.beginPath();
    ctx.arc(px(cx), py(cy), (r / PITCH_L) * W, a0, a1);
    ctx.stroke();
  };

  const dot = (x: number, y: number, r = 3) => {
    ctx.fillStyle = 'rgba(255,255,255,0.65)';
    ctx.beginPath(); ctx.arc(px(x), py(y), r, 0, Math.PI * 2); ctx.fill();
  };

  // Boundary
  strokeRect(0, 0, PITCH_L, PITCH_W);
  // Halfway line + centre circle + spot
  line(PITCH_L / 2, 0, PITCH_L / 2, PITCH_W);
  arc(PITCH_L / 2, PITCH_W / 2, 9.15);
  dot(PITCH_L / 2, PITCH_W / 2);

  // Penalty areas
  const paW = 16.5, paH = 40.32, paY = (PITCH_W - paH) / 2;
  strokeRect(0, paY, paW, paH);
  strokeRect(PITCH_L - paW, paY, paW, paH);

  // Goal areas
  const gaW = 5.5, gaH = 18.32, gaY = (PITCH_W - gaH) / 2;
  strokeRect(0, gaY, gaW, gaH);
  strokeRect(PITCH_L - gaW, gaY, gaW, gaH);

  // Goals (fainter)
  ctx.strokeStyle = 'rgba(255,255,255,0.35)';
  const goalH = 7.32, goalD = 2.44, goalY = (PITCH_W - goalH) / 2;
  strokeRect(-goalD, goalY, goalD, goalH);
  strokeRect(PITCH_L, goalY, goalD, goalH);
  ctx.strokeStyle = 'rgba(255,255,255,0.70)';

  // Penalty spots + arcs
  dot(11, PITCH_W / 2);
  dot(PITCH_L - 11, PITCH_W / 2);
  const aR = 9.15;
  const aOff = Math.acos((paW - 11) / aR);
  arc(11, PITCH_W / 2, aR, -aOff, aOff);
  arc(PITCH_L - 11, PITCH_W / 2, aR, Math.PI - aOff, Math.PI + aOff);

  // Zone thirds (dashed)
  ctx.strokeStyle = 'rgba(255,255,255,0.20)';
  ctx.setLineDash([5, 5]);
  line(35, 0, 35, PITCH_W);
  line(70, 0, 70, PITCH_W);
  ctx.setLineDash([]);
}

// ── Heatmap density → canvas ──────────────────────────────────────────────────

function drawHeatmap(
  ctx: CanvasRenderingContext2D,
  W: number,
  H: number,
  points: [number, number][],
) {
  if (points.length < 3) return;

  // 1-cell-per-metre grid for exact pitch mapping
  const cols = PITCH_L;   // 105
  const rows = PITCH_W;   // 68
  const raw = new Float32Array(cols * rows);

  for (const [x, y] of points) {
    // Points are in pitch metres (0–105, 0–68)
    const gx = Math.max(0, Math.min(cols - 1, Math.floor((x / PITCH_L) * cols)));
    const gy = Math.max(0, Math.min(rows - 1, Math.floor((y / PITCH_W) * rows)));
    raw[gy * cols + gx] += 1;
  }

  // Separable Gaussian blur — σ=4m gives natural smooth zones
  const blurred = gaussianBlur2D(raw, cols, rows, 4);

  let maxVal = 0;
  for (let i = 0; i < blurred.length; i++) if (blurred[i] > maxVal) maxVal = blurred[i];
  if (maxVal === 0) return;

  // Render density to offscreen canvas
  const off = document.createElement('canvas');
  off.width = cols;
  off.height = rows;
  const octx = off.getContext('2d')!;
  const img = octx.createImageData(cols, rows);

  for (let i = 0; i < blurred.length; i++) {
    const t = blurred[i] / maxVal;
    const [r, g, b, a] = colormap(t);
    img.data[i * 4]     = r;
    img.data[i * 4 + 1] = g;
    img.data[i * 4 + 2] = b;
    img.data[i * 4 + 3] = Math.round(a * 255);
  }
  octx.putImageData(img, 0, 0);

  // Scale up with bicubic-quality smoothing
  ctx.save();
  ctx.globalCompositeOperation = 'source-over';
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(off, 0, 0, W, H);
  ctx.restore();
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function HeatmapPitch({ points }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const W = canvas.width;
    const H = canvas.height;

    ctx.clearRect(0, 0, W, H);
    drawPitch(ctx, W, H);
    drawHeatmap(ctx, W, H, points);
  }, [points]);

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

        {/* Y-axis wing labels */}
        <div className="hm-y-labels">
          <span>Left</span>
          <span>Center</span>
          <span>Right</span>
        </div>
      </div>

      {/* X-axis zone labels */}
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
          width: 90px; height: 8px; border-radius: 4px;
          background: linear-gradient(90deg,
            transparent 0%,
            rgba(0,230,100,.6) 20%,
            rgba(200,230,0,.8) 45%,
            rgba(255,140,0,.85) 70%,
            rgba(255,0,0,.9) 100%);
          border: 1px solid rgba(255,255,255,.1);
        }

        .hm-canvas-wrap {
          position: relative;
          background: #0d1a0d;
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
          background: rgba(13,26,13,.85);
        }

        .hm-y-labels {
          position: absolute;
          right: 14px; top: 10px; bottom: 0;
          display: flex; flex-direction: column;
          justify-content: space-between;
          padding: 4px 0 4px;
          pointer-events: none;
        }
        .hm-y-labels span {
          font-size: 9px; font-weight: 600;
          text-transform: uppercase; letter-spacing: .06em;
          color: rgba(255,255,255,.22);
          writing-mode: vertical-rl;
          transform: rotate(180deg);
        }

        .hm-x-labels {
          display: grid;
          grid-template-columns: 1fr 1fr 1fr;
          background: #0d1a0d;
          padding: 0 10px 8px;
        }
        .hm-zone-block {
          display: flex; flex-direction: column; align-items: center;
          gap: 2px; padding: 6px 4px 2px;
          border-top: 2px solid transparent;
        }
        .hm-zone-def  { border-color: rgba(56,189,248,.45); }
        .hm-zone-mid  { border-color: rgba(0,230,118,.45); }
        .hm-zone-att  { border-color: rgba(251,191,36,.45); }
        .hm-zone-name {
          font-size: 10px; font-weight: 700;
          text-transform: uppercase; letter-spacing: .07em;
          color: rgba(255,255,255,.35);
        }
        .hm-zone-range {
          font-size: 9px; color: rgba(255,255,255,.18);
        }
      `}</style>
    </div>
  );
}
