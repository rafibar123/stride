import { useEffect, useRef } from 'react';

interface Props {
  points: [number, number][];
  pitchLength?: number;
  pitchWidth?: number;
}

const PITCH_L = 105;
const PITCH_W = 68;

function drawPitch(ctx: CanvasRenderingContext2D, W: number, H: number) {
  const px = (x: number) => (x / PITCH_L) * W;
  const py = (y: number) => (y / PITCH_W) * H;

  // grass gradient
  const grad = ctx.createLinearGradient(0, 0, 0, H);
  grad.addColorStop(0,   '#1a5c1a');
  grad.addColorStop(0.5, '#1f6b1f');
  grad.addColorStop(1,   '#1a5c1a');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, W, H);

  // stripe pattern
  const stripes = 10;
  for (let i = 0; i < stripes; i++) {
    if (i % 2 === 0) {
      ctx.fillStyle = 'rgba(255,255,255,0.03)';
      ctx.fillRect(px((PITCH_L / stripes) * i), 0, px(PITCH_L / stripes), H);
    }
  }

  ctx.strokeStyle = 'rgba(255,255,255,0.75)';
  ctx.lineWidth = Math.max(1, W * 0.003);
  ctx.lineCap = 'round';

  const line = (x1: number, y1: number, x2: number, y2: number) => {
    ctx.beginPath();
    ctx.moveTo(px(x1), py(y1));
    ctx.lineTo(px(x2), py(y2));
    ctx.stroke();
  };

  const arc = (cx: number, cy: number, r: number, a0 = 0, a1 = Math.PI * 2) => {
    ctx.beginPath();
    ctx.arc(px(cx), py(cy), (r / PITCH_L) * W, a0, a1);
    ctx.stroke();
  };

  const rect = (x: number, y: number, w: number, h: number) => {
    ctx.beginPath();
    ctx.strokeRect(px(x), py(y), px(w) - px(0), py(h) - py(0));
  };

  // boundary
  rect(0, 0, PITCH_L, PITCH_W);
  // halfway
  line(PITCH_L / 2, 0, PITCH_L / 2, PITCH_W);
  // centre circle
  arc(PITCH_L / 2, PITCH_W / 2, 9.15);
  ctx.fillStyle = 'rgba(255,255,255,0.7)';
  ctx.beginPath();
  ctx.arc(px(PITCH_L / 2), py(PITCH_W / 2), 3, 0, Math.PI * 2);
  ctx.fill();

  // penalty areas
  const paW = 16.5, paH = 40.32, paY = (PITCH_W - paH) / 2;
  rect(0, paY, paW, paH);
  rect(PITCH_L - paW, paY, paW, paH);

  // goal areas
  const gaW = 5.5, gaH = 18.32, gaY = (PITCH_W - gaH) / 2;
  rect(0, gaY, gaW, gaH);
  rect(PITCH_L - gaW, gaY, gaW, gaH);

  // goals
  ctx.strokeStyle = 'rgba(255,255,255,0.4)';
  const goalH = 7.32, goalD = 2.44, goalY = (PITCH_W - goalH) / 2;
  rect(-goalD, goalY, goalD, goalH);
  rect(PITCH_L, goalY, goalD, goalH);
  ctx.strokeStyle = 'rgba(255,255,255,0.75)';

  // penalty spots
  const spot = (x: number, y: number) => {
    ctx.fillStyle = 'rgba(255,255,255,0.7)';
    ctx.beginPath();
    ctx.arc(px(x), py(y), 3, 0, Math.PI * 2);
    ctx.fill();
  };
  spot(11, PITCH_W / 2);
  spot(PITCH_L - 11, PITCH_W / 2);

  // penalty arcs
  ctx.strokeStyle = 'rgba(255,255,255,0.75)';
  const aR = 9.15;
  const aStartLeft = Math.acos((paW - 11) / aR);
  arc(11, PITCH_W / 2, aR, -aStartLeft, aStartLeft);
  arc(PITCH_L - 11, PITCH_W / 2, aR, Math.PI - aStartLeft, Math.PI + aStartLeft);

  // zone lines (thirds)
  ctx.strokeStyle = 'rgba(255,255,255,0.18)';
  ctx.setLineDash([6, 6]);
  line(35, 0, 35, PITCH_W);
  line(70, 0, 70, PITCH_W);
  ctx.setLineDash([]);
}

