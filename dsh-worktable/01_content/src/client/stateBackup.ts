/**
 * 工作台状态备份：把「界面配置」导出成一个 JSON，便于放进 Git 带到另一台机器。
 *
 * 两部分：
 *   local   localStorage 里的项目 / 布局 / 快捷键 / 绑定 / 视图（几十 KB，适合进 Git）
 *   media   IndexedDB 里的背景图 / 视频（二进制，体积大，默认不导出）
 *
 * 导入时媒体按原始 id 写回，这样「当前背景」的 id 引用能直接对上。
 */
import { photoStore, type MediaKind, type PhotoRecord } from './photoStore'

export const STATE_KEYS = [
  'dsh.worktable.view.v1',
  'dsh.worktable.projects.v1',
  'dsh.worktable.consoleBgPhoto.v1',
] as const

export interface MediaEntry {
  id: string
  createdAt: number
  kind: MediaKind
  order?: number
  type: string
  dataB64: string
}

export interface StateFile {
  format: 'dsh-worktable-state'
  version: 1
  exportedAt: string
  appVersion: string
  local: Record<string, string | null>
  mediaIncluded: boolean
  media: MediaEntry[]
}

const CHUNK = 0x8000
function toB64(buf: ArrayBuffer): string {
  const bytes = new Uint8Array(buf)
  let s = ''
  for (let i = 0; i < bytes.length; i += CHUNK) {
    s += String.fromCharCode.apply(null, Array.from(bytes.subarray(i, i + CHUNK)) as unknown as number[])
  }
  return btoa(s)
}
function fromB64(b64: string): Uint8Array {
  const bin = atob(b64)
  const out = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i)
  return out
}

export interface ExportResult { blob: Blob; name: string; bytes: number; mediaCount: number; mediaBytes: number }

export async function exportState(includeMedia: boolean, appVersion: string): Promise<ExportResult> {
  const local: Record<string, string | null> = {}
  for (const k of STATE_KEYS) {
    try { local[k] = localStorage.getItem(k) } catch { local[k] = null }
  }
  const media: MediaEntry[] = []
  let mediaBytes = 0
  if (includeMedia) {
    const recs = await photoStore.list()
    for (const r of recs) {
      const buf = await r.blob.arrayBuffer()
      mediaBytes += buf.byteLength
      media.push({ id: r.id, createdAt: r.createdAt, kind: r.kind, order: r.order, type: r.blob.type || '', dataB64: toB64(buf) })
    }
  }
  const file: StateFile = {
    format: 'dsh-worktable-state',
    version: 1,
    exportedAt: new Date().toISOString(),
    appVersion,
    local,
    mediaIncluded: includeMedia,
    media,
  }
  const blob = new Blob([JSON.stringify(file)], { type: 'application/json' })
  const name = 'dsh-worktable-state-' + new Date().toISOString().slice(0, 10) + '.json'
  return { blob, name, bytes: blob.size, mediaCount: media.length, mediaBytes }
}

export interface ImportResult { local: number; media: number; skipped: number }

export async function importState(text: string, opts: { withMedia: boolean }): Promise<ImportResult> {
  const file = JSON.parse(text) as StateFile
  if (!file || file.format !== 'dsh-worktable-state') throw new Error('stateBackup: 文件格式不符')
  let localN = 0
  for (const [k, v] of Object.entries(file.local ?? {})) {
    if (!(STATE_KEYS as readonly string[]).includes(k)) continue
    try {
      if (v === null || v === undefined) localStorage.removeItem(k)
      else { localStorage.setItem(k, v); localN++ }
    } catch {}
  }
  let mediaN = 0
  let skipped = 0
  if (opts.withMedia && Array.isArray(file.media)) {
    for (const m of file.media) {
      try {
        const bytes = fromB64(m.dataB64)
        const blob = new Blob([bytes], { type: m.type || (m.kind === 'video' ? 'video/mp4' : 'image/png') })
        const rec: PhotoRecord = { id: m.id, createdAt: m.createdAt, kind: m.kind, blob, order: m.order }
        await photoStore.put(rec)
        mediaN++
      } catch { skipped++ }
    }
  }
  return { local: localN, media: mediaN, skipped }
}

/** 人类可读体积，用于导出后的提示 */
export function fmtSize(bytes: number): string {
  if (bytes >= 1048576) return (bytes / 1048576).toFixed(1) + ' MB'
  if (bytes >= 1024) return (bytes / 1024).toFixed(0) + ' KB'
  return bytes + ' B'
}
