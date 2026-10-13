import { describe, expect, it } from 'vitest';
import { formatBytes, MIB, selectMedia, type AttachmentMetadata, type MediaFile } from './media';

function file(name: string, size = 100, type = ''): MediaFile {
  return { name, size, type };
}

function existing(count: number): AttachmentMetadata[] {
  return Array.from({ length: count }, (_, index) => ({ name: `${index}.png`, kind: 'image', mediaType: 'image/png', sizeBytes: 100, uploadStatus: 'local-only' }));
}

describe('selectMedia', () => {
  it('accepts every allowed extension including uppercase and absent browser MIME', () => {
    for (const extension of ['jpg', 'jpeg', 'png', 'webp', 'gif', 'mp4', 'webm', 'mov', 'PNG', 'MOV']) {
      const selection = selectMedia([file(`回放.${extension}`)], []);
      expect(selection.rejected).toEqual([]);
      expect(selection.accepted[0].metadata.name).toBe(`回放.${extension}`);
      expect(selection.accepted[0].metadata.uploadStatus).toBe('local-only');
      expect(selection.accepted[0].metadata.mediaType).not.toBe('');
    }
  });

  it('accepts images and videos in input order and reports rejected files', () => {
    const files = [file('画面.png'), file('unsafe.exe'), file('回放.mp4')];
    const selection = selectMedia(files, []);
    expect(selection.accepted.map((item) => item.metadata.kind)).toEqual(['image', 'video']);
    expect(selection.accepted.map((item) => item.file)).toEqual([files[0], files[2]]);
    expect(selection.rejected).toEqual([{ name: 'unsafe.exe', reason: '仅支持 JPEG、PNG、WebP、GIF、MP4、WebM、MOV' }]);
  });

  it('accepts 10 MiB image and 200 MiB video boundaries, rejects one extra byte', () => {
    const selection = selectMedia([file('edge.png', 10 * MIB), file('large.png', 10 * MIB + 1), file('edge.mp4', 200 * MIB), file('large.mp4', 200 * MIB + 1)], []);
    expect(selection.accepted.map((item) => item.metadata.name)).toEqual(['edge.png', 'edge.mp4']);
    expect(selection.rejected.map((item) => item.reason)).toEqual(['单张图片不能超过 10 MiB', '单个视频不能超过 200 MiB']);
  });

  it('accepts an eighth attachment and rejects the ninth without replacing existing files', () => {
    const attachments = existing(7);
    const original = structuredClone(attachments);
    const selection = selectMedia([file('eighth.png'), file('ninth.mp4')], attachments);
    expect(selection.accepted.map((item) => item.metadata.name)).toEqual(['eighth.png']);
    expect(selection.rejected[0].reason).toBe('最多选择 8 个附件');
    expect(attachments).toEqual(original);
  });

  it('accepts exactly 400 MiB and rejects exceeding total size', () => {
    const selection = selectMedia([file('first.mp4', 200 * MIB), file('second.mp4', 200 * MIB), file('extra.png', 1)], []);
    expect(selection.accepted).toHaveLength(2);
    expect(selection.rejected).toEqual([{ name: 'extra.png', reason: '附件总大小不能超过 400 MiB' }]);
  });

  it('continues after total-size rejection and accepts a smaller next file', () => {
    const attachments: AttachmentMetadata[] = [{ name: 'old.mp4', kind: 'video', mediaType: 'video/mp4', sizeBytes: 395 * MIB, uploadStatus: 'local-only' }];
    const selection = selectMedia([file('too-much.png', 6 * MIB), file('fits.png', 5 * MIB)], attachments);
    expect(selection.rejected).toHaveLength(1);
    expect(selection.accepted[0].metadata.sizeBytes).toBe(5 * MIB);
  });

  it('keeps existing selection unchanged when input is empty', () => {
    const attachments = existing(2);
    expect(selectMedia([], attachments)).toEqual({ accepted: [], rejected: [] });
    expect(attachments).toHaveLength(2);
  });

  it('does not treat a disallowed extension as an allowed file based on MIME', () => {
    expect(selectMedia([file('program.exe', 100, 'image/png'), file('png')], []).accepted).toHaveLength(0);
  });

  it('rejects non-format names that match object prototype properties', () => {
    expect(selectMedia([file('sample.constructor'), file('sample.__proto__')], []).accepted).toHaveLength(0);
    expect(selectMedia([file('sample.constructor'), file('sample.__proto__')], []).rejected).toHaveLength(2);
  });

  it('formats byte units without decimal ambiguity', () => {
    expect(formatBytes(0)).toBe('0 B');
    expect(formatBytes(1024)).toBe('1.0 KiB');
    expect(formatBytes(10 * MIB)).toBe('10.0 MiB');
  });
});
