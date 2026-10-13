import type { Identity } from '../services/auth';
import type { Category, Platform, Severity, ValidFeedback } from './feedback';
import type { AttachmentMetadata } from './media';

export interface Ticket {
  schemaVersion: '1.0';
  project: 'M1';
  source: 'm1-feedback-demo';
  createdAt: string;
  title: string;
  category: Category;
  severity: Severity;
  reporter: Identity;
  description: string;
  environment: {
    build: string;
    platform: Platform;
    device?: string;
    scene?: string;
  };
  reproduction: {
    actual: string;
    stepsText?: string;
    expected?: string;
  };
  attachments: AttachmentMetadata[];
}

export function buildTicket(
  feedback: ValidFeedback,
  reporter: Identity,
  attachments: readonly AttachmentMetadata[],
  createdAt: string,
): Ticket {
  const device = feedback.device.trim();
  const scene = feedback.scene.trim();
  const stepsText = feedback.stepsText.trim();
  const expected = feedback.expected.trim();
  const actual = feedback.actual.trim();
  const sections = [
    ['问题描述', feedback.description.trim()],
    ['实际结果', actual],
    ['复现步骤', stepsText],
    ['预期结果', expected],
  ];

  return {
    schemaVersion: '1.0',
    project: 'M1',
    source: 'm1-feedback-demo',
    createdAt,
    title: feedback.title.trim(),
    category: feedback.category,
    severity: feedback.severity,
    reporter: {
      subject: reporter.subject,
      displayName: reporter.displayName,
      authMode: reporter.authMode,
    },
    description: sections
      .filter(([, content]) => content.length > 0)
      .map(([label, content]) => `${label}\n${content}`)
      .join('\n\n'),
    environment: {
      build: feedback.build.trim(),
      platform: feedback.platform,
      ...(device ? { device } : {}),
      ...(scene ? { scene } : {}),
    },
    reproduction: {
      actual,
      ...(stepsText ? { stepsText } : {}),
      ...(expected ? { expected } : {}),
    },
    attachments: attachments.map((attachment) => ({
      name: attachment.name,
      kind: attachment.kind,
      mediaType: attachment.mediaType,
      sizeBytes: attachment.sizeBytes,
      uploadStatus: 'local-only',
    })),
  };
}
