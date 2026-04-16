import { Link, NavLink, Outlet } from 'react-router-dom'

const navigationItems = [
  { to: '/viewer', label: 'Viewer' },
  { to: '/presentation', label: 'Presentation' },
]

export function AppShell() {
  return (
    <div className="app-shell">
      <header className="top-nav">
        <Link className="brand" to="/">
          Equipment Demo
        </Link>
        <nav>
          <ul>
            {navigationItems.map((item) => (
              <li key={item.to}>
                <NavLink
                  className={({ isActive }) =>
                    isActive ? 'nav-link active' : 'nav-link'
                  }
                  to={item.to}
                >
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </header>

      <main className="page-shell">
        <Outlet />
      </main>
    </div>
  )
}
