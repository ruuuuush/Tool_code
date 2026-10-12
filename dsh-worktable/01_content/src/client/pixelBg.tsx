/**
 * 像素网格动态背景：与控制室网格同频的方形像素阵列。
 *
 * 三种动画模式：
 *   wave  波纹   —— 两道斜向正弦波叠加，取三次方后只留波峰，形成块状光带
 *   rain  数字雨 —— 每列一个独立下落的光头，身后带拖尾
 *   noise 噪点   —— 随时间平滑插值的二维值噪声，块状等离子
 *
 * 画布铺满 .dsh-wt_consoleBg 背景层；网格线由该元素 ::after 绘制并叠在画布之上，
 * 所以像素块尺寸 = 网格尺寸 = --wt-pixelSize，两者天然对齐。
 */
import { useEffect, useRef, type CSSProperties } from 'react'

export type PixelMode = 'wave' | 'rain' | 'noise'

export interface PixelBgProps {
  /** 像素块边长（px），与网格 background-size 保持同一个值 */
  size: number
  /** 动画速度，50 为基准 1×，0 = 完全静止 */
  speed: number
  /** 亮度百分比 */
  bright: number
  /** 色相 0-360 */
  hue: number
  mode: PixelMode
}

/** 32 位整数哈希 → [0,1)：稳定的伪随机，不随时间抖动 */
function hash2(i: number, j: number): number {
  let h = (i * 374761393 + j * 668265263) | 0
  h = (h ^ (h >>> 13)) * 1274126177
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296
}

/** 二维值噪声：格点哈希 + 平滑双线性插值；t 为时间切片编号 */
function vnoise(x: number, y: number, t: number): number {
  const xi = Math.floor(x)
  const yi = Math.floor(y)
  const xf = x - xi
  const yf = y - yi
  const u = xf * xf * (3 - 2 * xf)
  const v = yf * yf * (3 - 2 * yf)
  const tx = xi + t * 131
  const a = hash2(tx, yi)
  const b = hash2(tx + 1, yi)
  const c = hash2(tx, yi + 1)
  const d = hash2(tx + 1, yi + 1)
  return (a * (1 - u) + b * u) * (1 - v) + (c * (1 - u) + d * u) * v
}

export function PixelBg(props: PixelBgProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const liveRef = useRef(props)
  liveRef.current = props

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let cols = 0
    let rows = 0
    let cell = 0
    let raf = 0
    let last = 0
    let t = 0
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    const reduce = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches

    const resize = () => {
      const w = canvas.clientWidth || 1
      const h = canvas.clientHeight || 1
      cell = Math.max(6, Math.round(liveRef.current.size) || 30)
      cols = Math.ceil(w / cell)
      rows = Math.ceil(h / cell)
      canvas.width = Math.round(w * dpr)
      canvas.height = Math.round(h * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }

    /** 单个像素格的亮度 0..1（在格子坐标系里计算，与画布分辨率无关） */
    const sample = (i: number, j: number): number => {
      const mode = liveRef.current.mode
      if (mode === 'wave') {
        const a = Math.sin(i * 0.3 + j * 0.46 - t * 1.6)
        const b = Math.sin(i * 0.13 - j * 0.21 + t * 0.9)
        const v = (a + b) * 0.25 + 0.5
        return v * v * v
      }
      if (mode === 'rain') {
        // 每列两颗错开的雨滴，头部亮、尾部按二次方快速衰减
        const drop = (sd: number): number => {
          const sp = 3 + sd * 6
          const len = 5 + Math.floor(sd * 9)
          const span = rows + len + 6
          const head = (((t * sp + sd * 97) % span) + span) % span - len
          const d = head - j
          if (d < 0 || d > len) return 0
          const k = 1 - d / len
          return k * k
        }
        return Math.min(1, drop(hash2(i * 7 + 1, 3)) + drop(hash2(i * 13 + 5, 11)) * 0.8)
      }
      const tt = t * 1.2
      const t0 = Math.floor(tt)
      const f = tt - t0
      const n = vnoise(i * 0.16, j * 0.16, t0) * (1 - f) + vnoise(i * 0.16, j * 0.16, t0 + 1) * f
      // 去底噪 + 幂曲线：只有较高区域亮起来，形成块状等离子而不是一片灰
      return Math.pow(Math.min(1, Math.max(0, (n - 0.28) / 0.5)), 1.3)
    }

    const paint = () => {
      const p = liveRef.current
      const bright = Math.max(0, p.bright) / 100
      ctx.clearRect(0, 0, cols * cell, rows * cell)
      for (let j = 0; j < rows; j++) {
        for (let i = 0; i < cols; i++) {
          const v = sample(i, j)
          if (v <= 0.02) continue
          const a = Math.min(1, v * bright * 0.9)
          if (a <= 0.01) continue
          ctx.fillStyle = 'hsla(' + p.hue + ', 82%, ' + (42 + v * 26).toFixed(0) + '%, ' + a.toFixed(3) + ')'
          ctx.fillRect(i * cell, j * cell, cell - 1, cell - 1)
        }
      }
    }

    const frame = (now: number) => {
      raf = requestAnimationFrame(frame)
      if (now - last < 33) return
      const dt = last === 0 ? 0.033 : Math.min(0.12, (now - last) / 1000)
      last = now
      const p = liveRef.current
      if (Math.max(6, Math.round(p.size) || 30) !== cell) resize()
      if (!reduce && p.speed > 0) t += dt * (p.speed / 50) * 2.2
      paint()
    }

    resize()
    paint()
    if (typeof ResizeObserver === 'function') {
      const ro = new ResizeObserver(() => { resize(); paint() })
      ro.observe(canvas)
      raf = requestAnimationFrame(frame)
      return () => { cancelAnimationFrame(raf); ro.disconnect() }
    }
    raf = requestAnimationFrame(frame)
    return () => cancelAnimationFrame(raf)
  }, [])

  return <canvas ref={canvasRef} className="dsh-wt_pixelCanvas" aria-hidden />
}

