import { useState } from 'react';
import { ChevronRight, User } from 'lucide-react';
import type { PlayerProfile } from '../types';

interface Props {
  onSubmit: (profile: PlayerProfile) => void;
}

export default function PlayerProfileForm({ onSubmit }: Props) {
  const [name, setName]             = useState('');
  const [number, setNumber]         = useState('');
  const [jerseyColor, setJerseyColor] = useState('#00e676');
  const [teamName, setTeamName]     = useState('');

  const canSubmit = name.trim().length > 0 && number.trim().length > 0;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    onSubmit({
      name: name.trim(),
      number: number.trim(),
      jerseyColor,
      teamName: teamName.trim(),
    });
  };

  return (
    <form className="ppf-wrap" onSubmit={handleSubmit}>
      <div className="ppf-header">
        <span className="ppf-icon"><User size={18} color="var(--green)" /></span>
        <div>
          <p className="ppf-title">Player details</p>
          <p className="ppf-sub">Used in your performance report and to help track you in the video.</p>
        </div>
      </div>

      <div className="ppf-grid">
        {/* Name */}
        <div className="ppf-field ppf-field-wide">
          <label className="ppf-label" htmlFor="ppf-name">Your name <span className="ppf-req">*</span></label>
          <input
            id="ppf-name"
            className="ppf-input"
            type="text"
            placeholder="e.g. Alex Johnson"
            maxLength={48}
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoFocus
          />
        </div>

        {/* Jersey number */}
        <div className="ppf-field">
          <label className="ppf-label" htmlFor="ppf-number">Jersey # <span className="ppf-req">*</span></label>
          <input
            id="ppf-number"
            className="ppf-input ppf-input-short"
            type="text"
            inputMode="numeric"
            placeholder="10"
            maxLength={3}
            value={number}
            onChange={(e) => setNumber(e.target.value.replace(/[^0-9]/g, ''))}
          />
        </div>

        {/* Jersey color */}
        <div className="ppf-field">
          <label className="ppf-label" htmlFor="ppf-color">Jersey color <span className="ppf-req">*</span></label>
          <div className="ppf-color-row">
            <input
              id="ppf-color"
              className="ppf-color-input"
              type="color"
              value={jerseyColor}
              onChange={(e) => setJerseyColor(e.target.value)}
            />
            <div className="ppf-color-swatch" style={{ background: jerseyColor }} />
            <span className="ppf-color-hex">{jerseyColor.toUpperCase()}</span>
          </div>
        </div>

        {/* Team name */}
        <div className="ppf-field ppf-field-wide">
          <label className="ppf-label" htmlFor="ppf-team">Team name <span className="ppf-opt">(optional)</span></label>
          <input
            id="ppf-team"
            className="ppf-input"
            type="text"
            placeholder="e.g. FC Riverside Under-17"
            maxLength={64}
            value={teamName}
            onChange={(e) => setTeamName(e.target.value)}
          />
        </div>
      </div>

      {/* Preview badge */}
      {(name || number) && (
        <div className="ppf-preview">
          <div
            className="ppf-jersey-badge"
            style={{ background: jerseyColor, color: _contrastColor(jerseyColor) }}
          >
            {number || '—'}
          </div>
          <div className="ppf-preview-text">
            <span className="ppf-preview-name">{name || 'Player'}</span>
            {teamName && <span className="ppf-preview-team">{teamName}</span>}
          </div>
        </div>
      )}

      <button className="ppf-btn" type="submit" disabled={!canSubmit}>
        Continue — Select yourself in the video
        <ChevronRight size={15} />
      </button>

      <style>{`
        .ppf-wrap {
          display: flex; flex-direction: column; gap: 18px;
        }

        .ppf-header { display: flex; align-items: flex-start; gap: 12px; }
        .ppf-icon {
          width: 36px; height: 36px; flex-shrink: 0;
          background: var(--green-dim); border: 1px solid rgba(0,230,118,.2);
          border-radius: 10px; display: flex; align-items: center; justify-content: center;
        }
        .ppf-title { font-size: 14px; font-weight: 700; color: var(--text); }
        .ppf-sub   { font-size: 12px; color: var(--text-muted); margin-top: 2px; }

        .ppf-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 12px;
        }
        .ppf-field { display: flex; flex-direction: column; gap: 6px; }
        .ppf-field-wide { grid-column: 1 / -1; }

        .ppf-label {
          font-size: 11px; font-weight: 700;
          text-transform: uppercase; letter-spacing: .07em;
          color: var(--text-muted);
        }
        .ppf-req  { color: var(--green); }
        .ppf-opt  { font-weight: 400; text-transform: none; letter-spacing: 0; color: var(--text-muted); opacity: .6; }

        .ppf-input {
          background: var(--surface-2); border: 1px solid var(--border);
          border-radius: var(--radius-sm); color: var(--text);
          font-size: 13px; padding: 9px 12px; outline: none;
          transition: border-color .15s;
          width: 100%; box-sizing: border-box;
        }
        .ppf-input::placeholder { color: var(--text-muted); opacity: .5; }
        .ppf-input:focus { border-color: var(--green); }
        .ppf-input-short { text-align: center; font-size: 20px; font-weight: 800;
                           letter-spacing: .05em; }

        .ppf-color-row {
          display: flex; align-items: center; gap: 10px;
          background: var(--surface-2); border: 1px solid var(--border);
          border-radius: var(--radius-sm); padding: 7px 12px;
          transition: border-color .15s;
        }
        .ppf-color-row:focus-within { border-color: var(--green); }
        .ppf-color-input {
          width: 28px; height: 28px; border: none; background: none;
          cursor: pointer; padding: 0; border-radius: 50%;
          outline: none;
        }
        .ppf-color-swatch {
          width: 24px; height: 24px; border-radius: 6px;
          border: 1px solid rgba(255,255,255,.12); flex-shrink: 0;
        }
        .ppf-color-hex {
          font-size: 11px; font-weight: 700; letter-spacing: .1em;
          color: var(--text-muted); font-family: var(--mono, monospace);
        }

        .ppf-preview {
          display: flex; align-items: center; gap: 12px;
          background: var(--surface-2); border: 1px solid var(--border);
          border-radius: var(--radius-sm); padding: 10px 14px;
        }
        .ppf-jersey-badge {
          width: 38px; height: 38px; border-radius: 8px;
          display: flex; align-items: center; justify-content: center;
          font-size: 15px; font-weight: 900; flex-shrink: 0;
          border: 2px solid rgba(255,255,255,.15);
          box-shadow: 0 2px 8px rgba(0,0,0,.35);
        }
        .ppf-preview-text { display: flex; flex-direction: column; gap: 2px; }
        .ppf-preview-name { font-size: 13px; font-weight: 700; color: var(--text); }
        .ppf-preview-team { font-size: 11px; color: var(--text-muted); }

        .ppf-btn {
          display: flex; align-items: center; justify-content: center; gap: 8px;
          background: var(--green); color: #07090f;
          border: none; border-radius: var(--radius-sm);
          padding: 13px 20px; font-size: 14px; font-weight: 800;
          cursor: pointer; box-shadow: 0 0 20px var(--green-glow);
          transition: opacity .2s, transform .15s;
        }
        .ppf-btn:hover:not(:disabled) { opacity: .9; transform: translateY(-1px); }
        .ppf-btn:disabled {
          opacity: .35; cursor: not-allowed; box-shadow: none; transform: none;
        }
      `}</style>
    </form>
  );
}

/** Pick black or white text for contrast over a hex background. */
function _contrastColor(hex: string): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  // WCAG relative luminance
  const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return lum > 0.55 ? '#07090f' : '#ffffff';
}
