import { useEffect, useRef, useState } from 'react';
import { AlertCircle, FileDown, ChevronRight, Gauge } from 'lucide-react';

import UploadZone from './components/UploadZone';
import ProgressBar from './components/ProgressBar';
import PlayerProfileForm from './components/PlayerProfileForm';
import PlayerSelector from './components/PlayerSelector';
import PlayerRating from './components/PlayerRating';
import PlayerStats from './components/PlayerStats';
import HeatmapPitch from './components/HeatmapPitch';

import type { AnalysisResult, AnalysisStage, PlayerProfile } from './types';

const API = 'http://127.0.0.1:8000';

export default function App() {
  const [file, setFile] = useState<File | null>(null);
  const [stage, setStage] = useState<AnalysisStage>('idle');
  const [playerProfile, setPlayerProfile] = useState<PlayerProfile | null>(null);
  const [progress, setProgress] = useState(0);
  const [backendStage, setBackendStage] = useState('starting');
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [frameSkip, setFrameSkip] = useState(10);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const pollTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = () => {
    if (pollTimer.current) { clearInterval(pollTimer.current); pollTimer.current = null; }
  };

  const handleFileSelected = (f: File) => {
    setFile(f);
    setStage('profiling');
    setResult(null);
    setError(null);
    setPlayerProfile(null);
  };

  const handleProfileSubmit = (profile: PlayerProfile) => {
    setPlayerProfile(profile);
    setStage('selecting');
  };

  const handleConfirm = async (clickX: number, clickY: number, previewId: string) => {
    if (!file) return;

    setStage('uploading');
    setProgress(0);
    setBackendStage('starting');

    const fd = new FormData();
    fd.append('preview_id', previewId);
    fd.append('frame_skip', String(frameSkip));
    fd.append('click_x', String(clickX));
    fd.append('click_y', String(clickY));
    if (playerProfile) {
      fd.append('jersey_color', playerProfile.jerseyColor);
      fd.append('player_name', playerProfile.name);
      fd.append('player_number', playerProfile.number);
      if (playerProfile.teamName) fd.append('team_name', playerProfile.teamName);
    }

    try {
      console.log('[stride] POST /analyze  preview=%s  click=(%.3f, %.3f)', previewId.slice(0, 8), clickX, clickY);
      const postRes = await fetch(`${API}/analyze`, { method: 'POST', body: fd });

      if (!postRes.ok) {
        const txt = await postRes.text();
        throw new Error(`Server error ${postRes.status}: ${txt}`);
      }

      const { job_id: jobId } = await postRes.json();
      console.log('[stride] job_id:', jobId);
      setStage('processing');

      await new Promise<void>((resolve, reject) => {
        let deadline: ReturnType<typeof setTimeout>;

        const done = (fn: () => void) => {
          clearInterval(timer);
          clearTimeout(deadline);
          pollTimer.current = null;
          fn();
        };

        const timer = setInterval(async () => {
          try {
            const res = await fetch(`${API}/progress/${jobId}`);
            if (!res.ok) return;
            const data = await res.json();
            const { pct, stage: s, result: r, error: e } = data;
            console.log('[poll]', jobId.slice(0, 8), pct + '%', s);

            setProgress(pct);
            setBackendStage(s);

            if (s === 'done' && r) {
              done(() => {
                setProgress(100);
                setBackendStage('done');
                setTimeout(() => { setResult(r); setStage('done'); }, 300);
                resolve();
              });
            } else if (s === 'error') {
              done(() => reject(new Error(e ?? 'Pipeline error')));
            }
          } catch { /* network hiccup — keep polling */ }
        }, 1000);

        deadline = setTimeout(
          () => done(() => reject(new Error('Timed out after 30 minutes.'))),
          30 * 60 * 1000,
        );

        pollTimer.current = timer;
      });

    } catch (e: unknown) {
      stopPolling();
      setStage('error');
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const handleDownloadPdf = async () => {
    if (!result) return;
    const payload = playerProfile
      ? { ...result, player_info: playerProfile }
      : result;
    const res = await fetch(`${API}/report`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) return alert('PDF generation failed');
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `stride_report_${result.run_id.slice(0, 8)}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const reset = () => {
    stopPolling();
    setFile(null);
    setStage('idle');
    setPlayerProfile(null);
    setProgress(0);
    setBackendStage('starting');
    setResult(null);
    setError(null);
    setShowAdvanced(false);
  };

  useEffect(() => () => stopPolling(), []);

  const player = result?.per_player_metrics?.[0] ?? null;
  const isActive = stage === 'uploading' || stage === 'processing';

  function _contrastHex(hex: string): string {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255 > 0.55 ? '#07090f' : '#ffffff';
  }

  return (
    <div className="app">
      {/* ── header ── */}
      <header className="app-header">
        <div className="header-inner">
          <div className="logo">
            <div className="logo-icon">
              <Gauge size={18} color="var(--green)" strokeWidth={2} />
            </div>
            <div>
              <span className="logo-title">Stride</span>
              <span className="logo-sub">Personal performance tracker</span>
            </div>
          </div>
          <div className="header-badges">
            <span className="badge badge-green">Live</span>
            <span className="badge">YOLOv8</span>
          </div>
        </div>
      </header>

      {/* ── main ── */}
      <main className="app-main">

        {/* upload / select card */}
        {stage !== 'done' && (
          <section className="card upload-card">
            <div className="card-title-row">
              <h2 className="card-title">
                {{
                  idle: 'Upload your clip',
                  profiling: 'Your player details',
                  selecting: 'Select yourself in the frame',
                  uploading: 'Analysing…',
                  processing: 'Analysing…',
                  error: 'Something went wrong',
                  done: '',
                }[stage]}
              </h2>
            </div>

            {(stage === 'idle' || stage === 'profiling' || stage === 'selecting') && (
              <UploadZone
                onFile={handleFileSelected}
                disabled={isActive}
              />
            )}

            {stage === 'profiling' && (
              <PlayerProfileForm onSubmit={handleProfileSubmit} />
            )}

            {stage === 'selecting' && file && (
              <PlayerSelector file={file} onConfirm={handleConfirm} />
            )}

            {(stage === 'idle' || stage === 'profiling' || stage === 'selecting') && (
              <div className="advanced-row">
                <button
                  className="advanced-toggle"
                  onClick={() => setShowAdvanced((v) => !v)}
                >
                  {showAdvanced ? '▾' : '▸'} Advanced
                </button>
                {showAdvanced && (
                  <div className="slider-row">
                    <div className="slider-labels">
                      <span className="slider-label">Frame Skip</span>
                      <span className="slider-badges">
                        <span className="slider-value">{frameSkip}</span>
                        <span className={`slider-tag ${frameSkip === 1 ? 'tag-quality' : frameSkip <= 3 ? 'tag-balanced' : 'tag-fast'}`}>
                          {frameSkip === 1 ? 'Full quality' : frameSkip <= 3 ? 'Balanced' : 'Fast'}
                        </span>
                      </span>
                    </div>
                    <input
                      type="range" min={1} max={10} value={frameSkip}
                      onChange={(e) => setFrameSkip(Number(e.target.value))}
                      className="frame-slider"
                      style={{ '--v': frameSkip } as React.CSSProperties}
                    />
                    <div className="slider-ticks">
                      <span>1× (every frame)</span>
                      <span>10×</span>
                    </div>
                  </div>
                )}
              </div>
            )}
          </section>
        )}

        {/* progress */}
        {isActive && (
          <ProgressBar progress={progress} stage={backendStage} />
        )}

        {/* error */}
        {stage === 'error' && error && (
          <div className="error-card">
            <AlertCircle size={18} color="var(--red)" />
            <div>
              <p className="error-title">Analysis failed</p>
              <p className="error-msg">{error}</p>
            </div>
            <button className="btn-ghost" onClick={reset}>Try again</button>
          </div>
        )}

        {/* results */}
        {result && player && stage === 'done' && (
          <div className="results-enter">
            <div className="run-meta">
              <div className="run-info">
                {playerProfile && (
                  <div className="player-badge">
                    <div
                      className="player-badge-num"
                      style={{ background: playerProfile.jerseyColor, color: _contrastHex(playerProfile.jerseyColor) }}
                    >
                      {playerProfile.number}
                    </div>
                    <div className="player-badge-text">
                      <span className="player-badge-name">{playerProfile.name}</span>
                      {playerProfile.teamName && (
                        <span className="player-badge-team">{playerProfile.teamName}</span>
                      )}
                    </div>
                  </div>
                )}
                <div className="run-tags">
                  <span className="badge">{result.frames_processed} frames</span>
                  <span className="badge">{result.fps.toFixed(0)} fps</span>
                  {result.pitch?.ready && <span className="badge badge-green">Pitch calibrated</span>}
                </div>
              </div>
              <div className="run-actions">
                <button className="btn-outline" onClick={handleDownloadPdf}>
                  <FileDown size={14} />
                  Export PDF
                </button>
                <button className="btn-ghost" onClick={reset}>
                  New clip <ChevronRight size={14} />
                </button>
              </div>
            </div>

            {result.rating && (
              <PlayerRating
                rating={result.rating}
                playerName={playerProfile?.name}
              />
            )}

            <PlayerStats stats={player} fps={result.fps} />

            <HeatmapPitch
              points={result.heatmap_points}
              pitchLength={result.pitch?.pitch_length_m}
              pitchWidth={result.pitch?.pitch_width_m}
            />

            {result.errors?.length > 0 && (
              <details className="error-details">
                <summary>Pipeline warnings ({result.errors.length})</summary>
                <ul>{result.errors.map((e, i) => <li key={i}>{e}</li>)}</ul>
              </details>
            )}
          </div>
        )}

        {result && !player && stage === 'done' && (
          <div className="error-card">
            <AlertCircle size={18} color="var(--amber)" />
            <div>
              <p className="error-title">No player tracked</p>
              <p className="error-msg">
                The selected position didn't match any detected player.
                Try a different frame position or a shorter clip with clearer footage.
              </p>
            </div>
            <button className="btn-ghost" onClick={reset}>Try again</button>
          </div>
        )}
      </main>

      <style>{`
        .app { min-height: 100vh; display: flex; flex-direction: column; background: var(--bg); }

        .app-header {
          background: var(--surface);
          border-bottom: 1px solid var(--border);
          position: sticky; top: 0; z-index: 100;
          backdrop-filter: blur(12px);
        }
        .header-inner {
          max-width: 900px; margin: 0 auto; padding: 0 24px;
          height: 60px; display: flex; align-items: center; justify-content: space-between;
        }
        .logo { display: flex; align-items: center; gap: 12px; }
        .logo-icon {
          width: 36px; height: 36px;
          background: var(--green-dim);
          border: 1px solid rgba(0,230,118,.2);
          border-radius: 10px;
          display: flex; align-items: center; justify-content: center;
        }
        .logo-title {
          display: block; font-size: 17px; font-weight: 800;
          color: var(--text); letter-spacing: -.01em;
        }
        .logo-sub {
          font-size: 10px; font-weight: 500;
          text-transform: uppercase; letter-spacing: .08em;
          color: var(--text-muted);
        }
        .header-badges { display: flex; gap: 6px; }

        .badge {
          font-size: 10px; font-weight: 700;
          text-transform: uppercase; letter-spacing: .06em;
          padding: 3px 8px; border-radius: 4px;
          background: var(--surface-3); border: 1px solid var(--border);
          color: var(--text-muted);
        }
        .badge-green {
          background: var(--green-dim); border-color: rgba(0,230,118,.25); color: var(--green);
        }

        .app-main {
          max-width: 900px; width: 100%; margin: 0 auto;
          padding: 32px 24px 64px;
          display: flex; flex-direction: column; gap: 20px;
        }

        .card {
          background: var(--surface); border: 1px solid var(--border);
          border-radius: var(--radius); padding: 24px;
          display: flex; flex-direction: column; gap: 16px;
        }
        .card-title-row { display: flex; justify-content: space-between; align-items: center; }
        .card-title { font-size: 16px; font-weight: 700; color: var(--text); }

        .section-title { font-size: 13px; font-weight: 700; color: var(--text); }

        .btn-outline {
          display: flex; align-items: center; gap: 6px;
          background: transparent; color: var(--text-dim);
          border: 1px solid var(--border); border-radius: var(--radius-sm);
          padding: 7px 14px; font-size: 12px; font-weight: 600;
          cursor: pointer; transition: border-color .2s, color .2s, background .2s;
          white-space: nowrap;
        }
        .btn-outline:hover { border-color: var(--green); color: var(--green); background: var(--green-dim); }

        .btn-ghost {
          display: flex; align-items: center; gap: 4px;
          background: none; border: none; color: var(--text-muted);
          font-size: 12px; font-weight: 600; cursor: pointer;
          transition: color .2s; padding: 4px 0;
        }
        .btn-ghost:hover { color: var(--text); }

        .error-card {
          display: flex; align-items: flex-start; gap: 14px;
          background: rgba(248,113,113,.06); border: 1px solid rgba(248,113,113,.25);
          border-radius: var(--radius); padding: 18px 20px;
        }
        .error-title { font-weight: 700; color: var(--red); font-size: 14px; }
        .error-msg { font-size: 12px; color: var(--text-muted); margin-top: 3px; word-break: break-all; }
        .error-card .btn-ghost { margin-left: auto; flex-shrink: 0; }

        .results-enter {
          display: flex; flex-direction: column; gap: 20px;
          animation: fadeUp .4s ease;
        }
        @keyframes fadeUp {
          from { opacity: 0; transform: translateY(12px); }
          to   { opacity: 1; transform: translateY(0); }
        }

        .run-meta {
          display: flex; align-items: center; justify-content: space-between;
          flex-wrap: wrap; gap: 12px;
        }
        .run-info { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
        .run-label { font-size: 12px; color: var(--text-muted); }
        .run-label code {
          font-family: var(--mono, monospace); color: var(--text-dim);
          background: var(--surface-2); padding: 2px 6px;
          border-radius: 4px; font-size: 11px;
        }
        .run-tags { display: flex; gap: 6px; flex-wrap: wrap; }
        .run-actions { display: flex; align-items: center; gap: 10px; }

        /* advanced toggle */
        .advanced-row { display: flex; flex-direction: column; gap: 8px; }
        .advanced-toggle {
          background: none; border: none; color: var(--text-muted);
          font-size: 11px; font-weight: 600; cursor: pointer;
          text-transform: uppercase; letter-spacing: .06em;
          padding: 0; align-self: flex-start;
          transition: color .15s;
        }
        .advanced-toggle:hover { color: var(--text); }

        .slider-row {
          display: flex; flex-direction: column; gap: 8px;
          padding: 14px 16px; background: var(--surface-2);
          border: 1px solid var(--border); border-radius: var(--radius-sm);
        }
        .slider-labels { display: flex; justify-content: space-between; align-items: center; }
        .slider-label {
          font-size: 11px; font-weight: 700;
          text-transform: uppercase; letter-spacing: .06em; color: var(--text-muted);
        }
        .slider-badges { display: flex; align-items: center; gap: 8px; }
        .slider-value {
          font-size: 16px; font-weight: 800;
          font-variant-numeric: tabular-nums; color: var(--text);
        }
        .slider-tag {
          font-size: 10px; font-weight: 700;
          text-transform: uppercase; letter-spacing: .06em;
          padding: 2px 8px; border-radius: 4px; border: 1px solid;
        }
        .tag-quality  { color: var(--blue);  background: var(--blue-dim);  border-color: rgba(56,189,248,.25); }
        .tag-balanced { color: var(--green); background: var(--green-dim); border-color: rgba(0,230,118,.25); }
        .tag-fast     { color: var(--amber); background: var(--amber-dim); border-color: rgba(251,191,36,.25); }
        .frame-slider {
          -webkit-appearance: none; appearance: none;
          width: 100%; height: 5px; border-radius: 3px;
          background: linear-gradient(
            to right,
            var(--green) 0%,
            var(--green) calc((var(--v, 3) - 1) / 9 * 100%),
            var(--surface-3) calc((var(--v, 3) - 1) / 9 * 100%)
          );
          outline: none; cursor: pointer;
        }
        .frame-slider::-webkit-slider-thumb {
          -webkit-appearance: none;
          width: 18px; height: 18px; border-radius: 50%;
          background: var(--green); box-shadow: 0 0 8px var(--green-glow);
          border: 2px solid var(--bg); cursor: pointer;
        }
        .frame-slider::-moz-range-thumb {
          width: 18px; height: 18px; border-radius: 50%;
          background: var(--green); box-shadow: 0 0 8px var(--green-glow);
          border: 2px solid var(--bg); cursor: pointer;
        }
        .slider-ticks {
          display: flex; justify-content: space-between;
          font-size: 10px; color: var(--text-muted);
        }

        .error-details {
          background: var(--surface); border: 1px solid var(--border);
          border-radius: var(--radius); padding: 14px 18px;
          font-size: 12px; color: var(--text-muted);
        }
        .error-details summary { cursor: pointer; font-weight: 600; color: var(--amber); }
        .error-details ul {
          margin-top: 10px; padding-left: 20px;
          display: flex; flex-direction: column; gap: 4px;
        }

        /* player badge in results header */
        .player-badge {
          display: flex; align-items: center; gap: 10px;
        }
        .player-badge-num {
          width: 38px; height: 38px; border-radius: 9px;
          display: flex; align-items: center; justify-content: center;
          font-size: 15px; font-weight: 900; flex-shrink: 0;
          border: 2px solid rgba(255,255,255,.14);
          box-shadow: 0 2px 10px rgba(0,0,0,.4);
        }
        .player-badge-text { display: flex; flex-direction: column; gap: 1px; }
        .player-badge-name { font-size: 14px; font-weight: 700; color: var(--text); }
        .player-badge-team { font-size: 11px; color: var(--text-muted); }
      `}</style>
    </div>
  );
}
