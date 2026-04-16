import { Navigate, NavLink, Route, Routes } from 'react-router-dom'
import { ViewerPage } from './pages/ViewerPage'
import { PresentationPage } from './pages/PresentationPage'

function App() {
  return (
    <div className="app-shell">
      <header className="top-nav">
        <h1>Equipment Demo</h1>
        <nav>
          <NavLink to="/viewer">Viewer</NavLink>
          <NavLink to="/presentation">Presentation</NavLink>
        </nav>
      </header>

      <main className="app-main">
        <Routes>
          <Route path="/" element={<Navigate replace to="/viewer" />} />
          <Route path="/viewer" element={<ViewerPage />} />
          <Route path="/presentation" element={<PresentationPage />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
