import { BrowserRouter, Routes, Route } from 'react-router-dom'
import NavBar from './components/NavBar.jsx'
import Overview from './pages/Overview.jsx'
import AuditLog from './pages/AuditLog.jsx'
import Anomalies from './pages/Anomalies.jsx'
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
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App