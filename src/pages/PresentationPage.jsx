import { useEffect, useRef } from 'react'
import Reveal from 'reveal.js'
import 'reveal.js/reveal.css'
import 'reveal.js/theme/black.css'
import { mergedScaffoldDataset } from '../features/merge/sampleSourceData.js'
import { PresentationModelSlide } from '../components/presentation/PresentationModelSlide.jsx'

const prioritizedTags = ['B200', 'B300', 'B301', 'P001A']

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

  const prioritizedEquipment = prioritizedTags
    .map((tag) => mergedScaffoldDataset.equipment.find((record) => record.tag === tag))
    .filter(Boolean)

  const fallbackEquipment = mergedScaffoldDataset.equipment.slice(
    0,
    Math.max(0, 4 - prioritizedEquipment.length),
  )

  const demoEquipment = [...prioritizedEquipment, ...fallbackEquipment].slice(0, 4)

  return (
    <div>
      <div className="action-row" style={{ marginBottom: '0.75rem' }}>
        <a
          className="button-like secondary"
          href="/presentation-live.html"
          target="_blank"
          rel="noreferrer"
        >
          Open static live presentation
        </a>
        <a className="button-like" href="/现场演示-设备坐标模型.pptx" download>
          Download PPTX
        </a>
      </div>

      <div className="presentation-wrap">
        <div className="reveal" ref={revealRootRef}>
          <div className="slides">
            <section>
              <h2>设备点位 3D 展示（Web PPT）</h2>
              <p>React + Vite + Reveal.js：用于演示从设备标签到模型坐标的转换结果。</p>
            </section>
            <section>
              <h2>模型展示页（示例点位）</h2>
              <PresentationModelSlide equipment={demoEquipment} />
            </section>
            <section>
              <h2>数据权威规则（关键）</h2>
              <ul>
                <li>Excel 是 TAG、尺寸、方向的唯一权威来源。</li>
                <li>2D PDF 只提供近似 x/y/rotation，不能当精确坐标。</li>
                <li>禁止猜测精确坐标。</li>
              </ul>
            </section>
            <section>
              <h2>不确定性与人工修正</h2>
              <ul>
                <li>每个设备点位都有状态：corrected / approximate / unresolved。</li>
                <li>每个坐标都带 confidence（0.00 - 1.00）。</li>
                <li>
                  当点位不确定时，需要在 Viewer 页面人工调整 x/y/rotation 并导出 JSON。
                </li>
              </ul>
            </section>
          </div>
        </div>
      </div>
    </div>
  )
}
