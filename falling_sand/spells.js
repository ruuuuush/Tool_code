(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.WandSpells = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const SPELLS = {
    // ================= PROJECTILES & SUMMONS (16) =================
    spark_bolt: {
      id: 'spark_bolt', kind: 'projectile', name: '火花弹', icon: '✦',
      color: '#c47bff', mana: 5, delay: 5, speed: 6.6, life: 70, damage: 12,
      desc: '高速低耗紫光弹，绝佳的触发器载体或速射子弹',
    },
    firebolt: {
      id: 'firebolt', kind: 'projectile', name: '爆破火球', icon: '🔥',
      color: '#ff7a24', mana: 14, delay: 11, speed: 5.2, life: 95, damage: 26,
      desc: '命中剧烈爆破、炸飞沙石碎片并点燃油木',
    },
    chain_bolt: {
      id: 'chain_bolt', kind: 'projectile', name: '链式闪电', icon: '⚡',
      color: '#6ce8ff', mana: 20, delay: 15, speed: 0, life: 1, damage: 34,
      desc: '瞬发分叉高压电弧，导电引爆金属/水体连接的火药与 C4',
    },
    blackhole: {
      id: 'blackhole', kind: 'projectile', name: '奇点黑洞', icon: '🕳',
      color: '#ba5cff', mana: 36, delay: 28, speed: 1.45, life: 150, damage: 8,
      desc: '缓慢推进吞噬沿途一切地形，叠加轨迹或消亡触发极其恐怖',
    },
    acid_ball: {
      id: 'acid_ball', kind: 'projectile', name: '强酸球', icon: '🧪',
      color: '#6aff44', mana: 11, delay: 9, speed: 4.6, life: 80, damage: 14,
      desc: '落地溅射荧光强酸与毒雾，融穿岩石与敌怪',
    },
    sawblade: {
      id: 'sawblade', kind: 'projectile', name: '回旋锯片', icon: '⚙',
      color: '#e0e9ff', mana: 14, delay: 12, speed: 5.8, life: 95, damage: 28,
      desc: '高速切木切怪并在片刻后回旋飞回！小心切到自己',
    },
    firework_spell: {
      id: 'firework_spell', kind: 'projectile', name: '烟花星弹', icon: '🎆',
      color: '#ff52c8', mana: 15, delay: 12, speed: 4.8, life: 60, damage: 18,
      desc: '命中或到期炸出绚烂彩色星雨，点亮暗穴并引燃可燃物',
    },
    cryo_orb: {
      id: 'cryo_orb', kind: 'projectile', name: '液氮寒球', icon: '❄',
      color: '#88f4ff', mana: 12, delay: 9, speed: 4.8, life: 80, damage: 14,
      desc: '命中释放 -196°C 液氮，瞬间冻结水潭与岩浆',
    },
    nuke: {
      id: 'nuke', kind: 'projectile', name: '微型核弹', icon: '☢',
      color: '#ffe84a', mana: 62, delay: 42, speed: 3.4, life: 110, damage: 95,
      desc: 'Noita 终极禁术！超大半径毁灭核爆，震塌洞穴并溅射熔岩火海',
    },
    plasma_cross: {
      id: 'plasma_cross', kind: 'projectile', name: '等离子十字', icon: '✚',
      color: '#ff4fd8', mana: 24, delay: 18, speed: 4.0, life: 22, damage: 18,
      desc: '落点展开旋转四向高能切割激光，切穿一切岩石与血肉（含自己！）',
    },
    meteor: {
      id: 'meteor', kind: 'projectile', name: '天外陨石', icon: '☄',
      color: '#ff5424', mana: 34, delay: 24, speed: 6.2, life: 110, damage: 52,
      desc: '从高空召唤巨型燃烧陨石砸向准星，沿途喷岩浆并轰出陨石坑',
    },
    rain_cloud: {
      id: 'rain_cloud', kind: 'projectile', name: '雷雨乌云', icon: '⛈',
      color: '#5eaaff', mana: 22, delay: 18, speed: 3.6, life: 20, damage: 0,
      desc: '在目标处召唤悬停雷暴云，倾盆大雨灌池并随机劈下闪电',
    },
    acid_cloud: {
      id: 'acid_cloud', kind: 'projectile', name: '酸雨毒云', icon: '☁',
      color: '#7dff4a', mana: 28, delay: 22, speed: 3.6, life: 20, damage: 0,
      desc: '召唤漂浮强酸毒云，持续浇灌腐蚀液融穿下方整片地层',
    },
    flamethrower: {
      id: 'flamethrower', kind: 'projectile', name: '烈焰喷射', icon: '🐉',
      color: '#ff942e', mana: 5, delay: 3, speed: 5.0, life: 24, damage: 8,
      desc: '高速连喷高压烈焰火流，配原油轨迹变身真正火焰喷射器',
    },
    teleport_spell: {
      id: 'teleport_spell', kind: 'projectile', name: '闪现传送弹', icon: '🌀',
      color: '#7bf5ff', mana: 14, delay: 12, speed: 7.4, life: 24, damage: 0,
      desc: '可编入魔杖的传送弹！可组合「传送+触发核爆/治愈/黑洞」神操作',
    },
    heal_bolt: {
      id: 'heal_bolt', kind: 'projectile', name: '治愈光弹', icon: '💚',
      color: '#4dff9b', mana: 18, delay: 16, speed: 4.2, life: 75, damage: 0,
      desc: '接触法师回复 +22 HP 并灭火解酸！搭配「强制回旋」或「弹跳」自奶',
    },

    // ================= TRIGGERS (4) =================
    trigger_hit: {
      id: 'trigger_hit', kind: 'trigger', name: '命中触发', icon: '◎', triggerType: 'hit',
      color: '#ff647c', mana: 5, delay: 2,
      desc: '下一颗弹丸撞墙/撞怪时，在落点自动释放后面的整条法术链',
    },
    trigger_timer: {
      id: 'trigger_timer', kind: 'trigger', name: '定时触发', icon: '⏱', triggerType: 'timer',
      color: '#ff8a5c', mana: 5, delay: 2,
      desc: '下一颗弹丸飞出 0.35 秒后在半空自动爆发后续法术链',
    },
    trigger_death: {
      id: 'trigger_death', kind: 'trigger', name: '消亡触发', icon: '💀', triggerType: 'death',
      color: '#e85cff', mana: 6, delay: 2,
      desc: '弹丸燃尽/消失的最后一刻才释放后续法术链（绝配黑洞/弹跳）',
    },
    trigger_double: {
      id: 'trigger_double', kind: 'trigger', name: '双倍触发', icon: '◈', triggerType: 'double_hit',
      color: '#ff3d6e', mana: 12, delay: 4,
      desc: '命中时将后续整条法术链连续双倍引爆！威力翻番',
    },

    // ================= MULTICAST & FORMATIONS (6) =================
    double: {
      id: 'double', kind: 'multicast', name: '双重施法', icon: '×2', count: 2, spread: 0.16,
      color: '#ffd147', mana: 2, delay: 2,
      desc: '将后续 2 个法术打包同时齐射',
    },
    triple: {
      id: 'triple', kind: 'multicast', name: '三重施法', icon: '×3', count: 3, spread: 0.28,
      color: '#ffb830', mana: 4, delay: 3,
      desc: '扇形同时齐射后续 3 个法术（共享前置修正器）',
    },
    quad: {
      id: 'quad', kind: 'multicast', name: '四重扇射', icon: '×4', count: 4, spread: 0.44,
      color: '#ffa224', mana: 6, delay: 4,
      desc: '宽扇形 4 连齐射，瞬间铺满视野弹幕',
    },
    bifurcate: {
      id: 'bifurcate', kind: 'multicast', name: '前后背射', icon: '⇄', count: 2, spread: Math.PI, ring: true,
      color: '#ffe066', mana: 2, delay: 1,
      desc: '朝前方与正后方同时发射，边逃命边向身后泼酸/埋雷',
    },
    hex: {
      id: 'hex', kind: 'multicast', name: '六芒星阵', icon: '✶6', count: 6, spread: Math.PI * 2, ring: true,
      color: '#ff9624', mana: 8, delay: 5,
      desc: '360° 环形爆发 6 发法术，与触发器搭配堪比星爆',
    },
    octa: {
      id: 'octa', kind: 'multicast', name: '八方灭世', icon: '✺8', count: 8, spread: Math.PI * 2, ring: true,
      color: '#ff6f1a', mana: 12, delay: 7,
      desc: '360° 八方向全向爆发 8 发法术，配合等离子十字/烟花清屏！',
    },

    // ================= MODIFIERS (14) =================
    homing: {
      id: 'homing', kind: 'modifier', name: '自动追踪', icon: '🎯',
      color: '#5ce6ff', mana: 7, delay: 1, mod: { homing: true },
      desc: '弹丸飞行中自动拐弯锁定附近敌怪',
    },
    bouncy: {
      id: 'bouncy', kind: 'modifier', name: '超强弹跳', icon: '⤴',
      color: '#6effb0', mana: 4, delay: 0, mod: { bounces: 5 },
      desc: '弹丸撞墙不爆，反弹 5 次满洞穴乱窜',
    },
    boomerang: {
      id: 'boomerang', kind: 'modifier', name: '强制回旋', icon: '🪃',
      color: '#a3ffcf', mana: 4, delay: 0, mod: { boomerang: true },
      desc: '让任意弹丸飞出后弯回法师身边！（配治愈光弹 = 完美自奶）',
    },
    split_air: {
      id: 'split_air', kind: 'modifier', name: '空中分裂', icon: '⑂',
      color: '#ff9ee8', mana: 10, delay: 3, mod: { splitAir: true },
      desc: '弹丸飞出片刻后自动一分为三裂变，与多重施法相乘指数级爆弹！',
    },
    orbit: {
      id: 'orbit', kind: 'modifier', name: '螺旋轨道', icon: '〰',
      color: '#a892ff', mana: 4, delay: 0, mod: { orbit: true },
      desc: '弹丸呈炫酷螺旋波浪轨迹飞行',
    },
    speed_up: {
      id: 'speed_up', kind: 'modifier', name: '超频速射', icon: '»',
      color: '#fff06b', mana: 2, delay: -6, mod: { speedMult: 1.55 },
      desc: '弹速 ×1.55 且大幅缩减魔杖冷却，变身机关枪',
    },
    pierce: {
      id: 'pierce', kind: 'modifier', name: '穿岩钻头', icon: '⛏',
      color: '#ffd088', mana: 6, delay: 1, mod: { pierce: 8 },
      desc: '弹丸凿穿沿途岩石与木头，边钻边溅射火花',
    },
    heavy_grav: {
      id: 'heavy_grav', kind: 'modifier', name: '重击迫击', icon: '⬇',
      color: '#ffad70', mana: 5, delay: 2, mod: { heavyGrav: true, powerMult: 1.55 },
      desc: '赋予抛物线重坠弹道，同时使伤害与爆破半径提升 55%！',
    },
    electric_arc: {
      id: 'electric_arc', kind: 'modifier', name: '闪电充能', icon: '🌩',
      color: '#7ef0ff', mana: 9, delay: 2, mod: { electricArc: true },
      desc: '弹丸周围持续放电，经过金属/水面直接通电引爆远处火药！',
    },
    water_trail: {
      id: 'water_trail', kind: 'modifier', name: '瀑布轨迹', icon: '💧',
      color: '#3aa4ff', mana: 5, delay: 0, mod: { trail: 'WATER' },
      desc: '弹丸沿途倾泻大量清水，灭火、淹火灵或配闪电充能造雷水暴',
    },
    oil_trail: {
      id: 'oil_trail', kind: 'modifier', name: '原油轨迹', icon: '🛢',
      color: '#b07442', mana: 5, delay: 1, mod: { trail: 'OIL' },
      desc: '弹丸飞行沿途不断泼洒易燃原油',
    },
    gunpowder_trail: {
      id: 'gunpowder_trail', kind: 'modifier', name: '火药轨迹', icon: '💣',
      color: '#8890a6', mana: 7, delay: 1, mod: { trail: 'GUNPOWDER' },
      desc: '弹丸沿途撒下火药粉带，再遇一丝火星整条路径连环起爆！',
    },
    acid_trail: {
      id: 'acid_trail', kind: 'modifier', name: '强酸轨迹', icon: '☣',
      color: '#72ff44', mana: 8, delay: 2, mod: { trail: 'ACID' },
      desc: '弹丸沿途持续滴落荧光强酸，飞过哪里哪里融穿',
    },
    lava_trail: {
      id: 'lava_trail', kind: 'modifier', name: '熔岩轨迹', icon: '🌋',
      color: '#ff5122', mana: 9, delay: 2, mod: { trail: 'LAVA' },
      desc: '弹丸飞行沿途倾泻 1100°C 岩浆，焚毁并照亮整片矿坑',
    },
  };

  const SPELL_LIST = Object.values(SPELLS);

  const SPELL_CATEGORIES = [
    { id: 'projectile', label: '投射物 / 召唤（16）' },
    { id: 'trigger',    label: '触发器（4）' },
    { id: 'multicast',  label: '多重 / 阵型（6）' },
    { id: 'modifier',   label: '修正器（14）' },
  ];

  // 10 legendary Noita-style combo recipes!
  const COMBO_RECIPES = [
    {
      id: 'blackhole_nuke',
      name: '黑洞钻地核弹',
      color: '#ffe84a',
      slots: ['trigger_death', 'blackhole', 'nuke'],
      desc: '奇点黑洞钻入矿坑深处 → 消亡瞬间在终点引爆微型核弹！',
    },
    {
      id: 'plasma_octa',
      name: '八方等离子绞肉阵',
      color: '#ff4fd8',
      slots: ['trigger_timer', 'spark_bolt', 'octa', 'plasma_cross'],
      desc: '半空 360° 展开 8 个旋转等离子切割十字，瞬间把矿坑切碎！',
    },
    {
      id: 'firecracker',
      name: '鞭炮火药熔岩弹',
      color: '#ff6a24',
      slots: ['gunpowder_trail', 'lava_trail', 'bouncy', 'spark_bolt'],
      desc: '弹跳火花弹边撒火药边滴岩浆，满洞穴霹雳啪啦连环起爆！',
    },
    {
      id: 'self_heal',
      name: '回旋自奶保命杖',
      color: '#4dff9b',
      slots: ['double', 'boomerang', 'water_trail', 'heal_bolt'],
      desc: '两颗带清水灭火的治愈弹飞出后弯回自己身上，瞬间满血复活！',
    },
    {
      id: 'acid_storm',
      name: '裂变追踪强酸导弹',
      color: '#6aff44',
      slots: ['triple', 'split_air', 'homing', 'acid_ball'],
      desc: '3 变 9 自动锁定矿坑怪物的制导强酸导弹群！',
    },
    {
      id: 'electro_flood',
      name: '雷暴瀑布黑洞',
      color: '#5eaaff',
      slots: ['water_trail', 'electric_arc', 'blackhole'],
      desc: '黑洞边挖隧道边倾泻瀑布并通高压电，一路电光石火！',
    },
    {
      id: 'meteor_shower',
      name: '天外陨石暴雨',
      color: '#ff5424',
      slots: ['trigger_hit', 'spark_bolt', 'triple', 'meteor'],
      desc: '标记落点 → 天空连续砸下 3 颗巨型熔岩陨石轰塌洞顶！',
    },
    {
      id: 'napalm_saw',
      name: '汽油火焰死亡飞锯',
      color: '#ff9642',
      slots: ['oil_trail', 'lava_trail', 'bouncy', 'sawblade'],
      desc: '飞锯沿途洒油+岩浆并在洞穴狂弹——极高概率自杀！',
    },
    {
      id: 'storm_alchemy',
      name: '酸雷双云灭世杖',
      color: '#7dff4a',
      slots: ['double', 'rain_cloud', 'acid_cloud'],
      desc: '同时在头顶召唤雷雨云 + 强酸毒云，边下酸雨边劈闪电！',
    },
    {
      id: 'tp_bomb',
      name: '闪现瞬爆刺客杖',
      color: '#7bf5ff',
      slots: ['trigger_hit', 'teleport_spell', 'hex', 'firework_spell'],
      desc: '闪现过去的同时在落点 360° 炸开六芒烟花星雨！',
    },
  ];

  // 4 starter custom wands (each has up to 10 slots)
  function createDefaultWands() {
    return [
      {
        name: '1 · 集束爆破杖',
        color: '#ff7a24',
        slots: ['trigger_hit', 'spark_bolt', 'triple', 'lava_trail', 'firebolt'],
      },
      {
        name: '2 · 雷瀑黑洞杖',
        color: '#c46bff',
        slots: ['acid_trail', 'electric_arc', 'blackhole'],
      },
      {
        name: '3 · 等离子星爆',
        color: '#ff4fd8',
        slots: ['trigger_timer', 'spark_bolt', 'quad', 'plasma_cross'],
      },
      {
        name: '4 · 回旋自奶杖',
        color: '#4dff9b',
        slots: ['double', 'boomerang', 'water_trail', 'heal_bolt'],
      },
    ];
  }

  function cloneMods(base) {
    return {
      homing: !!(base && base.homing),
      bounces: (base && base.bounces) || 0,
      boomerang: !!(base && base.boomerang),
      splitAir: !!(base && base.splitAir),
      orbit: !!(base && base.orbit),
      pierce: (base && base.pierce) || 0,
      speedMult: (base && base.speedMult) || 1,
      heavyGrav: !!(base && base.heavyGrav),
      powerMult: (base && base.powerMult) || 1,
      electricArc: !!(base && base.electricArc),
      trails: base && base.trails ? base.trails.slice() : [],
    };
  }

  function mergeMod(mods, modDef) {
    if (!modDef) return;
    if (modDef.homing) mods.homing = true;
    if (modDef.bounces) mods.bounces += modDef.bounces;
    if (modDef.boomerang) mods.boomerang = true;
    if (modDef.splitAir) mods.splitAir = true;
    if (modDef.orbit) mods.orbit = true;
    if (modDef.pierce) mods.pierce += modDef.pierce;
    if (modDef.speedMult) mods.speedMult = Math.min(2.6, mods.speedMult * modDef.speedMult);
    if (modDef.heavyGrav) mods.heavyGrav = true;
    if (modDef.powerMult) mods.powerMult = Math.min(2.4, mods.powerMult * modDef.powerMult);
    if (modDef.electricArc) mods.electricArc = true;
    if (modDef.trail && mods.trails.indexOf(modDef.trail) === -1) {
      mods.trails.push(modDef.trail);
    }
  }

  function compileWand(slotIds) {
    const valid = (slotIds || []).map((id) => SPELLS[id]).filter(Boolean);
    if (valid.length === 0) {
      return { actions: [], totalMana: 0, totalDelay: 10, summary: '空魔杖 — 点击下方卡牌装填法术' };
    }

    let totalMana = 0;
    let totalDelay = 0;

    function parseBlock(startIdx, inheritedMods, depth) {
      const actions = [];
      let idx = startIdx;
      const mods = cloneMods(inheritedMods);
      let pendingDraws = 1;
      let spread = 0.08;
      let isRing = false;
      let pendingTrigger = null;

      let safety = 0;
      while (idx < valid.length && pendingDraws > 0 && safety++ < 40) {
        const card = valid[idx++];
        totalMana += card.mana;
        totalDelay += card.delay;

        if (card.kind === 'modifier') {
          mergeMod(mods, card.mod);
        } else if (card.kind === 'multicast') {
          pendingDraws += card.count - 1;
          spread = Math.max(spread, card.spread || 0.2);
          if (card.ring) isRing = true;
        } else if (card.kind === 'trigger') {
          pendingTrigger = card.triggerType;
        } else if (card.kind === 'projectile') {
          const action = {
            spell: card,
            mods: cloneMods(mods),
            angleOffset: 0,
            triggerType: pendingTrigger,
            payload: null,
          };
          pendingTrigger = null;
          pendingDraws--;

          if (action.triggerType && idx < valid.length && depth < 3) {
            const sub = parseBlock(idx, null, depth + 1);
            action.payload = sub.actions;
            idx = sub.nextIdx;
          }
          actions.push(action);
        }
      }

      // Duplicate last projectile when multicast exceeds remaining cards
      if (actions.length > 0 && pendingDraws > 0) {
        const template = actions[actions.length - 1];
        const extra = Math.min(pendingDraws, 10);
        for (let k = 0; k < extra; k++) {
          actions.push({
            spell: template.spell,
            mods: cloneMods(template.mods),
            angleOffset: 0,
            triggerType: null,
            payload: null,
          });
        }
      }

      const n = actions.length;
      if (n > 1) {
        if (isRing) {
          for (let k = 0; k < n; k++) {
            actions[k].angleOffset = (k / n) * Math.PI * 2;
          }
        } else {
          for (let k = 0; k < n; k++) {
            actions[k].angleOffset = ((k / (n - 1)) - 0.5) * spread;
          }
        }
      }

      return { actions, nextIdx: idx };
    }

    const compiled = parseBlock(0, null, 0);
    const finalDelay = Math.max(3, Math.min(54, Math.round(totalDelay + 4)));
    const finalMana = Math.max(4, Math.min(95, Math.round(totalMana)));

    let triggerNote = '';
    if (compiled.actions.some((a) => a.payload && a.payload.length > 0)) {
      const subCount = compiled.actions.reduce((s, a) => s + (a.payload ? a.payload.length : 0), 0);
      triggerNote = `（含触发子链 ×${subCount}）`;
    }

    const summary =
      compiled.actions.length === 0
        ? '缺少【投射物】卡牌！请再装入一颗弹丸或召唤法术'
        : `主射 ${compiled.actions.length} 枚${triggerNote} · 蓝耗 ${finalMana} · 冷却 ${finalDelay}f`;

    return {
      actions: compiled.actions,
      totalMana: finalMana,
      totalDelay: finalDelay,
      summary,
    };
  }

  return {
    SPELLS,
    SPELL_LIST,
    SPELL_CATEGORIES,
    COMBO_RECIPES,
    createDefaultWands,
    compileWand,
  };
});
