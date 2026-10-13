import { useRef, useState } from 'react';
import { formatBytes, MEDIA_ACCEPT, type LocalAttachment } from '../domain/media';

interface AttachmentFieldProps {
  attachments: LocalAttachment[];
  errors: string[];
  onAddFiles: (files: File[]) => void;
  onRemoveFile: (id: string) => void;
}

function EvidenceCard({ attachment, index, onRemove }: {
  attachment: LocalAttachment;
  index: number;
  onRemove: () => void;
}) {
  const [failed, setFailed] = useState(false);

  return (
    <article className="evidence-card">
      <div className="evidence-toolbar"><span>EVIDENCE / {String(index + 1).padStart(2, '0')}</span><span>{attachment.kind === 'image' ? 'IMAGE' : 'VIDEO'}</span></div>
      <div className="evidence-preview">
        {failed ? (
          <div className="media-fallback" role="status">
            <span aria-hidden="true">{attachment.kind === 'video' ? '▷' : '▧'}</span>
            <p>{attachment.kind === 'video' ? '当前浏览器无法播放，文件仍可作为附件' : '无法预览此图片，文件仍可作为附件'}</p>
          </div>
        ) : attachment.kind === 'image' ? (
          <img src={attachment.previewUrl} alt={`证据图片：${attachment.name}`} onError={() => setFailed(true)} />
        ) : (
          <video src={attachment.previewUrl} controls preload="metadata" playsInline aria-label={`证据视频：${attachment.name}`} onError={() => setFailed(true)} />
        )}
        <span className="replay-corner" aria-hidden="true" />
      </div>
      <div className="evidence-info">
        <strong title={attachment.name}>{attachment.name}</strong>
        <span>{attachment.mediaType} · {formatBytes(attachment.sizeBytes)}</span>
        <div className="evidence-actions"><small>仅本地，未上传</small><button type="button" className="button-quiet" aria-label={`移除 ${attachment.name}`} onClick={onRemove}>移除</button></div>
      </div>
    </article>
  );
}

export default function AttachmentField({ attachments, errors, onAddFiles, onRemoveFile }: AttachmentFieldProps) {
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  return (
    <div className="attachment-field">
      <label htmlFor="evidence-files" className="field-label">图片与视频<span className="optional-label">选填</span></label>
      <input
        ref={input}
        id="evidence-files"
        className="visually-hidden"
        type="file"
        accept={MEDIA_ACCEPT}
        multiple
        tabIndex={-1}
        aria-describedby="media-limits"
        onChange={(event) => {
          const files = Array.from(event.currentTarget.files ?? []);
          if (files.length > 0) onAddFiles(files);
          event.currentTarget.value = '';
        }}
      />
      <div
        className={`drop-zone${dragging ? ' is-dragging' : ''}`}
        onDragOver={(event) => {
          event.preventDefault();
          event.dataTransfer.dropEffect = 'copy';
          setDragging(true);
        }}
        onDragLeave={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragging(false);
        }}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          const files = Array.from(event.dataTransfer.files);
          if (files.length > 0) onAddFiles(files);
        }}
      >
        <svg className="upload-symbol" viewBox="0 0 48 48" fill="none" aria-hidden="true"><path d="M9 15V9h9M30 9h9v6M39 33v6h-9M18 39H9v-6" stroke="currentColor" strokeWidth="1.5" /><path d="M24 31V17m0 0-6 6m6-6 6 6" stroke="currentColor" strokeWidth="2" /></svg>
        <strong>把现场，留在回放里</strong>
        <p>拖入图片、视频，或从设备中选择</p>
        <button className="button-secondary" type="button" onClick={() => input.current?.click()} aria-describedby="media-limits">选择图片或视频<span aria-hidden="true">＋</span></button>
        <span className="drop-local">仅本地选择与预览，不会上传</span>
      </div>
      <p id="media-limits" className="field-hint media-limits">JPEG / PNG / WebP / GIF · MP4 / WebM / MOV<br />最多 8 项 · 图片 ≤ 10 MiB · 视频 ≤ 200 MiB · 总计 ≤ 400 MiB</p>
      {errors.length > 0 && <ul className="media-error-list" role="alert">{errors.map((error, index) => <li key={`${index}-${error}`}>{error}</li>)}</ul>}
      {attachments.length > 0 && (
        <div className="evidence-grid" aria-label="本地回放证据">
          {attachments.map((attachment, index) => <EvidenceCard key={attachment.id} attachment={attachment} index={index} onRemove={() => onRemoveFile(attachment.id)} />)}
        </div>
      )}
    </div>
  );
}
