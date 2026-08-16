import { useEffect, useState } from 'react'
import { api } from '../api/client.js'

/**
 * Expected /api/datasets response shape (not built yet — apps/api is
 * still empty, same as every other page in this dashboard). Documented
 * here so whoever builds the API endpoint has a concrete target,
 * matching the pattern the other pages already use.
 *
 * Mirrors research/storage.py's manifest shape directly — this page is
 * just a visual window onto what save_dataset() has already recorded,
 * not a separate source of truth.
 *
 * {
 *   "datasets": [
 *     {
 *       "name": "btcusdt_candles_1m",
 *       "category": "raw",              // "raw" or "processed"
 *       "latest_version": 3,
 *       "row_count": 43200,
 *       "source": "hansika/historical_downloader",
 *       "created_at": "...",
 *       "metadata": { "start": "...", "end": "...", "gaps": [] }
 *     },
 *     ...
 *   ]
 * }
 */

function CategoryBadge({ category }) {
  return <span className={`category-badge category-badge--${category}`}>{category}</span>
}

function Datasets() {
  const [datasets, setDatasets] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api
      .getDatasets()
      .then((data) => setDatasets(data.datasets ?? data))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <section>
      <h1>Datasets</h1>
      <p className="page-subtitle">
        Historical data and computed features from the research environment
        (research/storage.py) — raw downloads and processed features, versioned.
      </p>

      {error && <p className="error">Failed to load: {error}</p>}
      {!error && loading && <p className="empty-note">Loading...</p>}
      {!error && !loading && (!datasets || datasets.length === 0) && (
        <p className="empty-note">No datasets saved yet.</p>
      )}

      {!error && !loading && datasets && datasets.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Category</th>
              <th>Latest Version</th>
              <th>Rows</th>
              <th>Source</th>
              <th>Coverage</th>
            </tr>
          </thead>
          <tbody>
            {datasets.map((ds) => (
              <tr key={`${ds.category}/${ds.name}`}>
                <td>{ds.name}</td>
                <td>
                  <CategoryBadge category={ds.category} />
                </td>
                <td>v{ds.latest_version}</td>
                <td>{ds.row_count?.toLocaleString?.() ?? ds.row_count}</td>
                <td>{ds.source}</td>
                <td>
                  {ds.metadata?.start && ds.metadata?.end
                    ? `${ds.metadata.start} → ${ds.metadata.end}`
                    : '—'}
                  {ds.metadata?.gaps?.length > 0 && (
                    <span className="gap-warning"> ({ds.metadata.gaps.length} gap{ds.metadata.gaps.length > 1 ? 's' : ''})</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}

export default Datasets