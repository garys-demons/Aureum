import { useEffect, useState } from 'react'
import { api } from '../api/client.js'

function Anomalies() {
  const [anomalies, setAnomalies] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api
      .getAnomalies()
      .then((data) => setAnomalies(data.items ?? data))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <section>
      <h1>Anomalies</h1>
      {error && <p className="error">Failed to load: {error}</p>}
      {!error && loading && <p className="empty-note">Loading...</p>}
      {!error && !loading && anomalies.length === 0 && (
        <p className="empty-note">No anomalies detected.</p>
      )}
      {!error && !loading && anomalies.length > 0 && (
        <ul className="anomaly-list">
          {anomalies.map((a) => (
            /* No severity field exists on the real AuditLog model yet —
               using a flat style for now. If severity gets added later
               (e.g. a new column, or inferred from event_type), swap
               "anomaly--info" back to the dynamic version:
               `anomaly anomaly--${a.severity ?? 'info'}` */
            <li key={a.id} className="anomaly anomaly--info">
              <strong>{a.event_type}</strong> — <code>{JSON.stringify(a.payload)}</code>
              <span className="anomaly-time">{a.occurred_at}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export default Anomalies