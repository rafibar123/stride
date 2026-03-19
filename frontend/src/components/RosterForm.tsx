import { useState } from 'react';
import { Play, Plus, Trash2 } from 'lucide-react';
import type { Roster, RosterTeam, RosterPlayer } from '../types';

interface Props {
  onSubmit: (roster: Roster) => void;
  disabled?: boolean;
}

const COLORS = [
  { value: 'red',       label: 'Red',       hex: '#ef4444' },
  { value: 'green',     label: 'Green',     hex: '#22c55e' },
  { value: 'blue',      label: 'Blue',      hex: '#3b82f6' },
  { value: 'dark_blue', label: 'Dark Blue', hex: '#1e3a8a' },
  { value: 'white',     label: 'White',     hex: '#e5e7eb' },
  { value: 'black',     label: 'Black',     hex: '#374151' },
  { value: 'yellow',    label: 'Yellow',    hex: '#eab308' },
  { value: 'orange',    label: 'Orange',    hex: '#f97316' },
  { value: 'purple',    label: 'Purple',    hex: '#a855f7' },
  { value: 'pink',      label: 'Pink',      hex: '#ec4899' },
];

const emptyTeam = (name: string, color: string): RosterTeam => ({
  name,
  color,
  players: [{ jersey: '', name: '' }],
});

