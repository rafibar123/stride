import type { PassStats as Stats } from '../types';

interface Props {
  stats: Stats;
}

function accuracyColor(pct: number, hasData: boolean): string {
  if (!hasData) return '#38bdf8'; // blue = no data
  if (pct >= 80) return '#00e676'; // green
  if (pct >= 60) return '#fbbf24'; // amber
  return '#f87171';                // red
}

function accuracyLabel(pct: number, hasData: boolean): string {
  if (!hasData) return 'No Data';
  if (pct >= 85) return 'Excellent';
  if (pct >= 70) return 'Good';
  if (pct >= 50) return 'Average';
  return 'Needs Work';
}

/** Animated ring progress indicator */
function RingGauge({ pct, color }: { pct: number; color: string }) {
  const R = 46;
  const circumference = 2 * Math.PI * R;
  const filled = (pct / 100) * circumference;

  return (
    <svg width="110" height="110" viewBox="0 0 110 110" className="ps-ring">
      {/* background track */}
      <circle
        cx="55" cy="55" r={R}
        fill="none"
        stroke="rgba(255,255,255,0.06)"
        strokeWidth="9"
      />
      {/* filled arc */}
      <circle
        cx="55" cy="55" r={R}
        fill="none"
        stroke={color}
        strokeWidth="9"
        strokeLinecap="round"
        strokeDasharray={`${filled} ${circumference - filled}`}
        strokeDashoffset={circumference * 0.25}   /* start at top */
        style={{ filter: `drop-shadow(0 0 6px ${color}88)`, transition: 'stroke-dasharray 0.8s cubic-bezier(.4,0,.2,1)' }}
      />
      {/* center text */}
      <text x="55" y="51" textAnchor="middle" fill={color}
        fontFamily="system-ui, sans-serif" fontWeight="900" fontSize="22">
        {Math.round(pct)}%
      </text>
      <text x="55" y="65" textAnchor="middle" fill="rgba(255,255,255,0.35)"
        fontFamily="system-ui, sans-serif" fontWeight="600" fontSize="9"
        textTransform="uppercase" letterSpacing="1">
        ACCURACY
      </text>
    </svg>
  );
}

/** Small pass result dot */
function ResultDot({ result }: { result: string }) {
  const c = result === 'accurate' ? '#00e676' : result === 'failed' ? '#f87171' : '#60748a';
  return (
    <span
      className="ps-dot"
      style={{ background: c, boxShadow: `0 0 5px ${c}88` }}
      title={result}
    />
  );
}

