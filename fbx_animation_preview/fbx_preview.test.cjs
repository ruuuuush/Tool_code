const { test } = require('node:test');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const path = require('node:path');
const { chromium } = require('playwright');

test('local FBX viewer loads animation, scrubs and switches files', { timeout: 120000 }, async () => {
  const server = spawn(process.execPath, [path.join(__dirname, 'fbx_preview_server.cjs')], {
    env: { ...process.env, PORT: '18765' }, stdio: ['ignore', 'pipe', 'pipe']
  });
  let browser;
  try {
    await new Promise((resolve, reject) => {
      server.stdout.once('data', resolve);
      server.once('error', reject);
      server.once('exit', code => reject(new Error(`Server exited: ${code}`)));
    });
    browser = await chromium.launch({
      executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
      headless: true, args: ['--enable-unsafe-swiftshader']
    });
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto('http://127.0.0.1:18765');
    await page.locator('#files').setInputFiles(path.join(__dirname, '..', 'walk.fbx'));
    await page.waitForFunction(() => !document.getElementById('play').disabled, { timeout: 60000 });
    assert.equal(await page.locator('#current-name').textContent(), 'walk.fbx');
    assert.equal(await page.locator('#file-count').textContent(), '1');
    assert.equal(await page.locator('#status').evaluate(node => node.classList.contains('error')), false);
    await page.locator('#play').click();
    assert.equal(await page.locator('#play').textContent(), '播放');
    await page.locator('#timeline').evaluate(node => {
      node.value = Number(node.max) / 2;
      node.dispatchEvent(new Event('input', { bubbles: true }));
    });
    const midpoint = Number(await page.locator('#timeline').inputValue());
    assert.ok(midpoint > 0);
    await page.locator('#restart').click();
    assert.equal(Number(await page.locator('#timeline').inputValue()), 0);
    await page.locator('#next-frame').click();
    assert.ok(Math.abs(Number(await page.locator('#timeline').inputValue()) - 1 / 30) < 0.001);
    assert.equal(await page.locator('#frame-number').textContent(), `帧 1 / ${Math.ceil(Number(await page.locator('#timeline').getAttribute('max')) * 30)}`);
    await page.keyboard.press('ArrowLeft');
    assert.equal(Number(await page.locator('#timeline').inputValue()), 0);
    await page.locator('#fps').selectOption('60');
    await page.locator('#restart').click();
    await page.keyboard.press('ArrowRight');
    assert.ok(Math.abs(Number(await page.locator('#timeline').inputValue()) - 1 / 60) < 0.001);
    await page.locator('#restart').click();
    await page.locator('#show-mesh').uncheck();
    await page.locator('#up-axis').selectOption('z');
    await page.locator('#frame').click();
    await page.locator('#search').fill('not-a-file');
    assert.equal(await page.locator('.file-item').count(), 0);
    await page.locator('#search').fill('');
    assert.equal(await page.locator('.file-item').count(), 1);
    await page.locator('#files').setInputFiles(path.join(__dirname, '..', 'Standard Walk.fbx'));
    await page.locator('#previous-file').click();
    await page.waitForFunction(() => document.getElementById('current-name').textContent === 'Standard Walk.fbx' && document.getElementById('loading').hidden, { timeout: 60000 });
    assert.equal(await page.locator('#status').evaluate(node => node.classList.contains('error')), false);
    assert.equal(await page.locator('#file-count').textContent(), '2');
    await page.locator('#show-mesh').check();
    await page.locator('#up-axis').selectOption('y');
    await page.locator('#play').click();
    assert.equal(await page.locator('#show-bones').isChecked(), false);
    const textured = await page.locator('#canvas').screenshot();
    await page.locator('#show-materials').uncheck();
    const gray = await page.locator('#canvas').screenshot();
    assert.notDeepEqual(gray, textured);
    await page.locator('#show-bones').check();
    const bones = await page.locator('#canvas').screenshot();
    assert.notDeepEqual(bones, gray);
    await page.locator('#show-bones').uncheck();
    await page.locator('#show-materials').check();
    const restored = await page.locator('#canvas').screenshot();
    assert.deepEqual(restored, textured);
    await page.locator('#show-materials').uncheck();
    await page.screenshot({ path: path.join(__dirname, 'fbx_preview_check.png') });
    await page.locator('#next-file').click();
    await page.waitForFunction(() => document.getElementById('current-name').textContent === 'walk.fbx' && document.getElementById('loading').hidden);
    await page.keyboard.press('PageUp');
    await page.waitForFunction(() => document.getElementById('current-name').textContent === 'Standard Walk.fbx' && document.getElementById('loading').hidden);
    await page.locator('#search').fill('Standard');
    assert.equal(await page.locator('#next-file').isDisabled(), true);
    assert.equal(await page.locator('#previous-file').isDisabled(), true);
    await page.locator('#search').fill('');
    const denied = await page.request.get('http://127.0.0.1:18765/walk.fbx');
    assert.equal(denied.status(), 404);
    if (process.env.FBX_REGRESSION_FILE) {
      const source = process.env.FBX_REGRESSION_FILE;
      const name = path.basename(source);
      await page.locator('#files').setInputFiles(source);
      await page.getByRole('button', { name: new RegExp(name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')) }).click();
      await page.waitForFunction(() => document.getElementById('loading').hidden);
      assert.equal(await page.locator('#current-name').textContent(), name);
      assert.equal(await page.locator('#status').evaluate(node => node.classList.contains('error')), false);
      assert.equal(await page.locator('#play').isDisabled(), false);
      await page.locator('#play').click();
      await page.locator('#timeline').evaluate(node => {
        node.value = Number(node.max) / 2;
        node.dispatchEvent(new Event('input', { bubbles: true }));
      });
      assert.ok(Number(await page.locator('#timeline').inputValue()) > 0);
      await page.screenshot({ path: path.join(__dirname, 'fbx_preview_check.png') });
    }
    assert.deepEqual(errors, []);
    console.log(await page.locator('#model-info').textContent());
    console.log(await page.locator('#status').textContent());
  } finally {
    await browser?.close();
    server.kill();
  }
});
