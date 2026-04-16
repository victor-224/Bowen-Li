import { useMemo, useState } from 'react'
import { ThreeViewport } from '../../features/viewer/ThreeViewport.jsx'
import { mergedScaffoldDataset } from '../../features/merge/sampleSourceData.js'

function sortByTag(records) {
  return [...records].sort((a, b) => a.tag.localeCompare(b.tag))
}

export function PresentationModelSlide() {
  const [searchTerm, setSearchTerm] = useState('B200')

  const rows = useMemo(() => {
    const query = searchTerm.trim().toLowerCase()
    const all = sortByTag(mergedScaffoldDataset.equipment)
    if (!query) return all
    return all.filter((item) => item.tag.toLowerCase().includes(query))
  }, [searchTerm])

  return (
    <div className="ppt-model-slide">
      <div className="ppt-model-left">
        <ThreeViewport />
        <p className="ppt-tip">
          3D model is a simplified geometry preview used for web presentation.
        </p>
      </div>

      <div className="ppt-model-right">
        <h3>Coordinate extraction preview</h3>
        <p className="ppt-sub">
          Focus tags like B200. If a tag is unresolved, it stays unresolved until
          manual correction.
        </p>

        <label className="input-label" htmlFor="ppt-tag-search">
          Search tag
        </label>
        <input
          id="ppt-tag-search"
          value={searchTerm}
          onChange={(event) => setSearchTerm(event.target.value)}
          placeholder="e.g. B200"
        />

        <table className="ppt-table">
          <thead>
            <tr>
              <th>tag</th>
              <th>x</th>
              <th>y</th>
              <th>rot</th>
              <th>status</th>
              <th>conf</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((item) => (
              <tr key={item.id}>
                <td>{item.tag}</td>
                <td>{item.position.x ?? '-'}</td>
                <td>{item.position.y ?? '-'}</td>
                <td>{item.position.rotationDeg ?? '-'}</td>
                <td>{item.positionStatus}</td>
                <td>{item.confidence.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>

        {rows.length === 0 ? (
          <p className="ppt-warning">
            No matching tag in current demo data. Keep it unresolved rather than
            guessing coordinates.
          </p>
        ) : null}
      </div>
    </div>
  )
}
