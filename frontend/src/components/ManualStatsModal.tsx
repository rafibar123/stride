import { useEffect, useRef, useState } from 'react';
import type { ManualStats } from '../types';

interface Props {
  onSubmit: (stats: ManualStats) => void;
  onSkip: () => void;
  loading?: boolean;
}

interface Field {
  key: keyof ManualStats;
  label: string;
  icon: string;
  hint: string;
}

const FIELDS: Field[] = [
  { key: 'passes_made',              label: 'Passes made',               icon: '⚽', hint: 'Total passes attempted' },
  { key: 'passes_successful',        label: 'Successful passes',         icon: '✅', hint: 'Passes that reached a teammate' },
  { key: 'shots_on_goal',            label: 'Shots on goal',             icon: '🥅', hint: 'Shots on target' },
  { key: 'ball_recoveries',          label: 'Ball recoveries',           icon: '🛡', hint: 'Times you won the ball back' },
  { key: 'lost_balls',               label: 'Times lost the ball',       icon: '❌', hint: 'Times you lost possession' },
  { key: 'aerial_duels_won',         label: 'Aerial duels won',          icon: '✈️', hint: 'Headers / aerial challenges won' },
  { key: 'aerial_duels_total',       label: 'Aerial duels total',        icon: '🔢', hint: 'Total aerial challenges' },
  { key: 'received_under_pressure',  label: 'Received under pressure',   icon: '💪', hint: 'Times you held the ball under pressure' },
  { key: 'created_space',            label: 'Created space',             icon: '🌟', hint: 'Times you created space for a teammate' },
];

const empty = (): ManualStats => ({
  passes_made: 0, passes_successful: 0,
  shots_on_goal: 0, ball_recoveries: 0, lost_balls: 0,
  aerial_duels_won: 0, aerial_duels_total: 0,
  received_under_pressure: 0, created_space: 0,
});

