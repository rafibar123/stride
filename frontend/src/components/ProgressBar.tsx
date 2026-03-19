import { useEffect, useRef } from 'react';
import { Loader2 } from 'lucide-react';

interface Props {
  progress: number; // 0-100, real value from backend
  stage: string;    // machine-readable stage key from backend
}

// ordered pipeline stages; each has a display label
const STAGES = [
  { key: 'starting',        label: 'Starting up' },
  { key: 'video_opened',    label: 'Reading video' },
  { key: 'models_loading',  label: 'Loading models' },
  { key: 'detecting',       label: 'Player detection' },
  { key: 'tracking',        label: 'Tracking player' },
  { key: 'post_processing', label: 'Computing metrics' },
  { key: 'done',            label: 'Done' },
];

// fallback label for unknown keys
const stageLabel = (key: string) =>
  STAGES.find((s) => s.key === key)?.label ?? key.replace(/_/g, ' ');

// which step index is active based on the current stage key
const activeIdx = (key: string) => {
  const i = STAGES.findIndex((s) => s.key === key);
  return i < 0 ? 0 : i;
};

export default function ProgressBar({ progress, stage }: Props) {
  const barRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (barRef.current) {
      barRef.current.style.width = `${Math.min(100, progress)}%`;
    }
  }, [progress]);

  const idx = activeIdx(stage);

  return (
    <div className="progress-wrap">
      <div className="progress-header">
        <div className="progress-label">
          <Loader2 size={14} className="spin" />
          <span>{stageLabel(stage)}{progress < 100 ? '…' : ''}</span>
        </div>
        <span className="progress-pct">{Math.round(progress)}%</span>
      </div>

      <div className="progress-track">
        <div className="progress-bar" ref={barRef} />
        <div className="progress-shimmer" />
      </div>

      <div className="progress-steps">
        {STAGES.filter((s) => s.key !== 'done').map((s, i) => (
          <div
            key={s.key}
            className={`progress-step ${
              i < idx ? 'done' : i === idx ? 'active' : ''
            }`}
          >
            <div className="step-dot" />
            <span>{s.label}</span>
          </div>
        ))}
      </div>

      <style>{`
        .progress-wrap {
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: var(--radius);
          padding: 20px 24px;
          display: flex;
          flex-direction: column;
          gap: 14px;
        }
        .progress-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .progress-label {
          display: flex;
          align-items: center;
          gap: 8px;
          font-weight: 600;
          color: var(--green);
          font-size: 13px;
          text-transform: capitalize;
        }
        .spin { animation: spin 1s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }

        .progress-pct {
          font-variant-numeric: tabular-nums;
          font-weight: 700;
          font-size: 13px;
          color: var(--text-dim);
        }
        .progress-track {
          height: 6px;
          background: var(--surface-3);
          border-radius: 3px;
          overflow: hidden;
          position: relative;
        }
        .progress-bar {
          height: 100%;
          background: linear-gradient(90deg, #00b359, var(--green));
          border-radius: 3px;
          transition: width 0.8s ease;
          position: relative;
          z-index: 1;
          box-shadow: 0 0 10px var(--green-glow);
        }
        .progress-shimmer {
          position: absolute;
          inset: 0;
          background: linear-gradient(
            90deg,
            transparent 0%,
            rgba(255,255,255,.08) 50%,
            transparent 100%
          );
          background-size: 200% 100%;
          animation: shimmer 1.4s infinite;
        }
        @keyframes shimmer {
          0% { background-position: -200% 0; }
          100% { background-position: 200% 0; }
        }
        .progress-steps {
          display: flex;
          flex-wrap: wrap;
          gap: 8px 16px;
        }
        .progress-step {
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 11px;
          color: var(--text-muted);
          transition: color .3s;
        }
        .progress-step.done   { color: var(--green); }
        .progress-step.active { color: var(--text); }
        .step-dot {
          width: 6px; height: 6px;
          border-radius: 50%;
          background: var(--border);
          transition: background .3s;
          flex-shrink: 0;
        }
        .progress-step.done .step-dot  { background: var(--green); }
        .progress-step.active .step-dot {
          background: var(--green);
          box-shadow: 0 0 6px var(--green);
          animation: pulse-dot 1s ease-in-out infinite;
        }
        @keyframes pulse-dot {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0.4; }
        }
      `}</style>
    </div>
  );
}
