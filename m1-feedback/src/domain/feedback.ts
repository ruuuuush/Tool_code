export const CATEGORIES = [
  { value: 'gameplay', label: '操作与比赛规则', tag: 'PLAY', hint: '操作响应、规则判定' },
  { value: 'animation', label: '球员动作与动画', tag: 'MOVE', hint: '动作衔接、角色表现' },
  { value: 'physics', label: '足球与碰撞物理', tag: 'BALL', hint: '球路、碰撞、穿模' },
  { value: 'ai', label: 'AI 与门将', tag: 'AI', hint: '决策、跑位、扑救' },
  { value: 'presentation', label: '画面、界面与音效', tag: 'LOOK', hint: '渲染、UI、声音' },
  { value: 'performance', label: '性能与崩溃', tag: 'PERF', hint: '帧率、卡顿、闪退' },
  { value: 'network', label: '联机与同步', tag: 'NET', hint: '连接、延迟、同步' },
  { value: 'other', label: '其他问题与建议', tag: 'MORE', hint: '其他异常、体验建议' },
] as const;

export const SEVERITIES = [
  { value: 'blocker', label: '阻断', hint: '无法继续测试' },
  { value: 'major', label: '严重', hint: '核心体验受影响' },
  { value: 'minor', label: '一般', hint: '局部异常' },
  { value: 'suggestion', label: '建议', hint: '体验优化' },
] as const;

export const PLATFORMS = [
  { value: 'windows', label: 'Windows' },
  { value: 'android', label: 'Android' },
  { value: 'ios', label: 'iOS' },
  { value: 'other', label: '其他平台' },
] as const;

export type Category = (typeof CATEGORIES)[number]['value'];
export type Severity = (typeof SEVERITIES)[number]['value'];
export type Platform = (typeof PLATFORMS)[number]['value'];

export interface Feedback {
  title: string;
  category: Category | '';
  severity: Severity;
  build: string;
  platform: Platform | '';
  device: string;
  scene: string;
  description: string;
  actual: string;
  stepsText: string;
  expected: string;
}

export const INITIAL_FEEDBACK: Feedback = {
  title: '',
  category: '',
  severity: 'minor',
  build: '',
  platform: '',
  device: '',
  scene: '',
  description: '',
  actual: '',
  stepsText: '',
  expected: '',
};

export const TEXT_RULES = {
  title: { label: '问题标题', max: 120, required: true },
  build: { label: '游戏版本 / Build', max: 100, required: true },
  device: { label: '设备信息', max: 200, required: false },
  scene: { label: '发生场景', max: 200, required: false },
  description: { label: '问题描述', max: 5000, required: true },
  actual: { label: '实际结果', max: 2000, required: true },
  stepsText: { label: '复现步骤', max: 3000, required: false },
  expected: { label: '预期结果', max: 2000, required: false },
} as const;

export type FeedbackErrors = Partial<Record<keyof Feedback, string>>;
export type ValidFeedback = Feedback & { category: Category; platform: Platform };

export type ValidationResult =
  | { valid: true; value: ValidFeedback }
  | { valid: false; errors: FeedbackErrors };

export function validateFeedback(feedback: Feedback): ValidationResult {
  const errors: FeedbackErrors = {};

  for (const key of Object.keys(TEXT_RULES) as (keyof typeof TEXT_RULES)[]) {
    const rule = TEXT_RULES[key];
    const length = feedback[key].trim().length;
    if (rule.required && length === 0) {
      errors[key] = `请填写${rule.label}`;
    } else if (length > rule.max) {
      errors[key] = `${rule.label}最多 ${rule.max} 字符`;
    }
  }

  if (!CATEGORIES.some((item) => item.value === feedback.category)) {
    errors.category = '请选择问题分类';
  }
  if (!SEVERITIES.some((item) => item.value === feedback.severity)) {
    errors.severity = '请选择严重程度';
  }
  if (!PLATFORMS.some((item) => item.value === feedback.platform)) {
    errors.platform = '请选择运行平台';
  }

  if (Object.keys(errors).length > 0) {
    return { valid: false, errors };
  }

  return { valid: true, value: { ...feedback } as ValidFeedback };
}
