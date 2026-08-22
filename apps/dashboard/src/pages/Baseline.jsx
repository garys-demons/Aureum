import { useEffect, useState } from 'react'
import { api } from '../api/client.js'
import EquityCurveChart from '../components/EquityCurveChart.jsx'

/**
 * Expected /api/baseline-run response shape (not built yet — apps/api
 * is still empty, same blocker every other page in this dashboard has
 * hit, documented since Phase 4's DASHBOARD_SCOPE.md). Real data
 * already exists on disk (research/backtest/run_baseline_evaluation.py
 * persists it via research.storage under the fixed "phase5_baseline"
 * run name) — what's missing is the server-side bridge to expose it
 * over HTTP, not the data itself.
 *
 * {
 *   "run_name": "phase5_baseline",
 *   "is_baseline": true,
 *   "strategy_name": "BaselineMarketMaker",
 *   "summary": {
 *     "starting_cash": 10000.0, "ending_cash": ..., "realized_pnl": ...,
 *     "unrealized_pnl": ..., "final_equity": ..., "total_return_pct": ...,
 *     "num_trades": ..., "num_closing_trades": ..., "win_rate_pct": ...,
 *     "max_drawdown_pct": ...
 *   },
 *   "equity_curve": [
 *     { "timestamp": "...", "equity": 10000.0 },
 *     ...
 *   ]
 * }
 */

function StatCard({ label, value }) {
  return (
    <div className="stat-card">
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
    </div>
  )
}

function formatPct(value) {
  if (value === null || value === undefined) return '—'
  return `${value.toFixed(2)}%`
}

function formatMoney(value) {
  if (value === null || value === undefined) return '—'
  return `$${value.toFixed(2)}`
}

function Baseline() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api
      .getBaselineRun()
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <section>
      <h1>Baseline Performance</h1>
      <p className="page-subtitle">
        The Phase 5 reference run ("phase5_baseline") — the zero-AI benchmark
        Phase 8's AI comparison will measure against.
      </p>

      {error && <p className="error">Failed to load: {error}</p>}
      {!error && loading && <p className="empty-note">Loading...</p>}
      {!error && !loading && !data && (
        <p className="empty-note">No baseline run found yet.</p>
      )}

      {!error && !loading && data && (
        <>
          <div className="stat-grid">
            <StatCard label="Total Return" value={formatPct(data.summary?.total_return_pct)} />
            <StatCard label="Realized PnL" value={formatMoney(data.summary?.realized_pnl)} />
            <StatCard label="Win Rate" value={formatPct(data.summary?.win_rate_pct)} />
            <StatCard label="Max Drawdown" value={formatPct(data.summary?.max_drawdown_pct)} />
            <StatCard label="Total Trades" value={data.summary?.num_trades ?? '—'} />
            <StatCard label="Final Equity" value={formatMoney(data.summary?.final_equity)} />
          </div>

          <h2 className="section-subtitle">Equity Curve</h2>
          <EquityCurveChart points={data.equity_curve} />
        </>
      )}
    </section>
  )
}

export default Baseline