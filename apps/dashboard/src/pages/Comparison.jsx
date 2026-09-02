import { useEffect, useState } from 'react'
import { api } from '../api/client.js'
import EquityCurveChart from '../components/EquityCurveChart.jsx'

/**
 * Expected /api/comparison/windows response shape (backend not built
 * yet — same documented-but-pending pattern as every other page).
 * Mirrors research/backtest/run_multi_window_comparison.py's 3 pinned
 * windows (recent_24h, prior_24h, prior_48h — Hansika's reproducible
 * windows, see research/download_sensitivity_windows.py) and
 * research/evaluation/comparison_harness.py's EvaluationResult /
 * compare_results() shapes directly.
 *
 * {
 *   "windows": [
 *     {
 *       "window_label": "recent_24h",
 *       "baseline": {
 *         "run_name": "phase5_baseline", "strategy_name": "BaselineMarketMaker",
 *         "summary": { starting_cash, ending_cash, realized_pnl, unrealized_pnl,
 *                      final_equity, total_return_pct, num_trades, num_buys,
 *                      num_sells, num_closing_trades, win_rate_pct, max_drawdown_pct },
 *         "equity_curve": [{ "timestamp": "...", "equity": 10000.0 }, ...]
 *       },
 *       "candidate": { same shape, run_name: "phase8_baseline_plus_ai" },
 *       "deltas": {
 *         "total_return_pct_delta": ..., "win_rate_pct_delta": ...,
 *         "num_trades_delta": ..., "max_drawdown_pct_delta": ...,
 *         "final_equity_delta": ...
 *       }
 *     },
 *     { "window_label": "prior_24h", ... },
 *     { "window_label": "prior_48h", ... }
 *   ]
 * }
 *
 * Single-window comparisons aren't statistically meaningful on their
 * own (Phase 8 task doc, Hansika's rigor requirement) — this is why
 * all 3 windows are always shown together, not one at a time behind a
 * selector.
 *
 * Deliberately does NOT render any "AI wins" / "baseline wins" verdict
 * — compare_results() itself returns structured deltas only, no
 * winner. This page shows numbers side by side per window; it
 * doesn't declare a conclusion, that's Hansika's statistical work.
 */

function StatRow({ label, baselineValue, candidateValue, delta, formatFn = (v) => v }) {
  const deltaDisplay = delta === null || delta === undefined ? '—' : formatFn(delta)
  const deltaClass = delta > 0 ? 'delta-positive' : delta < 0 ? 'delta-negative' : ''

  return (
    <tr>
      <td>{label}</td>
      <td>{formatFn(baselineValue)}</td>
      <td>{formatFn(candidateValue)}</td>
      <td className={deltaClass}>{deltaDisplay}</td>
    </tr>
  )
}

function fmtPct(v) {
  return v === null || v === undefined ? '—' : `${v.toFixed(2)}%`
}
function fmtMoney(v) {
  return v === null || v === undefined ? '—' : `$${v.toFixed(2)}`
}
function fmtInt(v) {
  return v === null || v === undefined ? '—' : v
}

const WINDOW_LABELS = {
  recent_24h: 'Recent 24h',
  prior_24h: 'Prior 24h',
  prior_48h: 'Prior 48h',
}

function WindowComparison({ window }) {
  const { baseline, candidate, deltas } = window

  return (
    <section className="window-comparison">
      <h2 className="section-subtitle">
        {WINDOW_LABELS[window.window_label] ?? window.window_label}
      </h2>

      <table>
        <thead>
          <tr>
            <th>Metric</th>
            <th>{baseline?.run_name ?? 'Baseline'}</th>
            <th>{candidate?.run_name ?? 'Baseline + AI'}</th>
            <th>Delta</th>
          </tr>
        </thead>
        <tbody>
          <StatRow
            label="Total Return"
            baselineValue={baseline?.summary?.total_return_pct}
            candidateValue={candidate?.summary?.total_return_pct}
            delta={deltas?.total_return_pct_delta}
            formatFn={fmtPct}
          />
          <StatRow
            label="Win Rate"
            baselineValue={baseline?.summary?.win_rate_pct}
            candidateValue={candidate?.summary?.win_rate_pct}
            delta={deltas?.win_rate_pct_delta}
            formatFn={fmtPct}
          />
          <StatRow
            label="Max Drawdown"
            baselineValue={baseline?.summary?.max_drawdown_pct}
            candidateValue={candidate?.summary?.max_drawdown_pct}
            delta={deltas?.max_drawdown_pct_delta}
            formatFn={fmtPct}
          />
          <StatRow
            label="Trade Count"
            baselineValue={baseline?.summary?.num_trades}
            candidateValue={candidate?.summary?.num_trades}
            delta={deltas?.num_trades_delta}
            formatFn={fmtInt}
          />
          <StatRow
            label="Final Equity"
            baselineValue={baseline?.summary?.final_equity}
            candidateValue={candidate?.summary?.final_equity}
            delta={deltas?.final_equity_delta}
            formatFn={fmtMoney}
          />
        </tbody>
      </table>

      <EquityCurveChart
        series={[
          { name: baseline?.run_name ?? 'Baseline', points: baseline?.equity_curve, color: '#4caf87' },
          { name: candidate?.run_name ?? 'Baseline + AI', points: candidate?.equity_curve, color: '#7ab0ff' },
        ]}
      />
    </section>
  )
}

function Comparison() {
  const [windows, setWindows] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api
      .getComparisonWindows()
      .then((data) => setWindows(data.windows ?? data))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <section>
      <h1>Baseline vs. Baseline + AI</h1>
      <p className="page-subtitle">
        Phase 8 comparison across all 3 pinned windows (recent 24h, prior 24h,
        prior 48h) — structured deltas only, no verdict. A single window isn't
        statistically meaningful on its own, so all 3 are always shown together.
      </p>

      {error && <p className="error">Failed to load: {error}</p>}
      {!error && loading && <p className="empty-note">Loading...</p>}
      {!error && !loading && windows.length === 0 && (
        <p className="empty-note">No comparison data available yet.</p>
      )}

      {!error && !loading && windows.length > 0 && (
        <>
          {windows.map((w) => (
            <WindowComparison key={w.window_label} window={w} />
          ))}
        </>
      )}
    </section>
  )
}

export default Comparison