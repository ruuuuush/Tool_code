export const MIB = 1024 * 1024;

export const MEDIA_LIMITS = {
  count: 8,
  imageBytes: 10 * MIB,
  videoBytes: 200 * MIB,
  totalBytes: 400 * MIB,
} as const;

const MEDIA_FORMATS = {
  jpg: { kind: 'image', mediaType: 'image/jpeg' },
  jpeg: { kind: 'image', mediaType: 'image/jpeg' },
  png: { kind: 'image', mediaType: 'image/png' },
  webp: { kind: 'image', mediaType: 'image/webp' },
  gif: { kind: 'image', mediaType: 'image/gif' },
  mp4: { kind: 'video', mediaType: 'video/mp4' },
  webm: { kind: 'video', mediaType: 'video/webm' },
  mov: { kind: 'video', mediaType: 'video/quicktime' },
} as const;

export const MEDIA_ACCEPT = '.jpg,.jpeg,.png,.webp,.gif,.mp4,.webm,.mov';

export type MediaKind = 'image' | 'video';

export interface AttachmentMetadata {
  name: string;
  kind: MediaKind;
  mediaType: string;
  sizeBytes: number;
  uploadStatus: 'local-only';
}

export interface LocalAttachment extends AttachmentMetadata {
  id: string;
  file: File;
  previewUrl: string;
}

export interface MediaFile {
  name: string;
  type: string;
  size: number;
}

export function selectMedia<T extends MediaFile>(
  files: readonly T[],
  existing: readonly AttachmentMetadata[],
): {
  accepted: { file: T; metadata: AttachmentMetadata }[];
  rejected: { name: string; reason: string }[];
} {
  const accepted: { file: T; metadata: AttachmentMetadata }[] = [];
  const rejected: { name: string; reason: string }[] = [];
  let count = existing.length;
  let total = existing.reduce((sum, item) => sum + item.sizeBytes, 0);

  for (const file of files) {
    const extension = file.name.match(/\.([^.]+)$/)?.[1].toLowerCase() ?? '';
    const format = Object.hasOwn(MEDIA_FORMATS, extension)
      ? MEDIA_FORMATS[extension as keyof typeof MEDIA_FORMATS]
      : undefined;
    if (!format) {
      rejected.push({ name: file.name, reason: '仅支持 JPEG、PNG、WebP、GIF、MP4、WebM、MOV' });
      continue;
    }

    let reason = '';
    if (file.size > (format.kind === 'image' ? MEDIA_LIMITS.imageBytes : MEDIA_LIMITS.videoBytes)) {
      reason = format.kind === 'image' ? '单张图片不能超过 10 MiB' : '单个视频不能超过 200 MiB';
    } else if (count >= MEDIA_LIMITS.count) {
      reason = '最多选择 8 个附件';
    } else if (total + file.size > MEDIA_LIMITS.totalBytes) {
      reason = '附件总大小不能超过 400 MiB';
    }

    if (reason) {
      rejected.push({ name: file.name, reason });
      continue;
    }

    accepted.push({
      file,
      metadata: {
        name: file.name,
        kind: format.kind,
        mediaType: format.mediaType,
        sizeBytes: file.size,
        uploadStatus: 'local-only',
      },
    });
    count += 1;
    total += file.size;
  }

  return { accepted, rejected };
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < MIB) return `${(bytes / 1024).toFixed(1)} KiB`;
  return `${(bytes / MIB).toFixed(1)} MiB`;
}
