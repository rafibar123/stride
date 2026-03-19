import { useState } from 'react';
import { ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react';
import type { PlayerMetric } from '../types';

interface Props { players: PlayerMetric[]; }

type SortKey = 'track_id' | 'distance_m' | 'avg_speed_mps' | 'max_speed_mps' | 'total_frames';

export default function PlayerTable({ players }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>('distance_m');
  const [sortAsc, setSortAsc] = useState(false);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc((a) => !a);
    else { setSortKey(key); setSortAsc(false); }
  };

  const sorted = [...players].sort((a, b) => {
    const v = (a[sortKey] as number) - (b[sortKey] as number);
    return sortAsc ? v : -v;
  });

  const SortIcon = ({ col }: { col: SortKey }) =>
    sortKey === col
      ? sortAsc ? <ChevronUp size={12} /> : <ChevronDown size={12} />
      : <ChevronsUpDown size={12} style={{ opacity: 0.35 }} />;

  const teamColor = (id: number | null) =>
    id === 1 ? 'var(--blue)' : id === 2 ? 'var(--amber)' : 'var(--text-muted)';

  const zoneBar = (zf: PlayerMetric['zone_frames']) => {
    const total = (zf.defensive_third + zf.middle_third + zf.attacking_third) || 1;
    const d = (zf.defensive_third / total) * 100;
    const m = (zf.middle_third    / total) * 100;
    const a = (zf.attacking_third / total) * 100;
    return (
      <div className="zone-bar-wrap" title={`Def ${d.toFixed(0)}%  Mid ${m.toFixed(0)}%  Att ${a.toFixed(0)}%`}>
        <div className="zone-bar">
          <div style={{ width: `${d}%`, background: 'var(--blue)',   opacity: .85 }} />
          <div style={{ width: `${m}%`, background: 'var(--green)',  opacity: .85 }} />
          <div style={{ width: `${a}%`, background: 'var(--amber)',  opacity: .85 }} />
        </div>
        <div className="zone-labels">
          <span style={{ color: 'var(--blue)'  }}>{d.toFixed(0)}%</span>
          <span style={{ color: 'var(--green)' }}>{m.toFixed(0)}%</span>
          <span style={{ color: 'var(--amber)' }}>{a.toFixed(0)}%</span>
        </div>
      </div>
    );
  };

  const cols: { key: SortKey; label: string; sortable: boolean }[] = [
    { key: 'track_id',      label: 'Player',   sortable: true },
    { key: 'track_id',      label: 'Team',     sortable: false },
    { key: 'distance_m',    label: 'Distance', sortable: true },
    { key: 'avg_speed_mps', label: 'Avg Spd',  sortable: true },
    { key: 'max_speed_mps', label: 'Max Spd',  sortable: true },
    { key: 'total_frames',  label: 'Tracked',  sortable: true },
  ];

  return (
    <div className="table-wrap">
      <div className="table-header">
        <span className="section-title">Player Metrics</span>
        <span className="table-count">{players.length} players</span>
      </div>

      <div className="table-scroll">
        <table className="player-table">
          <thead>
            <tr>
              {cols.map((c) => (
                <th
                  key={c.label}
                  className={c.sortable ? 'sortable' : ''}
                  onClick={() => c.sortable && toggleSort(c.key)}
                >
                  <span>{c.label}</span>
                  {c.sortable && <SortIcon col={c.key} />}
                </th>
              ))}
              <th>Zone Split</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((p) => (
              <tr key={p.track_id}>
                <td>
                  <div className="player-id">
                    {p.name
                      ? <span className="player-name">{p.name}</span>
                      : <span className="player-badge">#{p.track_id}</span>
                    }
                  </div>
                </td>
                <td>
                  <span
                    className="team-chip"
                    style={{ borderColor: teamColor(p.team_id), color: teamColor(p.team_id) }}
                  >
                    {p.team_id != null ? `Team ${p.team_id}` : '—'}
                  </span>
                </td>
                <td>
                  <span className="val-primary">{p.distance_m.toFixed(1)}</span>
                  <span className="val-unit"> m</span>
                </td>
                <td>
                  <span className="val-primary">{(p.avg_speed_mps * 3.6).toFixed(1)}</span>
                  <span className="val-unit"> km/h</span>
                </td>
                <td>
                  <div className="speed-cell">
                    <span className="val-primary">{(p.max_speed_mps * 3.6).toFixed(1)}</span>
                    <span className="val-unit"> km/h</span>
                    {p.max_speed_mps >= 5.0 && <span className="sprint-tag">SPRINT</span>}
                  </div>
                </td>
                <td>
                  <span className="val-muted">{p.total_frames} fr</span>
                </td>
                <td className="zone-td">{zoneBar(p.zone_frames)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <style>{`
        .table-wrap {
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: var(--radius);
          overflow: hidden;
        }
        .table-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 16px 20px;
          border-bottom: 1px solid var(--border);
        }
        .table-count {
          font-size: 12px;
          color: var(--text-muted);
          background: var(--surface-3);
          padding: 3px 10px;
          border-radius: 20px;
          border: 1px solid var(--border);
        }
        .table-scroll { overflow-x: auto; }
        .player-table {
          width: 100%;
          border-collapse: collapse;
          font-size: 13px;
          min-width: 660px;
        }
        .player-table th {
          padding: 10px 16px;
          text-align: left;
          font-size: 10px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: .07em;
          color: var(--text-muted);
          background: var(--surface-2);
          border-bottom: 1px solid var(--border);
          white-space: nowrap;
          user-select: none;
        }
        .player-table th.sortable {
          cursor: pointer;
          transition: color .2s;
        }
        .player-table th.sortable:hover { color: var(--text); }
        .player-table th span, .player-table th svg {
          vertical-align: middle;
        }
        .player-table th span { margin-right: 4px; }
        .player-table td {
          padding: 11px 16px;
          border-bottom: 1px solid var(--border-dim);
          vertical-align: middle;
        }
        .player-table tbody tr { transition: background .15s; }
        .player-table tbody tr:hover { background: var(--surface-2); }
        .player-table tbody tr:last-child td { border-bottom: none; }

        .player-badge {
          background: var(--surface-3);
          border: 1px solid var(--border);
          border-radius: 6px;
          padding: 2px 8px;
          font-size: 12px;
          font-weight: 700;
          font-variant-numeric: tabular-nums;
          color: var(--text-dim);
        }
        .player-name {
          font-size: 13px;
          font-weight: 600;
          color: var(--text);
        }
        .team-chip {
          border: 1px solid;
          border-radius: 20px;
          padding: 2px 10px;
          font-size: 11px;
          font-weight: 600;
        }
        .val-primary { font-weight: 700; font-variant-numeric: tabular-nums; }
        .val-unit    { font-size: 11px; color: var(--text-muted); }
        .val-muted   { font-size: 12px; color: var(--text-muted); font-variant-numeric: tabular-nums; }
        .speed-cell  { display: flex; align-items: center; gap: 6px; }
        .sprint-tag  {
          font-size: 9px; font-weight: 700;
          text-transform: uppercase; letter-spacing: .06em;
          background: rgba(251,191,36,.12);
          color: var(--amber);
          border: 1px solid rgba(251,191,36,.3);
          border-radius: 4px;
          padding: 1px 5px;
        }

        .zone-td { min-width: 140px; }
        .zone-bar-wrap { display: flex; flex-direction: column; gap: 3px; }
        .zone-bar {
          display: flex;
          height: 6px;
          border-radius: 3px;
          overflow: hidden;
          background: var(--surface-3);
          gap: 1px;
        }
        .zone-bar div { transition: width .4s ease; border-radius: 2px; }
        .zone-labels {
          display: flex;
          justify-content: space-between;
          font-size: 10px;
          font-variant-numeric: tabular-nums;
        }
      `}</style>
    </div>
  );
}
