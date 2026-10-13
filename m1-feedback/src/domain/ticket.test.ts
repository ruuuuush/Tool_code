import { describe, expect, it } from 'vitest';
import { enterDemo } from '../services/auth';
import { INITIAL_FEEDBACK, type ValidFeedback } from './feedback';
import type { AttachmentMetadata } from './media';
import { buildTicket } from './ticket';

const feedback: ValidFeedback = {
  ...INITIAL_FEEDBACK,
  title: '  足球碰撞异常  ',
  category: 'physics',
  severity: 'blocker',
  build: '  实际 Build / 中文分支  ',
  platform: 'windows',
  description: '  发生碰撞后球体穿过角色。  ',
  actual: '  球体穿模。  ',
};
const createdAt = '2026-10-08T06:00:00.000Z';

describe('buildTicket', () => {
  it('builds minimal neutral payload with stable codes and no optional keys', () => {
    const ticket = buildTicket(feedback, enterDemo(), [], createdAt);
    expect(ticket).toMatchObject({ schemaVersion: '1.0', project: 'M1', source: 'm1-feedback-demo', createdAt, title: '足球碰撞异常', category: 'physics', severity: 'blocker' });
    expect(ticket.environment).toEqual({ build: '实际 Build / 中文分支', platform: 'windows' });
    expect(ticket.reproduction).toEqual({ actual: '球体穿模。' });
    expect(ticket.attachments).toEqual([]);
    expect(ticket.reporter).toEqual({ subject: 'demo:tester', displayName: 'M1 内部测试员', authMode: 'demo' });
    expect(ticket.description).toBe('问题描述\n发生碰撞后球体穿过角色。\n\n实际结果\n球体穿模。');
  });

  it('preserves internal line breaks, Chinese, quotes and HTML-like text', () => {
    const stepsText = '第一步：点击"开始"\n第二步：<script>不是 HTML</script>';
    const ticket = buildTicket({ ...feedback, stepsText: `  ${stepsText}  `, expected: '  正常碰撞\n保持球路  ', device: '  测试设备  ', scene: '  实际场景  ' }, enterDemo(), [], createdAt);
    expect(ticket.reproduction.stepsText).toBe(stepsText);
    expect(ticket.reproduction.expected).toBe('正常碰撞\n保持球路');
    expect(ticket.environment.device).toBe('测试设备');
    expect(ticket.environment.scene).toBe('实际场景');
    expect(ticket.description).toContain(`复现步骤\n${stepsText}\n\n预期结果\n正常碰撞\n保持球路`);
    expect(JSON.parse(JSON.stringify(ticket))).toEqual(ticket);
  });

  it('omits whitespace-only optional values and sections', () => {
    const ticket = buildTicket({ ...feedback, device: ' \n ', scene: '\t', stepsText: '\n ', expected: '   ' }, enterDemo(), [], createdAt);
    expect(ticket.environment).not.toHaveProperty('device');
    expect(ticket.environment).not.toHaveProperty('scene');
    expect(ticket.reproduction).not.toHaveProperty('stepsText');
    expect(ticket.reproduction).not.toHaveProperty('expected');
    expect(ticket.description).not.toContain('复现步骤');
    expect(ticket.description).not.toContain('预期结果');
  });

  it('whitelists attachment metadata and strips local file or URL information', () => {
    const attachment = {
      name: '回放.mp4',
      kind: 'video' as const,
      mediaType: 'video/mp4',
      sizeBytes: 5242880,
      uploadStatus: 'local-only' as const,
      file: new Blob(['private media']),
      previewUrl: 'blob:local-preview',
      path: 'C:\\private\\回放.mp4',
      base64: 'private-content',
    };
    const ticket = buildTicket(feedback, enterDemo(), [attachment], createdAt);
    expect(ticket.attachments).toEqual([{ name: '回放.mp4', kind: 'video', mediaType: 'video/mp4', sizeBytes: 5242880, uploadStatus: 'local-only' }]);
    const json = JSON.stringify(ticket);
    for (const excluded of ['blob:', 'private media', 'private-content', 'previewUrl', 'base64', 'C:\\private']) {
      expect(json).not.toContain(excluded);
    }
  });

  it('converts only current attachments and copies metadata', () => {
    const attachment: AttachmentMetadata = { name: '剩余.png', kind: 'image', mediaType: 'image/png', sizeBytes: 123, uploadStatus: 'local-only' };
    const ticket = buildTicket(feedback, enterDemo(), [attachment], createdAt);
    expect(ticket.attachments).toHaveLength(1);
    expect(ticket.attachments[0]).not.toBe(attachment);
    expect(ticket.attachments[0].name).toBe('剩余.png');
  });

  it('is deterministic and never mutates input or reporter', () => {
    const reporter = enterDemo();
    const original = structuredClone(feedback);
    const ticket = buildTicket(feedback, reporter, [], createdAt);
    expect(buildTicket(feedback, reporter, [], createdAt)).toEqual(ticket);
    expect(feedback).toEqual(original);
    expect(ticket.reporter).not.toBe(reporter);
  });
});