/**
 * 媒体背景像素化：把底层 img/video（含 GIF 动图）按 pixel 倍降采样后以最近邻放大绘制，
 * 得到硬边像素块。底层元素保持可见并继续播放（drawImage 抓当前帧），画布覆盖在其上；
 * 网格线仍由 .dsh-wt_consoleBg::after 叠在最上层，所以这里不能加 z-index。
 */
export function PixelateOverlay(props: { pixel: number; style?: CSSProperties }) {
  const ref = useRef<HTMLCanvasElement | null>(null)
  const live = useRef(props)
  live.current = props
  useEffect(() => {
    const canvas = ref.current
    const host = canvas?.parentElement
    if (!canvas || !host) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    let raf = 0
    let last = 0
    let small: HTMLCanvasElement | null = null
    const dpr = Math.min(window.devicePixelRatio || 1, 2)

    /** 取当前真正可见的媒体：图片优先；视频取计算透明度最大者（宿主用双视频交叉淡入淡出） */
    const pick = (): HTMLImageElement | HTMLVideoElement | null => {
      const img = host.querySelector('img.dsh-wt_consoleMedia')
      if (img) return img as HTMLImageElement
      let best: HTMLVideoElement | null = null
      let bestOp = -1
      host.querySelectorAll('video.dsh-wt_consoleMedia').forEach((v) => {
        const el = v as HTMLVideoElement
        const op = parseFloat(getComputedStyle(el).opacity || '1')
        if (!Number.isNaN(op) && op > bestOp) { bestOp = op; best = el }
      })
      return best
    }

    const frame = (now: number) => {
      raf = requestAnimationFrame(frame)
      if (now - last < 40) return
      last = now
      const src = pick()
      if (!src) return
      const w = canvas.clientWidth
      const h = canvas.clientHeight
      if (!w || !h) return
      const sw = src instanceof HTMLVideoElement ? src.videoWidth : src.naturalWidth
      const sh = src instanceof HTMLVideoElement ? src.videoHeight : src.naturalHeight
      if (!sw || !sh) return
      const px = Math.max(2, Math.round(live.current.pixel))
      const nw = Math.max(1, Math.round(w / px))
      const nh = Math.max(1, Math.round(h / px))
      if (!small) small = document.createElement('canvas')
      if (small.width !== nw || small.height !== nh) { small.width = nw; small.height = nh }
      const sctx = small.getContext('2d')
      if (!sctx) return
      // 等价 object-fit:cover 的居中裁剪
      const k = Math.max(nw / sw, nh / sh)
      const dw = sw * k
      const dh = sh * k
      sctx.imageSmoothingEnabled = true
      sctx.clearRect(0, 0, nw, nh)
      sctx.drawImage(src, (nw - dw) / 2, (nh - dh) / 2, dw, dh)
      if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
        canvas.width = Math.round(w * dpr)
        canvas.height = Math.round(h * dpr)
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      }
      ctx.imageSmoothingEnabled = false
      ctx.clearRect(0, 0, w, h)
      ctx.drawImage(small, 0, 0, nw, nh, 0, 0, nw * px, nh * px)
    }
    raf = requestAnimationFrame(frame)
    return () => cancelAnimationFrame(raf)
  }, [])
  return <canvas ref={ref} className="dsh-wt_consoleMedia" style={props.style} aria-hidden />
}
