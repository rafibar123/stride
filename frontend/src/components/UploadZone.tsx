import { useCallback, useRef, useState } from 'react';
import { Upload, Video, X } from 'lucide-react';

interface Props {
  onFile: (f: File) => void;
  disabled: boolean;
}

export default function UploadZone({ onFile, disabled }: Props) {
  const [dragging, setDragging] = useState(false);
  const [preview, setPreview] = useState<{ name: string; size: string } | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const accept = (file: File) => {
    setPreview({
      name: file.name,
      size: `${(file.size / 1024 / 1024).toFixed(1)} MB`,
    });
    onFile(file);
  };

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      if (disabled) return;
      const file = e.dataTransfer.files[0];
      if (file?.type.startsWith('video/')) accept(file);
    },
    [disabled],
  );

  const clear = (e: React.MouseEvent) => {
    e.stopPropagation();
    setPreview(null);
    if (inputRef.current) inputRef.current.value = '';
  };

  return (
    <div
      className={`upload-zone ${dragging ? 'drag-over' : ''} ${disabled ? 'disabled' : ''}`}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      onClick={() => !disabled && inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept="video/*"
        style={{ display: 'none' }}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) accept(f);
        }}
      />

      {preview ? (
        <div className="upload-preview">
          <div className="upload-preview-icon">
            <Video size={28} color="var(--green)" />
          </div>
          <div className="upload-preview-info">
            <span className="upload-preview-name">{preview.name}</span>
            <span className="upload-preview-size">{preview.size}</span>
          </div>
          {!disabled && (
            <button className="upload-clear" onClick={clear} title="Remove">
              <X size={16} />
            </button>
          )}
        </div>
      ) : (
        <div className="upload-empty">
          <div className="upload-icon-wrap">
            <Upload size={32} color="var(--green)" strokeWidth={1.5} />
          </div>
          <p className="upload-title">Drop your match video here</p>
          <p className="upload-sub">or click to browse · MP4, MOV, AVI</p>
        </div>
      )}

      <style>{`
        .upload-zone {
          border: 2px dashed var(--border);
          border-radius: var(--radius);
          background: var(--surface);
          padding: 40px 24px;
          cursor: pointer;
          transition: border-color .2s, background .2s, box-shadow .2s;
          position: relative;
          overflow: hidden;
        }
        .upload-zone::before {
          content: '';
          position: absolute;
          inset: 0;
          background: radial-gradient(ellipse at 50% 100%, var(--green-dim) 0%, transparent 70%);
          opacity: 0;
          transition: opacity .3s;
          pointer-events: none;
        }
        .upload-zone:not(.disabled):hover,
        .upload-zone.drag-over {
          border-color: var(--green);
          box-shadow: 0 0 24px var(--green-glow);
        }
        .upload-zone:not(.disabled):hover::before,
        .upload-zone.drag-over::before { opacity: 1; }
        .upload-zone.disabled { opacity: 0.6; cursor: not-allowed; }

        .upload-empty {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 10px;
        }
        .upload-icon-wrap {
          width: 64px; height: 64px;
          background: var(--green-dim);
          border-radius: 50%;
          display: flex; align-items: center; justify-content: center;
          border: 1px solid rgba(0,230,118,.2);
        }
        .upload-title {
          font-size: 16px;
          font-weight: 600;
          color: var(--text);
        }
        .upload-sub { color: var(--text-muted); font-size: 13px; }

        .upload-preview {
          display: flex;
          align-items: center;
          gap: 14px;
        }
        .upload-preview-icon {
          width: 48px; height: 48px;
          background: var(--green-dim);
          border-radius: var(--radius-sm);
          display: flex; align-items: center; justify-content: center;
          flex-shrink: 0;
        }
        .upload-preview-info {
          display: flex;
          flex-direction: column;
          gap: 2px;
          min-width: 0;
        }
        .upload-preview-name {
          font-weight: 600;
          color: var(--text);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          max-width: 320px;
        }
        .upload-preview-size { color: var(--text-muted); font-size: 12px; }
        .upload-clear {
          margin-left: auto;
          background: var(--surface-3);
          border: 1px solid var(--border);
          border-radius: 6px;
          padding: 6px;
          cursor: pointer;
          color: var(--text-muted);
          display: flex;
          align-items: center;
          transition: color .2s, background .2s;
          flex-shrink: 0;
        }
        .upload-clear:hover { color: var(--red); background: rgba(248,113,113,.1); }
      `}</style>
    </div>
  );
}
