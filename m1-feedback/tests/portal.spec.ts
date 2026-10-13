import { expect, test, type Page } from '@playwright/test';
import { readFile } from 'node:fs/promises';

const image = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jC1sAAAAASUVORK5CYII=', 'base64');

async function enter(page: Page) {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: '欢迎来到回放室' })).toBeVisible();
  await page.getByRole('button', { name: '使用演示身份进入' }).click();
  await expect(page.getByRole('heading', { name: '回放问题，让好球继续。', exact: true })).toBeVisible();
}

async function fill(page: Page) {
  await page.getByLabel('问题标题').fill('射门结束后角色停顿');
  await page.getByRole('radio', { name: /球员动作与动画/ }).check();
  await page.getByLabel('游戏版本 / Build').fill('测试 Build / 中文');
  await page.getByLabel('运行平台').selectOption('windows');
  await page.getByLabel('问题描述').fill('动作结束后没有立即响应下一次移动输入。');
  await page.getByLabel('实际结果').fill('角色短暂停顿。');
}

test('complete local feedback flow, attachment lifecycle and no remote requests', async ({ page }) => {
  const pageErrors: string[] = [];
  const remoteRequests: string[] = [];
  page.on('pageerror', (error) => pageErrors.push(error.message));
  page.on('request', (request) => {
    if (/^https?:/.test(request.url()) && new URL(request.url()).hostname !== '127.0.0.1') remoteRequests.push(request.url());
  });
  await page.addInitScript(() => {
    const record = { created: [] as string[], revoked: [] as string[] };
    (window as unknown as { urlRecord: typeof record }).urlRecord = record;
    const create = URL.createObjectURL.bind(URL);
    const revoke = URL.revokeObjectURL.bind(URL);
    URL.createObjectURL = (object) => {
      const url = create(object);
      record.created.push(url);
      return url;
    };
    URL.revokeObjectURL = (url) => {
      record.revoked.push(url);
      revoke(url);
    };
  });
  await enter(page);
  await page.getByRole('button', { name: '预览并模拟提交' }).click();
  await expect(page.getByText('请填写问题标题', { exact: true })).toBeVisible();
  await expect(page.getByLabel('问题标题')).toBeFocused();
  await fill(page);
  await page.getByText('补充复现步骤与预期结果', { exact: false }).click();
  await page.getByLabel('复现步骤').fill('执行射门\n紧接着输入移动');
  await page.getByLabel('预期结果').fill('正常响应移动输入');
  await page.locator('#evidence-files').setInputFiles([
    { name: '现场.png', mimeType: 'image/png', buffer: image },
    { name: '回放.mov', mimeType: 'video/quicktime', buffer: Buffer.from('unsupported demo codec') },
  ]);
  await expect(page.getByRole('img', { name: '证据图片：现场.png' })).toBeVisible();
  await expect(page.getByText('当前浏览器无法播放，文件仍可作为附件')).toBeVisible();
  await page.getByRole('button', { name: '移除 现场.png' }).click();
  await expect(page.getByRole('img', { name: '证据图片：现场.png' })).toHaveCount(0);
  await page.getByRole('button', { name: '预览并模拟提交' }).click();
  await expect(page.getByRole('heading', { name: '回放确认，准备就绪。', exact: true })).toBeFocused();
  const json = page.getByRole('code');
  let payload = JSON.parse(await json.innerText());
  expect(payload.attachments).toHaveLength(1);
  expect(payload.attachments[0]).toMatchObject({ name: '回放.mov', kind: 'video', uploadStatus: 'local-only' });
  expect(await json.innerText()).not.toContain('blob:');
  await page.getByRole('button', { name: '返回修改' }).click();
  await expect(page.getByLabel('问题标题')).toHaveValue('射门结束后角色停顿');
  await expect(page.getByLabel('复现步骤')).toHaveValue('执行射门\n紧接着输入移动');
  await expect(page.getByRole('button', { name: '移除 回放.mov' })).toBeVisible();
  await page.getByRole('radio', { name: /足球与碰撞物理/ }).check();
  await page.getByRole('button', { name: '预览并模拟提交' }).click();
  payload = JSON.parse(await json.innerText());
  expect(payload.category).toBe('physics');
  await page.getByRole('button', { name: '确认模拟提交' }).click();
  await expect(page.getByRole('button', { name: '正在模拟提交…' })).toBeDisabled();
  await expect(page.getByRole('heading', { name: '模拟问题单已生成。', exact: true })).toBeVisible();
  await expect(page.getByText('未提交易协作 · 附件未上传', { exact: true })).toBeVisible();
  page.once('dialog', (dialog) => dialog.accept());
  await page.getByRole('button', { name: '创建另一条反馈' }).click();
  await expect(page.getByLabel('问题标题')).toHaveValue('');
  await expect(page.getByRole('radio', { name: /一般/ })).toBeChecked();
  await expect(page.getByRole('button', { name: '移除 回放.mov' })).toHaveCount(0);
  const urls = await page.evaluate(() => (window as unknown as { urlRecord: { created: string[]; revoked: string[] } }).urlRecord);
  expect(urls.created).toHaveLength(2);
  expect(new Set(urls.revoked)).toEqual(new Set(urls.created));
  await page.getByRole('button', { name: '退出', exact: true }).click();
  await expect(page.getByRole('heading', { name: '欢迎来到回放室' })).toBeVisible();
  expect(remoteRequests).toEqual([]);
  expect(pageErrors).toEqual([]);
  expect(await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length }))).toEqual({ local: 0, session: 0 });
});

