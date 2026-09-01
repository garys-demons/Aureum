import { useEffect, useState } from 'react'
import { api } from '../api/client.js'
import EquityCurveChart from '../components/EquityCurveChart.jsx'

/**
 * Expected /api/comparison response shape (backend not built yet —
 * same documented-but-pending pattern as every other page). Mirrors
 * research/evaluation/comparison_harness.py's EvaluationResult and
 * compare_results() shapes directly — this page is a visual window
 * onto exactly what that module already computes, not a separate
 * source of truth.
 *
 * {
 *   "baseline": {
 *     "run_name": "phase5_baseline", "strategy_name": "BaselineMarketMaker",
 *     "summary": { starting_cash, ending_cash, realized_pnl, unrealized_pnl,
 *                  final_equity, total_return_pct, num_trades, num_buys,
 *                  num_sells, num_closing_trades, win_rate_pct, max_drawdown_pct },
 *     "equity_curve": [{ "timestamp": "...", "equity": 10000.0 }, ...]
 *   },
 *   "candidate": { same shape, run_name: "phase8_baseline_plus_ai" },
 *   "deltas": {
 *     "total_return_pct_delta": ..., "win_rate_pct_delta": ...,
 *     "num_trades_delta": ..., "max_drawdown_pct_delta": ...,
 *     "final_equity_delta": ...
 *   }
 * }
 *
 * Deliberately does NOT render any "AI wins" / "baseline wins" verdict
 * — compare_results() itself returns structured deltas only, no
 * winner, per the Phase 7/8 task docs ("do NOT make any 'AI beats
 * baseline' claim in this phase - that determination belongs to
 * Phase 8['s statistical work]"). This page shows numbers side by
 * side; it doesn't declare a conclusion.
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

function Comparison() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api
      .getComparison()
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <section>
      <h1>Baseline vs. Baseline + AI</h1>
      <p className="page-subtitle">
        Phase 8 comparison — direct, side-by-side metrics for phase5_baseline and
        phase8_baseline_plus_ai. Structured deltas only; this page draws no
        conclusion about which is "better" — that determination is a separate,
        deliberate statistical judgment, not implied by these numbers alone.
      </p>

      {error && <p className="error">Failed to load: {error}</p>}
      {!error && loading && <p className="empty-note">Loading...</p>}
      {!error && !loading && !data && (
        <p className="empty-note">No comparison data available yet.</p>
      )}

      {!error && !loading && data && (
        <>
          <table>
            <thead>
              <tr>
                <th>Metric</th>
                <th>{data.baseline?.run_name ?? 'Baseline'}</th>
                <th>{data.candidate?.run_name ?? 'Baseline + AI'}</th>
                <th>Delta</th>
              </tr>
            </thead>
            <tbody>
              <StatRow
                label="Total Return"
                baselineValue={data.baseline?.summary?.total_return_pct}
                candidateValue={data.candidate?.summary?.total_return_pct}
                delta={data.deltas?.total_return_pct_delta}
                formatFn={fmtPct}
              />
              <StatRow
                label="Win Rate"
                baselineValue={data.baseline?.summary?.win_rate_pct}
                candidateValue={data.candidate?.summary?.win_rate_pct}
                delta={data.deltas?.win_rate_pct_delta}
                formatFn={fmtPct}
              />
              <StatRow
                label="Max Drawdown"
                baselineValue={data.baseline?.summary?.max_drawdown_pct}
                candidateValue={data.candidate?.summary?.max_drawdown_pct}
                delta={data.deltas?.max_drawdown_pct_delta}
                formatFn={fmtPct}
              />
              <StatRow
                label="Trade Count"
                baselineValue={data.baseline?.summary?.num_trades}
                candidateValue={data.candidate?.summary?.num_trades}
                delta={data.deltas?.num_trades_delta}
                formatFn={fmtInt}
              />
              <StatRow
                label="Final Equity"
                baselineValue={data.baseline?.summary?.final_equity}
                candidateValue={data.candidate?.summary?.final_equity}
                delta={data.deltas?.final_equity_delta}
                formatFn={fmtMoney}
              />
            </tbody>
          </table>

          <h2 className="section-subtitle">Equity Curves (overlaid)</h2>
          <EquityCurveChart
            series={[
              { name: data.baseline?.run_name ?? 'Baseline', points: data.baseline?.equity_curve, color: '#4caf87' },
              { name: data.candidate?.run_name ?? 'Baseline + AI', points: data.candidate?.equity_curve, color: '#7ab0ff' },
            ]}
          />
        </>
      )}
    </section>
  )
}

export default Comparison