function drawHeatmap(ctx: CanvasRenderingContext2D, W: number, H: number, points: [number, number][]) {
  if (!points.length) return;

  // build density grid
  const cols = 84, rows = 54;
  const grid = new Float32Array(cols * rows);

  for (const [x, y] of points) {
    const gx = Math.floor((x / PITCH_L) * cols);
    const gy = Math.floor((y / PITCH_W) * rows);
    const cx = Math.max(0, Math.min(cols - 1, gx));
    const cy = Math.max(0, Math.min(rows - 1, gy));
    // accumulate with gaussian spread
    for (let dy = -2; dy <= 2; dy++) {
      for (let dx = -2; dx <= 2; dx++) {
        const nx = cx + dx, ny = cy + dy;
        if (nx < 0 || nx >= cols || ny < 0 || ny >= rows) continue;
        const w = Math.exp(-(dx * dx + dy * dy) / 2);
        grid[ny * cols + nx] += w;
      }
    }
  }

  let maxVal = 0;
  for (let i = 0; i < grid.length; i++) if (grid[i] > maxVal) maxVal = grid[i];
  if (maxVal === 0) return;

  // color stops: transparent → yellow → orange → red
  const colormap = (t: number): [number, number, number, number] => {
    if (t < 0.001) return [0, 0, 0, 0];
    if (t < 0.25)  return [255, 255,  0, t * 3];
    if (t < 0.55)  return [255, Math.round(200 * (1 - (t - 0.25) / 0.3)), 0, 0.55 + t * 0.5];
    return [255, 0, 0, Math.min(0.88, 0.6 + t * 0.4)];
  };

  const offscreen = document.createElement('canvas');
  offscreen.width = cols;
  offscreen.height = rows;
  const octx = offscreen.getContext('2d')!;
  const img = octx.createImageData(cols, rows);

  for (let i = 0; i < grid.length; i++) {
    const t = grid[i] / maxVal;
    const [r, g, b, a] = colormap(t);
    img.data[i * 4]     = r;
    img.data[i * 4 + 1] = g;
    img.data[i * 4 + 2] = b;
    img.data[i * 4 + 3] = Math.round(a * 255);
  }
  octx.putImageData(img, 0, 0);

  ctx.save();
  ctx.globalCompositeOperation = 'screen';
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(offscreen, 0, 0, W, H);
  ctx.restore();
}

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

  return (
    <div className="heatmap-wrap">
      <div className="heatmap-header">
        <span className="section-title">Your Movement Heatmap</span>
        <div className="heatmap-legend">
          <span>Low</span>
          <div className="legend-bar" />
          <span>High</span>
        </div>
      </div>
      <div className="heatmap-canvas-wrap">
        <canvas ref={canvasRef} width={840} height={544} className="heatmap-canvas" />
        <div className="heatmap-zone-labels">
          <span>Def. Third</span>
          <span>Mid. Third</span>
          <span>Att. Third</span>
        </div>
      </div>
      <style>{`
        .heatmap-wrap {
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: var(--radius);
          overflow: hidden;
        }
        .heatmap-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 16px 20px;
          border-bottom: 1px solid var(--border);
        }
        .heatmap-legend {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 11px;
          color: var(--text-muted);
        }
        .legend-bar {
          width: 80px;
          height: 8px;
          border-radius: 4px;
          background: linear-gradient(90deg, transparent, #ffff00 40%, #ff8800 70%, #ff0000);
          border: 1px solid rgba(255,255,255,.1);
        }
        .heatmap-canvas-wrap {
          position: relative;
          padding: 12px;
          background: #0a1a0a;
        }
        .heatmap-canvas {
          width: 100%;
          height: auto;
          display: block;
          border-radius: 6px;
        }
        .heatmap-zone-labels {
          display: flex;
          justify-content: space-around;
          padding: 6px 0 2px;
          font-size: 10px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: .06em;
          color: rgba(255,255,255,.25);
        }
      `}</style>
    </div>
  );
}