test('refresh, cancelled logout and invalid optional detail keep correct state', async ({ page }) => {
  await enter(page);
  await fill(page);
  page.once('dialog', (dialog) => dialog.dismiss());
  await page.getByRole('button', { name: '退出', exact: true }).click();
  await expect(page.getByLabel('问题标题')).toHaveValue('射门结束后角色停顿');
  await page.getByText('补充复现步骤与预期结果', { exact: false }).click();
  await page.getByLabel('复现步骤').fill('步'.repeat(3001));
  await page.getByText('补充复现步骤与预期结果', { exact: false }).click();
  await page.getByRole('button', { name: '预览并模拟提交' }).click();
  await expect(page.getByText('复现步骤最多 3000 字符', { exact: true })).toBeVisible();
  await expect(page.getByLabel('复现步骤')).toBeFocused();
  await page.reload();
  await expect(page.getByRole('button', { name: '使用演示身份进入' })).toBeVisible();
  await page.getByRole('button', { name: '使用演示身份进入' }).click();
  await expect(page.getByLabel('问题标题')).toHaveValue('');
});

test('black red white theme keeps readable red actions across all screens', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  const theme = await page.evaluate(() => {
    const styles = getComputedStyle(document.documentElement);
    return {
      background: styles.getPropertyValue('--bg').trim(),
      accent: styles.getPropertyValue('--accent').trim(),
      text: styles.color,
      browserTheme: document.querySelector('meta[name="theme-color"]')?.getAttribute('content'),
    };
  });
  expect(theme).toEqual({ background: '#09090b', accent: '#ff4054', text: 'rgb(255, 255, 255)', browserTheme: '#09090B' });
  await expect(page.locator('.pitch-svg path[stroke="#ff4054"]')).toHaveCount(2);
  const entry = page.getByRole('button', { name: '使用演示身份进入' });
  await expect(entry).toHaveCSS('color', 'rgb(255, 255, 255)');
  await expect(entry).toHaveCSS('background-color', 'rgb(227, 35, 60)');
  for (const hovered of [false, true]) {
    if (hovered) await entry.hover();
    const contrast = await entry.evaluate((element) => {
      const styles = getComputedStyle(element);
      const luminance = (color: string) => {
        const channels = color.match(/[\d.]+/g)!.slice(0, 3).map((value) => Number(value) / 255)
          .map((value) => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4);
        return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
      };
      const foreground = luminance(styles.color);
      const background = luminance(styles.backgroundColor);
      return (Math.max(foreground, background) + 0.05) / (Math.min(foreground, background) + 0.05);
    });
    expect(contrast).toBeGreaterThanOrEqual(4.5);
  }
  await expect(entry).toHaveCSS('background-color', 'rgb(201, 29, 50)');
  await entry.click();
  await fill(page);
  await expect(page.locator('.category-option.is-selected')).toHaveCSS('border-top-color', 'rgba(255, 64, 84, 0.6)');
  await expect(page.locator('.scoreboard strong').first()).toHaveCSS('color', 'rgb(255, 255, 255)');
  await expect(page.getByRole('button', { name: '预览并模拟提交' })).toHaveCSS('color', 'rgb(255, 255, 255)');
  await page.getByRole('button', { name: '预览并模拟提交' }).click();
  await expect(page.getByRole('button', { name: '确认模拟提交' })).toHaveCSS('color', 'rgb(255, 255, 255)');
  await expect(page.getByLabel('通用问题单 JSON 数据')).toHaveCSS('color', 'rgb(217, 217, 223)');
  await page.getByRole('button', { name: '确认模拟提交' }).click();
  await expect(page.getByRole('heading', { name: '模拟问题单已生成。', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: '创建另一条反馈' })).toHaveCSS('color', 'rgb(255, 255, 255)');
});

