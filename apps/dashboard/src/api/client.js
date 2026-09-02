const BASE_URL = '/api'

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })

  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(`Request failed (${res.status}): ${body}`)
  }

  return res.json()
}

export const api = {
  getAuditLog: (params = {}) => {
    const qs = new URLSearchParams(params).toString()
    return request(`/audit-log${qs ? `?${qs}` : ''}`)
  },
  getAnomalies: (params = {}) => {
    const qs = new URLSearchParams(params).toString()
    return request(`/anomalies${qs ? `?${qs}` : ''}`)
  },
  getOverviewStats: () => request('/overview'),
  getOrderBook: (symbol) => request(`/order-book/${symbol}`),
  // getDatasets was missing here despite Datasets.jsx calling it —
  // the page currently throws "api.getDatasets is not a function" at
  // runtime instead of showing the normal "Failed to load" state.
  // Restoring it (Phase 5 fix, found while adding getBaselineRun).
  getDatasets: () => request('/datasets'),
  getBaselineRun: () => request('/baseline-run'),
  getRiskDecisions: (params = {}) => {
    const qs = new URLSearchParams(params).toString()
    return request(`/risk/decisions${qs ? `?${qs}` : ''}`)
  },
    getAiActivity: (params = {}) => {
    const qs = new URLSearchParams(params).toString()
    return request(`/ai-reasoning/activity${qs ? `?${qs}` : ''}`)
  },
  // Replaced single-window getComparison() — a single window isn't
  // statistically meaningful on its own (Phase 8 methodology, agreed
  // with Gauri/Hansika), so the dashboard now always shows all 3
  // pinned windows together.
  getComparisonWindows: () => request('/comparison/windows'),
}