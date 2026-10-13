import { useState, type ChangeEvent, type RefObject } from 'react';
import {
  CATEGORIES,
  PLATFORMS,
  SEVERITIES,
  TEXT_RULES,
  type Feedback,
  type FeedbackErrors,
} from '../domain/feedback';
import { formatBytes, type LocalAttachment } from '../domain/media';
import AttachmentField from './AttachmentField';
import PitchScene from './PitchScene';

interface FeedbackFormProps {
  headingRef: RefObject<HTMLHeadingElement | null>;
  feedback: Feedback;
  errors: FeedbackErrors;
  attachments: LocalAttachment[];
  mediaErrors: string[];
  onChange: (feedback: Feedback) => void;
  onAddFiles: (files: File[]) => void;
  onRemoveFile: (id: string) => void;
  onPreview: () => void;
}

function TextField({ name, value, error, onChange, multiline = false, placeholder }: {
  name: keyof typeof TEXT_RULES;
  value: string;
  error?: string;
  onChange: (value: string) => void;
  multiline?: boolean;
  placeholder: string;
}) {
  const rule = TEXT_RULES[name];
  const id = `feedback-${name}`;
  const attributes = {
    id,
    name,
    value,
    required: rule.required,
    'aria-invalid': Boolean(error),
    'aria-describedby': `${id}-hint${error ? ` ${id}-error` : ''}`,
    placeholder,
    onChange: (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => onChange(event.currentTarget.value),
  };

  return (
    <div className={`field${error ? ' field-invalid' : ''}`}>
      <label className="field-label" htmlFor={id}>{rule.label}<span className={rule.required ? 'required-label' : 'optional-label'}>{rule.required ? '必填' : '选填'}</span></label>
      {multiline ? <textarea {...attributes} rows={name === 'description' || name === 'stepsText' ? 5 : 3} /> : <input {...attributes} type="text" autoComplete="off" />}
      <div className="field-meta"><span id={`${id}-hint`} className="field-hint">{name === 'build' ? '填写实际测试版本，不限格式' : name === 'stepsText' ? '按实际情况填写，无法复现可留空' : ''}</span><span className="char-count">{value.trim().length} / {rule.max}</span></div>
      {error && <p className="field-error" id={`${id}-error`}>{error}</p>}
    </div>
  );
}

export default function FeedbackForm({ headingRef, feedback, errors, attachments, mediaErrors, onChange, onAddFiles, onRemoveFile, onPreview }: FeedbackFormProps) {
  const [detailsOpen, setDetailsOpen] = useState(Boolean(feedback.stepsText || feedback.expected));
  const category = CATEGORIES.find((item) => item.value === feedback.category);
  const severity = SEVERITIES.find((item) => item.value === feedback.severity)!;
  const imageCount = attachments.filter((item) => item.kind === 'image').length;
  const videoCount = attachments.filter((item) => item.kind === 'video').length;
  const totalBytes = attachments.reduce((sum, item) => sum + item.sizeBytes, 0);

  function change<K extends keyof Feedback>(key: K, value: Feedback[K]) {
    onChange({ ...feedback, [key]: value });
  }

  function text(name: keyof typeof TEXT_RULES, placeholder: string, multiline = false) {
    return <TextField name={name} value={feedback[name]} error={errors[name]} onChange={(value) => change(name, value)} multiline={multiline} placeholder={placeholder} />;
  }

  return (
    <>
      <section className="page-intro">
        <div><div className="eyebrow"><span className="line-marker" />NEW FIELD REPORT</div><h1 ref={headingRef} tabIndex={-1}>回放问题，让好球继续<span className="accent-period">。</span></h1><p>描述异常、补充现场。把每一次反馈变成下一次改进的起点。</p></div>
        <div className="intro-stamp" aria-hidden="true"><span>M1</span><small>DETAILS<br />MAKE THE GAME</small></div>
      </section>

      <form className="feedback-layout" noValidate onSubmit={(event) => {
        event.preventDefault();
        onPreview();
      }}>
        <div className="form-sections">
          <section className="form-card" aria-labelledby="section-locate">
            <div className="section-heading"><span className="section-number">01</span><div><h2 id="section-locate">定位问题</h2><p>先告诉我们，哪一个细节出了问题。</p></div><span className="section-code">LOCATE</span></div>
            {text('title', '用一句话描述异常，例如：射门后角色短暂停顿')}

            <fieldset className="choice-field" aria-describedby={errors.category ? 'category-error' : undefined}>
              <legend className="field-label">问题分类<span className="required-label">必选</span></legend>
              <div className="category-grid">
                {CATEGORIES.map((item, index) => <label className={`category-option${feedback.category === item.value ? ' is-selected' : ''}`} key={item.value}>
                  <input type="radio" name="category" id={index === 0 ? 'feedback-category' : undefined} value={item.value} checked={feedback.category === item.value} required aria-invalid={Boolean(errors.category)} aria-describedby={errors.category ? 'category-error' : undefined} onChange={() => change('category', item.value)} />
                  <span className="category-tag" aria-hidden="true">{item.tag}</span><span className="category-text"><strong>{item.label}</strong><small>{item.hint}</small></span><span className="choice-check" aria-hidden="true">{feedback.category === item.value ? '✓' : ''}</span>
                </label>)}
              </div>
              {errors.category && <p className="field-error" id="category-error">{errors.category}</p>}
            </fieldset>

            <fieldset className="choice-field severity-field">
              <legend className="field-label">严重程度<span className="required-label">必填</span></legend>
              <div className="severity-options">
                {SEVERITIES.map((item, index) => <label className={`severity-option severity-${item.value}${feedback.severity === item.value ? ' is-selected' : ''}`} key={item.value}>
                  <input type="radio" name="severity" id={index === 0 ? 'feedback-severity' : undefined} checked={feedback.severity === item.value} value={item.value} required onChange={() => change('severity', item.value)} />
                  <span className="severity-indicator" aria-hidden="true" /><strong>{item.label}</strong><small>{item.hint}</small>
                </label>)}
              </div>
              {errors.severity && <p className="field-error" id="severity-error">{errors.severity}</p>}
            </fieldset>

            <div className="field-row">
              {text('build', '填写实际 Build 或版本标识')}
              <div className={`field${errors.platform ? ' field-invalid' : ''}`}>
                <label className="field-label" htmlFor="feedback-platform">运行平台<span className="required-label">必选</span></label>
                <select id="feedback-platform" value={feedback.platform} required aria-invalid={Boolean(errors.platform)} aria-describedby={errors.platform ? 'platform-error' : undefined} onChange={(event) => change('platform', event.currentTarget.value as Feedback['platform'])}>
                  <option value="">选择测试平台</option>{PLATFORMS.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
                </select>
                <div className="field-meta"><span className="field-hint">选择问题发生的平台</span></div>
                {errors.platform && <p className="field-error" id="platform-error">{errors.platform}</p>}
              </div>
            </div>
            <div className="field-row last-row">{text('device', '设备型号、系统或硬件信息')}{text('scene', '填写实际场景 / 对局模式')}</div>
          </section>

          <section className="form-card" aria-labelledby="section-reproduce">
            <div className="section-heading"><span className="section-number">02</span><div><h2 id="section-reproduce">还原现场</h2><p>具体的描述，比「有问题」更有帮助。</p></div><span className="section-code">REPLAY</span></div>
            {text('description', '问题发生时，你正在做什么？看到了什么异常？', true)}
            {text('actual', '实际发生了什么？对测试造成了什么影响？', true)}
            <details className="reproduction-details" open={detailsOpen || Boolean(errors.stepsText || errors.expected)} onToggle={(event) => setDetailsOpen(event.currentTarget.open)}>
              <summary><span>补充复现步骤与预期结果<small>选填 · 帮助更快定位</small></span><span className="details-plus" aria-hidden="true">＋</span></summary>
              <div className="details-fields">{text('stepsText', '1. 进入实际测试场景\n2. 执行触发问题的操作\n3. 观察异常', true)}{text('expected', '你认为正确的表现应该是什么？', true)}</div>
            </details>
          </section>

          <section className="form-card evidence-section" aria-labelledby="section-evidence">
            <div className="section-heading"><span className="section-number">03</span><div><h2 id="section-evidence">回放证据</h2><p>一帧画面，一段回放，都能让问题更清楚。</p></div><span className="section-code">EVIDENCE</span></div>
            <AttachmentField attachments={attachments} errors={mediaErrors} onAddFiles={onAddFiles} onRemoveFile={onRemoveFile} />
          </section>
        </div>

        <aside className="feedback-sidebar" aria-label="本次反馈摘要">
          <div className="summary-card">
            <div className="summary-topline"><span>REPORT BOARD</span><span className="outline-label">LOCAL ONLY</span></div>
            <h2>本次反馈摘要</h2>
            <div className="summary-category"><span className="field-hint">问题分类</span><strong>{category?.label ?? '等待选择分类'}</strong></div>
            <div className="summary-severity"><span>严重程度</span><strong className={`severity-text-${severity.value}`}>{severity.label}</strong></div>
            <div className="scoreboard" aria-label={`已选择 ${imageCount} 张图片、${videoCount} 个视频`}>
              <div><strong>{String(imageCount).padStart(2, '0')}</strong><span>图片 / IMAGE</span></div><span className="score-divider">:</span><div><strong>{String(videoCount).padStart(2, '0')}</strong><span>视频 / VIDEO</span></div>
            </div>
            <div className="attachment-total"><span>{attachments.length} / 8 个附件</span><span>{formatBytes(totalBytes)} / 400 MiB</span></div>
            <PitchScene compact />
            <div className="summary-notice"><strong>先还原，再开单。</strong><p>当前只生成通用问题单预览。<br />OpenID、上传与易协作均未接入。</p></div>
            <div className="memory-notice">内容仅保存在当前页面，刷新或退出会清空。</div>
          </div>
        </aside>

        <div className="form-submit-bar">
          <div><strong>准备好回放这次问题了吗？</strong><p>先预览，再确认模拟提交。附件不会上传。</p></div>
          <button className="button-primary" type="submit">预览并模拟提交<span aria-hidden="true">↗</span></button>
        </div>
      </form>
    </>
  );
}
