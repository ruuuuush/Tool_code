(function () {
  'use strict';

  const { EL, ELEMENT_META, ELEMENT_NAMES, SandWorld } = window.SandEngine;
  const { PRESETS } = window.SandPresets;
  const { SandAudioEngine } = window.SandAudio;
  const { SPELLS, SPELL_LIST, SPELL_CATEGORIES, COMBO_RECIPES } = window.WandSpells;
  const { NoitaController } = window.NoitaMode;

  const GRID_W = 400;
  const GRID_H = 240;
  const MAX_SLOTS = 10;

  const LIGHTNING_TOOL_ID = -1;
  const BOMB_TOOL_ID = -2;
  const VORTEX_TOOL_ID = -3;

  const CATEGORIES = [
    { id: 'powder', label: '粉体 / 生物' },
    { id: 'liquid', label: '流体 / 炼金' },
    { id: 'solid',  label: '建筑 / 机关' },
    { id: 'energy', label: '能量 / 神力工具' },
  ];

  const SPECIAL_TOOLS = [
    {
      id: LIGHTNING_TOOL_ID,
      key: 'lightning',
      name: '闪电',
      cat: 'energy',
      color: '#76e8ff',
      desc: '劈下分叉雷电，经金属/水面导电，将细沙熔成玻璃并引爆火药',
    },
    {
      id: BOMB_TOOL_ID,
      key: 'bomb',
      name: '物理炸弹',
      cat: 'energy',
      color: '#ff4f5e',
      desc: '抛出一颗带引信的弹跳炸弹，倒计时结束引爆并炸飞漫天碎片',
    },
    {
      id: VORTEX_TOOL_ID,
      key: 'vortex',
      name: '旋风卷流',
      cat: 'energy',
      color: '#9b8aff',
      desc: '按住产生高能漩涡，将周围沙水火药与星火卷上高空飞舞',
    },
  ];

  const PALETTE_ITEMS = [
    ...ELEMENT_META.filter((m) => m.id !== EL.EMPTY),
    ...SPECIAL_TOOLS,
    ELEMENT_META.find((m) => m.id === EL.EMPTY),
  ];

  const mainCanvas = document.getElementById('sim-canvas');
  const glowCanvas = document.getElementById('glow-canvas');
  const fxCanvas = document.getElementById('fx-canvas');
  const stageWrap = document.getElementById('stage-wrap');
  const stageShake = document.getElementById('stage-shake');

  mainCanvas.width = GRID_W;
  mainCanvas.height = GRID_H;
  glowCanvas.width = GRID_W;
  glowCanvas.height = GRID_H;
  fxCanvas.width = GRID_W;
  fxCanvas.height = GRID_H;

  const mainCtx = mainCanvas.getContext('2d', { alpha: false });
  const glowCtx = glowCanvas.getContext('2d', { alpha: true });
  const fxCtx = fxCanvas.getContext('2d', { alpha: true });

  const mainImage = mainCtx.createImageData(GRID_W, GRID_H);
  const glowImage = glowCtx.createImageData(GRID_W, GRID_H);
  const mainBuf32 = new Uint32Array(mainImage.data.buffer);
  const glowBuf32 = new Uint32Array(glowImage.data.buffer);

  const world = new SandWorld(GRID_W, GRID_H);
  const audio = new SandAudioEngine();
  const noita = new NoitaController(world, EL);

  const state = {
    mode: 'noita', // 'noita' | 'sandbox'
    craftOpen: false,
    selectedId: LIGHTNING_TOOL_ID,
    brushRadius: 6,
    paused: false,
    bloom: true,
    lighting: true,
    thermal: false,
    scatter: true,
    sound: true,
    speed: 1,
    isPointerDown: false,
    pointerButton: 0,
    lastGridX: -1,
    lastGridY: -1,
    hoverX: -1,
    hoverY: -1,
    lastActionTime: 0,
    activePresetId: 'noita_mine',
  };

  // DOM refs
  const paletteRoot = document.getElementById('palette-root');
  const presetRoot = document.getElementById('preset-root');
  const brushSlider = document.getElementById('brush-slider');
  const brushValue = document.getElementById('brush-value');
  const modeBtn = document.getElementById('btn-mode');
  const craftBtn = document.getElementById('btn-craft');
  const hudCraftBtn = document.getElementById('btn-hud-craft');
  const pauseBtn = document.getElementById('btn-pause');
  const stepBtn = document.getElementById('btn-step');
  const clearBtn = document.getElementById('btn-clear');
  const bloomBtn = document.getElementById('btn-bloom');
  const lightBtn = document.getElementById('btn-light');
  const thermalBtn = document.getElementById('btn-thermal');
  const gravityBtn = document.getElementById('btn-gravity');
  const windBtn = document.getElementById('btn-wind');
  const detonateBtn = document.getElementById('btn-detonate');
  const soundBtn = document.getElementById('btn-sound');
  const speedBtn = document.getElementById('btn-speed');
  const shotBtn = document.getElementById('btn-shot');
  const statFps = document.getElementById('stat-fps');
  const statParticles = document.getElementById('stat-particles');
  const statInspect = document.getElementById('stat-inspect');
  const activeNameEl = document.getElementById('active-name');
  const activeDescEl = document.getElementById('active-desc');
  const activeDotEl = document.getElementById('active-dot');
  const presetHintEl = document.getElementById('preset-hint');

  // Noita HUD DOM refs
  const noitaHud = document.getElementById('noita-hud');
  const hpFill = document.getElementById('hud-hp-fill');
  const hpText = document.getElementById('hud-hp-text');
  const flyFill = document.getElementById('hud-fly-fill');
  const manaFill = document.getElementById('hud-mana-fill');
  const statusRow = document.getElementById('hud-statuses');
  const wandSlotsRoot = document.getElementById('hud-wands');
  const killCountEl = document.getElementById('hud-kills');
  const deathOverlay = document.getElementById('death-overlay');
  const deathReasonEl = document.getElementById('death-reason');
  const respawnBtn = document.getElementById('btn-respawn');
  const spawnMonsterBtn = document.getElementById('btn-spawn-monsters');

  // Wand Crafting Modal DOM refs
  const craftModal = document.getElementById('craft-modal');
  const craftTabsRoot = document.getElementById('craft-wand-tabs');
  const craftSlotsRoot = document.getElementById('craft-slots');
  const craftSummaryEl = document.getElementById('craft-summary');
  const craftHoverEl = document.getElementById('craft-hover-desc');
  const craftRecipesRoot = document.getElementById('craft-recipes');
  const craftLibraryRoot = document.getElementById('craft-library');
  const craftClearBtn = document.getElementById('btn-craft-clear');
  const craftCloseBtn = document.getElementById('btn-craft-close');

  const btnById = new Map();

  function getItemMeta(id) {
    return PALETTE_ITEMS.find((x) => x.id === id) || PALETTE_ITEMS[0];
  }

  function updateActiveCard() {
    if (state.mode === 'noita') {
      const w = noita.getActiveWand();
      const comp = noita.getActiveCompiled();
      const icons = w.slots.map((id) => (SPELLS[id] ? SPELLS[id].name : '')).filter(Boolean).join(' → ');
      activeNameEl.textContent = w.name;
      activeDescEl.textContent = icons
        ? `${icons}（${comp.summary}）· 按 Tab 魔改法术组合`
        : '空魔杖 — 按 Tab 打开工坊装填法术卡';
      activeDotEl.style.background = w.color;
      activeDotEl.style.boxShadow = `0 0 12px ${w.color}`;
    } else {
      const meta = getItemMeta(state.selectedId);
      activeNameEl.textContent = meta.name;
      activeDescEl.textContent = meta.desc;
      activeDotEl.style.background = meta.color;
      activeDotEl.style.boxShadow = `0 0 12px ${meta.color}`;
    }
  }

  function renderWandHotbar() {
    wandSlotsRoot.innerHTML = '';
    noita.wands.forEach((w, idx) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'wand-slot' + (idx === noita.selectedWand ? ' active' : '');
      const chainIcons = w.slots
        .slice(0, 5)
        .map((id) => {
          const sp = SPELLS[id];
          return sp ? `<span class="mini-card" style="color:${sp.color}">${sp.icon}</span>` : '';
        })
        .join('');
      const more = w.slots.length > 5 ? `<span class="mini-more">+${w.slots.length - 5}</span>` : '';
      btn.title = `[${idx + 1}] ${w.name}（点击切换，按 Tab 编排法术）`;
      btn.innerHTML = `<span class="wand-key">${idx + 1}</span><span class="wand-gem" style="background:${w.color};box-shadow:0 0 8px ${w.color}"></span><span class="wand-chain">${chainIcons || '空'}${more}</span>`;
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        selectWand(idx);
      });
      wandSlotsRoot.appendChild(btn);
    });
  }

  function selectWand(index) {
    noita.selectedWand = (index + noita.wands.length) % noita.wands.length;
    renderWandHotbar();
    updateActiveCard();
    if (state.craftOpen) renderCraftModal();
  }

  function setCraftOpen(open) {
    state.craftOpen = open;
    craftModal.classList.toggle('visible', open);
    craftBtn.classList.toggle('is-wizard', open);
    if (open) {
      noita.firing = false;
      noita.keys.left = noita.keys.right = noita.keys.up = noita.keys.down = false;
      if (state.mode !== 'noita') setMode('noita');
      renderCraftModal();
    }
  }

  function renderCraftModal() {
    // 1. Wand selector tabs
    craftTabsRoot.innerHTML = '';
    noita.wands.forEach((w, idx) => {
      const tab = document.createElement('button');
      tab.type = 'button';
      tab.className = 'craft-tab' + (idx === noita.selectedWand ? ' active' : '');
      tab.innerHTML = `<span class="swatch" style="background:${w.color}"></span>${w.name}`;
      tab.addEventListener('click', () => selectWand(idx));
      craftTabsRoot.appendChild(tab);
    });

    // 2. Active wand 8 spell slots
    const wand = noita.getActiveWand();
    const compiled = noita.recompileWand(noita.selectedWand);
    craftSlotsRoot.innerHTML = '';

    for (let i = 0; i < MAX_SLOTS; i++) {
      const id = wand.slots[i];
      const sp = id ? SPELLS[id] : null;
      const slotEl = document.createElement('button');
      slotEl.type = 'button';
      slotEl.className = 'spell-slot' + (sp ? ' filled' : '');
      if (sp) {
        slotEl.style.borderColor = `${sp.color}aa`;
        slotEl.style.boxShadow = `inset 0 0 14px ${sp.color}22`;
        slotEl.title = `${sp.name}（点击移除）：${sp.desc}`;
        slotEl.innerHTML = `<span class="slot-idx">${i + 1}</span><span class="slot-icon" style="color:${sp.color}">${sp.icon}</span><span class="slot-name">${sp.name}</span><span class="slot-rm">×</span>`;
        slotEl.addEventListener('click', () => {
          wand.slots.splice(i, 1);
          noita.recompileWand(noita.selectedWand);
          renderCraftModal();
          renderWandHotbar();
          updateActiveCard();
        });
      } else {
        slotEl.innerHTML = `<span class="slot-idx">${i + 1}</span><span class="slot-empty">空槽</span>`;
      }
      craftSlotsRoot.appendChild(slotEl);

      if (i < MAX_SLOTS - 1) {
        const arrow = document.createElement('span');
        arrow.className = 'slot-arrow';
        arrow.textContent = '→';
        craftSlotsRoot.appendChild(arrow);
      }
    }

    craftSummaryEl.textContent = compiled.summary;

    // 3. One-click signature recipes
    craftRecipesRoot.innerHTML = '';
    for (const rec of COMBO_RECIPES) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'recipe-btn';
      btn.title = rec.desc;
      btn.innerHTML = `<span class="swatch" style="background:${rec.color};box-shadow:0 0 8px ${rec.color}"></span><span class="recipe-name">${rec.name}</span>`;
      btn.addEventListener('mouseenter', () => {
        craftHoverEl.textContent = `⚡ 配方【${rec.name}】：${rec.desc}`;
      });
      btn.addEventListener('click', () => {
        wand.slots = rec.slots.slice(0, MAX_SLOTS);
        wand.name = `${noita.selectedWand + 1} · ${rec.name}`;
        noita.recompileWand(noita.selectedWand);
        renderCraftModal();
        renderWandHotbar();
        updateActiveCard();
      });
      craftRecipesRoot.appendChild(btn);
    }

    // 4. Spell card library by category
    craftLibraryRoot.innerHTML = '';
    for (const cat of SPELL_CATEGORIES) {
      const sec = document.createElement('div');
      sec.className = 'lib-sec';

      const h = document.createElement('div');
      h.className = 'lib-title';
      h.textContent = cat.label;
      sec.appendChild(h);

      const grid = document.createElement('div');
      grid.className = 'lib-grid';

      const cards = SPELL_LIST.filter((s) => s.kind === cat.id);
      for (const sp of cards) {
        const card = document.createElement('button');
        card.type = 'button';
        card.className = 'spell-card';
        card.style.borderColor = `${sp.color}55`;
        card.title = `${sp.name}（蓝耗 ${sp.mana}）：${sp.desc}`;
        card.innerHTML = `
          <span class="card-icon" style="color:${sp.color};text-shadow:0 0 8px ${sp.color}88">${sp.icon}</span>
          <span class="card-meta">
            <span class="card-name">${sp.name}</span>
            <span class="card-cost">MP ${sp.mana}${sp.delay < 0 ? ' · 极速' : ''}</span>
          </span>`;
        card.addEventListener('mouseenter', () => {
          const delayTxt = sp.delay < 0 ? `冷却 ${sp.delay}f` : `冷却 +${sp.delay}f`;
          craftHoverEl.textContent = `${sp.icon} 【${sp.name}】 MP ${sp.mana} · ${delayTxt} — ${sp.desc}`;
        });
        card.addEventListener('click', () => {
          if (wand.slots.length >= MAX_SLOTS) return;
          wand.slots.push(sp.id);
          noita.recompileWand(noita.selectedWand);
          renderCraftModal();
          renderWandHotbar();
          updateActiveCard();
        });
        grid.appendChild(card);
      }

      sec.appendChild(grid);
      craftLibraryRoot.appendChild(sec);
    }
  }

  function setMode(newMode) {
    state.mode = newMode;
    noita.enabled = newMode === 'noita';
    noita.firing = false;
    noita.keys.left = noita.keys.right = noita.keys.up = noita.keys.down = false;

    if (newMode === 'noita') {
      if (noita.player.dead) {
        const preset = PRESETS.find((p) => p.id === state.activePresetId);
        const sp = preset && preset.spawn ? preset.spawn : { x: 60, y: 50 };
        noita.spawnPlayer(sp.x, sp.y);
      } else if (noita.collidesBox(noita.player.x, noita.player.y, noita.player.w, noita.player.h)) {
        noita.spawnPlayer(noita.player.x, noita.player.y);
      }
      stageWrap.style.cursor = 'none';
    } else {
      setCraftOpen(false);
      stageWrap.style.cursor = 'crosshair';
    }

    noitaHud.classList.toggle('visible', newMode === 'noita');
    modeBtn.textContent = newMode === 'noita' ? '🧙 法师模式 · 开' : '🎨 沙盒画笔';
    modeBtn.classList.toggle('is-wizard', newMode === 'noita');
    updateActiveCard();
  }

  function selectTool(id) {
    state.selectedId = id;
    for (const [itemId, btn] of btnById.entries()) {
      btn.classList.toggle('active', itemId === id);
    }
    if (state.mode === 'noita') {
      setMode('sandbox');
    } else {
      updateActiveCard();
    }
  }

  function buildPalette() {
    paletteRoot.innerHTML = '';
    for (const cat of CATEGORIES) {
      const group = document.createElement('div');
      group.className = 'pal-group';

      const title = document.createElement('div');
      title.className = 'pal-title';
      title.textContent = cat.label;
      group.appendChild(title);

      const grid = document.createElement('div');
      grid.className = 'pal-grid';

      const items = PALETTE_ITEMS.filter((item) => item.cat === cat.id);
      for (const item of items) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'el-btn';
        btn.title = `${item.name}：${item.desc}`;
        btn.innerHTML = `<span class="swatch" style="background:${item.color};box-shadow:0 0 8px ${item.color}88"></span><span class="el-label">${item.name}</span>`;
        btn.addEventListener('click', () => selectTool(item.id));
        grid.appendChild(btn);
        btnById.set(item.id, btn);
      }

      group.appendChild(grid);
      paletteRoot.appendChild(group);
    }
  }

  function loadPreset(presetId) {
    const preset = PRESETS.find((p) => p.id === presetId);
    if (!preset) return;
    state.activePresetId = presetId;
    world.gravityY = 1;
    world.windX = 0;
    noita.clearEntities();
    preset.build(world, EL);
    presetHintEl.textContent = preset.hint;

    const sp = preset.spawn || { x: 54, y: 42 };
    noita.spawnPlayer(sp.x, sp.y);
    if (preset.hasEnemies) {
      noita.populateDungeonEnemies();
    }

    updateToggleUI();
    presetRoot.querySelectorAll('.preset-btn').forEach((b) => {
      b.classList.toggle('active', b.dataset.preset === presetId);
    });
  }

  function buildPresets() {
    presetRoot.innerHTML = '';
    for (const preset of PRESETS) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'preset-btn';
      btn.dataset.preset = preset.id;
      btn.textContent = preset.name;
      btn.addEventListener('click', () => loadPreset(preset.id));
      presetRoot.appendChild(btn);
    }
  }

  function updateBrushUI() {
    brushSlider.value = String(state.brushRadius);
    brushValue.textContent = `${state.brushRadius}px`;
  }

  function updateToggleUI() {
    pauseBtn.textContent = state.paused ? '▶' : '⏸';
    pauseBtn.classList.toggle('is-warn', state.paused);

    bloomBtn.classList.toggle('is-on', state.bloom);
    glowCanvas.style.opacity = state.bloom ? '0.96' : '0';

    lightBtn.classList.toggle('is-on', state.lighting && !state.thermal);
    thermalBtn.classList.toggle('is-hot', state.thermal);

    soundBtn.textContent = state.sound ? '🔊' : '🔇';
    soundBtn.classList.toggle('is-on', state.sound);
    audio.enabled = state.sound;

    speedBtn.textContent = state.speed === 0.25 ? '0.25x' : `${state.speed}x`;
    speedBtn.classList.toggle('is-warn', state.speed !== 1);

    gravityBtn.textContent =
      world.gravityY === 1 ? '重力↓' : world.gravityY === -1 ? '重力↑' : '失重○';
    gravityBtn.classList.toggle('is-warn', world.gravityY !== 1);

    windBtn.textContent =
      world.windX === 0 ? '风0' : world.windX > 0 ? '风→' : '风←';
    windBtn.classList.toggle('is-on', world.windX !== 0);
  }

  function updateNoitaHUD() {
    if (state.mode !== 'noita') return;
    const p = noita.player;
    hpFill.style.width = `${Math.max(0, (p.hp / p.maxHp) * 100)}%`;
    hpText.textContent = `${Math.ceil(p.hp)} / ${p.maxHp}`;
    flyFill.style.width = `${Math.max(0, (p.flight / p.maxFlight) * 100)}%`;
    manaFill.style.width = `${Math.max(0, (p.mana / p.maxMana) * 100)}%`;
    killCountEl.textContent = `👾 ${noita.kills} · 剩余 ${noita.enemies.length}`;

    const tags = [];
    if (p.burning > 0) tags.push('<span class="stain stain-fire">🔥 着火</span>');
    if (p.acid > 0) tags.push('<span class="stain stain-acid">🧪 腐蚀</span>');
    if (p.oiled > 0) tags.push('<span class="stain stain-oil">🛢 沾油</span>');
    if (p.wet > 0) tags.push('<span class="stain stain-wet">💧 湿润</span>');
    if (p.frozen > 0) tags.push('<span class="stain stain-ice">❄ 极寒</span>');
    statusRow.innerHTML = tags.join('');

    deathOverlay.classList.toggle('visible', p.dead);
    if (p.dead) {
      deathReasonEl.textContent = `死因：${p.deathCause}`;
    }
  }

  function clientToGrid(clientX, clientY) {
    const rect = mainCanvas.getBoundingClientRect();
    const gx = Math.floor(((clientX - rect.left) / rect.width) * GRID_W);
    const gy = Math.floor(((clientY - rect.top) / rect.height) * GRID_H);
    return {
      x: Math.max(0, Math.min(GRID_W - 1, gx)),
      y: Math.max(0, Math.min(GRID_H - 1, gy)),
    };
  }

  function applySandboxTool(gx, gy, isDrag) {
    audio.ensureContext();
    const useEraser = state.pointerButton === 2 || state.selectedId === EL.EMPTY;
    const now = performance.now();

    if (!useEraser) {
      if (state.selectedId === LIGHTNING_TOOL_ID) {
        if (!isDrag || now - state.lastActionTime > 95) {
          world.strikeLightning(gx, gy);
          state.lastActionTime = now;
        }
        return;
      }
      if (state.selectedId === BOMB_TOOL_ID) {
        if (!isDrag || now - state.lastActionTime > 220) {
          const vx = isDrag && state.lastGridX >= 0 ? Math.max(-4, Math.min(4, (gx - state.lastGridX) * 0.35)) : (Math.random() - 0.5) * 1.6;
          const vy = isDrag && state.lastGridY >= 0 ? Math.max(-4, Math.min(2, (gy - state.lastGridY) * 0.35 - 1)) : -1.8;
          world.throwBomb(gx, gy, vx, vy);
          state.lastActionTime = now;
        }
        return;
      }
      if (state.selectedId === VORTEX_TOOL_ID) {
        world.applyVortex(gx, gy, Math.max(18, state.brushRadius * 3.2), false);
        return;
      }
      if (state.selectedId === EL.FIREWORK) {
        if (!isDrag || now - state.lastActionTime > 150) {
          world.paintCircle(gx, gy, 1, EL.FIREWORK, false);
          state.lastActionTime = now;
        }
        return;
      }
    }

    const el = useEraser ? EL.EMPTY : state.selectedId;
    const r = useEraser ? Math.max(2, state.brushRadius) : state.brushRadius;
    if (isDrag && state.lastGridX >= 0) {
      world.paintLine(state.lastGridX, state.lastGridY, gx, gy, r, el, state.scatter);
    } else {
      world.paintCircle(gx, gy, r, el, state.scatter);
    }
  }

  function renderFxOverlay() {
    fxCtx.clearRect(0, 0, GRID_W, GRID_H);

    for (let i = 0; i < world.shockwaves.length; i++) {
      const s = world.shockwaves[i];
      fxCtx.save();
      fxCtx.globalAlpha = s.alpha;
      fxCtx.strokeStyle = s.color;
      fxCtx.lineWidth = Math.max(1, 2.6 * s.alpha);
      fxCtx.beginPath();
      fxCtx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
      fxCtx.stroke();
      fxCtx.restore();
    }

    if (state.mode === 'noita') {
      noita.renderOverlay(fxCtx);
      return;
    }

    if (state.hoverX < 0 || state.hoverY < 0) return;
    const x = state.hoverX + 0.5;
    const y = state.hoverY + 0.5;
    const isErase = state.selectedId === EL.EMPTY || (state.isPointerDown && state.pointerButton === 2);

    fxCtx.save();
    if (!isErase && state.selectedId === LIGHTNING_TOOL_ID) {
      fxCtx.strokeStyle = 'rgba(118, 232, 255, 0.95)';
      fxCtx.lineWidth = 1;
      fxCtx.beginPath();
      fxCtx.moveTo(x - 6, y); fxCtx.lineTo(x + 6, y);
      fxCtx.moveTo(x, y - 6); fxCtx.lineTo(x, y + 6);
      fxCtx.stroke();
    } else if (!isErase && state.selectedId === VORTEX_TOOL_ID) {
      const r = Math.max(18, state.brushRadius * 3.2);
      fxCtx.strokeStyle = 'rgba(155, 138, 255, 0.85)';
      fxCtx.setLineDash([4, 3]);
      fxCtx.lineWidth = 1;
      fxCtx.beginPath();
      fxCtx.arc(x, y, r, 0, Math.PI * 2);
      fxCtx.stroke();
    } else if (!isErase && (state.selectedId === BOMB_TOOL_ID || state.selectedId === EL.FIREWORK)) {
      const meta = getItemMeta(state.selectedId);
      fxCtx.strokeStyle = meta.color;
      fxCtx.lineWidth = 1;
      fxCtx.beginPath();
      fxCtx.arc(x, y, 4.5, 0, Math.PI * 2);
      fxCtx.stroke();
    } else {
      const meta = getItemMeta(state.selectedId);
      fxCtx.strokeStyle = isErase ? 'rgba(255, 92, 92, 0.95)' : meta.color;
      fxCtx.lineWidth = 1;
      fxCtx.beginPath();
      fxCtx.arc(x, y, Math.max(1, state.brushRadius), 0, Math.PI * 2);
      fxCtx.stroke();
    }
    fxCtx.restore();
  }

  // Pointer interactions
  stageWrap.addEventListener('contextmenu', (e) => e.preventDefault());

  stageWrap.addEventListener('pointerdown', (e) => {
    if (state.craftOpen || e.target.closest('button') || e.target.closest('#craft-modal')) return;
    e.preventDefault();
    audio.ensureContext();
    stageWrap.setPointerCapture(e.pointerId);
    const pos = clientToGrid(e.clientX, e.clientY);
    state.hoverX = pos.x;
    state.hoverY = pos.y;
    noita.aimX = pos.x;
    noita.aimY = pos.y;

    if (state.mode === 'noita') {
      if (e.button === 2) {
        noita.castTeleport();
      } else {
        noita.firing = true;
        noita.castPrimary();
      }
      return;
    }

    state.isPointerDown = true;
    state.pointerButton = e.button;
    applySandboxTool(pos.x, pos.y, false);
    state.lastGridX = pos.x;
    state.lastGridY = pos.y;
  });

  stageWrap.addEventListener('pointermove', (e) => {
    if (state.craftOpen) return;
    const pos = clientToGrid(e.clientX, e.clientY);
    state.hoverX = pos.x;
    state.hoverY = pos.y;
    noita.aimX = pos.x;
    noita.aimY = pos.y;

    if (state.mode === 'sandbox' && state.isPointerDown) {
      applySandboxTool(pos.x, pos.y, true);
      state.lastGridX = pos.x;
      state.lastGridY = pos.y;
    }
  });

  function stopPointer() {
    state.isPointerDown = false;
    noita.firing = false;
    state.lastGridX = -1;
    state.lastGridY = -1;
  }

  stageWrap.addEventListener('pointerup', stopPointer);
  stageWrap.addEventListener('pointercancel', stopPointer);
  stageWrap.addEventListener('pointerleave', () => {
    state.hoverX = -1;
    state.hoverY = -1;
  });

  stageWrap.addEventListener(
    'wheel',
    (e) => {
      if (state.craftOpen) return;
      e.preventDefault();
      if (state.mode === 'noita') {
        selectWand(noita.selectedWand + (e.deltaY > 0 ? 1 : -1));
      } else {
        const delta = e.deltaY < 0 ? 1 : -1;
        state.brushRadius = Math.max(1, Math.min(26, state.brushRadius + delta));
        updateBrushUI();
      }
    },
    { passive: false }
  );

  // Controls
  modeBtn.addEventListener('click', () => setMode(state.mode === 'noita' ? 'sandbox' : 'noita'));
  craftBtn.addEventListener('click', () => setCraftOpen(!state.craftOpen));
  hudCraftBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    setCraftOpen(!state.craftOpen);
  });
  craftCloseBtn.addEventListener('click', () => setCraftOpen(false));
  craftClearBtn.addEventListener('click', () => {
    noita.getActiveWand().slots = [];
    noita.recompileWand(noita.selectedWand);
    renderCraftModal();
    renderWandHotbar();
    updateActiveCard();
  });

  respawnBtn.addEventListener('click', () => {
    const preset = PRESETS.find((p) => p.id === state.activePresetId);
    const sp = preset && preset.spawn ? preset.spawn : { x: 54, y: 42 };
    noita.spawnPlayer(sp.x, sp.y);
  });

  spawnMonsterBtn.addEventListener('click', () => {
    audio.ensureContext();
    noita.populateDungeonEnemies();
    if (state.mode !== 'noita') setMode('noita');
  });

  brushSlider.addEventListener('input', () => {
    state.brushRadius = Number(brushSlider.value);
    updateBrushUI();
  });

  pauseBtn.addEventListener('click', () => { state.paused = !state.paused; updateToggleUI(); });
  stepBtn.addEventListener('click', () => {
    state.paused = true;
    updateToggleUI();
    world.step();
    noita.step();
  });
  clearBtn.addEventListener('click', () => {
    world.clear();
    noita.clearEntities();
    presetHintEl.textContent = '画布已清空 — 自由建造你的矿坑或炼金实验';
    presetRoot.querySelectorAll('.preset-btn').forEach((b) => b.classList.remove('active'));
  });
  bloomBtn.addEventListener('click', () => { state.bloom = !state.bloom; updateToggleUI(); });
  lightBtn.addEventListener('click', () => { state.thermal = false; state.lighting = !state.lighting; updateToggleUI(); });
  thermalBtn.addEventListener('click', () => { state.thermal = !state.thermal; updateToggleUI(); });
  gravityBtn.addEventListener('click', () => {
    const order = [1, 0, -1];
    world.gravityY = order[(order.indexOf(world.gravityY) + 1) % order.length];
    updateToggleUI();
  });
  windBtn.addEventListener('click', () => {
    const order = [0, 1, -1];
    world.windX = order[(order.indexOf(world.windX) + 1) % order.length];
    updateToggleUI();
  });
  detonateBtn.addEventListener('click', () => {
    audio.ensureContext();
    const n = world.detonateAllC4();
    if (n === 0) presetHintEl.textContent = '画布里还没有 C4 炸药：铺设 C4 或切「赛博电路爆破厂 / 诺伊塔矿坑」体验起爆！';
  });
  soundBtn.addEventListener('click', () => { state.sound = !state.sound; updateToggleUI(); });
  speedBtn.addEventListener('click', () => {
    const speeds = [1, 2, 0.25];
    state.speed = speeds[(speeds.indexOf(state.speed) + 1) % speeds.length];
    updateToggleUI();
  });

  shotBtn.addEventListener('click', () => {
    const out = document.createElement('canvas');
    out.width = GRID_W * 3;
    out.height = GRID_H * 3;
    const octx = out.getContext('2d');
    octx.imageSmoothingEnabled = false;
    octx.drawImage(mainCanvas, 0, 0, out.width, out.height);
    if (state.bloom) {
      octx.save();
      octx.globalCompositeOperation = 'screen';
      octx.filter = 'blur(12px)';
      octx.drawImage(glowCanvas, 0, 0, out.width, out.height);
      octx.restore();
    }
    octx.drawImage(fxCanvas, 0, 0, out.width, out.height);
    const link = document.createElement('a');
    link.download = `mini-noita-wand-${Date.now()}.png`;
    link.href = out.toDataURL('image/png');
    link.click();
  });

  // Keyboard bindings
  const SANDBOX_HOTKEYS = [
    EL.SAND, EL.WATER, EL.FIRE, EL.LAVA, EL.GUNPOWDER, EL.C4, EL.NITROGEN, EL.FIREWORK, LIGHTNING_TOOL_ID,
  ];

  window.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT') return;
    const k = e.key.toLowerCase();

    if (e.key === 'Tab') {
      e.preventDefault();
      setCraftOpen(!state.craftOpen);
      return;
    }
    if (e.key === 'Escape' && state.craftOpen) {
      setCraftOpen(false);
      return;
    }
    if (state.craftOpen) return;

    if (k === 'n') {
      setMode(state.mode === 'noita' ? 'sandbox' : 'noita');
      return;
    }

    if (state.mode === 'noita') {
      if (k === 'a' || e.key === 'ArrowLeft') { noita.keys.left = true; return; }
      if (k === 'd' || e.key === 'ArrowRight') { noita.keys.right = true; return; }
      if (k === 'w' || e.key === 'ArrowUp' || e.code === 'Space') {
        e.preventDefault();
        noita.keys.up = true;
        return;
      }
      if (k === 's' || e.key === 'ArrowDown') { noita.keys.down = true; return; }
      if (k === 'r' && noita.player.dead) {
        const preset = PRESETS.find((p) => p.id === state.activePresetId);
        const sp = preset && preset.spawn ? preset.spawn : { x: 54, y: 42 };
        noita.spawnPlayer(sp.x, sp.y);
        return;
      }
      if (e.key >= '1' && e.key <= '4') {
        selectWand(Number(e.key) - 1);
        return;
      }
    }

    if (e.code === 'Space' || k === 'p') {
      e.preventDefault();
      state.paused = !state.paused;
      updateToggleUI();
    } else if (k === 'c') {
      world.clear();
      noita.clearEntities();
    } else if (k === 'x') {
      audio.ensureContext();
      world.detonateAllC4();
    } else if (k === 't') {
      state.thermal = !state.thermal;
      updateToggleUI();
    } else if (k === 'l') {
      state.thermal = false;
      state.lighting = !state.lighting;
      updateToggleUI();
    } else if (k === 'g') {
      state.bloom = !state.bloom;
      updateToggleUI();
    } else if (k === 'm') {
      state.sound = !state.sound;
      updateToggleUI();
    } else if (state.mode === 'sandbox') {
      if (k === 's') { state.paused = true; updateToggleUI(); world.step(); }
      else if (k === 'r') {
        const order = [1, 0, -1];
        world.gravityY = order[(order.indexOf(world.gravityY) + 1) % order.length];
        updateToggleUI();
      } else if (k === 'w') {
        const order = [0, 1, -1];
        world.windX = order[(order.indexOf(world.windX) + 1) % order.length];
        updateToggleUI();
      } else if (e.key === '[') { state.brushRadius = Math.max(1, state.brushRadius - 1); updateBrushUI(); }
      else if (e.key === ']') { state.brushRadius = Math.min(26, state.brushRadius + 1); updateBrushUI(); }
      else if (k === 'e' || e.key === '0') selectTool(EL.EMPTY);
      else if (e.key >= '1' && e.key <= '9') selectTool(SANDBOX_HOTKEYS[Number(e.key) - 1]);
    }
  });

  window.addEventListener('keyup', (e) => {
    const k = e.key.toLowerCase();
    if (k === 'a' || e.key === 'ArrowLeft') noita.keys.left = false;
    if (k === 'd' || e.key === 'ArrowRight') noita.keys.right = false;
    if (k === 'w' || e.key === 'ArrowUp' || e.code === 'Space') noita.keys.up = false;
    if (k === 's' || e.key === 'ArrowDown') noita.keys.down = false;
  });

  // Main animation loop
  let fpsFrames = 0;
  let fpsTimer = performance.now();
  let slowAccum = 0;

  function tickLoop(now) {
    if (state.mode === 'sandbox' && !state.craftOpen && state.isPointerDown && state.hoverX >= 0 && state.hoverY >= 0) {
      applySandboxTool(state.hoverX, state.hoverY, true);
    }

    if (!state.paused && !state.craftOpen) {
      if (state.speed === 2) {
        world.step(); noita.step();
        world.step(); noita.step();
      } else if (state.speed === 0.25) {
        slowAccum++;
        if ((slowAccum & 3) === 0) {
          world.step(); noita.step();
        }
      } else {
        world.step();
        noita.step();
      }
    }

    const events = world.consumeEvents();
    if (events.length > 0) audio.playEvents(events);

    if (world.shake > 0.15) {
      const sx = ((Math.random() - 0.5) * world.shake).toFixed(1);
      const sy = ((Math.random() - 0.5) * world.shake).toFixed(1);
      stageShake.style.transform = `translate3d(${sx}px, ${sy}px, 0)`;
    } else {
      stageShake.style.transform = 'none';
    }

    const extraLights = noita.collectLights();
    world.render(mainBuf32, state.bloom ? glowBuf32 : null, {
      lighting: state.lighting,
      thermal: state.thermal,
      extraLights,
    });
    mainCtx.putImageData(mainImage, 0, 0);
    if (state.bloom) glowCtx.putImageData(glowImage, 0, 0);
    renderFxOverlay();
    updateNoitaHUD();

    if (state.hoverX >= 0 && state.hoverY >= 0) {
      const hoveredEl = world.get(state.hoverX, state.hoverY);
      const tempC = Math.round(world.getTemp(state.hoverX, state.hoverY));
      statInspect.textContent = `${ELEMENT_NAMES[hoveredEl] || '未知'} · ${tempC}°C (${state.hoverX}, ${state.hoverY})`;
    } else {
      statInspect.textContent = '移入画布探测元素与温度';
    }

    fpsFrames++;
    if (now - fpsTimer >= 350) {
      const fps = Math.round((fpsFrames * 1000) / (now - fpsTimer));
      statFps.textContent = `${fps} FPS`;
      statParticles.textContent = `${world.activeCount.toLocaleString()} 粒子`;
      fpsFrames = 0;
      fpsTimer = now;
    }

    requestAnimationFrame(tickLoop);
  }

  buildPalette();
  buildPresets();
  renderWandHotbar();
  selectWand(0);
  loadPreset('noita_mine');
  setMode('noita');
  updateBrushUI();
  updateToggleUI();
  requestAnimationFrame(tickLoop);
})();
