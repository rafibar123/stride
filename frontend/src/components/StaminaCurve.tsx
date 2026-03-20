import type { StaminaSegment } from '../types';

interface Props {
  segments: StaminaSegment[];
  insight: string;
}

export default function StaminaCurve({ segments, insight }: Props) {
  if (!segments || segments.length === 0) return null;

  const maxIntensity = Math.max(...segments.map((s) => s.intensity), 1);

  // Color each bar based on relative intensity vs first segment
  const barColor = (idx: number, intensity: number) => {
    if (idx === 0) return '#00e676';
    const first = segments[0].intensity || 1;
    const ratio = intensity / first;
    if (ratio >= 0.9) return '#00e676';
    if (ratio >= 0.7) return '#fbbf24';
    return '#f87171';
  };

  const chartH = 80;
  const barW   = 36;
  const gap    = 10;
  const totalW = segments.length * (barW + gap) - gap;

  const isDropping =
    segments.length >= 4 &&
    segments[segments.length - 1].intensity < segments[0].intensity * 0.85;

  return (
    <div className="sc-wrap">
      <div className="sc-header">
        <span className="section-title">Stamina Curve</span>
        {isDropping && <span className="sc-badge-warn">Energy drop detected</span>}
      </div>

      {/* SVG bar chart */}
      <div className="sc-chart-wrap">
        <svg
          width={totalW}
          height={chartH + 28}
          viewBox={`0 0 ${totalW} ${chartH + 28}`}
          style={{ overflow: 'visible', width: '100%', maxWidth: totalW }}
        >
          {segments.map((seg, i) => {
            const barH = Math.max(4, (seg.intensity / maxIntensity) * chartH);
            const x = i * (barW + gap);
            const y = chartH - barH;
            const color = barColor(i, seg.intensity);

            return (
              <g key={seg.segment}>
                {/* Background track */}
                <rect
                  x={x} y={0} width={barW} height={chartH}
                  rx={6} fill="var(--surface-3)"
                />
                {/* Bar */}
                <rect
                  x={x} y={y} width={barW} height={barH}
                  rx={6} fill={color}
                  style={{ filter: `drop-shadow(0 0 6px ${color}60)` }}
                />
                {/* Intensity label */}
                <text
                  x={x + barW / 2} y={y - 5}
                  textAnchor="middle"
                  fontSize="10" fontWeight="700"
                  fill={color}
                >
                  {seg.intensity}%
                </text>
                {/* Time label */}
                <text
                  x={x + barW / 2} y={chartH + 16}
                  textAnchor="middle"
                  fontSize="9" fill="var(--text-muted)"
                >
                  {seg.label}
                </text>
                {/* Sprint pip */}
                {seg.sprint_count > 0 && (
                  <text
                    x={x + barW / 2} y={chartH + 26}
                    textAnchor="middle"
                    fontSize="8" fill="#fbbf24"
                  >
                    {'⚡'.repeat(Math.min(seg.sprint_count, 3))}
                  </text>
                )}
              </g>
            );
          })}

          {/* Trend line through bar tops */}
          <polyline
            points={segments
              .map((seg, i) => {
                const barH = Math.max(4, (seg.intensity / maxIntensity) * chartH);
                const cx = i * (barW + gap) + barW / 2;
                const cy = chartH - barH;
                return `${cx},${cy}`;
              })
              .join(' ')}
            fill="none"
            stroke="rgba(255,255,255,.18)"
            strokeWidth="1.5"
            strokeDasharray="4 3"
          />
        </svg>
      </div>

      {insight && (
        <p className="sc-insight">
          <span className="sc-insight-icon">
            {isDropping ? '📉' : '📈'}
          </span>
          {insight}
        </p>
      )}

      <style>{`
        .sc-wrap {
          background: var(--surface); border: 1px solid var(--border);
          border-radius: var(--radius); overflow: hidden;
        }
        .sc-header {
          display: flex; justify-content: space-between; align-items: center;
          padding: 14px 20px; border-bottom: 1px solid var(--border);
        }
        .sc-badge-warn {
          font-size: 10px; font-weight: 700; text-transform: uppercase;
          letter-spacing: .07em; padding: 3px 10px; border-radius: 20px;
          background: rgba(251,191,36,.12); border: 1px solid rgba(251,191,36,.3);
          color: #fbbf24;
        }
        .sc-chart-wrap {
          padding: 20px 20px 8px;
          overflow-x: auto;
        }
        .sc-insight {
          margin: 0; padding: 12px 20px;
          font-size: 12px; color: var(--text-dim); line-height: 1.5;
          border-top: 1px solid var(--border);
          display: flex; align-items: flex-start; gap: 8px;
        }
        .sc-insight-icon { font-size: 14px; flex-shrink: 0; margin-top: 1px; }
      `}</style>
    </div>
  );
}
