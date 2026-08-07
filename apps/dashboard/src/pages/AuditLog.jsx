import { useEffect, useState } from 'react'
import { api } from '../api/client.js'

function AuditLog() {
  const [entries, setEntries] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api
      .getAuditLog()
      .then((data) => setEntries(data.items ?? data))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <section>
      <h1>Audit Log</h1>
      {error && <p className="error">Failed to load: {error}</p>}
      {!error && loading && <p className="empty-note">Loading...</p>}
      {!error && !loading && entries.length === 0 && (
        <p className="empty-note">No data yet — waiting for the pipeline.</p>
      )}
      {!error && !loading && entries.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Occurred At</th>
              <th>Category</th>
              <th>Event Type</th>
              <th>Source</th>
              <th>Payload</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => (
              <tr key={entry.id}>
                {/* occurred_at, category, event_type, source, payload — the
                    actual columns on core/persistence/models.py's AuditLog,
                    not "timestamp"/"details" which don't exist on the real
                    model. */}
                <td>{entry.occurred_at}</td>
                <td>{entry.category}</td>
                <td>{entry.event_type}</td>
                <td>{entry.source}</td>
                <td>
                  <code>{JSON.stringify(entry.payload)}</code>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}

export default AuditLog