export default function PassStats({ stats }: Props) {
  const { total, accurate, failed, unknown, accuracy_pct, events, coach_note } = stats;
  const hasData = total >= 3;
  const color = accuracyColor(accuracy_pct, hasData);
  const label = accuracyLabel(accuracy_pct, hasData);

  return (
    <div className="ps-wrap">
      <div className="ps-header">
        <span className="section-title">Passing Analysis</span>
        {hasData && (
          <span className="ps-badge" style={{ color, borderColor: color + '55', background: color + '18' }}>
            {label}
          </span>
        )}
      </div>

      <div className="ps-body">
        {/* ── left: ring gauge ── */}
        <div className="ps-gauge-col">
          <RingGauge pct={hasData ? accuracy_pct : 0} color={color} />
          {!hasData && (
            <span className="ps-no-data">Ball not tracked</span>
          )}
        </div>

        {/* ── center: score breakdown ── */}
        <div className="ps-stats-col">
          <div className="ps-fraction" style={{ color }}>
            <span className="ps-num">{hasData ? accurate : '–'}</span>
            <span className="ps-sep">/</span>
            <span className="ps-den">{hasData ? total : '–'}</span>
          </div>
          <span className="ps-fraction-label">passes accurate</span>

          <div className="ps-breakdown">
            {hasData && (
              <>
                <div className="ps-stat-row">
                  <span className="ps-stat-dot" style={{ background: '#00e676' }} />
                  <span className="ps-stat-label">Accurate</span>
                  <span className="ps-stat-val" style={{ color: '#00e676' }}>{accurate}</span>
                </div>
                <div className="ps-stat-row">
                  <span className="ps-stat-dot" style={{ background: '#f87171' }} />
                  <span className="ps-stat-label">Failed</span>
                  <span className="ps-stat-val" style={{ color: '#f87171' }}>{failed}</span>
                </div>
                {unknown > 0 && (
                  <div className="ps-stat-row">
                    <span className="ps-stat-dot" style={{ background: '#60748a' }} />
                    <span className="ps-stat-label">Unclear</span>
                    <span className="ps-stat-val" style={{ color: '#60748a' }}>{unknown}</span>
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {/* ── right: pass timeline dots ── */}
        {events.length > 0 && (
          <div className="ps-timeline-col">
            <span className="ps-tl-label">Pass timeline</span>
            <div className="ps-dots">
              {events.map((ev, i) => (
                <ResultDot key={i} result={ev.result} />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ── coach note ── */}
      <div className="ps-coach">
        <span className="ps-coach-icon">⚽</span>
        <p className="ps-coach-text">{coach_note}</p>
      </div>

      <style>{`
        .ps-wrap {
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: var(--radius);
          overflow: hidden;
          display: flex;
          flex-direction: column;
        }

        .ps-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 14px 20px;
          border-bottom: 1px solid var(--border);
        }

        .ps-badge {
          font-size: 10px; font-weight: 800;
          text-transform: uppercase; letter-spacing: .07em;
          padding: 3px 10px; border-radius: 20px;
          border: 1px solid;
        }

        .ps-body {
          display: flex;
          align-items: center;
          gap: 28px;
          padding: 20px 24px;
          flex-wrap: wrap;
        }

        .ps-gauge-col {
          display: flex; flex-direction: column; align-items: center; gap: 6px;
          flex-shrink: 0;
        }
        .ps-ring { display: block; }
        .ps-no-data {
          font-size: 10px; color: var(--text-muted);
          text-transform: uppercase; letter-spacing: .06em;
        }

        .ps-stats-col {
          display: flex; flex-direction: column; gap: 4px;
          flex: 1; min-width: 120px;
        }

        .ps-fraction {
          display: flex; align-items: baseline; gap: 3px;
          line-height: 1;
        }
        .ps-num {
          font-size: 52px; font-weight: 900;
          font-variant-numeric: tabular-nums;
          line-height: 1;
        }
        .ps-sep {
          font-size: 28px; font-weight: 300;
          color: rgba(255,255,255,0.25);
          margin: 0 1px;
        }
        .ps-den {
          font-size: 28px; font-weight: 700;
          color: rgba(255,255,255,0.45);
        }
        .ps-fraction-label {
          font-size: 11px; color: var(--text-muted);
          text-transform: uppercase; letter-spacing: .06em;
          margin-bottom: 8px;
        }

        .ps-breakdown { display: flex; flex-direction: column; gap: 6px; }
        .ps-stat-row {
          display: flex; align-items: center; gap: 8px;
        }
        .ps-stat-dot {
          width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0;
        }
        .ps-stat-label { font-size: 12px; color: var(--text-muted); flex: 1; }
        .ps-stat-val   { font-size: 14px; font-weight: 800; font-variant-numeric: tabular-nums; }

        .ps-timeline-col {
          display: flex; flex-direction: column; gap: 10px;
          align-self: flex-start;
        }
        .ps-tl-label {
          font-size: 9px; font-weight: 700;
          text-transform: uppercase; letter-spacing: .07em;
          color: var(--text-muted);
        }
        .ps-dots {
          display: flex; flex-wrap: wrap; gap: 5px;
          max-width: 120px;
        }
        .ps-dot {
          width: 10px; height: 10px; border-radius: 50%;
          display: inline-block; flex-shrink: 0;
        }

        /* coach note */
        .ps-coach {
          display: flex; align-items: flex-start; gap: 10px;
          padding: 12px 20px 16px;
          border-top: 1px solid var(--border);
          background: var(--surface-2);
        }
        .ps-coach-icon { font-size: 16px; flex-shrink: 0; margin-top: 1px; }
        .ps-coach-text {
          font-size: 12px; color: var(--text-muted);
          line-height: 1.55; margin: 0;
          font-style: italic;
        }
      `}</style>
    </div>
  );
}
