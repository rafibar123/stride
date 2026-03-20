import type { AdvancedMetrics } from '../types';

interface Props { metrics: AdvancedMetrics; }

export default function ActivityBreakdown({ metrics }: Props) {
  const { activity, direction_changes, sprint_recovery_avg_sec, sprint_moments } = metrics;
  const { standing_pct, walking_pct, running_pct } = activity;

  // Donut chart via conic-gradient
  const donut = `conic-gradient(
    #f87171 0% ${standing_pct}%,
    #fbbf24 ${standing_pct}% ${standing_pct + walking_pct}%,
    #00e676 ${standing_pct + walking_pct}% 100%
  )`;

  const agility =
    direction_changes >= 30 ? 'Excellent'
    : direction_changes >= 18 ? 'Good'
    : direction_changes >= 8  ? 'Average'
    : 'Low';

  const agilityColor =
    direction_changes >= 30 ? 'var(--green)'
    : direction_changes >= 18 ? '#38bdf8'
    : direction_changes >= 8  ? '#fbbf24'
    : '#f87171';

  return (
    <div className="ab-wrap">
      <div className="ab-header">
        <span className="section-title">Activity Breakdown</span>
        <span className="ab-badge">AI Detected</span>
      </div>

      <div className="ab-body">
        {/* Donut */}
        <div className="ab-donut-col">
          <div className="ab-donut" style={{ background: donut }}>
            <div className="ab-donut-hole">
              <span className="ab-donut-pct">{running_pct}%</span>
              <span className="ab-donut-sub">active</span>
            </div>
          </div>
          <div className="ab-legend">
            <div className="ab-legend-item">
              <span className="ab-dot" style={{ background: '#00e676' }} />
              <span>Running</span>
              <strong>{running_pct}%</strong>
            </div>
            <div className="ab-legend-item">
              <span className="ab-dot" style={{ background: '#fbbf24' }} />
              <span>Walking</span>
              <strong>{walking_pct}%</strong>
            </div>
            <div className="ab-legend-item">
              <span className="ab-dot" style={{ background: '#f87171' }} />
              <span>Standing</span>
              <strong>{standing_pct}%</strong>
            </div>
          </div>
        </div>

        {/* Stats column */}
        <div className="ab-stats-col">
          <div className="ab-stat-card">
            <span className="ab-stat-label">Direction Changes</span>
            <span className="ab-stat-value" style={{ color: agilityColor }}>
              {direction_changes}
            </span>
            <span className="ab-stat-tag" style={{ color: agilityColor }}>
              {agility} agility
            </span>
          </div>

          {sprint_recovery_avg_sec > 0 && (
            <div className="ab-stat-card">
              <span className="ab-stat-label">Sprint Recovery</span>
              <span className="ab-stat-value" style={{ color: '#38bdf8' }}>
                {sprint_recovery_avg_sec}s
              </span>
              <span className="ab-stat-tag" style={{ color: 'var(--text-muted)' }}>
                avg between sprints
              </span>
            </div>
          )}

          {sprint_moments.length > 0 && (
            <div className="ab-highlights">
              <span className="ab-stat-label">Top Sprint</span>
              <div className="ab-highlight-row">
                <span className="ab-lightning">⚡</span>
                <span className="ab-highlight-time">{sprint_moments[0].label}</span>
                <span className="ab-highlight-speed">{sprint_moments[0].speed_kmh} km/h</span>
              </div>
            </div>
          )}
        </div>
      </div>

      <style>{`
        .ab-wrap {
          background: var(--surface); border: 1px solid var(--border);
          border-radius: var(--radius); overflow: hidden;
        }
        .ab-header {
          display: flex; justify-content: space-between; align-items: center;
          padding: 14px 20px; border-bottom: 1px solid var(--border);
        }
        .ab-badge {
          font-size: 10px; font-weight: 700; text-transform: uppercase;
          letter-spacing: .07em; padding: 3px 10px; border-radius: 20px;
          background: var(--surface-2); border: 1px solid var(--border);
          color: var(--text-muted);
        }
        .ab-body {
          display: grid; grid-template-columns: auto 1fr;
          gap: 20px; padding: 20px;
          align-items: start;
        }
        @media (max-width: 500px) {
          .ab-body { grid-template-columns: 1fr; }
        }

        /* Donut */
        .ab-donut-col { display: flex; flex-direction: column; align-items: center; gap: 14px; }
        .ab-donut {
          width: 120px; height: 120px; border-radius: 50%;
          display: flex; align-items: center; justify-content: center;
          flex-shrink: 0;
        }
        .ab-donut-hole {
          width: 76px; height: 76px; border-radius: 50%;
          background: var(--surface);
          display: flex; flex-direction: column; align-items: center; justify-content: center;
        }
        .ab-donut-pct { font-size: 20px; font-weight: 900; color: var(--text); }
        .ab-donut-sub { font-size: 9px; color: var(--text-muted); text-transform: uppercase; letter-spacing: .08em; }

        .ab-legend { display: flex; flex-direction: column; gap: 6px; }
        .ab-legend-item {
          display: flex; align-items: center; gap: 8px;
          font-size: 11px; color: var(--text-dim);
        }
        .ab-legend-item strong { margin-left: auto; color: var(--text); font-size: 12px; }
        .ab-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }

        /* Stats */
        .ab-stats-col { display: flex; flex-direction: column; gap: 10px; }
        .ab-stat-card {
          background: var(--surface-2); border: 1px solid var(--border);
          border-radius: 10px; padding: 12px 14px;
          display: flex; flex-direction: column; gap: 2px;
        }
        .ab-stat-label {
          font-size: 10px; font-weight: 700; text-transform: uppercase;
          letter-spacing: .07em; color: var(--text-muted);
        }
        .ab-stat-value { font-size: 28px; font-weight: 900; line-height: 1.1; }
        .ab-stat-tag { font-size: 10px; font-weight: 600; }

        .ab-highlights {
          background: var(--surface-2); border: 1px solid var(--border);
          border-radius: 10px; padding: 12px 14px;
          display: flex; flex-direction: column; gap: 6px;
        }
        .ab-highlight-row { display: flex; align-items: center; gap: 8px; }
        .ab-lightning { font-size: 16px; }
        .ab-highlight-time {
          font-size: 13px; font-weight: 700; color: var(--text);
          font-variant-numeric: tabular-nums;
        }
        .ab-highlight-speed {
          font-size: 13px; font-weight: 800; color: var(--green); margin-left: auto;
        }
      `}</style>
    </div>
  );
}
