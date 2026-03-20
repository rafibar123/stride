import type { PlayerRating as Rating } from '../types';

interface Props {
  rating: Rating;
  playerName?: string;
}

/** Colour based on rating value */
function ratingColor(v: number): string {
  if (v >= 8.5) return '#fbbf24'; // gold
  if (v >= 7.0) return '#00e676'; // green
  if (v >= 5.5) return '#38bdf8'; // blue
  return '#f87171';               // red
}

function ratingLabel(v: number): string {
  if (v >= 9.0) return 'World Class';
  if (v >= 8.0) return 'Excellent';
  if (v >= 7.0) return 'Very Good';
  if (v >= 6.0) return 'Good';
  if (v >= 5.0) return 'Average';
  return 'Developing';
}

/** Filled star SVGs (half-star aware) — returns array of 10 partial fills */
function StarBar({ value }: { value: number }) {
  const stars = Array.from({ length: 10 }, (_, i) => {
    const fill = Math.min(1, Math.max(0, value - i));
    return fill;
  });
  const color = ratingColor(value);
  return (
    <div className="pr-stars">
      {stars.map((fill, i) => (
        <span key={i} className="pr-star-wrap">
          {/* background (empty) star */}
          <svg width="14" height="14" viewBox="0 0 24 24" className="pr-star-bg">
            <polygon points="12,2 15.09,8.26 22,9.27 17,14.14 18.18,21.02 12,17.77 5.82,21.02 7,14.14 2,9.27 8.91,8.26"
              stroke="rgba(255,255,255,0.15)" strokeWidth="1.5" fill="rgba(255,255,255,0.06)" />
          </svg>
          {/* foreground (filled) star — clipped by fill fraction */}
          {fill > 0 && (
            <svg width="14" height="14" viewBox="0 0 24 24" className="pr-star-fg"
              style={{ clipPath: `inset(0 ${(1 - fill) * 100}% 0 0)` }}>
              <polygon points="12,2 15.09,8.26 22,9.27 17,14.14 18.18,21.02 12,17.77 5.82,21.02 7,14.14 2,9.27 8.91,8.26"
                fill={color} />
            </svg>
          )}
        </span>
      ))}
    </div>
  );
}

interface BarProps {
  label: string;
  value: number;
  detail: string;
}

function AttributeBar({ label, value, detail }: BarProps) {
  const color = ratingColor(value);
  const pct = ((value - 3) / 6.8) * 100; // map 3-9.8 → 0-100%
  return (
    <div className="pr-attr">
      <div className="pr-attr-top">
        <span className="pr-attr-label">{label}</span>
        <span className="pr-attr-value" style={{ color }}>{value.toFixed(1)}</span>
      </div>
      <div className="pr-attr-track">
        <div
          className="pr-attr-fill"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <span className="pr-attr-detail">{detail}</span>
    </div>
  );
}

