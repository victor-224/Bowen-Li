import { useEffect, useRef } from 'react'
import Reveal from 'reveal.js'
import 'reveal.js/dist/reveal.css'
import 'reveal.js/dist/theme/white.css'

export function PresentationPage() {
  const deckRef = useRef(null)

  useEffect(() => {
    if (!deckRef.current) {
      return undefined
    }

    const deck = new Reveal(deckRef.current, {
      embedded: true,
      hash: false,
      controls: true,
      progress: true,
      transition: 'fade',
    })
    deck.initialize()

    return () => {
      if (typeof deck.destroy === 'function') {
        deck.destroy()
      }
    }
  }, [])

  return (
    <section className="presentation-shell">
      <div className="reveal" ref={deckRef}>
        <div className="slides">
          <section>
            <h2>React + Vite Equipment Demo</h2>
            <p>
              Routes:
              <br />
              <code>/viewer</code> for interactive validation and correction
              <br />
              <code>/presentation</code> for stakeholder walkthroughs
            </p>
          </section>

          <section>
            <h3>Source Priority Rules</h3>
            <ul>
              <li>Excel is source-of-truth for tag, dimensions, orientation.</li>
              <li>2D PDF contributes approximate position only.</li>
              <li>No guessing exact coordinates from noisy 2D references.</li>
            </ul>
          </section>

          <section>
            <h3>Position Uncertainty + Manual Correction</h3>
            <ul>
              <li>Every equipment record stores status + confidence.</li>
              <li>
                Uncertain items are flagged as <code>approximate</code> or <code>unresolved</code>.
              </li>
              <li>
                User can edit <code>x</code>, <code>y</code>, and <code>rotationDeg</code> in viewer.
              </li>
              <li>Corrected model is exported as JSON for downstream BIM alignment.</li>
            </ul>
          </section>

          <section>
            <h3>Scope of This First Milestone</h3>
            <ul>
              <li>Project structure created.</li>
              <li>Parsing strategy documented.</li>
              <li>Merged schema implemented with source trace + confidence fields.</li>
              <li>Full BIM extraction and precise coordinate solver deferred.</li>
            </ul>
          </section>
        </div>
      </div>
    </section>
  )
}
