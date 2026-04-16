import { useMemo, useState } from 'react'
import { EquipmentScene } from '../components/viewer/EquipmentScene'
import { seedMergedModel } from '../data/seedMergedData'
import { mergeEquipmentData } from '../parsing/mergeData'
import { parseExcelEquipment, parsePdfApproxPositions } from '../parsing/sourceAdapters'

function updateSelectedEquipment(model, selectedId, updater) {
  return {
    ...model,
    equipment: model.equipment.map((item) => {
      if (item.id !== selectedId) {
        return item
      }

      return updater(item)
    }),
  }
}

function toNullableNumber(value) {
  if (value === '') {
    return null
  }

  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

function downloadJson(name, content) {
  const blob = new Blob([JSON.stringify(content, null, 2)], {
    type: 'application/json;charset=utf-8',
  })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = name
  anchor.click()
  URL.revokeObjectURL(url)
}

export function ViewerPage() {
  const [mergedModel, setMergedModel] = useState(seedMergedModel)
  const [selectedId, setSelectedId] = useState(seedMergedModel.equipment[0]?.id ?? null)
  const [search, setSearch] = useState('')
  const [cameraCommand, setCameraCommand] = useState(null)
  const [excelFile, setExcelFile] = useState(null)
  const [pdfFile, setPdfFile] = useState(null)
  const [loadState, setLoadState] = useState('Using seed model. Upload source files to rebuild.')

  const selectedItem = useMemo(
    () => mergedModel.equipment.find((item) => item.id === selectedId) ?? null,
    [mergedModel.equipment, selectedId],
  )

  const filteredEquipment = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) {
      return mergedModel.equipment
    }

    return mergedModel.equipment.filter((item) => {
      return (
        item.tag.toLowerCase().includes(q) ||
        item.type.toLowerCase().includes(q) ||
        item.position.status.toLowerCase().includes(q)
      )
    })
  }, [mergedModel.equipment, search])

  const unresolvedItems = useMemo(() => {
    return mergedModel.equipment.filter((item) => item.position.status !== 'resolved')
  }, [mergedModel.equipment])

  function setManualPositionField(field, rawValue) {
    if (!selectedItem) {
      return
    }

    const value = toNullableNumber(rawValue)

    setMergedModel((prev) =>
      updateSelectedEquipment(prev, selectedItem.id, (item) => {
        const nextPosition = {
          ...item.position,
          [field]: value,
        }

        const isResolvedNow =
          nextPosition.x !== null &&
          nextPosition.y !== null &&
          nextPosition.rotationDeg !== null

        return {
          ...item,
          position: {
            ...nextPosition,
            status: isResolvedNow ? 'resolved' : 'approximate',
            confidence: isResolvedNow ? 0.92 : Math.max(nextPosition.confidence, 0.5),
            note: isResolvedNow
              ? 'Position manually corrected by user.'
              : 'Partially corrected; verify before final use.',
          },
          manualCorrection: {
            isEdited: true,
            editedAtIso: new Date().toISOString(),
            reason: 'Manual x/y/rotation correction in viewer.',
          },
        }
      }),
    )
  }

  async function handleRebuildFromFiles() {
    if (!excelFile) {
      setLoadState('Excel file is required because it is the source-of-truth.')
      return
    }

    setLoadState('Parsing source files...')

    try {
      const excelRows = await parseExcelEquipment(excelFile)
      const pdfPositionsByTag = pdfFile ? await parsePdfApproxPositions(pdfFile) : {}
      const rebuilt = mergeEquipmentData({
        excelRows,
        pdfPositionsByTag,
        projectName: 'Uploaded Equipment Model',
      })
      setMergedModel(rebuilt)
      setSelectedId(rebuilt.equipment[0]?.id ?? null)
      setLoadState(
        'Model rebuilt. Remember: PDF coordinates remain approximate until manually corrected.',
      )
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      setLoadState(`Could not parse uploaded files: ${detail}`)
    }
  }

  return (
    <section className="viewer-layout">
      <aside className="panel">
        <h2>Source + Merge Controls</h2>
        <p className="muted">
          Excel controls tag/size/orientation. PDF contributes approximate x/y only.
        </p>
        <label>
          Equipment Excel
          <input
            type="file"
            accept=".xlsx,.xls"
            onChange={(event) => setExcelFile(event.target.files?.[0] ?? null)}
          />
        </label>
        <label>
          2D Layout PDF
          <input type="file" accept=".pdf" onChange={(event) => setPdfFile(event.target.files?.[0] ?? null)} />
        </label>
        <button type="button" onClick={handleRebuildFromFiles}>
          Rebuild from files
        </button>
        <p className="status">{loadState}</p>

        <div className="toolbar-row">
          <button type="button" onClick={() => setCameraCommand({ type: 'reset', id: Date.now() })}>
            Reset View
          </button>
          <button
            type="button"
            onClick={() => setCameraCommand({ type: 'focus', id: Date.now() })}
            disabled={!selectedItem}
          >
            Focus Selected
          </button>
          <button
            type="button"
            onClick={() => downloadJson('corrected-merged-model.json', mergedModel)}
          >
            Export JSON
          </button>
        </div>

        <label>
          Search tags/types
          <input
            value={search}
            placeholder="ex: V-101, pump, unresolved"
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>

        <h3>Equipment List</h3>
        <ul className="equipment-list">
          {filteredEquipment.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                className={selectedId === item.id ? 'active' : ''}
                onClick={() => setSelectedId(item.id)}
              >
                <strong>{item.tag}</strong> ({item.type}) - {item.position.status} / conf{' '}
                {item.position.confidence.toFixed(2)}
              </button>
            </li>
          ))}
        </ul>
      </aside>

      <div className="scene-wrap">
        <EquipmentScene
          equipment={mergedModel.equipment}
          selectedId={selectedId}
          selectedItem={selectedItem}
          cameraCommand={cameraCommand}
          onSelect={setSelectedId}
        />
      </div>

      <aside className="panel">
        <h2>Selection + Manual Correction</h2>
        {!selectedItem && <p>No equipment selected.</p>}
        {selectedItem && (
          <div className="inspector">
            <p>
              <strong>{selectedItem.tag}</strong> ({selectedItem.type})
            </p>
            <p>
              Status: {selectedItem.position.status} ({selectedItem.position.confidence.toFixed(2)})
            </p>
            <p className="muted">{selectedItem.position.note}</p>

            <label>
              x
              <input
                type="number"
                step="0.1"
                value={selectedItem.position.x ?? ''}
                onChange={(event) => setManualPositionField('x', event.target.value)}
              />
            </label>
            <label>
              y
              <input
                type="number"
                step="0.1"
                value={selectedItem.position.y ?? ''}
                onChange={(event) => setManualPositionField('y', event.target.value)}
              />
            </label>
            <label>
              rotationDeg
              <input
                type="number"
                step="1"
                value={selectedItem.position.rotationDeg ?? ''}
                onChange={(event) => setManualPositionField('rotationDeg', event.target.value)}
              />
            </label>
          </div>
        )}

        <h3>Unresolved / Approximate</h3>
        <ul className="unresolved-list">
          {unresolvedItems.map((item) => (
            <li key={`u-${item.id}`}>
              <strong>{item.tag}</strong> - {item.position.status} ({item.position.confidence.toFixed(2)})
            </li>
          ))}
          {unresolvedItems.length === 0 && <li>All items marked resolved.</li>}
        </ul>
      </aside>
    </section>
  )
}
