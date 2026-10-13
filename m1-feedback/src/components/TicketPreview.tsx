import type { RefObject } from 'react';
import { CATEGORIES, PLATFORMS, SEVERITIES } from '../domain/feedback';
import { formatBytes } from '../domain/media';
import type { Ticket } from '../domain/ticket';
import type { DemoResult } from '../services/submit';

interface TicketPreviewProps {
  headingRef: RefObject<HTMLHeadingElement | null>;
  ticket: Ticket;
  result: DemoResult | null;
  submitting: boolean;
  onEdit: () => void;
  onSubmit: () => void;
  onStartAnother: () => void;
}

export default function TicketPreview({ headingRef, ticket, result, submitting, onEdit, onSubmit, onStartAnother }: TicketPreviewProps) {
  const category = CATEGORIES.find((item) => item.value === ticket.category)!;
  const severity = SEVERITIES.find((item) => item.value === ticket.severity)!;
  const platform = PLATFORMS.find((item) => item.value === ticket.environment.platform)!;

  return (
    <div className="preview-page">
      <section className="page-intro preview-intro">
        <div><div className="eyebrow"><span className="line-marker" />{result ? 'DEMO REPORT / READY' : 'VAR CHECK / PREVIEW'}</div><h1 ref={headingRef} tabIndex={-1}>{result ? '模拟问题单已生成' : '回放确认，准备就绪'}<span className="accent-period">。</span></h1><p>{result ? '这是一份本地演示结果，内容未保存到远端。' : '再看一眼问题与证据，确认后仅模拟提交。'}</p></div>
        <span className="preview-seal" aria-hidden="true">{result ? '✓' : 'VAR'}</span>
      </section>

      <div className={`submission-banner${result ? ' is-complete' : ''}`} role="status">
        <span className="status-dot" /><strong>未提交易协作 · 附件未上传</strong><span>演示身份 · 通用问题单 · 仅本地</span>
      </div>

      <div className="preview-grid">
        <article className="form-card ticket-card" aria-labelledby="ticket-title">
          <div className="summary-topline"><span>M1 / FIELD REPORT</span><span className="outline-label">{result ? 'DEMO RESULT' : 'PREVIEW'}</span></div>
          <h2 id="ticket-title">{ticket.title}</h2>
          <div className="ticket-tags"><span>{category.label}</span><span className={`severity-text-${severity.value}`}>{severity.label}</span><span>{platform.label}</span></div>
          <dl className="ticket-environment">
            <div><dt>游戏版本 / Build</dt><dd>{ticket.environment.build}</dd></div>
            <div><dt>反馈身份</dt><dd>{ticket.reporter.displayName} · 演示</dd></div>
            {ticket.environment.device && <div><dt>设备信息</dt><dd>{ticket.environment.device}</dd></div>}
            {ticket.environment.scene && <div><dt>发生场景</dt><dd>{ticket.environment.scene}</dd></div>}
            <div><dt>本地生成时间</dt><dd>{new Date(ticket.createdAt).toLocaleString('zh-CN', { hour12: false })}</dd></div>
          </dl>
          <div className="ticket-description"><h3>问题与复现信息</h3><p>{ticket.description}</p></div>
          <section className="ticket-attachments" aria-labelledby="preview-evidence-title">
            <div className="ticket-section-title"><h3 id="preview-evidence-title">回放证据</h3><span>{ticket.attachments.length} 个 · 仅元数据</span></div>
            {ticket.attachments.length === 0 ? <p className="field-hint">未选择附件。文字反馈同样有效。</p> : (
              <ul>{ticket.attachments.map((attachment, index) => <li key={`${index}-${attachment.name}`}>
                <span className="attachment-index">{String(index + 1).padStart(2, '0')}</span><div><strong>{attachment.name}</strong><small>{attachment.kind === 'image' ? '图片' : '视频'} · {attachment.mediaType} · {formatBytes(attachment.sizeBytes)}</small></div><span className="local-only-label">仅本地，未上传</span>
              </li>)}</ul>
            )}
          </section>
        </article>

        <section className="form-card json-card" aria-labelledby="json-title">
          <div className="summary-topline"><span>DATA PAYLOAD</span><span>JSON / 1.0</span></div>
          <h2 id="json-title">通用问题单 JSON</h2>
          <p className="json-description">不是易协作 API 请求。附件仅包含元数据，不包含媒体内容或本地预览链接。</p>
          <pre className="json-preview" tabIndex={0} aria-label="通用问题单 JSON 数据"><code>{JSON.stringify(ticket, null, 2)}</code></pre>
          <div className="json-footer"><span className="status-dot" />供应商字段映射与真实上传后续接入</div>
        </section>
      </div>

      <div className="preview-actions">
        <button className="button-secondary" type="button" onClick={onEdit} disabled={submitting}><span aria-hidden="true">←</span>{result ? '继续修改当前反馈' : '返回修改'}</button>
        {result ? (
          <button className="button-primary" type="button" onClick={onStartAnother}>创建另一条反馈<span aria-hidden="true">＋</span></button>
        ) : (
          <button className="button-primary" type="button" onClick={onSubmit} disabled={submitting} aria-busy={submitting}>{submitting ? '正在模拟提交…' : '确认模拟提交'}<span aria-hidden="true">{submitting ? '◌' : '↗'}</span></button>
        )}
      </div>
      <p className="preview-memory-note">内容只在当前页面保留，刷新、退出或创建另一条反馈会清空。</p>
    </div>
  );
}
