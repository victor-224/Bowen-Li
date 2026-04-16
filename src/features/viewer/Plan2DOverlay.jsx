function toPercent(value, min, max) {
  if (value === null || value === undefined) return null
  if (max <= min) return 0
  return ((value - min) / (max - min)) * 100
}

export function Plan2DOverlay({
  records,
  selectedId,
  onSelectRecord,
  xRange = [0, 30],
  yRange = [0, 20],
}) {
  const [minX, maxX] = xRange
  const [minY, maxY] = yRange

  const mapped = records
    .filter((record) => record.position.x !== null && record.position.y !== null)
    .map((record) => ({
      ...record,
      xPercent: toPercent(record.position.x, minX, maxX),
      yPercent: toPercent(record.position.y, minY, maxY),
    }))

  return (
    <section className="plan-overlay-card content-card">
      <div className="plan-overlay-header">
        <h2>2D Plan Click-to-Coordinate</h2>
        <p className="small-note">
          Click a marker on the plan to select equipment and map tag to x/y.
          Positions remain approximate unless manually corrected.
        </p>
      </div>

      <div className="plan-surface" role="application" aria-label="2D equipment plan">
        <div className="plan-grid" aria-hidden="true" />
        {mapped.map((record) => (
          <button
            key={record.id}
            type="button"
            className={
              record.id === selectedId ? 'plan-marker active' : 'plan-marker'
            }
            style={{
              left: `${record.xPercent}%`,
              top: `${100 - record.yPercent}%`,
            }}
            onClick={() => onSelectRecord(record.id)}
            title={`${record.tag} -> (${record.position.x}, ${record.position.y})`}
          >
            {record.tag}
          </button>
        ))}
      </div>

      <a
        className="button-like secondary"
        href="/plans/annexe-1-layout-train.pdf"
        target="_blank"
        rel="noreferrer"
      >
        Open uploaded plan PDF
      </a>
    </section>
  )
}
