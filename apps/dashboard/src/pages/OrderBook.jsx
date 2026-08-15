import { useEffect, useState } from 'react'
import { api } from '../api/client.js'

const SYMBOL = 'BTCUSDT' // Phase 1/2 currently only trades one symbol (config/exchange.yaml)

/**
 * Expected /api/order-book/{symbol} response shape (not built yet —
 * apps/api is still empty, same as every other page in this dashboard).
 * Documented here so whoever builds the API endpoint has a concrete
 * target, matching the pattern the other pages already use:
 *
 * {
 *   "symbol": "BTCUSDT",
 *   "best_bid": [64990.0, 1.5],   // [price, quantity]
 *   "best_ask": [65010.0, 1.2],
 *   "spread": 20.0,
 *   "bid_depth": 42,               // number of price levels
 *   "ask_depth": 38,
 *   "last_update_id": 123456,
 *   "history": [                   // recent snapshots, newest first
 *     { "occurred_at": "...", "spread": 20.0, "bid_depth": 42, "ask_depth": 38 },
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

function formatPriceLevel(level) {
  if (!level) return '—'
  const [price, quantity] = level
  return `${price} (${quantity})`
}

function OrderBook() {
  const [book, setBook] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api
      .getOrderBook(SYMBOL)
      .then(setBook)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <section>
      <h1>Order Book — {SYMBOL}</h1>

      {error && <p className="error">Failed to load: {error}</p>}
      {!error && loading && <p className="empty-note">Loading...</p>}
      {!error && !loading && !book && (
        <p className="empty-note">No order book data yet — waiting for the pipeline.</p>
      )}

      {!error && !loading && book && (
        <>
          <div className="stat-grid">
            <StatCard label="Best Bid" value={formatPriceLevel(book.best_bid)} />
            <StatCard label="Best Ask" value={formatPriceLevel(book.best_ask)} />
            <StatCard label="Spread" value={book.spread ?? '—'} />
            <StatCard label="Depth (bids / asks)" value={`${book.bid_depth ?? '—'} / ${book.ask_depth ?? '—'}`} />
          </div>

          <h2 className="section-subtitle">Recent history</h2>
          {(!book.history || book.history.length === 0) && (
            <p className="empty-note">No history yet.</p>
          )}
          {book.history && book.history.length > 0 && (
            <table>
              <thead>
                <tr>
                  <th>Occurred At</th>
                  <th>Spread</th>
                  <th>Bid Depth</th>
                  <th>Ask Depth</th>
                </tr>
              </thead>
              <tbody>
                {book.history.map((row, i) => (
                  <tr key={i}>
                    <td>{row.occurred_at}</td>
                    <td>{row.spread}</td>
                    <td>{row.bid_depth}</td>
                    <td>{row.ask_depth}</td>
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

export default OrderBook