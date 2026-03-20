import { useEffect, useState } from 'react';
import type { AnalysisResult, PlayerProfile, StoredMatch } from '../types';

interface Props {
  result: AnalysisResult;
  playerProfile: PlayerProfile | null;
}

const STORAGE_KEY = 'stride_match_history';
const MAX_STORED  = 20;

function loadHistory(): StoredMatch[] {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '[]');
  } catch {
    return [];
  }
}

function saveMatch(match: StoredMatch, history: StoredMatch[]): StoredMatch[] {
  // avoid duplicates by run_id
  const filtered = history.filter((m) => m.run_id !== match.run_id);
  const updated  = [match, ...filtered].slice(0, MAX_STORED);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
  return updated;
}

function pctChange(curr: number, prev: number): number {
  if (prev === 0) return 0;
  return Math.round(((curr - prev) / prev) * 100);
}

function TrendArrow({ delta }: { delta: number }) {
  if (Math.abs(delta) < 3) {
    return <span style={{ color: 'var(--text-muted)' }}>→ stable</span>;
  }
  const up    = delta > 0;
  const color = up ? 'var(--green)' : '#f87171';
  return (
    <span style={{ color }}>
      {up ? '↑' : '↓'} {Math.abs(delta)}%
    </span>
  );
}

interface CompRow { label: string; curr: string; delta: number; unit: string; }

export default function MatchHistory({ result, playerProfile }: Props) {
  const [prev, setPrev] = useState<StoredMatch | null>(null);

  const player   = result.per_player_metrics?.[0];
  const passStats = result.pass_stats;

  useEffect(() => {
    const history = loadHistory();
    // find last different run
    const lastDiff = history.find((m) => m.run_id !== result.run_id) ?? null;
    setPrev(lastDiff);

    const curr: StoredMatch = {
      run_id:           result.run_id,
      timestamp:        Date.now(),
      player_name:      playerProfile?.name,
      distance_m:       player?.distance_m ?? 0,
      sprint_count:     player?.sprint_count ?? 0,
      avg_speed_kmh:    (player?.avg_speed_mps ?? 0) * 3.6,
      max_speed_kmh:    (player?.max_speed_mps ?? 0) * 3.6,
      pass_accuracy_pct: passStats?.accuracy_pct,
      overall_rating:   result.rating?.overall,
    };
    saveMatch(curr, history);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result.run_id]);

  if (!prev || !player) return null;

  const currDist  = player.distance_m;
  const currSprint = player.sprint_count;
  const currSpeed  = (player.avg_speed_mps ?? 0) * 3.6;
  const currRating = result.rating?.overall ?? 0;

  const rows: CompRow[] = [
    {
      label: 'Distance',
      curr:  `${(currDist / 1000).toFixed(2)} km`,
      delta: pctChange(currDist, prev.distance_m),
      unit:  'km',
    },
    {
      label:  'Sprints',
      curr:   String(currSprint),
      delta:  pctChange(currSprint, prev.sprint_count),
      unit:   '',
    },
    {
      label: 'Avg Speed',
      curr:  `${currSpeed.toFixed(1)} km/h`,
      delta: pctChange(currSpeed, prev.avg_speed_kmh),
      unit:  'km/h',
    },
    ...(currRating > 0 && prev.overall_rating
      ? [{
          label: 'Rating',
          curr:  `${currRating.toFixed(1)}/10`,
          delta: pctChange(currRating, prev.overall_rating),
          unit:  '/10',
        }]
      : []),
  ];

  const prevDate = new Date(prev.timestamp).toLocaleDateString('en-GB', {
    day: 'numeric', month: 'short',
  });

  const improving = rows.filter((r) => r.delta > 3).length;
  const declining = rows.filter((r) => r.delta < -3).length;

  return (
    <div className="mh-wrap">
      <div className="mh-header">
        <span className="section-title">vs Last Match</span>
        <span className="mh-date">
          {prev.player_name ? `${prev.player_name} · ` : ''}
          {prevDate}
        </span>
      </div>

      <div className="mh-trend-summary">
        {improving > declining ? (
          <p className="mh-trend mh-trend-up">
            📈 You improved in {improving} out of {rows.length} metrics compared to last time — keep it up!
          </p>
        ) : declining > improving ? (
          <p className="mh-trend mh-trend-down">
            📉 Performance dipped in {declining} areas — review training focus for next session.
          </p>
        ) : (
          <p className="mh-trend mh-trend-flat">
            📊 Consistent performance compared to last match — stable form.
          </p>
        )}
      </div>

      <div className="mh-rows">
        {rows.map((row) => (
          <div key={row.label} className="mh-row">
            <span className="mh-label">{row.label}</span>
            <span className="mh-curr">{row.curr}</span>
            <span className="mh-delta">
              <TrendArrow delta={row.delta} />
            </span>
          </div>
        ))}
      </div>

      <style>{`
        .mh-wrap {
          background: var(--surface); border: 1px solid var(--border);
          border-radius: var(--radius); overflow: hidden;
        }
        .mh-header {
          display: flex; justify-content: space-between; align-items: center;
          padding: 14px 20px; border-bottom: 1px solid var(--border);
        }
        .mh-date { font-size: 11px; color: var(--text-muted); font-weight: 600; }

        .mh-trend-summary { padding: 12px 20px; border-bottom: 1px solid var(--border); }
        .mh-trend {
          margin: 0; font-size: 12px; line-height: 1.5; padding: 8px 12px;
          border-radius: 8px; border: 1px solid;
        }
        .mh-trend-up   { background: rgba(0,230,118,.06); border-color: rgba(0,230,118,.2); color: var(--green); }
        .mh-trend-down { background: rgba(248,113,113,.06); border-color: rgba(248,113,113,.2); color: #f87171; }
        .mh-trend-flat { background: var(--surface-2); border-color: var(--border); color: var(--text-dim); }

        .mh-rows { display: flex; flex-direction: column; }
        .mh-row {
          display: grid; grid-template-columns: 1fr auto auto;
          gap: 16px; align-items: center;
          padding: 12px 20px; border-bottom: 1px solid var(--border);
        }
        .mh-row:last-child { border-bottom: none; }
        .mh-label  { font-size: 12px; color: var(--text-muted); font-weight: 600; }
        .mh-curr   { font-size: 13px; font-weight: 800; color: var(--text); font-variant-numeric: tabular-nums; }
        .mh-delta  { font-size: 12px; font-weight: 700; font-variant-numeric: tabular-nums; text-align: right; min-width: 70px; }
      `}</style>
    </div>
  );
}
