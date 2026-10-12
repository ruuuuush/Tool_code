/**
 * 工作台「用量」dock：侧栏底部的余额 + 本会话 token 条。
 *
 * 数据来源：
 *   余额   宿主 Typert 远程服务 remote.account.getBalance(clientMeta)
 *          → { normal_wallets: [{currency, balance}], bonus_wallets: [...] }
 *   token  会话投影 sessionStats（turns / steps / decodeTokens / llmMs），
 *          由 sessionsSnapshotStore 的 snapshot.projectionsBySession 读取。
 *
 * 两者都按「有则显示、无则留空」处理：服务缺席或读取失败时只显示占位，不影响侧栏其余部分。
 */
import { useCallback, useEffect, useRef, useState } from 'react'

export interface UsageStats {
  turns?: number
  steps?: number
  decodeTokens?: number
  llmMs?: number
  toolMs?: number
}

interface Props {
  ctx: any
  sessionId: string
  stats: UsageStats | null
  t: (k: any, p?: any) => string
}

/** 账户远程方法要求的客户端元数据（与 dsh-client-ui-settings-account 同构） */
const DSH_CLIENT_VERSION = '0.2.0-rc.2'
function clientMeta(locale: string) {
  return {
    version: DSH_CLIENT_VERSION,
    locale: locale || 'zh',
    timezoneOffsetSeconds: -new Date().getTimezoneOffset() * 60,
  }
}

interface Wallet { currency: string; amount: number; bonus: boolean }

/** 容错解析：normal_wallets / bonus_wallets 是已知结构，其余形态一并兜住 */
function walletsOf(v: any): Wallet[] {
  const out: Wallet[] = []
  const push = (list: any, bonus: boolean) => {
    if (!Array.isArray(list)) return
    for (const w of list) {
      const amount = Number(w?.balance ?? w?.amount ?? NaN)
      if (!Number.isFinite(amount)) continue
      out.push({ currency: String(w?.currency ?? ''), amount, bonus })
    }
  }
  // 已知结构：{ value: [{currency, balance}], bonusWallets: [...] }；其余形态一并兜住
  push(v?.value ?? v?.normal_wallets ?? v?.normalWallets ?? v?.wallets, false)
  push(v?.bonusWallets ?? v?.bonus_wallets ?? v?.bonus, true)
  return out
}

const SYMBOL: Record<string, string> = { CNY: '¥', USD: '$' }
function fmtMoney(w: Wallet) {
  const sym = SYMBOL[w.currency] ?? (w.currency ? w.currency + ' ' : '')
  return sym + w.amount.toFixed(2)
}
function fmtTokens(n: number) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'k'
  return String(n)
}
function fmtMs(ms: number) {
  const s = Math.round(ms / 1000)
  if (s < 60) return s + 's'
  const m = Math.floor(s / 60)
  return m + 'm' + String(s % 60).padStart(2, '0') + 's'
}

export function UsageDock({ ctx, sessionId, stats, t }: Props) {
  const [wallets, setWallets] = useState<Wallet[] | null>(null)
  const [failed, setFailed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [at, setAt] = useState(0)
  const timer = useRef<number | null>(null)

  const refresh = useCallback(async () => {
    const api = (() => { try { return ctx?.get?.('remote.account') ?? ctx?.remote?.account ?? null } catch { return null } })()
    if (!api || typeof api.getBalance !== 'function') { setFailed(true); return }
    setBusy(true)
    try {
      const locale = (() => { try { return ctx?.locale?.getSnapshot?.().active ?? '' } catch { return '' } })()
      const res = await api.getBalance(clientMeta(locale))
      const value = res && typeof res === 'object' && 'ok' in res ? (res.ok ? res.value : null) : res
      const list = walletsOf(value)
      if (list.length === 0) { setFailed(true); setWallets(null) } else { setWallets(list); setFailed(false) }
    } catch { setFailed(true) } finally { setBusy(false); setAt(Date.now()) }
  }, [ctx])

  useEffect(() => {
    void refresh()
    timer.current = window.setInterval(() => { void refresh() }, 120_000)
    return () => { if (timer.current !== null) window.clearInterval(timer.current) }
  }, [refresh])

  const normal = wallets?.filter((w) => !w.bonus) ?? []
  const bonus = wallets?.filter((w) => w.bonus) ?? []
  const tok = stats?.decodeTokens

  const tip = [
    t('usage.balance') + ': ' + (wallets === null ? (failed ? t('usage.unavailable') : '…') : normal.map(fmtMoney).join(' / ')),
    bonus.length ? t('usage.bonus') + ': ' + bonus.map(fmtMoney).join(' / ') : '',
    sessionId ? t('usage.session') + ': ' + (stats ? (t('usage.turns') + ' ' + (stats.turns ?? 0) + ' · ' + t('usage.steps') + ' ' + (stats.steps ?? 0)) : '—') : '',
    tok !== undefined ? t('usage.tokens') + ': ' + tok : '',
    stats?.llmMs !== undefined ? t('usage.modelTime') + ': ' + fmtMs(stats.llmMs) : '',
    at ? t('usage.updated') + ' ' + new Date(at).toLocaleTimeString() : '',
    t('usage.refreshHint'),
  ].filter(Boolean).join('\n')

  return (
    <div className="dsh-wt_usage" title={tip}>
      <span className="dsh-wt_usageIcon" aria-hidden>◈</span>
      <span className="dsh-wt_usageBal">
        {wallets === null ? (failed ? t('usage.unavailable') : '…') : normal.map(fmtMoney).join(' / ')}
        {bonus.length > 0 && <span className="dsh-wt_usageBonus">{'+' + bonus.map(fmtMoney).join(' / ')}</span>}
      </span>
      <span className="dsh-wt_usageTok" title={t('usage.tokens')}>
        {tok === undefined ? '—' : fmtTokens(tok) + ' tok'}
      </span>
      <button
        type="button"
        className={'dsh-wt_usageRefresh' + (busy ? ' dsh-wt_usageBusy' : '')}
        aria-label={t('usage.refresh')}
        title={t('usage.refresh')}
        onClick={(e) => { e.stopPropagation(); void refresh() }}
      >⟳</button>
    </div>
  )
}
