import { Link } from 'react-router-dom'

export function HomePage() {
  return (
    <section className="content-card">
      <h1>React + Vite Equipment Demo Scaffold</h1>
      <p>
        This first iteration sets up project structure, route foundations, and a
        transparent merge schema for Excel + 2D PDF inputs.
      </p>
      <ul className="bullet-list">
        <li>Excel values are authoritative for tag, size, and orientation.</li>
        <li>2D PDF positions are treated as approximate guidance only.</li>
        <li>
          Uncertain coordinates are explicitly marked approximate/unresolved with
          confidence.
        </li>
      </ul>

      <div className="action-row">
        <Link className="button-like" to="/viewer">
          Open Viewer
        </Link>
        <Link className="button-like secondary" to="/presentation">
          Open Presentation
        </Link>
        <a
          className="button-like secondary"
          href="/presentation/live-presentation.html"
          target="_blank"
          rel="noreferrer"
        >
          Open Live HTML PPT
        </a>
        <a
          className="button-like secondary"
          href="/downloads/equipment-demo-presentation.pptx"
          download
        >
          Download PPTX
        </a>
        <a
          className="button-like secondary"
          href="/live-presentation.html"
          target="_blank"
          rel="noreferrer"
        >
          Open Root Live PPT
        </a>
      </div>
    </section>
  )
}
