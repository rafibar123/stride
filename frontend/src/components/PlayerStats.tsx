import { Activity, Zap, Wind, TrendingUp, Circle } from 'lucide-react';
import type { PlayerStats as Stats } from '../types';

interface Props { stats: Stats; fps: number; }

export default function PlayerStats({ stats, fps }: Props) {
  const {
    zone_frames, distance_m, avg_speed_mps, max_speed_mps,
    sprint_count, total_frames,
    ball_time_s, ball_time_pct, ball_time_str,
  } = stats;

  const dur_s = total_frames / Math.max(fps, 1);
  const dur_str = dur_s >= 60
    ? `${Math.floor(dur_s / 60)}m ${Math.round(dur_s % 60)}s`
    : `${Math.round(dur_s)}s`;

  const distKm = distance_m >= 1000;
  const distVal = distKm ? (distance_m / 1000).toFixed(2) : distance_m.toFixed(0);
  const distUnit = distKm ? 'km' : 'm';

  const hasBallTime = ball_time_s != null && ball_time_s > 0;

  const cards = [
    {
      icon: <Activity size={20} />,
      label: 'Distance Run',
      value: distVal,
      unit: distUnit,
      color: 'green',
      sub: `${dur_str} tracked`,
    },
    {
      icon: <Zap size={20} />,
      label: 'Top Speed',
      value: (max_speed_mps * 3.6).toFixed(1),
      unit: 'km/h',
      color: 'amber',
      sub: `${max_speed_mps.toFixed(2)} m/s`,
    },
    {
      icon: <Wind size={20} />,
      label: 'Avg Speed',
      value: (avg_speed_mps * 3.6).toFixed(1),
      unit: 'km/h',
      color: 'blue',
      sub: `${avg_speed_mps.toFixed(2)} m/s`,
    },
    {
      icon: <TrendingUp size={20} />,
      label: 'Sprint Bursts',
      value: sprint_count,
      unit: '',
      color: 'red',
      sub: '≥ 18 km/h threshold',
    },
  ];

  // Zone bar
  const zTotal = (zone_frames.defensive_third + zone_frames.middle_third + zone_frames.attacking_third) || 1;
  const zd = (zone_frames.defensive_third / zTotal) * 100;
  const zm = (zone_frames.middle_third / zTotal) * 100;
  const za = (zone_frames.attacking_third / zTotal) * 100;

  return (
    <div className="ps-root">
      <div className="stats-grid">
        {cards.map((c) => (
          <div key={c.label} className={`stat-card sc-${c.color}`}>
            <div className="sc-top">
              <div className={`sc-icon sc-${c.color}`}>{c.icon}</div>
              <span className="sc-label">{c.label}</span>
            </div>
            <div className="sc-val-row">
              <span className="sc-val">{c.value}</span>
              {c.unit && <span className="sc-unit">{c.unit}</span>}
            </div>
            <span className="sc-sub">{c.sub}</span>
          </div>
        ))}
      </div>

      {hasBallTime && (
        <div className="ball-time-card">
          <div className="bt-left">
            <div className="bt-icon">
              <Circle size={18} strokeWidth={2.5} />
            </div>
            <div className="bt-text">
              <span className="bt-label">Time With Ball</span>
              <span className="bt-sub">within 1 m of ball</span>
            </div>
          </div>
          <div className="bt-right">
            <span className="bt-time">{ball_time_str}</span>
            <div className="bt-pct-wrap">
              <div className="bt-bar-track">
                <div className="bt-bar-fill" style={{ width: `${Math.min(ball_time_pct ?? 0, 100)}%` }} />
              </div>
              <span className="bt-pct">{(ball_time_pct ?? 0).toFixed(1)}%</span>
            </div>
          </div>
        </div>
      )}

      <div className="zone-card">
        <div className="zone-card-header">
          <span className="section-title">Zone Coverage</span>
          <div className="zone-legend">
            <span className="zl-item zl-def">Defensive {zd.toFixed(0)}%</span>
            <span className="zl-item zl-mid">Middle {zm.toFixed(0)}%</span>
            <span className="zl-item zl-att">Attacking {za.toFixed(0)}%</span>
          </div>
        </div>
        <div className="zone-bar">
          <div className="zb-seg zb-def" style={{ width: `${zd}%` }} />
          <div className="zb-seg zb-mid" style={{ width: `${zm}%` }} />
          <div className="zb-seg zb-att" style={{ width: `${za}%` }} />
        </div>
      </div>

      <style>{`
        .ps-root { display: flex; flex-direction: column; gap: 16px; }

        .stats-grid {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 14px;
        }
        @media (max-width: 700px) {
          .stats-grid { grid-template-columns: repeat(2, 1fr); }
        }

        .stat-card {
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: var(--radius);
          padding: 20px 18px 16px;
          display: flex;
          flex-direction: column;
          gap: 6px;
          position: relative;
          overflow: hidden;
          transition: transform .2s, box-shadow .2s;
        }
        .stat-card::before {
          content: '';
          position: absolute;
          top: 0; left: 0; right: 0;
          height: 2px;
        }
        .stat-card.sc-green::before  { background: linear-gradient(90deg, var(--green), transparent); }
        .stat-card.sc-amber::before  { background: linear-gradient(90deg, var(--amber), transparent); }
        .stat-card.sc-blue::before   { background: linear-gradient(90deg, var(--blue), transparent); }
        .stat-card.sc-red::before    { background: linear-gradient(90deg, var(--red), transparent); }
        .stat-card:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,.4); }

        .sc-top { display: flex; align-items: center; gap: 8px; }
        .sc-icon {
          width: 34px; height: 34px;
          border-radius: var(--radius-sm);
          display: flex; align-items: center; justify-content: center;
          flex-shrink: 0;
        }
        .sc-icon.sc-green  { background: var(--green-dim);  color: var(--green); }
        .sc-icon.sc-amber  { background: var(--amber-dim);  color: var(--amber); }
        .sc-icon.sc-blue   { background: var(--blue-dim);   color: var(--blue); }
        .sc-icon.sc-red    { background: rgba(248,113,113,.1); color: var(--red); }
        .sc-label {
          font-size: 11px; font-weight: 600;
          text-transform: uppercase; letter-spacing: .06em;
          color: var(--text-muted);
        }
        .sc-val-row { display: flex; align-items: baseline; gap: 5px; margin-top: 4px; }
        .sc-val  { font-size: 30px; font-weight: 800; color: var(--text); line-height: 1; font-variant-numeric: tabular-nums; }
        .sc-unit { font-size: 14px; color: var(--text-muted); font-weight: 500; }
        .sc-sub  { font-size: 11px; color: var(--text-muted); margin-top: 2px; }

        .ball-time-card {
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: var(--radius);
          padding: 16px 20px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 16px;
        }
        .bt-left  { display: flex; align-items: center; gap: 12px; }
        .bt-icon  {
          width: 36px; height: 36px; border-radius: var(--radius-sm);
          background: var(--green-dim); color: var(--green);
          display: flex; align-items: center; justify-content: center;
          flex-shrink: 0;
        }
        .bt-text  { display: flex; flex-direction: column; gap: 2px; }
        .bt-label { font-size: 12px; font-weight: 700; color: var(--text); }
        .bt-sub   { font-size: 10px; color: var(--text-muted); text-transform: uppercase; letter-spacing: .05em; }

        .bt-right { display: flex; align-items: center; gap: 16px; flex-shrink: 0; }
        .bt-time  {
          font-size: 28px; font-weight: 800; color: var(--text);
          font-variant-numeric: tabular-nums; white-space: nowrap;
        }
        .bt-pct-wrap { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; }
        .bt-bar-track {
          width: 90px; height: 5px; border-radius: 3px;
          background: var(--surface-3);
          overflow: hidden;
        }
        .bt-bar-fill {
          height: 100%; border-radius: 3px;
          background: var(--green);
          box-shadow: 0 0 6px var(--green-glow);
          transition: width .6s ease;
        }
        .bt-pct { font-size: 11px; font-weight: 700; color: var(--green); }

        .zone-card {
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: var(--radius);
          padding: 18px 20px;
          display: flex;
          flex-direction: column;
          gap: 12px;
        }
        .zone-card-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          flex-wrap: wrap;
          gap: 8px;
        }
        .zone-legend { display: flex; gap: 16px; }
        .zl-item {
          font-size: 11px; font-weight: 600;
          display: flex; align-items: center; gap: 5px;
        }
        .zl-item::before {
          content: '';
          display: inline-block;
          width: 10px; height: 10px;
          border-radius: 2px;
        }
        .zl-def { color: var(--blue);  }
        .zl-def::before { background: var(--blue); }
        .zl-mid { color: var(--green); }
        .zl-mid::before { background: var(--green); }
        .zl-att { color: var(--amber); }
        .zl-att::before { background: var(--amber); }

        .zone-bar {
          display: flex;
          height: 10px;
          border-radius: 5px;
          overflow: hidden;
          background: var(--surface-3);
          gap: 2px;
        }
        .zb-seg { transition: width .5s ease; border-radius: 3px; }
        .zb-def { background: var(--blue);  opacity: .85; }
        .zb-mid { background: var(--green); opacity: .85; }
        .zb-att { background: var(--amber); opacity: .85; }
      `}</style>
    </div>
  );
}
