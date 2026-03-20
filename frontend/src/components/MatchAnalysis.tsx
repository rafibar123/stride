import type { MatchAnalysis as Analysis, TrainingDrill } from '../types';

interface Props {
  analysis: Analysis;
}

function DrillCard({ drill, index }: { drill: TrainingDrill; index: number }) {
  const accent = ['#00e676', '#38bdf8', '#fbbf24'][index] ?? '#00e676';
  return (
    <div className="ma-drill" style={{ '--drill-accent': accent } as React.CSSProperties}>
      <div className="ma-drill-num" style={{ color: accent }}>{index + 1}</div>
      <div className="ma-drill-body">
        <span className="ma-drill-name">{drill.drill}</span>
        <div className="ma-drill-meta">
          <span className="ma-drill-duration">⏱ {drill.duration}</span>
          <span className="ma-drill-focus">{drill.focus}</span>
        </div>
      </div>
    </div>
  );
}

export default function MatchAnalysis({ analysis }: Props) {
  const { actions, summary, recommendations, ai_generated } = analysis;
  const { positive_count, negative_count } = actions;

  return (
    <div className="ma-wrap">

      {/* ── Header ── */}
      <div className="ma-header">
        <span className="section-title">Match Analysis</span>
        <span className={`ma-source-badge ${ai_generated ? 'ma-badge-ai' : 'ma-badge-rule'}`}>
          {ai_generated ? '✦ AI Generated' : '⚙ Auto Analysis'}
        </span>
      </div>

      {/* ── Action counters ── */}
      <div className="ma-actions">
        <div className="ma-action-card ma-pos">
          <span className="ma-action-icon">✅</span>
          <div className="ma-action-body">
            <span className="ma-action-count">{positive_count}</span>
            <span className="ma-action-label">Positive actions</span>
          </div>
          <div className="ma-action-items">
            {actions.positive_items.slice(0, 6).map((it, i) => (
              <span key={i} className="ma-action-tag ma-tag-pos">{it.label}</span>
            ))}
            {actions.positive_items.length > 6 && (
              <span className="ma-action-tag ma-tag-pos">+{actions.positive_items.length - 6} more</span>
            )}
          </div>
        </div>

        <div className="ma-action-card ma-neg">
          <span className="ma-action-icon">❌</span>
          <div className="ma-action-body">
            <span className="ma-action-count">{negative_count}</span>
            <span className="ma-action-label">Negative actions</span>
          </div>
          <div className="ma-action-items">
            {actions.negative_items.slice(0, 6).map((it, i) => (
              <span key={i} className="ma-action-tag ma-tag-neg">{it.label}</span>
            ))}
            {actions.negative_items.length > 6 && (
              <span className="ma-action-tag ma-tag-neg">+{actions.negative_items.length - 6} more</span>
            )}
          </div>
        </div>
      </div>

      {/* ── Match summary ── */}
      <div className="ma-section">
        <span className="ma-section-label">Match Summary</span>
        <div className="ma-summary">
          {summary.map((sentence, i) => (
            <div key={i} className="ma-sentence">
              <span className="ma-sentence-num">{i + 1}</span>
              <p className="ma-sentence-text">{sentence}</p>
            </div>
          ))}
        </div>
      </div>

      {/* ── Training recommendations ── */}
      <div className="ma-section">
        <span className="ma-section-label">Training Recommendations</span>
        <div className="ma-drills">
          {recommendations.map((drill, i) => (
            <DrillCard key={i} drill={drill} index={i} />
          ))}
        </div>
      </div>

      <style>{`
        .ma-wrap {
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: var(--radius);
          overflow: hidden;
          display: flex;
          flex-direction: column;
        }

        .ma-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 14px 20px;
          border-bottom: 1px solid var(--border);
        }

        .ma-source-badge {
          font-size: 10px; font-weight: 700;
          text-transform: uppercase; letter-spacing: .07em;
          padding: 3px 10px; border-radius: 20px; border: 1px solid;
        }
        .ma-badge-ai {
          color: var(--green); background: var(--green-dim);
          border-color: rgba(0,230,118,.25);
        }
        .ma-badge-rule {
          color: var(--text-muted); background: var(--surface-2);
          border-color: var(--border);
        }

        /* ── Action counters ── */
        .ma-actions {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 12px;
          padding: 16px 20px;
          border-bottom: 1px solid var(--border);
        }
        @media (max-width: 540px) {
          .ma-actions { grid-template-columns: 1fr; }
        }

        .ma-action-card {
          border-radius: 10px;
          border: 1px solid;
          padding: 14px 16px;
          display: flex;
          flex-direction: column;
          gap: 8px;
        }
        .ma-pos {
          background: rgba(0,230,118,.05);
          border-color: rgba(0,230,118,.2);
        }
        .ma-neg {
          background: rgba(248,113,113,.05);
          border-color: rgba(248,113,113,.2);
        }

        .ma-action-icon { font-size: 18px; }
        .ma-action-body {
          display: flex; align-items: baseline; gap: 8px;
        }
        .ma-action-count {
          font-size: 40px; font-weight: 900;
          font-variant-numeric: tabular-nums;
          line-height: 1;
        }
        .ma-pos .ma-action-count { color: var(--green); }
        .ma-neg .ma-action-count { color: #f87171; }
        .ma-action-label {
          font-size: 11px; color: var(--text-muted);
          text-transform: uppercase; letter-spacing: .06em;
        }

        .ma-action-items {
          display: flex; flex-wrap: wrap; gap: 5px;
        }
        .ma-action-tag {
          font-size: 10px; font-weight: 600;
          padding: 2px 8px; border-radius: 4px;
        }
        .ma-tag-pos {
          background: rgba(0,230,118,.12);
          color: rgba(0,230,118,.85);
        }
        .ma-tag-neg {
          background: rgba(248,113,113,.12);
          color: rgba(248,113,113,.85);
        }

        /* ── Sections ── */
        .ma-section {
          padding: 16px 20px;
          border-bottom: 1px solid var(--border);
          display: flex;
          flex-direction: column;
          gap: 12px;
        }
        .ma-section:last-child { border-bottom: none; }
        .ma-section-label {
          font-size: 11px; font-weight: 700;
          text-transform: uppercase; letter-spacing: .08em;
          color: var(--text-muted);
        }

        /* ── Summary sentences ── */
        .ma-summary { display: flex; flex-direction: column; gap: 10px; }
        .ma-sentence {
          display: flex; align-items: flex-start; gap: 12px;
        }
        .ma-sentence-num {
          width: 22px; height: 22px;
          background: var(--surface-2); border: 1px solid var(--border);
          border-radius: 50%;
          display: flex; align-items: center; justify-content: center;
          font-size: 11px; font-weight: 700; color: var(--green);
          flex-shrink: 0; margin-top: 1px;
        }
        .ma-sentence-text {
          font-size: 13px; line-height: 1.6;
          color: var(--text-dim); margin: 0;
        }

        /* ── Training drills ── */
        .ma-drills { display: flex; flex-direction: column; gap: 10px; }
        .ma-drill {
          display: flex; align-items: flex-start; gap: 14px;
          background: var(--surface-2);
          border: 1px solid var(--border);
          border-left: 3px solid var(--drill-accent, #00e676);
          border-radius: 8px;
          padding: 12px 14px;
          transition: border-color .2s;
        }
        .ma-drill-num {
          font-size: 22px; font-weight: 900;
          font-variant-numeric: tabular-nums;
          line-height: 1; flex-shrink: 0; margin-top: 1px;
          text-shadow: 0 0 12px currentColor;
        }
        .ma-drill-body {
          display: flex; flex-direction: column; gap: 4px; flex: 1;
        }
        .ma-drill-name {
          font-size: 13px; font-weight: 700; color: var(--text);
        }
        .ma-drill-meta {
          display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
        }
        .ma-drill-duration {
          font-size: 11px; color: var(--text-muted); font-weight: 600;
        }
        .ma-drill-focus {
          font-size: 11px; color: var(--text-muted);
          border-left: 1px solid var(--border);
          padding-left: 10px;
        }
      `}</style>
    </div>
  );
}
