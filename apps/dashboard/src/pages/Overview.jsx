import { useEffect, useState } from 'react'
import { api } from '../api/client.js'

function Overview() {
  const [stats, setStats] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api
      .getOverviewStats()
      .then(setStats)
      .catch((err) => setError(err.message))
  }, [])

  return (
    <section>
      <h1>Overview</h1>
      {error && <p className="error">Failed to load: {error}</p>}
      {!stats && !error && <p>Loading...</p>}
      {stats && <pre>{JSON.stringify(stats, null, 2)}</pre>}
    </section>
  )
}

export default Overview