export default function ManualStatsModal({ onSubmit, onSkip, loading = false }: Props) {
  const [values, setValues] = useState<Record<keyof ManualStats, string>>({
    passes_made: '', passes_successful: '', shots_on_goal: '',
    ball_recoveries: '', lost_balls: '',
    aerial_duels_won: '', aerial_duels_total: '',
    received_under_pressure: '', created_space: '',
  });
  const [error, setError] = useState('');
  const firstRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    firstRef.current?.focus();
  }, []);

  const set = (key: keyof ManualStats, raw: string) => {
    if (raw !== '' && !/^\d+$/.test(raw)) return; // digits only
    setError('');
    setValues((v) => ({ ...v, [key]: raw }));
  };

  const handleSubmit = () => {
    const parsed = { ...empty() };
    for (const { key } of FIELDS) {
      parsed[key] = values[key] === '' ? 0 : parseInt(values[key], 10);
    }
    if (parsed.passes_successful > parsed.passes_made && parsed.passes_made > 0) {
      setError('Successful passes cannot exceed total passes made.');
      return;
    }
    if (parsed.aerial_duels_won > parsed.aerial_duels_total && parsed.aerial_duels_total > 0) {
      setError('Aerial duels won cannot exceed total aerial duels.');
      return;
    }
    onSubmit(parsed);
  };

  const anyFilled = FIELDS.some(({ key }) => values[key] !== '');

  return (
    <div className="msm-backdrop" onClick={(e) => e.target === e.currentTarget && onSkip()}>
      <div className="msm-card" role="dialog" aria-modal="true">

        {/* Header */}
        <div className="msm-header">
          <div className="msm-title-row">
            <span className="msm-title">Add your match details</span>
            <span className="msm-emoji">📊</span>
          </div>
          <p className="msm-subtitle">
            Combine your memory with AI tracking for a complete report.
            Takes about 30 seconds.
          </p>
        </div>

        {/* Fields */}
        <div className="msm-fields">
          {FIELDS.map(({ key, label, icon, hint }, i) => (
            <div key={key} className="msm-field">
              <label className="msm-label">
                <span className="msm-field-icon">{icon}</span>
                <span>{label}</span>
              </label>
              <input
                ref={i === 0 ? firstRef : undefined}
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                className="msm-input"
                placeholder="0"
                value={values[key]}
                onChange={(e) => set(key, e.target.value)}
                disabled={loading}
                onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
              />
              <span className="msm-hint">{hint}</span>
            </div>
          ))}
        </div>

        {error && <p className="msm-error">{error}</p>}

        {/* Actions */}
        <div className="msm-actions">
          <button
            className="msm-btn-primary"
            onClick={handleSubmit}
            disabled={loading || !anyFilled}
          >
            {loading ? (
              <span className="msm-spinner" />
            ) : (
              '✦ Generate full report'
            )}
          </button>
          <button className="msm-btn-skip" onClick={onSkip} disabled={loading}>
            Skip — use AI data only
          </button>
        </div>
      </div>

      <style>{`
        .msm-backdrop {
          position: fixed; inset: 0; z-index: 1000;
          background: rgba(0,0,0,.72);
          backdrop-filter: blur(6px);
          display: flex; align-items: center; justify-content: center;
          padding: 20px;
          animation: msm-fade-in .18s ease;
        }
        @keyframes msm-fade-in {
          from { opacity: 0; }
          to   { opacity: 1; }
        }

        .msm-card {
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: 18px;
          width: 100%; max-width: 440px;
          overflow: hidden;
          animation: msm-slide-up .22s ease;
          box-shadow: 0 24px 64px rgba(0,0,0,.6);
        }
        @keyframes msm-slide-up {
          from { transform: translateY(20px); opacity: 0; }
          to   { transform: translateY(0);    opacity: 1; }
        }

        .msm-header {
          padding: 22px 24px 16px;
          border-bottom: 1px solid var(--border);
          background: linear-gradient(135deg, rgba(0,230,118,.06) 0%, transparent 60%);
        }
        .msm-title-row {
          display: flex; align-items: center; justify-content: space-between;
          margin-bottom: 6px;
        }
        .msm-title {
          font-size: 17px; font-weight: 800; color: var(--text);
          letter-spacing: -.01em;
        }
        .msm-emoji { font-size: 22px; }
        .msm-subtitle {
          font-size: 12px; color: var(--text-muted); line-height: 1.5; margin: 0;
        }

        .msm-fields {
          padding: 16px 24px;
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 12px;
        }
        @media (max-width: 400px) {
          .msm-fields { grid-template-columns: 1fr; }
        }

        .msm-field {
          display: flex; flex-direction: column; gap: 4px;
        }
        .msm-label {
          display: flex; align-items: center; gap: 6px;
          font-size: 11px; font-weight: 700;
          text-transform: uppercase; letter-spacing: .06em;
          color: var(--text-muted);
        }
        .msm-field-icon { font-size: 13px; }

        .msm-input {
          background: var(--surface-2);
          border: 1px solid var(--border);
          border-radius: 8px;
          color: var(--text);
          font-size: 22px; font-weight: 800;
          font-variant-numeric: tabular-nums;
          padding: 8px 12px;
          width: 100%; box-sizing: border-box;
          outline: none;
          transition: border-color .15s, box-shadow .15s;
          -moz-appearance: textfield;
        }
        .msm-input:focus {
          border-color: var(--green);
          box-shadow: 0 0 0 3px rgba(0,230,118,.15);
        }
        .msm-input::placeholder { color: var(--text-muted); font-weight: 400; font-size: 16px; }
        .msm-input:disabled { opacity: .5; cursor: not-allowed; }

        .msm-hint {
          font-size: 10px; color: var(--text-muted);
        }

        .msm-error {
          margin: 0 24px 4px;
          font-size: 11px; color: #f87171; font-weight: 600;
        }

        .msm-actions {
          padding: 12px 24px 20px;
          display: flex; flex-direction: column; gap: 8px;
        }

        .msm-btn-primary {
          width: 100%;
          background: var(--green); color: #07090f;
          border: none; border-radius: 10px;
          padding: 13px 20px;
          font-size: 13px; font-weight: 800;
          letter-spacing: .02em;
          cursor: pointer;
          transition: opacity .15s, transform .1s;
          display: flex; align-items: center; justify-content: center;
          min-height: 44px;
        }
        .msm-btn-primary:hover:not(:disabled) { opacity: .88; }
        .msm-btn-primary:active:not(:disabled) { transform: scale(.98); }
        .msm-btn-primary:disabled { opacity: .4; cursor: not-allowed; }

        .msm-spinner {
          width: 16px; height: 16px;
          border: 2px solid rgba(0,0,0,.3);
          border-top-color: #07090f;
          border-radius: 50%;
          animation: msm-spin .7s linear infinite;
        }
        @keyframes msm-spin { to { transform: rotate(360deg); } }

        .msm-btn-skip {
          background: none; border: none;
          color: var(--text-muted);
          font-size: 12px; font-weight: 600;
          cursor: pointer; padding: 4px 0;
          transition: color .15s;
          text-align: center;
        }
        .msm-btn-skip:hover:not(:disabled) { color: var(--text); }
        .msm-btn-skip:disabled { opacity: .4; cursor: not-allowed; }
      `}</style>
    </div>
  );
}