for (const width of [1440, 768, 360]) {
  test(`responsive ${width}px and reduced motion`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto('/');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await expect(page.getByRole('button', { name: '使用演示身份进入' })).toBeVisible();
    const buttonBox = await page.getByRole('button', { name: '使用演示身份进入' }).boundingBox();
    expect(buttonBox!.height).toBeGreaterThanOrEqual(44);
    await page.screenshot({ path: test.info().outputPath(`login-${width}.png`), fullPage: true });
    await page.getByRole('button', { name: '使用演示身份进入' }).click();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    const form = await page.locator('.form-sections').boundingBox();
    const summary = await page.getByRole('complementary').boundingBox();
    if (width >= 1100) expect(summary!.x).toBeGreaterThan(form!.x + form!.width);
    else expect(summary!.y).toBeGreaterThan(form!.y + form!.height);
    expect(await page.locator('.pitch-glow').first().evaluate((element) => getComputedStyle(element).animationName)).toBe('none');
    const touchTargets = await page.locator('.button-primary, .button-secondary, .button-quiet, .category-option, .severity-option').evaluateAll((elements) => elements.every((element) => {
      const box = element.getBoundingClientRect();
      return box.width >= 44 && box.height >= 44;
    }));
    expect(touchTargets).toBe(true);
    await page.screenshot({ path: test.info().outputPath(`form-${width}.png`), fullPage: true });
    await fill(page);
    await page.getByRole('button', { name: '预览并模拟提交' }).click();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: test.info().outputPath(`preview-${width}.png`), fullPage: true });
  });
}

test('keyboard navigation completes selection, media preview and simulated submission', async ({ page }) => {
  await page.goto('/');
  await page.keyboard.press('Tab');
  await expect(page.getByRole('button', { name: '使用演示身份进入' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { name: '回放问题，让好球继续。', exact: true })).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.getByLabel('问题标题')).toBeFocused();
  await page.keyboard.type('Keyboard report');
  await page.keyboard.press('Tab');
  await expect(page.getByRole('radio', { name: /操作与比赛规则/ })).toBeFocused();
  await page.keyboard.press('Space');
  await page.keyboard.press('ArrowRight');
  await expect(page.getByRole('radio', { name: /球员动作与动画/ })).toBeChecked();
  expect(await page.getByRole('radio', { name: /球员动作与动画/ }).evaluate((element) => getComputedStyle(element.parentElement!).outlineWidth)).toBe('2px');
  await page.keyboard.press('Tab');
  await expect(page.getByRole('radio', { name: /一般/ })).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.getByLabel('游戏版本 / Build')).toBeFocused();
  await page.keyboard.type('keyboard-build');
  await page.keyboard.press('Tab');
  await expect(page.getByLabel('运行平台')).toBeFocused();
  await page.keyboard.press('ArrowDown');
  await page.keyboard.press('Tab');
  await expect(page.getByLabel('设备信息')).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.getByLabel('发生场景')).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.getByLabel('问题描述')).toBeFocused();
  await page.keyboard.type('Movement pauses after shooting.');
  await page.keyboard.press('Tab');
  await expect(page.getByLabel('实际结果')).toBeFocused();
  await page.keyboard.type('Player stops.');
  await page.keyboard.press('Tab');
  await page.keyboard.press('Enter');
  await page.keyboard.press('Tab');
  await expect(page.getByLabel('复现步骤')).toBeFocused();
  await page.keyboard.type('Shoot then move.');
  await page.keyboard.press('Tab');
  await expect(page.getByLabel('预期结果')).toBeFocused();
  await page.keyboard.type('Player moves.');
  await page.keyboard.press('Tab');
  await expect(page.getByRole('button', { name: '选择图片或视频' })).toBeFocused();
  const chooser = page.waitForEvent('filechooser');
  await page.keyboard.press('Enter');
  await (await chooser).setFiles({ name: 'keyboard.png', mimeType: 'image/png', buffer: image });
  await page.keyboard.press('Tab');
  await expect(page.getByRole('button', { name: '移除 keyboard.png' })).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.getByRole('button', { name: '预览并模拟提交' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { name: '回放确认，准备就绪。', exact: true })).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.getByLabel('通用问题单 JSON 数据')).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.getByRole('button', { name: '返回修改' })).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.getByRole('button', { name: '确认模拟提交' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { name: '模拟问题单已生成。', exact: true })).toBeFocused();
});

