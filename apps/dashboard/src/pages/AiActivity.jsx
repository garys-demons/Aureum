import { useEffect, useState } from 'react'
import { api } from '../api/client.js'

/**
 * Expected /api/ai-reasoning/activity response shape (backend not
 * built yet — same documented-but-pending pattern as every other page,
 * apps/api is still empty). The data itself already exists —
 * core/persistence/ai_reasoning_audit.py writes it via the existing
 * audit_log/record_decision() mechanism (Phase 7, Aryan) — what's
 * missing is the HTTP endpoint to serve it.
 *
 * [
 *   {
 *     "id": "uuid...",
 *     "event_type": "regime_classified" | "retrieval_match",
 *     "occurred_at": "2026-08-29T10:20:36Z",
 *     "payload": {
 *       // regime_classified:
 *       "symbol": "ADAUSDT", "regime": "high_volatility", "confidence": 0.75,
 *       "volatility": 0.0025, "rsi_value": 48.0, "reason": "..."
 *       // retrieval_match (once the retrieval mechanism is built):
 *       "symbol": "ADAUSDT", "query_description": "...",
 *       "matches": [...], "match_count": 2
 *     }
 *   },
 *   ...
 * ]
 *
 * Ordered most-recent-first (matches repository.get_recent()).
 *
 * THIS PAGE IS DELIBERATELY OBSERVATIONAL ONLY — Phase 7's load-bearing
 * rule is zero live influence. No button, form, or control here may
 * ever be wired to anything that could feed back into core/execution
 * or core/risk — this page only ever displays what the AI Research
 * Layer has already produced, nothing more.
 */

const REGIME_LABELS = {
  ranging: 'Ranging',
  trending: 'Trending',
  high_volatility: 'High Volatility',
  unknown: 'Unknown',
}

function RegimeBadge({ regime }) {
  const label = REGIME_LABELS[regime] ?? regime
  return <span className={`category-badge category-badge--regime-${regime}`}>{label}</span>
}

function CurrentRegimeBanner({ latest }) {
  if (!latest || latest.event_type !== 'regime_classified') return null
  const { symbol, regime, confidence, reason } = latest.payload

  return (
    <div className="anomaly">
      <strong>Current regime — {symbol}:</strong> <RegimeBadge regime={regime} />{' '}
      (confidence {(confidence * 100).toFixed(0)}%)
      <div className="page-subtitle" style={{ margin: '0.35rem 0 0' }}>{reason}</div>
    </div>
  )
}

function AiActivity() {
  const [activity, setActivity] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api
      .getAiActivity({ limit: 50 })
      .then((data) => setActivity(data.items ?? data))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <section>
      <h1>AI Activity</h1>
      <p className="page-subtitle">
        Observational view of the AI Research Layer (Phase 7) — market regime
        classifications and retrieval matches. Read-only by design: this page
        has no controls, and nothing here can influence a real trade.
      </p>

      {error && <p className="error">Failed to load: {error}</p>}
      {!error && loading && <p className="empty-note">Loading...</p>}

      {!error && !loading && (
        <>
          <CurrentRegimeBanner latest={activity[0]} />

          <h2 className="section-subtitle">Recent Activity</h2>
          {activity.length === 0 ? (
            <p className="empty-note">No AI reasoning activity recorded yet.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Symbol</th>
                  <th>Type</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {activity.map((a) => (
                  <tr key={a.id}>
                    <td>{a.occurred_at}</td>
                    <td>{a.payload?.symbol}</td>
                    <td>
                      {a.event_type === 'regime_classified' ? (
                        <RegimeBadge regime={a.payload?.regime} />
                      ) : (
                        <span className="category-badge">retrieval match</span>
                      )}
                    </td>
                    <td>
                      {a.event_type === 'regime_classified'
                        ? a.payload?.reason
                        : `${a.payload?.match_count ?? 0} similar condition(s) found`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </section>
  )
}

export default AiActivity