export default function PlayerRating({ rating, playerName }: Props) {
  const { overall, physical, attacking, positioning, pressing, breakdown } = rating;
  const overallColor = ratingColor(overall);

  const attrs: BarProps[] = [
    {
      label: 'Physical',
      value: physical,
      detail: `${breakdown.pace_kmh} km/h top · ${breakdown.dist_per_min_m} m/min`,
    },
    {
      label: 'Attacking',
      value: attacking,
      detail: `${breakdown.att_third_pct}% att. third · ${breakdown.sprints_per_min.toFixed(1)} sprints/min`,
    },
    {
      label: 'Positioning',
      value: positioning,
      detail: `${breakdown.mid_third_pct}% mid · ${breakdown.att_third_pct}% att · ${breakdown.def_third_pct}% def`,
    },
    {
      label: 'Pressing',
      value: pressing,
      detail: `${breakdown.sprints_per_min.toFixed(1)} closing runs/min · ${breakdown.def_third_pct}% def. work`,
    },
  ];

  return (
    <div className="pr-root">
      {/* ── left: FIFA card ── */}
      <div className="pr-card" style={{ '--accent': overallColor } as React.CSSProperties}>
        <div className="pr-card-glow" style={{ background: overallColor }} />

        <div className="pr-card-header">
          <span className="pr-card-tag">PERFORMANCE RATING</span>
          {playerName && <span className="pr-card-name">{playerName}</span>}
        </div>

        <div className="pr-score-block">
          <div className="pr-score" style={{ color: overallColor }}>
            {overall.toFixed(1)}
          </div>
          <StarBar value={overall} />
          <span className="pr-score-label" style={{ color: overallColor }}>
            {ratingLabel(overall)}
          </span>
        </div>

        <div className="pr-card-mini-grid">
          {[
            { k: 'PHY', v: physical },
            { k: 'ATT', v: attacking },
            { k: 'POS', v: positioning },
            { k: 'PRS', v: pressing },
          ].map(({ k, v }) => (
            <div key={k} className="pr-mini">
              <span className="pr-mini-val" style={{ color: ratingColor(v) }}>{v.toFixed(1)}</span>
              <span className="pr-mini-lbl">{k}</span>
            </div>
          ))}
        </div>

        <div className="pr-card-footer">
          {breakdown.duration_min.toFixed(1)} min analysed
        </div>
      </div>

      {/* ── right: attribute bars ── */}
      <div className="pr-bars">
        <div className="pr-bars-title">Attribute Breakdown</div>
        {attrs.map((a) => (
          <AttributeBar key={a.label} {...a} />
        ))}
      </div>

      <style>{`
        .pr-root {
          display: grid;
          grid-template-columns: 220px 1fr;
          gap: 20px;
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: var(--radius);
          padding: 24px;
          align-items: start;
        }
        @media (max-width: 640px) {
          .pr-root { grid-template-columns: 1fr; }
        }

        /* ── FIFA card ── */
        .pr-card {
          position: relative;
          background: linear-gradient(160deg, #0e1a10 0%, #07090f 60%, #0a100a 100%);
          border: 1px solid rgba(255,255,255,0.08);
          border-radius: 16px;
          padding: 20px 16px 16px;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 14px;
          overflow: hidden;
        }
        .pr-card-glow {
          position: absolute;
          top: -60px; left: 50%;
          transform: translateX(-50%);
          width: 180px; height: 180px;
          border-radius: 50%;
          opacity: 0.08;
          filter: blur(40px);
          pointer-events: none;
        }

        .pr-card-header {
          display: flex; flex-direction: column; align-items: center; gap: 4px;
          z-index: 1;
        }
        .pr-card-tag {
          font-size: 8px; font-weight: 800;
          letter-spacing: .14em; text-transform: uppercase;
          color: var(--text-muted);
        }
        .pr-card-name {
          font-size: 12px; font-weight: 700;
          color: var(--text); letter-spacing: .03em;
          text-align: center;
        }

        .pr-score-block {
          display: flex; flex-direction: column; align-items: center; gap: 8px;
          z-index: 1;
        }
        .pr-score {
          font-size: 72px;
          font-weight: 900;
          line-height: 1;
          letter-spacing: -.04em;
          font-variant-numeric: tabular-nums;
          text-shadow: 0 0 40px currentColor;
          transition: color .3s;
        }
        .pr-score-label {
          font-size: 11px; font-weight: 800;
          text-transform: uppercase; letter-spacing: .1em;
        }

        /* stars */
        .pr-stars {
          display: flex; gap: 2px; align-items: center;
        }
        .pr-star-wrap {
          position: relative; width: 14px; height: 14px;
          display: inline-block;
        }
        .pr-star-bg, .pr-star-fg {
          position: absolute; top: 0; left: 0;
        }

        /* mini 4-score grid */
        .pr-card-mini-grid {
          display: grid; grid-template-columns: repeat(4, 1fr);
          gap: 8px; width: 100%; z-index: 1;
          border-top: 1px solid rgba(255,255,255,0.07);
          padding-top: 14px;
        }
        .pr-mini {
          display: flex; flex-direction: column; align-items: center; gap: 3px;
        }
        .pr-mini-val {
          font-size: 16px; font-weight: 800;
          font-variant-numeric: tabular-nums;
        }
        .pr-mini-lbl {
          font-size: 8px; font-weight: 700;
          letter-spacing: .1em; color: var(--text-muted);
          text-transform: uppercase;
        }

        .pr-card-footer {
          font-size: 9px; color: var(--text-muted);
          z-index: 1; text-align: center;
        }

        /* ── bars ── */
        .pr-bars {
          display: flex; flex-direction: column; gap: 16px;
        }
        .pr-bars-title {
          font-size: 12px; font-weight: 700;
          text-transform: uppercase; letter-spacing: .08em;
          color: var(--text-muted);
          padding-bottom: 4px;
          border-bottom: 1px solid var(--border);
        }
        .pr-attr {
          display: flex; flex-direction: column; gap: 5px;
        }
        .pr-attr-top {
          display: flex; justify-content: space-between; align-items: baseline;
        }
        .pr-attr-label {
          font-size: 13px; font-weight: 700; color: var(--text);
        }
        .pr-attr-value {
          font-size: 20px; font-weight: 900;
          font-variant-numeric: tabular-nums;
          line-height: 1;
        }
        .pr-attr-track {
          height: 6px; border-radius: 3px;
          background: var(--surface-3);
          overflow: hidden;
        }
        .pr-attr-fill {
          height: 100%; border-radius: 3px;
          transition: width .6s cubic-bezier(.4,0,.2,1);
          box-shadow: 0 0 8px currentColor;
        }
        .pr-attr-detail {
          font-size: 10px; color: var(--text-muted);
        }
      `}</style>
    </div>
  );
}
