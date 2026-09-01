/**
 * A minimal SVG line chart — built by hand rather than adding a
 * charting library (recharts, chart.js, etc.) for one chart. Keeps
 * the dashboard's dependency list as lean as it's been through every
 * prior phase (still just react/react-dom/react-router-dom).
 *
 * Two usage modes:
 *   <EquityCurveChart points={curve} />                    — single series (Baseline.jsx, unchanged)
 *   <EquityCurveChart series={[{name, points, color}, ...]} /> — multiple overlaid series (Phase 8 Comparison.jsx)
 *
 * points/series[].points: array of { timestamp, equity } — same shape
 * research.storage saves for a run's equity curve.
 */
function EquityCurveChart({ points, series, width = 640, height = 220 }) {
  const seriesData = series ?? (points ? [{ name: null, points, color: '#4caf87' }] : [])
  const hasEnoughData = seriesData.some((s) => s.points && s.points.length >= 2)

  if (!hasEnoughData) {
    return <p className="empty-note">Not enough equity history to draw a chart yet.</p>
  }

  const padding = { top: 16, right: 16, bottom: 24, left: 56 }
  const plotWidth = width - padding.left - padding.right
  const plotHeight = height - padding.top - padding.bottom

  // Min/max computed ACROSS all series, so multiple curves share one
  // consistent scale — otherwise each line would be independently
  // normalized and visually incomparable, defeating the point of
  // overlaying them.
  const allEquities = seriesData.flatMap((s) => (s.points ?? []).map((p) => p.equity))
  const minEquity = Math.min(...allEquities)
  const maxEquity = Math.max(...allEquities)
  const range = maxEquity - minEquity || 1 // avoid divide-by-zero on a flat line

  const y = (equity) => padding.top + plotHeight - ((equity - minEquity) / range) * plotHeight

  // x is fractional position within EACH series' own point count —
  // correct whether series have the same number of points or not
  // (e.g. two runs against the same dataset should match, but this
  // doesn't assume that).
  const buildPath = (pts) =>
    pts
      .map((p, i) => {
        const x = padding.left + (i / (pts.length - 1)) * plotWidth
        return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y(p.equity).toFixed(1)}`
      })
      .join(' ')

  const isSingleSeries = !series

  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" role="img" aria-label="Equity curve">
      {isSingleSeries && seriesData[0]?.points?.length >= 2 && (
        <line
          x1={padding.left} y1={y(seriesData[0].points[0].equity)}
          x2={width - padding.right} y2={y(seriesData[0].points[0].equity)}
          stroke="var(--panel-border, #2a2a2a)" strokeDasharray="4 4" strokeWidth="1"
        />
      )}

      {seriesData.map(
        (s, idx) =>
          s.points &&
          s.points.length >= 2 && (
            <path
              key={s.name ?? idx}
              d={buildPath(s.points)}
              fill="none"
              stroke={s.color ?? '#4caf87'}
              strokeWidth="2"
            />
          )
      )}

      <text x={4} y={padding.top + 4} fontSize="10" fill="var(--text-faint, #666)">
        {maxEquity.toFixed(2)}
      </text>
      <text x={4} y={height - padding.bottom} fontSize="10" fill="var(--text-faint, #666)">
        {minEquity.toFixed(2)}
      </text>

      {series && (
        <g transform={`translate(${padding.left}, ${height - 12})`}>
          {seriesData.map((s, idx) => (
            <g key={s.name ?? idx} transform={`translate(${idx * 140}, 0)`}>
              <rect width="10" height="10" fill={s.color ?? '#4caf87'} />
              <text x="14" y="9" fontSize="10" fill="var(--text-faint, #666)">
                {s.name}
              </text>
            </g>
          ))}
        </g>
      )}
    </svg>
  )
}

export default EquityCurveChart