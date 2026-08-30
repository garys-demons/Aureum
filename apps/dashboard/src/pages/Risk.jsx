import { useEffect, useState } from 'react'
import { api } from '../api/client.js'

/**
 * Expected /api/risk/decisions response shape (backend not built yet —
 * same documented-but-pending pattern as Baseline.jsx/getBaselineRun,
 * apps/api is still empty for every page). The data itself already
 * exists — core/persistence/risk_audit.py writes it via the existing
 * audit_log/record_decision() mechanism (Phase 6, Aryan) — what's
 * missing is the HTTP endpoint to serve it.
 *
 * [
 *   {
 *     "id": "uuid...",
 *     "event_type": "risk_allowed" | "risk_rejected" | "kill_switch_triggered",
 *     "occurred_at": "2026-08-27T10:20:36Z",
 *     "payload": {
 *       "action": "buy", "symbol": "BTCUSDT", "quantity": 10,
 *       "current_inventory": 0, "allowed": true,
 *       "kill_switch": { "active": false, "category": null,
 *                         "reason": null, "triggered_at": null }
 *     }
 *   },
 *   ...
 * ]
 *
 * Ordered most-recent-first (matches repository.get_recent()).
 */

function KillSwitchBanner({ status }) {
  if (!status) return null

  if (status.active) {
    return (
      <div className="anomaly anomaly--critical">
        <strong>Kill switch ACTIVE</strong> — {status.category}: {status.reason}
        <span className="anomaly-time">Triggered at {status.triggered_at}</span>
      </div>
    )
  }

  return (
    <div className="anomaly">
      <strong>Kill switch inactive</strong> — trading allowed
    </div>
  )
}

function Risk() {
  const [decisions, setDecisions] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api
      .getRiskDecisions({ limit: 50 })
      .then((data) => setDecisions(data.items ?? data))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  // Current kill-switch state is derived from the most recent decision's
  // embedded snapshot — there's no separate "live status" endpoint, since
  // every persisted decision already carries a full kill_switch snapshot
  // at the moment it was made.
  const currentKillSwitchStatus = decisions[0]?.payload?.kill_switch ?? null

  return (
    <section>
      <h1>Risk</h1>
      <p className="page-subtitle">
        Current kill-switch state and the most recent risk decisions made by
        the risk engine (Phase 6) — every allow, reject, and trigger is
        recorded here via the audit trail.
      </p>

      {error && <p className="error">Failed to load: {error}</p>}
      {!error && loading && <p className="empty-note">Loading...</p>}

      {!error && !loading && (
        <>
          <KillSwitchBanner status={currentKillSwitchStatus} />

          <h2 className="section-subtitle">Recent Decisions</h2>
          {decisions.length === 0 ? (
            <p className="empty-note">No risk decisions recorded yet.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Symbol</th>
                  <th>Action</th>
                  <th>Quantity</th>
                  <th>Result</th>
                </tr>
              </thead>
              <tbody>
                {decisions.map((d) => (
                  <tr key={d.id}>
                    <td>{d.occurred_at}</td>
                    <td>{d.payload?.symbol}</td>
                    <td>{d.payload?.action}</td>
                    <td>{d.payload?.quantity}</td>
                    <td>{d.event_type}</td>
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

export default Risk