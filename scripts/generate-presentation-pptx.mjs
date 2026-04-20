import fs from 'node:fs'
import path from 'node:path'
import PptxGenJS from 'pptxgenjs'

const outputDir = path.resolve('public', 'downloads')
const outputPath = path.join(outputDir, 'equipment-demo-presentation.pptx')

function ensureDir(targetDir) {
  if (!fs.existsSync(targetDir)) {
    fs.mkdirSync(targetDir, { recursive: true })
  }
}

async function generate() {
  ensureDir(outputDir)

  const pptx = new PptxGenJS()
  pptx.author = 'Equipment Demo'
  pptx.company = 'Hackathon Team'
  pptx.layout = 'LAYOUT_WIDE'
  pptx.subject = 'Equipment coordinate demo'
  pptx.title = 'Equipment Coordinate Demo'
  pptx.lang = 'zh-CN'

  const themeColor = '1E293B'
  const accent = '38BDF8'
  const text = 'E2E8F0'

  const slide1 = pptx.addSlide()
  slide1.background = { color: '0F172A' }
  slide1.addText('设备点位坐标演示', {
    x: 0.8,
    y: 1.0,
    w: 11.5,
    h: 0.8,
    fontFace: 'Microsoft YaHei',
    fontSize: 38,
    bold: true,
    color: text,
  })
  slide1.addText('Web Demo + 现场备份 PPTX', {
    x: 0.8,
    y: 1.95,
    w: 11.0,
    h: 0.5,
    fontFace: 'Microsoft YaHei',
    fontSize: 20,
    color: accent,
  })
  slide1.addShape(pptx.ShapeType.roundRect, {
    x: 0.8,
    y: 3.0,
    w: 12,
    h: 2.4,
    fill: { color: themeColor },
    line: { color: '334155', pt: 1 },
    radius: 0.08,
  })
  slide1.addText(
    [
      {
        text: '重点：',
        options: { bold: true, color: 'F8FAFC' },
      },
      {
        text: '在平面图上点击物件即可对应 x / y 坐标（例如 B200）。',
        options: { color: text },
      },
    ],
    {
      x: 1.1,
      y: 3.4,
      w: 11.2,
      h: 0.8,
      fontFace: 'Microsoft YaHei',
      fontSize: 20,
    },
  )
  slide1.addText('打开地址：/presentation 或 /presentation-live', {
    x: 1.1,
    y: 4.2,
    w: 11.2,
    h: 0.5,
    fontFace: 'Consolas',
    fontSize: 14,
    color: '93C5FD',
  })

  const slide2 = pptx.addSlide()
  slide2.background = { color: '0B1220' }
  slide2.addText('数据与可信度规则', {
    x: 0.8,
    y: 0.5,
    w: 12,
    h: 0.7,
    fontFace: 'Microsoft YaHei',
    fontSize: 32,
    bold: true,
    color: text,
  })
  const rules = [
    'Excel 是 TAG、尺寸、方向的权威来源',
    '2D Plan / PDF 仅提供近似位置',
    '不允许猜测精确坐标',
    '不确定项必须标记 approximate / unresolved + confidence',
    '人工修改 x/y/rotation 后导出 corrected JSON',
  ]
  rules.forEach((rule, index) => {
    slide2.addText(`• ${rule}`, {
      x: 1.0,
      y: 1.5 + index * 0.75,
      w: 11.5,
      h: 0.5,
      fontFace: 'Microsoft YaHei',
      fontSize: 20,
      color: 'CBD5E1',
    })
  })

  const slide3 = pptx.addSlide()
  slide3.background = { color: '0F172A' }
  slide3.addText('点击平面图点位 -> 坐标结果', {
    x: 0.8,
    y: 0.5,
    w: 12,
    h: 0.7,
    fontFace: 'Microsoft YaHei',
    fontSize: 30,
    bold: true,
    color: text,
  })
  slide3.addShape(pptx.ShapeType.roundRect, {
    x: 0.8,
    y: 1.4,
    w: 7.6,
    h: 4.9,
    fill: { color: '020617' },
    line: { color: '334155', pt: 1 },
    radius: 0.06,
  })
  slide3.addText('Plan 2D click area (现场可在网页中直接点击)', {
    x: 1.1,
    y: 1.7,
    w: 7.0,
    h: 0.35,
    fontFace: 'Microsoft YaHei',
    fontSize: 13,
    color: '94A3B8',
  })
  slide3.addShape(pptx.ShapeType.ellipse, {
    x: 2.1,
    y: 2.5,
    w: 0.25,
    h: 0.25,
    fill: { color: '22C55E' },
    line: { color: '16A34A', pt: 1 },
  })
  slide3.addText('B200', {
    x: 2.4,
    y: 2.45,
    w: 1.4,
    h: 0.3,
    fontFace: 'Consolas',
    fontSize: 12,
    color: 'E2E8F0',
  })
  slide3.addShape(pptx.ShapeType.roundRect, {
    x: 8.7,
    y: 1.4,
    w: 4.0,
    h: 4.9,
    fill: { color: '111827' },
    line: { color: '334155', pt: 1 },
    radius: 0.06,
  })
  slide3.addText('示例坐标', {
    x: 9.0,
    y: 1.75,
    w: 3.4,
    h: 0.4,
    fontFace: 'Microsoft YaHei',
    fontSize: 18,
    bold: true,
    color: 'BFDBFE',
  })
  slide3.addText('B200 -> (x=8.20, y=4.70)', {
    x: 9.0,
    y: 2.35,
    w: 3.4,
    h: 0.35,
    fontFace: 'Consolas',
    fontSize: 14,
    color: 'E2E8F0',
  })
  slide3.addText('status: approximate', {
    x: 9.0,
    y: 2.8,
    w: 3.4,
    h: 0.35,
    fontFace: 'Consolas',
    fontSize: 14,
    color: 'FBBF24',
  })
  slide3.addText('confidence: 0.52', {
    x: 9.0,
    y: 3.25,
    w: 3.4,
    h: 0.35,
    fontFace: 'Consolas',
    fontSize: 14,
    color: 'E2E8F0',
  })

  const slide4 = pptx.addSlide()
  slide4.background = { color: '0B1220' }
  slide4.addText('现场使用建议', {
    x: 0.8,
    y: 0.5,
    w: 12,
    h: 0.7,
    fontFace: 'Microsoft YaHei',
    fontSize: 30,
    bold: true,
    color: text,
  })
  slide4.addText('1) 首选网页: /presentation-live（最稳）', {
    x: 1.0,
    y: 1.6,
    w: 11.5,
    h: 0.5,
    fontFace: 'Microsoft YaHei',
    fontSize: 21,
    color: 'CBD5E1',
  })
  slide4.addText('2) 备选网页: /presentation（Reveal.js）', {
    x: 1.0,
    y: 2.4,
    w: 11.5,
    h: 0.5,
    fontFace: 'Microsoft YaHei',
    fontSize: 21,
    color: 'CBD5E1',
  })
  slide4.addText('3) 离线兜底: 下载并打开 equipment-demo-presentation.pptx', {
    x: 1.0,
    y: 3.2,
    w: 11.5,
    h: 0.5,
    fontFace: 'Microsoft YaHei',
    fontSize: 21,
    color: 'CBD5E1',
  })

  await pptx.writeFile({ fileName: outputPath })
  console.log(`PPTX generated at ${outputPath}`)
}

generate().catch((error) => {
  console.error(error)
  process.exit(1)
})
