import { BrowserRouter, Routes, Route } from 'react-router-dom'
import NavBar from './components/NavBar.jsx'
import Overview from './pages/Overview.jsx'
import AuditLog from './pages/AuditLog.jsx'
import Anomalies from './pages/Anomalies.jsx'
import OrderBook from './pages/OrderBook.jsx'
import Datasets from './pages/Datasets.jsx'
import Baseline from './pages/Baseline.jsx'
import Risk from './pages/Risk.jsx'
import AiActivity from './pages/AiActivity.jsx'
import Comparison from './pages/Comparison.jsx'
import './App.css'

function App() {
  return (
    <BrowserRouter>
      <div className="app-shell">
        <NavBar />
        <main className="app-content">
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/audit-log" element={<AuditLog />} />
            <Route path="/anomalies" element={<Anomalies />} />
            <Route path="/order-book" element={<OrderBook />} />
            <Route path="/datasets" element={<Datasets />} />
            <Route path="/baseline" element={<Baseline />} />
            <Route path="/risk" element={<Risk />} />
            <Route path="/ai-activity" element={<AiActivity />} />
            <Route path="/comparison" element={<Comparison />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App