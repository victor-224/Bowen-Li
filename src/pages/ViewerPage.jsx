import { useMemo, useRef, useState } from 'react'
import { mergedScaffoldDataset } from '../features/merge/sampleSourceData.js'
import { mergedEquipmentSchema } from '../features/merge/mergedSchema.js'
import { ThreeViewport } from '../features/viewer/ThreeViewport.jsx'
import { downloadJsonFile } from '../utils/downloadJson.js'

function parseNumberOrNull(value) {
  if (value === '' || value === null || value === undefined) return null
  const numeric = Number(value)
  return Number.isNaN(numeric) ? null : numeric
}

export function ViewerPage() {
  const [searchTerm, setSearchTerm] = useState('')
  const [records, setRecords] = useState(mergedScaffoldDataset.equipment)
  const [selectedId, setSelectedId] = useState(mergedScaffoldDataset.equipment[0]?.id)
  const viewportRef = useRef(null)

  const selected = records.find((item) => item.id === selectedId) ?? null

  const filteredRecords = useMemo(() => {
    const query = searchTerm.trim().toLowerCase()
    if (!query) return records
    return records.filter((record) => {
      return (
        record.tag.toLowerCase().includes(query) ||
        record.type.toLowerCase().includes(query)
      )
    })
  }, [records, searchTerm])

  const unresolvedRecords = useMemo(() => {
    return records.filter((record) => record.positionStatus !== 'corrected')
  }, [records])

  const updateSelectedPosition = (field, rawValue) => {
    if (!selected) return
    const parsed = parseNumberOrNull(rawValue)
    setRecords((current) =>
      current.map((record) => {
        if (record.id !== selected.id) return record

        const position = {
          ...record.position,
          [field]: parsed,
        }

        const allCoordinatesResolved = Object.values(position).every(
          (value) => value !== null,
        )

        return {
          ...record,
          position,
          positionStatus: allCoordinatesResolved ? 'corrected' : 'unresolved',
          confidence: allCoordinatesResolved ? 0.9 : 0.15,
          unresolvedReason: allCoordinatesResolved
            ? null
            : 'Manual correction still incomplete.',
          source: {
            ...record.source,
            manualCorrection: {
              correctedAt: new Date().toISOString(),
              correctedBy: 'viewer-user',
              reason: 'manual-position-edit',
            },
          },
        }
      }),
    )
  }

  const exportCorrectedJson = () => {
    const payload = {
      ...mergedScaffoldDataset,
      meta: {
        ...mergedScaffoldDataset.meta,
        exportedAt: new Date().toISOString(),
      },
      schema: mergedEquipmentSchema,
      equipment: records,
    }
    downloadJsonFile('corrected-equipment-layout.json', payload)
  }

  return (
    <section className="viewer-layout">
      <aside className="left-panel content-card">
        <h1>Viewer</h1>
        <p className="small-note">
          Excel values (tag, size, orientation) are authoritative. 2D PDF values
          are approximate position hints only.
        </p>

        <label className="input-label" htmlFor="equipment-search">
          Search equipment
        </label>
        <input
          id="equipment-search"
          value={searchTerm}
          onChange={(event) => setSearchTerm(event.target.value)}
          placeholder="tag or type"
        />

        <ul className="equipment-list">
          {filteredRecords.map((record) => (
            <li key={record.id}>
              <button
                className={record.id === selectedId ? 'row-button active' : 'row-button'}
                onClick={() => setSelectedId(record.id)}
              >
                <span>{record.tag}</span>
                <span className="row-meta">
                  {record.positionStatus} ({record.confidence.toFixed(2)})
                </span>
              </button>
            </li>
          ))}
        </ul>
      </aside>

      <div className="center-panel">
        <ThreeViewport ref={viewportRef} />
        <div className="action-row">
          <button onClick={() => viewportRef.current?.resetView()}>Reset View</button>
          <button onClick={() => viewportRef.current?.focusSelected()}>
            Focus Selected
          </button>
          <button onClick={exportCorrectedJson}>Export JSON</button>
        </div>
      </div>

      <aside className="right-panel content-card">
        <h2>Selected</h2>
        {selected ? (
          <div className="detail-grid">
            <div>
              <strong>{selected.tag}</strong>
            </div>
            <div>{selected.size}</div>
            <div>{selected.orientation}</div>
            <div>{selected.geometryProxy}</div>

            <label htmlFor="x-edit">x</label>
            <input
              id="x-edit"
              value={selected.position.x ?? ''}
              onChange={(event) => updateSelectedPosition('x', event.target.value)}
            />

            <label htmlFor="y-edit">y</label>
            <input
              id="y-edit"
              value={selected.position.y ?? ''}
              onChange={(event) => updateSelectedPosition('y', event.target.value)}
            />

            <label htmlFor="rotation-edit">rotation (deg)</label>
            <input
              id="rotation-edit"
              value={selected.position.rotationDeg ?? ''}
              onChange={(event) =>
                updateSelectedPosition('rotationDeg', event.target.value)
              }
            />
          </div>
        ) : (
          <p>No selected record.</p>
        )}

        <h2>Unresolved / Approximate</h2>
        <ul className="unresolved-list">
          {unresolvedRecords.map((record) => (
            <li key={record.id}>
              <strong>{record.tag}</strong> - {record.positionStatus} (
              {record.confidence.toFixed(2)})
            </li>
          ))}
        </ul>
      </aside>
    </section>
  )
}
