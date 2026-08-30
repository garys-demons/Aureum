/**
 * A minimal SVG line chart — built by hand rather than adding a
 * charting library (recharts, chart.js, etc.) for one chart. Keeps
 * the dashboard's dependency list as lean as it's been through every
 * prior phase (still just react/react-dom/react-router-dom).
 *
 * points: array of { timestamp, equity } — same shape
 * research.storage saves for a run's equity curve.
 */
function EquityCurveChart({ points, width = 640, height = 220 }) {
  if (!points || points.length < 2) {
    return <p className="empty-note">Not enough equity history to draw a chart yet.</p>
  }

  const padding = { top: 16, right: 16, bottom: 24, left: 56 }
  const plotWidth = width - padding.left - padding.right
  const plotHeight = height - padding.top - padding.bottom

  const equities = points.map((p) => p.equity)
  const minEquity = Math.min(...equities)
  const maxEquity = Math.max(...equities)
  const range = maxEquity - minEquity || 1 // avoid divide-by-zero on a flat line

  const x = (i) => padding.left + (i / (points.length - 1)) * plotWidth
  const y = (equity) => padding.top + plotHeight - ((equity - minEquity) / range) * plotHeight

  const linePath = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${x(i).toFixed(1)} ${y(p.equity).toFixed(1)}`)
    .join(' ')

  // A light reference line at the run's starting equity, so it's
  // visually obvious whether the run is currently up or down overall.
  const startingEquity = points[0].equity
  const startingY = y(startingEquity)

  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" role="img" aria-label="Equity curve">
      <line
        x1={padding.left} y1={startingY} x2={width - padding.right} y2={startingY}
        stroke="var(--panel-border, #2a2a2a)" strokeDasharray="4 4" strokeWidth="1"
      />
      <path d={linePath} fill="none" stroke="#4caf87" strokeWidth="2" />
      <text x={4} y={padding.top + 4} fontSize="10" fill="var(--text-faint, #666)">
        {maxEquity.toFixed(2)}
      </text>
      <text x={4} y={height - padding.bottom} fontSize="10" fill="var(--text-faint, #666)">
        {minEquity.toFixed(2)}
      </text>
    </svg>
  )
}

export default EquityCurveChart