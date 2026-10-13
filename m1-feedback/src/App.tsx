import { useEffect, useRef, useState } from 'react';
import {
  INITIAL_FEEDBACK,
  validateFeedback,
  type Feedback,
  type FeedbackErrors,
} from './domain/feedback';
import { selectMedia, type LocalAttachment } from './domain/media';
import { buildTicket, type Ticket } from './domain/ticket';
import { enterDemo, type Identity } from './services/auth';
import { simulateSubmission, type DemoResult } from './services/submit';
import LoginScreen from './components/LoginScreen';
import FeedbackForm from './components/FeedbackForm';
import TicketPreview from './components/TicketPreview';

export default function App() {
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [feedback, setFeedback] = useState<Feedback>({ ...INITIAL_FEEDBACK });
  const [errors, setErrors] = useState<FeedbackErrors>({});
  const [attachments, setAttachments] = useState<LocalAttachment[]>([]);
  const [mediaErrors, setMediaErrors] = useState<string[]>([]);
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [result, setResult] = useState<DemoResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [screen, setScreen] = useState<'form' | 'preview'>('form');
  const currentAttachments = useRef<LocalAttachment[]>([]);
  const activeSubmission = useRef<symbol | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    heading.current?.focus({ preventScroll: true });
    window.scrollTo({ top: 0, behavior: 'instant' });
  }, [identity, screen, result]);

  useEffect(() => () => {
    activeSubmission.current = null;
    for (const attachment of currentAttachments.current) {
      URL.revokeObjectURL(attachment.previewUrl);
    }
  }, []);

  function resetFeedback() {
    activeSubmission.current = null;
    for (const attachment of currentAttachments.current) {
      URL.revokeObjectURL(attachment.previewUrl);
    }
    currentAttachments.current = [];
    setAttachments([]);
    setFeedback({ ...INITIAL_FEEDBACK });
    setErrors({});
    setMediaErrors([]);
    setTicket(null);
    setResult(null);
    setSubmitting(false);
    setScreen('form');
  }

  function hasChanges() {
    return attachments.length > 0 || (Object.keys(feedback) as (keyof Feedback)[])
      .some((key) => feedback[key] !== INITIAL_FEEDBACK[key]);
  }

  function logout() {
    if (hasChanges() && !window.confirm('退出将清空当前文字、附件和本地预览，内容不会被保存。确认退出？')) return;
    resetFeedback();
    setIdentity(null);
  }

  function startAnother() {
    if (hasChanges() && !window.confirm('创建另一条反馈将清空当前内容和附件，内容不会被保存。确认继续？')) return;
    resetFeedback();
  }

  function updateFeedback(next: Feedback) {
    setFeedback(next);
    if (Object.keys(errors).length > 0) {
      const validation = validateFeedback(next);
      setErrors(validation.valid ? {} : validation.errors);
    }
  }

  function addFiles(files: File[]) {
    const selection = selectMedia(files, currentAttachments.current);
    const added = selection.accepted.map(({ file, metadata }) => ({
      ...metadata,
      id: crypto.randomUUID(),
      file,
      previewUrl: URL.createObjectURL(file),
    }));
    currentAttachments.current = [...currentAttachments.current, ...added];
    setAttachments(currentAttachments.current);
    setMediaErrors(selection.rejected.map((item) => `${item.name}：${item.reason}`));
  }

  function removeFile(id: string) {
    const attachment = currentAttachments.current.find((item) => item.id === id)!;
    URL.revokeObjectURL(attachment.previewUrl);
    currentAttachments.current = currentAttachments.current.filter((item) => item.id !== id);
    setAttachments(currentAttachments.current);
    setMediaErrors([]);
  }

  function preview() {
    const validation = validateFeedback(feedback);
    if (!validation.valid) {
      setErrors(validation.errors);
      const firstKey = (Object.keys(INITIAL_FEEDBACK) as (keyof Feedback)[])
        .find((key) => validation.errors[key]);
      const control = document.getElementById(`feedback-${firstKey}`);
      if (control?.closest('details')) control.closest('details')!.open = true;
      requestAnimationFrame(() => control?.focus());
      return;
    }
    setErrors({});
    setTicket(buildTicket(validation.value, identity!, attachments, new Date().toISOString()));
    setResult(null);
    setScreen('preview');
  }

  async function submit() {
    if (activeSubmission.current) return;
    const operation = Symbol();
    activeSubmission.current = operation;
    setSubmitting(true);
    const nextResult = await simulateSubmission(ticket!);
    if (activeSubmission.current !== operation) return;
    setResult(nextResult);
    setSubmitting(false);
    activeSubmission.current = null;
  }

  function editFeedback() {
    activeSubmission.current = null;
    setSubmitting(false);
    setResult(null);
    setTicket(null);
    setScreen('form');
  }

  if (!identity) {
    return <LoginScreen headingRef={heading} onEnter={() => setIdentity(enterDemo())} />;
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">跳到主要内容</a>
      <header className="site-header">
        <div className="brand-lockup" aria-label="M1 问题反馈站">
          <span className="brand-mark">M1<span className="brand-dot" /></span>
          <span className="brand-copy">VAR ROOM<span>问题反馈站</span></span>
        </div>
        <div className="header-session">
          <span className="demo-badge"><span className="status-dot" />演示模式</span>
          <span className="user-name">{identity.displayName}</span>
          <button className="button-quiet" type="button" onClick={logout}>退出</button>
        </div>
      </header>

      <main id="main-content" className="main-content">
        {screen === 'form' ? (
          <FeedbackForm
            headingRef={heading}
            feedback={feedback}
            errors={errors}
            attachments={attachments}
            mediaErrors={mediaErrors}
            onChange={updateFeedback}
            onAddFiles={addFiles}
            onRemoveFile={removeFile}
            onPreview={preview}
          />
        ) : (
          <TicketPreview
            headingRef={heading}
            ticket={ticket!}
            result={result}
            submitting={submitting}
            onEdit={editFeedback}
            onSubmit={submit}
            onStartAnother={startAnother}
          />
        )}
      </main>
      <footer className="site-footer">
        <span>M1 / EVERY DETAIL CHANGES THE GAME</span>
        <span>本地演示 · 刷新页面会清空本地内容</span>
      </footer>
    </div>
  );
}
