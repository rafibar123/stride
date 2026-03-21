import { useEffect, useRef, useState } from 'react';
import { Play, RotateCcw, Loader2 } from 'lucide-react';

const API = 'https://web-production-c4e3a.up.railway.app';

interface Props {
  file: File;
  onConfirm: (clickX: number, clickY: number, previewId: string) => void;
}

export default function PlayerSelector({ file, onConfirm }: Props) {
  const imgRef = useRef<HTMLImageElement>(null);
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [click, setClick] = useState<{ x: number; y: number } | null>(null);
  const [hover, setHover] = useState<{ x: number; y: number } | null>(null);
  const [uploading, setUploading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setPreviewId(null);
    setClick(null);
    setError(null);
    setUploading(true);

    const fd = new FormData();
    fd.append('video', file);

    fetch(`${API}/preview`, { method: 'POST', body: fd })
      .then((r) => {
        if (!r.ok) return r.text().then((t) => { throw new Error(t); });
        return r.json();
      })
      .then((data) => {
        setPreviewId(data.preview_id);
        setUploading(false);
      })
      .catch((e) => {
        setError(e.message ?? 'Upload failed');
        setUploading(false);
      });
  }, [file]);

  const getCoords = (e: React.MouseEvent<HTMLImageElement>) => {
    const rect = (e.target as HTMLImageElement).getBoundingClientRect();
    return {
      x: (e.clientX - rect.left) / rect.width,
      y: (e.clientY - rect.top)  / rect.height,
    };
  };

  const dot = click ?? hover;

  return (
    <div className="ps-wrap">
      <div className="ps-header">
        <span className="ps-icon">👆</span>
        <div>
          <p className="ps-title">Click on yourself in the frame</p>
          <p className="ps-sub">The AI will track only you for the entire clip.</p>
        </div>
      </div>

      <div className="ps-frame-wrap">
        {uploading && (
          <div className="ps-overlay">
            <Loader2 size={20} className="ps-spin" />
            <span>Uploading video…</span>
          </div>
        )}

        {error && (
          <div className="ps-overlay ps-overlay-error">
            <span>⚠ {error}</span>
          </div>
        )}

        {previewId && (
          <>
            <img
              ref={imgRef}
              src={`${API}/frame/${previewId}`}
              alt="Select your position"
              className={`ps-img ${click ? '' : 'ps-crosshair'}`}
              draggable={false}
              onClick={(e) => setClick(getCoords(e))}
              onMouseMove={(e) => setHover(getCoords(e))}
              onMouseLeave={() => setHover(null)}
            />
            {dot && (
              <div
                className={`ps-dot ${click ? 'ps-dot-locked' : 'ps-dot-ghost'}`}
                style={{ left: `${dot.x * 100}%`, top: `${dot.y * 100}%` }}
              />
            )}
          </>
        )}
      </div>

      <div className="ps-actions">
        {click && previewId ? (
          <>
            <button className="ps-btn-run" onClick={() => onConfirm(click.x, click.y, previewId)}>
              <Play size={15} fill="currentColor" />
              Start Tracking Me
            </button>
            <button className="ps-btn-reset" onClick={() => setClick(null)}>
              <RotateCcw size={13} />
              Reselect
            </button>
          </>
        ) : (
          <p className="ps-hint">
            {uploading ? 'Uploading…' : error ? 'Fix the error above to continue' : 'Click on your position in the frame above'}
          </p>
        )}
      </div>

      <style>{`
        .ps-wrap { display: flex; flex-direction: column; gap: 14px; }

        .ps-header { display: flex; align-items: center; gap: 12px; }
        .ps-icon   { font-size: 22px; flex-shrink: 0; }
        .ps-title  { font-size: 14px; font-weight: 700; color: var(--text); }
        .ps-sub    { font-size: 12px; color: var(--text-muted); margin-top: 2px; }

        .ps-frame-wrap {
          position: relative;
          border-radius: var(--radius-sm);
          overflow: hidden;
          border: 1px solid var(--border);
          background: var(--surface-3);
          min-height: 160px;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .ps-img {
          display: block;
          width: 100%;
          height: auto;
          max-height: 440px;
          object-fit: contain;
          user-select: none;
        }
        .ps-crosshair { cursor: crosshair; }

        .ps-overlay {
          position: absolute;
          inset: 0;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 10px;
          font-size: 13px;
          color: var(--text-muted);
          background: var(--surface-3);
        }
        .ps-overlay-error { color: var(--red); }

        .ps-spin { animation: ps-rotate 0.8s linear infinite; }
        @keyframes ps-rotate { to { transform: rotate(360deg); } }

        .ps-dot {
          position: absolute;
          width: 26px;
          height: 26px;
          border-radius: 50%;
          transform: translate(-50%, -50%);
          pointer-events: none;
        }
        .ps-dot-ghost {
          background: rgba(0,230,118,.25);
          border: 2px solid rgba(0,230,118,.6);
          box-shadow: 0 0 10px rgba(0,230,118,.3);
          transition: left 0.04s, top 0.04s;
        }
        .ps-dot-locked {
          background: rgba(0,230,118,.4);
          border: 2.5px solid var(--green);
          box-shadow: 0 0 0 6px rgba(0,230,118,.12), 0 0 20px var(--green-glow);
          animation: ps-pulse 1.8s ease-in-out infinite;
        }
        @keyframes ps-pulse {
          0%,100% { box-shadow: 0 0 0 6px rgba(0,230,118,.12), 0 0 20px var(--green-glow); }
          50%     { box-shadow: 0 0 0 11px rgba(0,230,118,.05), 0 0 28px var(--green-glow); }
        }

        .ps-actions { display: flex; align-items: center; gap: 10px; }

        .ps-btn-run {
          flex: 1;
          display: flex; align-items: center; justify-content: center; gap: 8px;
          background: var(--green); color: #07090f;
          border: none; border-radius: var(--radius-sm);
          padding: 12px 20px; font-size: 14px; font-weight: 700;
          cursor: pointer; box-shadow: 0 0 20px var(--green-glow);
          transition: opacity .2s, transform .15s;
        }
        .ps-btn-run:hover { opacity: .9; transform: translateY(-1px); }

        .ps-btn-reset {
          display: flex; align-items: center; gap: 6px;
          background: none; border: 1px solid var(--border);
          color: var(--text-muted); border-radius: var(--radius-sm);
          padding: 10px 14px; font-size: 12px; font-weight: 600;
          cursor: pointer; transition: border-color .15s, color .15s;
          white-space: nowrap;
        }
        .ps-btn-reset:hover { border-color: var(--text-muted); color: var(--text); }

        .ps-hint {
          font-size: 12px; color: var(--text-muted);
          text-align: center; flex: 1; padding: 8px 0;
        }
      `}</style>
    </div>
  );
}
