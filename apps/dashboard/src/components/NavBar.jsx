import { NavLink } from 'react-router-dom'

const links = [
  { to: '/', label: 'Overview', end: true },
  { to: '/audit-log', label: 'Audit Log' },
  { to: '/anomalies', label: 'Anomalies' },
  { to: '/order-book', label: 'Order Book' },
  { to: '/datasets', label: 'Datasets' },
  { to: '/baseline', label: 'Baseline' },
  { to: '/risk', label: 'Risk' },
  { to: '/ai-activity', label: 'AI Activity' },
  { to: '/comparison', label: 'Comparison' },
]

function NavBar() {
  return (
    <nav className="navbar">
      <div className="navbar-brand">Aureum</div>
      <ul className="navbar-links">
        {links.map((link) => (
          <li key={link.to}>
            <NavLink to={link.to} end={link.end}>
              {link.label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}

export default NavBar