test('local video playback survives preview and editing', async ({ page }) => {
  await enter(page);
  await fill(page);
  const recorded = await readFile(new URL('./replay.webm', import.meta.url));
  await page.locator('#evidence-files').setInputFiles({ name: '可播放.webm', mimeType: 'video/webm', buffer: recorded });
  const video = page.locator('video');
  await expect.poll(() => video.evaluate((element) => (element as HTMLVideoElement).videoWidth)).toBeGreaterThan(0);
  await video.evaluate((element) => (element as HTMLVideoElement).play());
  await expect.poll(() => video.evaluate((element) => (element as HTMLVideoElement).currentTime)).toBeGreaterThan(0);
  await page.getByRole('button', { name: '预览并模拟提交' }).click();
  await page.getByRole('button', { name: '返回修改' }).click();
  await expect.poll(() => video.evaluate((element) => (element as HTMLVideoElement).videoWidth)).toBeGreaterThan(0);
  await expect(page.getByText('当前浏览器无法播放，文件仍可作为附件')).toHaveCount(0);
});

test('confirming logout clears input and releases local evidence', async ({ page }) => {
  await page.addInitScript(() => {
    const record = { created: [] as string[], revoked: [] as string[] };
    (window as unknown as { urlRecord: typeof record }).urlRecord = record;
    const create = URL.createObjectURL.bind(URL);
    const revoke = URL.revokeObjectURL.bind(URL);
    URL.createObjectURL = (object) => {
      const url = create(object);
      record.created.push(url);
      return url;
    };
    URL.revokeObjectURL = (url) => {
      record.revoked.push(url);
      revoke(url);
    };
  });
  await enter(page);
  await page.getByLabel('问题标题').fill('退出测试');
  await page.locator('#evidence-files').setInputFiles({ name: 'logout.png', mimeType: 'image/png', buffer: image });
  page.once('dialog', (dialog) => dialog.accept());
  await page.getByRole('button', { name: '退出', exact: true }).click();
  await expect(page.getByRole('button', { name: '使用演示身份进入' })).toBeVisible();
  const urls = await page.evaluate(() => (window as unknown as { urlRecord: { created: string[]; revoked: string[] } }).urlRecord);
  expect(new Set(urls.created)).toEqual(new Set(urls.revoked));
  await page.getByRole('button', { name: '使用演示身份进入' }).click();
  await expect(page.getByLabel('问题标题')).toHaveValue('');
  await expect(page.getByRole('button', { name: '移除 logout.png' })).toHaveCount(0);
});

test('dragged mixed files are checked sequentially without clearing valid evidence', async ({ page }) => {
  await enter(page);
  const data = await page.evaluateHandle(() => {
    const transfer = new DataTransfer();
    transfer.items.add(new File(['sample'], '拖入.png', { type: 'image/png' }));
    transfer.items.add(new File(['unsupported'], '拒绝.exe', { type: 'application/octet-stream' }));
    return transfer;
  });
  await page.locator('.drop-zone').dispatchEvent('drop', { dataTransfer: data });
  await expect(page.getByRole('button', { name: '移除 拖入.png' })).toBeVisible();
  await expect(page.getByRole('alert')).toContainText('拒绝.exe');
  await page.locator('#evidence-files').setInputFiles([]);
  await expect(page.getByRole('button', { name: '移除 拖入.png' })).toBeVisible();
  await data.dispose();
});
