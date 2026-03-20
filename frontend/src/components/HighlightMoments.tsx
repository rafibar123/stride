import type { SprintMoment } from '../types';

interface Props { moments: SprintMoment[]; }

const MEDALS = ['🥇', '🥈', '🥉'];
const ACCENT = ['#00e676', '#38bdf8', '#fbbf24'];

export default function HighlightMoments({ moments }: Props) {
  if (!moments || moments.length === 0) return null;

  return (
    <div className="hm-wrap">
      <div className="hm-header">
        <span className="section-title">Sprint Highlights</span>
        <span className="hm-badge">Top {moments.length}</span>
      </div>

      <div className="hm-list">
        {moments.map((m, i) => (
          <div key={i} className="hm-row" style={{ '--hm-accent': ACCENT[i] } as React.CSSProperties}>
            <span className="hm-medal">{MEDALS[i] ?? '⚡'}</span>
            <div className="hm-info">
              <span className="hm-rank">Sprint #{i + 1}</span>
              <span className="hm-time">at {m.label}</span>
            </div>
            <div className="hm-speed-wrap">
              <span className="hm-speed">{m.speed_kmh}</span>
              <span className="hm-unit">km/h</span>
            </div>
          </div>
        ))}
      </div>

      <style>{`
        .hm-wrap {
          background: var(--surface); border: 1px solid var(--border);
          border-radius: var(--radius); overflow: hidden;
        }
        .hm-header {
          display: flex; justify-content: space-between; align-items: center;
          padding: 14px 20px; border-bottom: 1px solid var(--border);
        }
        .hm-badge {
          font-size: 10px; font-weight: 700; text-transform: uppercase;
          letter-spacing: .07em; padding: 3px 10px; border-radius: 20px;
          background: var(--green-dim); border: 1px solid rgba(0,230,118,.25);
          color: var(--green);
        }
        .hm-list { display: flex; flex-direction: column; }
        .hm-row {
          display: flex; align-items: center; gap: 14px;
          padding: 14px 20px;
          border-bottom: 1px solid var(--border);
          border-left: 3px solid var(--hm-accent, var(--green));
          transition: background .15s;
        }
        .hm-row:last-child { border-bottom: none; }
        .hm-row:hover { background: var(--surface-2); }

        .hm-medal { font-size: 20px; flex-shrink: 0; }
        .hm-info { display: flex; flex-direction: column; gap: 2px; flex: 1; }
        .hm-rank {
          font-size: 12px; font-weight: 700; color: var(--text);
        }
        .hm-time {
          font-size: 11px; color: var(--text-muted);
          font-variant-numeric: tabular-nums;
        }
        .hm-speed-wrap {
          display: flex; align-items: baseline; gap: 3px; flex-shrink: 0;
        }
        .hm-speed {
          font-size: 28px; font-weight: 900;
          font-variant-numeric: tabular-nums;
          color: var(--hm-accent, var(--green));
          text-shadow: 0 0 16px var(--hm-accent, var(--green));
        }
        .hm-unit {
          font-size: 11px; color: var(--text-muted); font-weight: 600;
        }
      `}</style>
    </div>
  );
}
