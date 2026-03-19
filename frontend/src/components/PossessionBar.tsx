import type { PossessionEntry, EventMetrics } from '../types';

interface Props {
  possession: PossessionEntry[];
  eventMetrics: EventMetrics;
}

export default function PossessionBar({ possession, eventMetrics: e }: Props) {
  const t1 = possession.find((p) => p.team_id === 1);
  const t2 = possession.find((p) => p.team_id === 2);
  const pct1 = t1 ? Math.round(t1.share * 100) : 50;
  const pct2 = t2 ? Math.round(t2.share * 100) : 50;

  return (
    <div className="poss-wrap">
      <div className="poss-header">
        <span className="section-title">Match Overview</span>
      </div>

      <div className="poss-body">
        {/* possession strip */}
        <div className="poss-section">
          <div className="poss-teams">
            <div className="team-label t1">
              <div className="team-dot t1" />
              <span>Team 1</span>
              <strong>{pct1}%</strong>
            </div>
            <span className="poss-vs">Possession</span>
            <div className="team-label t2">
              <strong>{pct2}%</strong>
              <span>Team 2</span>
              <div className="team-dot t2" />
            </div>
          </div>
          <div className="poss-bar-track">
            <div className="poss-bar-t1" style={{ width: `${pct1}%` }} />
            <div className="poss-bar-t2" style={{ width: `${pct2}%` }} />
          </div>
        </div>

        {/* xG row */}
        <div className="xg-section">
          <div className="xg-row">
            <div className="xg-block t1-color">
              <span className="xg-label">xG</span>
              <span className="xg-val">{e.xG_team_1.toFixed(3)}</span>
            </div>
            <div className="xg-mid">
              <span>Expected Goals</span>
            </div>
            <div className="xg-block t2-color">
              <span className="xg-label">xG</span>
              <span className="xg-val">{e.xG_team_2.toFixed(3)}</span>
            </div>
          </div>
          <div className="xg-row">
            <div className="xg-block t1-color">
              <span className="xg-label">xT</span>
              <span className="xg-val">{e.xT_team_1.toFixed(3)}</span>
            </div>
            <div className="xg-mid"><span>Expected Threat</span></div>
            <div className="xg-block t2-color">
              <span className="xg-label">xT</span>
              <span className="xg-val">{e.xT_team_2.toFixed(3)}</span>
            </div>
          </div>
        </div>
      </div>

      <style>{`
        .poss-wrap {
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: var(--radius);
          overflow: hidden;
        }
        .poss-header {
          padding: 16px 20px;
          border-bottom: 1px solid var(--border);
        }
        .poss-body { padding: 20px; display: flex; flex-direction: column; gap: 20px; }

        .poss-section { display: flex; flex-direction: column; gap: 10px; }
        .poss-teams {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .team-label {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 13px;
        }
        .team-label strong { font-size: 20px; font-weight: 800; }
        .team-label.t1 strong { color: var(--blue); }
        .team-label.t2 strong { color: var(--amber); }
        .team-dot {
          width: 10px; height: 10px;
          border-radius: 50%;
        }
        .team-dot.t1 { background: var(--blue); box-shadow: 0 0 6px var(--blue); }
        .team-dot.t2 { background: var(--amber); box-shadow: 0 0 6px var(--amber); }
        .poss-vs {
          font-size: 11px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: .08em;
          color: var(--text-muted);
        }
        .poss-bar-track {
          height: 10px;
          border-radius: 5px;
          overflow: hidden;
          display: flex;
          background: var(--surface-3);
        }
        .poss-bar-t1 {
          background: linear-gradient(90deg, var(--blue), #60a5fa);
          transition: width .6s ease;
          border-radius: 5px 0 0 5px;
        }
        .poss-bar-t2 {
          background: linear-gradient(90deg, #d97706, var(--amber));
          transition: width .6s ease;
          border-radius: 0 5px 5px 0;
        }

        .xg-section { display: flex; flex-direction: column; gap: 8px; }
        .xg-row {
          display: flex;
          align-items: center;
          gap: 10px;
        }
        .xg-block {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 2px;
          background: var(--surface-2);
          border: 1px solid var(--border);
          border-radius: var(--radius-sm);
          padding: 10px 18px;
          min-width: 80px;
        }
        .xg-block.t1-color { border-color: rgba(56,189,248,.25); }
        .xg-block.t2-color { border-color: rgba(251,191,36,.25); }
        .xg-label {
          font-size: 10px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: .08em;
          color: var(--text-muted);
        }
        .xg-val {
          font-size: 22px;
          font-weight: 800;
          font-variant-numeric: tabular-nums;
        }
        .t1-color .xg-val { color: var(--blue); }
        .t2-color .xg-val { color: var(--amber); }
        .xg-mid {
          flex: 1;
          text-align: center;
          font-size: 11px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: .07em;
          color: var(--text-muted);
        }
      `}</style>
    </div>
  );
}