export default function RosterForm({ onSubmit, disabled = false }: Props) {
  const [teams, setTeams] = useState<[RosterTeam, RosterTeam]>([
    emptyTeam('Home Team', 'red'),
    emptyTeam('Away Team', 'green'),
  ]);

  const updateTeam = (ti: 0 | 1, patch: Partial<RosterTeam>) => {
    setTeams((prev) => {
      const next: [RosterTeam, RosterTeam] = [{ ...prev[0] }, { ...prev[1] }];
      next[ti] = { ...next[ti], ...patch };
      return next;
    });
  };

  const updatePlayer = (ti: 0 | 1, pi: number, patch: Partial<RosterPlayer>) => {
    setTeams((prev) => {
      const next: [RosterTeam, RosterTeam] = [{ ...prev[0] }, { ...prev[1] }];
      const players = [...next[ti].players];
      players[pi] = { ...players[pi], ...patch };
      next[ti] = { ...next[ti], players };
      return next;
    });
  };

  const addPlayer = (ti: 0 | 1) => {
    if (teams[ti].players.length >= 11) return;
    updateTeam(ti, { players: [...teams[ti].players, { jersey: '', name: '' }] });
  };

  const removePlayer = (ti: 0 | 1, pi: number) => {
    const players = teams[ti].players.filter((_, i) => i !== pi);
    updateTeam(ti, { players: players.length ? players : [{ jersey: '', name: '' }] });
  };

  const handleSubmit = () => {
    const cleaned: [RosterTeam, RosterTeam] = [
      {
        ...teams[0],
        players: teams[0].players.filter((p) => p.name.trim()),
      },
      {
        ...teams[1],
        players: teams[1].players.filter((p) => p.name.trim()),
      },
    ];
    onSubmit({ teams: cleaned });
  };

  return (
    <div className="roster-wrap">
      <div className="roster-header">
        <h3 className="roster-title">Player Registration</h3>
        <p className="roster-sub">
          Enter each player's name and jersey number. The system will match shirt
          colors to teams automatically.
        </p>
      </div>

      <div className="roster-teams">
        {([0, 1] as const).map((ti) => {
          const team = teams[ti];
          const colorDef = COLORS.find((c) => c.value === team.color) ?? COLORS[0];
          return (
            <div key={ti} className="roster-team">
              <div className="team-header">
                <input
                  className="team-name-input"
                  value={team.name}
                  onChange={(e) => updateTeam(ti, { name: e.target.value })}
                  placeholder="Team name"
                />
                <div className="color-select-wrap">
                  <span className="color-dot" style={{ background: colorDef.hex }} />
                  <select
                    className="color-select"
                    value={team.color}
                    onChange={(e) => updateTeam(ti, { color: e.target.value })}
                  >
                    {COLORS.map((c) => (
                      <option key={c.value} value={c.value}>{c.label}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="player-list">
                <div className="player-list-header">
                  <span>Jersey</span>
                  <span>Player Name</span>
                </div>
                {team.players.map((p, pi) => (
                  <div key={pi} className="player-row">
                    <input
                      className="jersey-input"
                      value={p.jersey}
                      onChange={(e) => updatePlayer(ti, pi, { jersey: e.target.value })}
                      placeholder="#"
                      maxLength={3}
                    />
                    <input
                      className="name-input"
                      value={p.name}
                      onChange={(e) => updatePlayer(ti, pi, { name: e.target.value })}
                      placeholder="Player name"
                    />
                    <button
                      className="remove-btn"
                      onClick={() => removePlayer(ti, pi)}
                      tabIndex={-1}
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                ))}
                {team.players.length < 11 && (
                  <button className="add-player-btn" onClick={() => addPlayer(ti)}>
                    <Plus size={13} /> Add player
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <button className="btn-run" onClick={handleSubmit} disabled={disabled}>
        <Play size={15} fill="currentColor" />
        {disabled ? 'Upload a video to start' : 'Run Analysis'}
      </button>

      <style>{`
        .roster-wrap {
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: var(--radius);
          padding: 24px;
          display: flex;
          flex-direction: column;
          gap: 20px;
        }
        .roster-header { display: flex; flex-direction: column; gap: 4px; }
        .roster-title {
          font-size: 15px; font-weight: 700; color: var(--text);
        }
        .roster-sub { font-size: 12px; color: var(--text-muted); }

        .roster-teams {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 16px;
        }
        @media (max-width: 700px) { .roster-teams { grid-template-columns: 1fr; } }

        .roster-team {
          background: var(--surface-2);
          border: 1px solid var(--border);
          border-radius: var(--radius-sm);
          padding: 14px;
          display: flex;
          flex-direction: column;
          gap: 10px;
        }
        .team-header {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .team-name-input {
          flex: 1;
          background: var(--surface-3);
          border: 1px solid var(--border);
          border-radius: 6px;
          padding: 6px 10px;
          font-size: 13px;
          font-weight: 700;
          color: var(--text);
          outline: none;
        }
        .team-name-input:focus { border-color: var(--green); }

        .color-select-wrap {
          display: flex;
          align-items: center;
          gap: 6px;
          background: var(--surface-3);
          border: 1px solid var(--border);
          border-radius: 6px;
          padding: 4px 8px;
        }
        .color-dot {
          width: 12px; height: 12px;
          border-radius: 50%;
          flex-shrink: 0;
          border: 1px solid rgba(255,255,255,.15);
        }
        .color-select {
          background: transparent;
          border: none;
          color: var(--text-dim);
          font-size: 12px;
          outline: none;
          cursor: pointer;
        }
        .color-select option { background: #1a1a2e; }

        .player-list { display: flex; flex-direction: column; gap: 4px; }
        .player-list-header {
          display: grid;
          grid-template-columns: 44px 1fr;
          gap: 6px;
          padding: 0 30px 0 0;
          font-size: 10px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: .06em;
          color: var(--text-muted);
        }
        .player-row {
          display: grid;
          grid-template-columns: 44px 1fr 24px;
          gap: 6px;
          align-items: center;
        }
        .jersey-input, .name-input {
          background: var(--surface-3);
          border: 1px solid var(--border);
          border-radius: 5px;
          padding: 5px 8px;
          font-size: 12px;
          color: var(--text);
          outline: none;
          width: 100%;
          box-sizing: border-box;
        }
        .jersey-input { text-align: center; font-weight: 700; }
        .jersey-input:focus, .name-input:focus { border-color: var(--green); }

        .remove-btn {
          background: none;
          border: none;
          color: var(--text-muted);
          cursor: pointer;
          padding: 4px;
          border-radius: 4px;
          display: flex; align-items: center; justify-content: center;
          transition: color .15s, background .15s;
        }
        .remove-btn:hover { color: var(--red); background: rgba(248,113,113,.1); }

        .add-player-btn {
          display: flex;
          align-items: center;
          gap: 5px;
          background: none;
          border: 1px dashed var(--border);
          border-radius: 5px;
          color: var(--text-muted);
          font-size: 11px;
          padding: 5px 10px;
          cursor: pointer;
          transition: border-color .15s, color .15s;
          margin-top: 2px;
        }
        .add-player-btn:hover { border-color: var(--green); color: var(--green); }

        .btn-run {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          background: var(--green);
          color: #07090f;
          border: none;
          border-radius: var(--radius-sm);
          padding: 12px 28px;
          font-size: 14px;
          font-weight: 700;
          cursor: pointer;
          box-shadow: 0 0 20px var(--green-glow);
          transition: opacity .2s, transform .15s;
          width: 100%;
        }
        .btn-run:hover:not(:disabled) { opacity: .9; transform: translateY(-1px); }
        .btn-run:disabled { opacity: .45; cursor: not-allowed; box-shadow: none; }
      `}</style>
    </div>
  );
}
