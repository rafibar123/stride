import { Activity, Zap, Users, Target, ArrowLeftRight, Timer } from 'lucide-react';
import type { AnalysisResult } from '../types';

interface Props { result: AnalysisResult; }

export default function StatsCards({ result }: Props) {
  const m = result.motion_metrics;
  const e = result.event_metrics;

  const poss1 = e.total_possession_frames > 0
    ? Math.round(e.team_1_possession_frames / e.total_possession_frames * 100)
    : 0;
  const poss2 = 100 - poss1;

  const cards = [
    {
      icon: <Users size={18} />,
      label: 'Players Tracked',
      value: m.player_count,
      unit: '',
      color: 'blue',
      sub: `${result.frames_processed} frames · ${result.fps.toFixed(0)} fps`,
    },
    {
      icon: <Activity size={18} />,
      label: 'Total Distance',
      value: m.total_distance_m >= 1000
        ? (m.total_distance_m / 1000).toFixed(2)
        : m.total_distance_m.toFixed(0),
      unit: m.total_distance_m >= 1000 ? 'km' : 'm',
      color: 'green',
      sub: `${m.sprint_count} sprint bursts`,
    },
    {
      icon: <Zap size={18} />,
      label: 'Max Speed',
      value: (m.max_speed_mps * 3.6).toFixed(1),
      unit: 'km/h',
      color: 'amber',
      sub: `${m.max_speed_mps.toFixed(2)} m/s`,
    },
    {
      icon: <Target size={18} />,
      label: 'Shots · xG',
      value: e.shot_count,
      unit: 'shots',
      color: 'red',
      sub: `xG  ${e.xG_team_1.toFixed(2)} : ${e.xG_team_2.toFixed(2)}`,
    },
    {
      icon: <ArrowLeftRight size={18} />,
      label: 'Passes',
      value: e.pass_success,
      unit: '',
      color: 'purple',
      sub: `${e.turnover_count} turnovers`,
    },
    {
      icon: <Timer size={18} />,
      label: 'Possession',
      value: `${poss1} : ${poss2}`,
      unit: '%',
      color: 'blue',
      sub: 'Team 1 vs Team 2',
      wide: true,
    },
  ];

  return (
    <div className="stats-grid">
      {cards.map((c) => (
        <div key={c.label} className={`stat-card accent-${c.color} ${c.wide ? 'wide' : ''}`}>
          <div className="stat-card-top">
            <div className={`stat-icon accent-${c.color}`}>{c.icon}</div>
            <span className="stat-label">{c.label}</span>
          </div>
          <div className="stat-value-row">
            <span className="stat-value">{c.value}</span>
            {c.unit && <span className="stat-unit">{c.unit}</span>}
          </div>
          <div className="stat-sub">{c.sub}</div>
        </div>
      ))}

      <style>{`
        .stats-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
          gap: 14px;
        }
        .stat-card {
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: var(--radius);
          padding: 18px;
          display: flex;
          flex-direction: column;
          gap: 6px;
          transition: transform .2s, box-shadow .2s;
          position: relative;
          overflow: hidden;
        }
        .stat-card::before {
          content: '';
          position: absolute;
          top: 0; left: 0; right: 0;
          height: 2px;
        }
        .stat-card.accent-green::before { background: linear-gradient(90deg, var(--green), transparent); }
        .stat-card.accent-blue::before  { background: linear-gradient(90deg, var(--blue), transparent); }
        .stat-card.accent-amber::before { background: linear-gradient(90deg, var(--amber), transparent); }
        .stat-card.accent-red::before   { background: linear-gradient(90deg, var(--red), transparent); }
        .stat-card.accent-purple::before { background: linear-gradient(90deg, var(--purple), transparent); }
        .stat-card:hover {
          transform: translateY(-2px);
          box-shadow: 0 8px 24px rgba(0,0,0,.4);
        }
        .stat-card-top {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .stat-icon {
          width: 32px; height: 32px;
          border-radius: var(--radius-sm);
          display: flex; align-items: center; justify-content: center;
          flex-shrink: 0;
        }
        .stat-icon.accent-green  { background: var(--green-dim);  color: var(--green); }
        .stat-icon.accent-blue   { background: var(--blue-dim);   color: var(--blue); }
        .stat-icon.accent-amber  { background: var(--amber-dim);  color: var(--amber); }
        .stat-icon.accent-red    { background: rgba(248,113,113,.1); color: var(--red); }
        .stat-icon.accent-purple { background: rgba(167,139,250,.1); color: var(--purple); }
        .stat-label {
          font-size: 11px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: .06em;
          color: var(--text-muted);
        }
        .stat-value-row {
          display: flex;
          align-items: baseline;
          gap: 5px;
          margin-top: 4px;
        }
        .stat-value {
          font-size: 28px;
          font-weight: 800;
          color: var(--text);
          line-height: 1;
          font-variant-numeric: tabular-nums;
        }
        .stat-unit { font-size: 13px; color: var(--text-muted); font-weight: 500; }
        .stat-sub  { font-size: 11px; color: var(--text-muted); margin-top: 2px; }
      `}</style>
    </div>
  );
}
