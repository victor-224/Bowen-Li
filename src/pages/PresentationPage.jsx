import { useEffect, useRef } from 'react'
import Reveal from 'reveal.js'
import 'reveal.js/dist/reveal.css'
import 'reveal.js/dist/theme/black.css'

export function PresentationPage() {
  const revealRootRef = useRef(null)

  useEffect(() => {
    if (!revealRootRef.current) return undefined

    const deck = new Reveal(revealRootRef.current, {
      controls: true,
      progress: true,
      hash: true,
      transition: 'slide',
    })

    deck.initialize()

    return () => {
      deck.destroy()
    }
  }, [])

  return (
    <div className="presentation-wrap">
      <div className="reveal" ref={revealRootRef}>
        <div className="slides">
          <section>
            <h2>Equipment Viewer Scaffold</h2>
            <p>React + Vite with /viewer and /presentation routes.</p>
          </section>
          <section>
            <h2>Data Authority Rules</h2>
            <ul>
              <li>Excel is source of truth for tag, size, and orientation.</li>
              <li>2D PDF contributes approximate x/y/rotation only.</li>
              <li>No guessed exact coordinates.</li>
            </ul>
          </section>
          <section>
            <h2>Position Uncertainty + Manual Correction</h2>
            <ul>
              <li>Each item carries status: corrected, approximate, or unresolved.</li>
              <li>Each position includes confidence (0.00 - 1.00).</li>
              <li>
                Manual editor allows x/y/rotation correction and JSON export for
                traceable updates.
              </li>
            </ul>
          </section>
        </div>
      </div>
    </div>
  )
}
