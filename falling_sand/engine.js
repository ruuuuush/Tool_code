(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.SandEngine = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const EL = {
    EMPTY: 0,
    SAND: 1,
    WATER: 2,
    STONE: 3,
    WOOD: 4,
    FIRE: 5,
    SMOKE: 6,
    STEAM: 7,
    OIL: 8,
    GUNPOWDER: 9,
    LAVA: 10,
    ACID: 11,
    PLANT: 12,
    ICE: 13,
    SNOW: 14,
    GLASS: 15,
    FUSE: 16,
    CLONER: 17,
    VOID: 18,
    SPARK: 19,
    TOXIC: 20,
    SALT: 21,
    METAL: 22,
    C4: 23,
    NITROGEN: 24,
    FIREWORK: 25,
    MITE: 26,
    EMBER: 27,
  };

  const ELEMENT_META = [
    { id: EL.SAND,      key: 'sand',      name: '细沙',     cat: 'powder', color: '#e8c468', desc: '沉入液体，高温或雷击熔成玻璃' },
    { id: EL.GUNPOWDER, key: 'gunpowder', name: '火药',     cat: 'powder', color: '#565a66', desc: '遇火、电、高温剧烈爆炸并炸飞碎片' },
    { id: EL.SNOW,      key: 'snow',      name: '积雪',     cat: 'powder', color: '#e6f4ff', desc: '轻盈飘落，受热融化成水' },
    { id: EL.SALT,      key: 'salt',      name: '晶盐',     cat: 'powder', color: '#f4f0e6', desc: '融冰、溶于清水' },
    { id: EL.MITE,      key: 'mite',      name: '噬木蚁',   cat: 'powder', color: '#ff6b9d', desc: '活体像素生物！专啃木材与藤蔓，遇火四散' },

    { id: EL.WATER,     key: 'water',     name: '清水',     cat: 'liquid', color: '#2b98ff', desc: '灭火、导电、滋润藤蔓，高温沸腾成蒸汽' },
    { id: EL.OIL,       key: 'oil',       name: '原油',     cat: 'liquid', color: '#784c2b', desc: '浮于水面，极易燃并升起滚滚黑烟' },
    { id: EL.LAVA,      key: 'lava',      name: '岩浆',     cat: 'liquid', color: '#ff4f18', desc: '1100°C 炽热光源，烤红金属、遇水成石' },
    { id: EL.ACID,      key: 'acid',      name: '强酸',     cat: 'liquid', color: '#64ff36', desc: '荧光腐蚀液，蚀穿岩石木材，玻璃免疫' },
    { id: EL.NITROGEN,  key: 'nitrogen',  name: '液氮',     cat: 'liquid', color: '#8af5ff', desc: '-196°C 极寒液体，瞬间冻结水流与岩浆' },

    { id: EL.STONE,     key: 'stone',     name: '岩石',     cat: 'solid',  color: '#768092', desc: '坚固地形，耐高温，可被强酸或高爆击碎' },
    { id: EL.METAL,     key: 'metal',     name: '金属',     cat: 'solid',  color: '#9aa8bd', desc: '优良导体！高效传导热量与闪电电流' },
    { id: EL.WOOD,      key: 'wood',      name: '木材',     cat: 'solid',  color: '#965c34', desc: '建筑结构，遇高温碳化燃烧，噬木蚁最爱' },
    { id: EL.PLANT,     key: 'plant',     name: '藤蔓',     cat: 'solid',  color: '#34c45c', desc: '吸水自动向上攀爬生长，极易燃' },
    { id: EL.GLASS,     key: 'glass',     name: '玻璃',     cat: 'solid',  color: '#8ce0ff', desc: '透光耐酸实验器皿，怕爆炸冲击波' },
    { id: EL.ICE,       key: 'ice',       name: '坚冰',     cat: 'solid',  color: '#9beeff', desc: '低温冻结邻近清水，受热融化' },
    { id: EL.FUSE,      key: 'fuse',      name: '导火索',   cat: 'solid',  color: '#d48d5c', desc: '沿线高速传导火星，串联爆破装置' },
    { id: EL.C4,        key: 'c4',        name: 'C4 炸药',  cat: 'solid',  color: '#d8d2b8', desc: '稳定高爆塑胶，按 X 遥控起爆或通电/点火引爆' },
    { id: EL.CLONER,    key: 'cloner',    name: '复制器',   cat: 'solid',  color: '#df5cff', desc: '记住首次接触的动态元素并源源不断喷出' },
    { id: EL.VOID,      key: 'void',      name: '黑洞',     cat: 'solid',  color: '#322052', desc: '吞噬接触到的所有动态物质' },

    { id: EL.FIRE,      key: 'fire',      name: '火焰',     cat: 'energy', color: '#ff8c24', desc: '实时照亮暗穴，加热周围并点燃可燃物' },
    { id: EL.FIREWORK,  key: 'firework',  name: '烟花弹',   cat: 'energy', color: '#ff52c8', desc: '嗖地升空并在高空炸开绚烂彩色星雨！' },
    { id: EL.EMPTY,     key: 'empty',     name: '橡皮擦',   cat: 'energy', color: '#1b2336', desc: '清除画笔范围内的任意物质' },
  ];

  const ELEMENT_NAMES = {
    [EL.EMPTY]: '空气',
    [EL.SAND]: '细沙',
    [EL.WATER]: '清水',
    [EL.STONE]: '岩石',
    [EL.WOOD]: '木材',
    [EL.FIRE]: '火焰',
    [EL.SMOKE]: '浓烟',
    [EL.STEAM]: '蒸汽',
    [EL.OIL]: '原油',
    [EL.GUNPOWDER]: '火药',
    [EL.LAVA]: '岩浆',
    [EL.ACID]: '强酸',
    [EL.PLANT]: '藤蔓',
    [EL.ICE]: '坚冰',
    [EL.SNOW]: '积雪',
    [EL.GLASS]: '玻璃',
    [EL.FUSE]: '导火索',
    [EL.CLONER]: '复制器',
    [EL.VOID]: '黑洞',
    [EL.SPARK]: '电弧火花',
    [EL.TOXIC]: '酸雾',
    [EL.SALT]: '晶盐',
    [EL.METAL]: '金属',
    [EL.C4]: 'C4 炸药',
    [EL.NITROGEN]: '液氮',
    [EL.FIREWORK]: '烟花弹',
    [EL.MITE]: '噬木蚁',
    [EL.EMBER]: '火星余烬',
  };

  function packABGR(r, g, b, a) {
    return (((a & 255) << 24) | ((b & 255) << 16) | ((g & 255) << 8) | (r & 255)) >>> 0;
  }

  function clampByte(v) {
    return v < 0 ? 0 : v > 255 ? 255 : v | 0;
  }

  function createRng(seed) {
    let s = (seed >>> 0) || 0x9e3779b9;
    return function next() {
      s ^= s << 13;
      s ^= s >>> 17;
      s ^= s << 5;
      return (s >>> 0) / 4294967296;
    };
  }

  const IS_LIQUID = new Uint8Array(32);
  IS_LIQUID[EL.WATER] = 1;
  IS_LIQUID[EL.OIL] = 1;
  IS_LIQUID[EL.LAVA] = 1;
  IS_LIQUID[EL.ACID] = 1;
  IS_LIQUID[EL.NITROGEN] = 1;

  const IS_STATIC = new Uint8Array(32);
  IS_STATIC[EL.STONE] = 1;
  IS_STATIC[EL.METAL] = 1;
  IS_STATIC[EL.WOOD] = 1;
  IS_STATIC[EL.PLANT] = 1;
  IS_STATIC[EL.ICE] = 1;
  IS_STATIC[EL.GLASS] = 1;
  IS_STATIC[EL.FUSE] = 1;
  IS_STATIC[EL.C4] = 1;
  IS_STATIC[EL.CLONER] = 1;
  IS_STATIC[EL.VOID] = 1;

  const DENSITY = new Uint8Array(32);
  DENSITY[EL.EMPTY] = 0;
  DENSITY[EL.SMOKE] = 1;
  DENSITY[EL.STEAM] = 1;
  DENSITY[EL.TOXIC] = 2;
  DENSITY[EL.FIRE] = 2;
  DENSITY[EL.EMBER] = 5;
  DENSITY[EL.NITROGEN] = 13;
  DENSITY[EL.OIL] = 15;
  DENSITY[EL.WATER] = 20;
  DENSITY[EL.ACID] = 22;
  DENSITY[EL.SNOW] = 24;
  DENSITY[EL.MITE] = 28;
  DENSITY[EL.LAVA] = 35;
  DENSITY[EL.GUNPOWDER] = 45;
  DENSITY[EL.SALT] = 48;
  DENSITY[EL.SAND] = 50;

  // Base temperature in Celsius (ambient = 22)
  const AMBIENT_TEMP = 22;
  const BASE_TEMP = new Int16Array(32);
  BASE_TEMP.fill(AMBIENT_TEMP);
  BASE_TEMP[EL.LAVA] = 1100;
  BASE_TEMP[EL.FIRE] = 650;
  BASE_TEMP[EL.SPARK] = 800;
  BASE_TEMP[EL.EMBER] = 550;
  BASE_TEMP[EL.STEAM] = 125;
  BASE_TEMP[EL.ICE] = -18;
  BASE_TEMP[EL.SNOW] = -6;
  BASE_TEMP[EL.NITROGEN] = -196;

  // Thermal conductivity (0..1)
  const CONDUCTIVITY = new Float32Array(32);
  CONDUCTIVITY.fill(0.08);
  CONDUCTIVITY[EL.METAL] = 0.52;
  CONDUCTIVITY[EL.WATER] = 0.22;
  CONDUCTIVITY[EL.LAVA] = 0.25;
  CONDUCTIVITY[EL.NITROGEN] = 0.35;
  CONDUCTIVITY[EL.ICE] = 0.18;
  CONDUCTIVITY[EL.GLASS] = 0.04;
  CONDUCTIVITY[EL.EMPTY] = 0.03;

  // Color palette for fireworks bursts
  const FW_COLORS = [
    [255, 86, 146],
    [76, 232, 255],
    [255, 224, 72],
    [134, 255, 92],
    [192, 118, 255],
    [255, 140, 62],
  ];

  // FLIR thermal color LUT (0..255 -> ABGR)
  const THERMAL_LUT = new Uint32Array(256);
  (function buildThermalLUT() {
    const stops = [
      [0,   12,  16,  52],
      [42,  24,  48, 138],
      [92, 112,  28, 168],
      [148, 212,  42,  92],
      [196, 255, 132,  24],
      [234, 255, 234,  92],
      [255, 255, 255, 255],
    ];
    for (let i = 0; i < 256; i++) {
      let s0 = stops[0];
      let s1 = stops[stops.length - 1];
      for (let k = 0; k < stops.length - 1; k++) {
        if (i >= stops[k][0] && i <= stops[k + 1][0]) {
          s0 = stops[k];
          s1 = stops[k + 1];
          break;
        }
      }
      const span = Math.max(1, s1[0] - s0[0]);
      const t = (i - s0[0]) / span;
      const r = clampByte(s0[1] + (s1[1] - s0[1]) * t);
      const g = clampByte(s0[2] + (s1[2] - s0[2]) * t);
      const b = clampByte(s0[3] + (s1[3] - s0[3]) * t);
      THERMAL_LUT[i] = packABGR(r, g, b, 255);
    }
  })();

  class SandWorld {
    constructor(width, height, seed) {
      this.width = width;
      this.height = height;
      this.size = width * height;
      this.grid = new Uint8Array(this.size);
      this.life = new Uint8Array(this.size);
      this.variant = new Uint8Array(this.size);
      this.updated = new Uint8Array(this.size);
      this.temp = new Float32Array(this.size);
      this.charge = new Uint8Array(this.size);
      this.temp.fill(AMBIENT_TEMP);

      // Quarter-res dynamic lightmap
      this.lw = Math.ceil(width / 4);
      this.lh = Math.ceil(height / 4);
      this.lightR = new Float32Array(this.lw * this.lh);
      this.lightG = new Float32Array(this.lw * this.lh);
      this.lightB = new Float32Array(this.lw * this.lh);
      this.lightTmpR = new Float32Array(this.lw * this.lh);
      this.lightTmpG = new Float32Array(this.lw * this.lh);
      this.lightTmpB = new Float32Array(this.lw * this.lh);

      this.tick = 1;
      this.frameCount = 0;
      this.activeCount = 0;
      this.rng = createRng(seed || (Date.now() & 0xffffffff));

      // Physics controls
      this.gravityY = 1; // 1 normal, -1 inverted, 0 zero-g
      this.windX = 0;    // -1..1

      // Dynamic overlays: flying ballistic debris, bombs, shockwaves, sound events
      this.particles = [];
      this.bombs = [];
      this.shockwaves = [];
      this.pendingExplosions = [];
      this.recentExplosions = [];
      this.events = [];
      this.shake = 0;
    }

    clear() {
      this.grid.fill(EL.EMPTY);
      this.life.fill(0);
      this.variant.fill(0);
      this.updated.fill(0);
      this.charge.fill(0);
      this.temp.fill(AMBIENT_TEMP);
      this.pendingExplosions.length = 0;
      this.particles.length = 0;
      this.bombs.length = 0;
      this.shockwaves.length = 0;
      this.events.length = 0;
      this.activeCount = 0;
      this.shake = 0;
    }

    inBounds(x, y) {
      return x >= 0 && x < this.width && y >= 0 && y < this.height;
    }

    get(x, y) {
      if (!this.inBounds(x, y)) return EL.STONE;
      return this.grid[y * this.width + x];
    }

    getTemp(x, y) {
      if (!this.inBounds(x, y)) return AMBIENT_TEMP;
      return this.temp[y * this.width + x];
    }

    emitEvent(type, intensity, x, y) {
      if (this.events.length < 24) {
        this.events.push({ type, intensity, x, y });
      }
    }

    consumeEvents() {
      if (this.events.length === 0) return [];
      return this.events.splice(0, this.events.length);
    }

    setCell(x, y, type, force) {
      if (!this.inBounds(x, y)) return;
      const i = y * this.width + x;
      if (!force && type !== EL.EMPTY && this.grid[i] !== EL.EMPTY) return;
      this.grid[i] = type;
      this.variant[i] = (this.rng() * 255) | 0;
      this.updated[i] = this.tick;
      this.charge[i] = 0;
      this.temp[i] = BASE_TEMP[type];

      if (type === EL.FIRE) {
        this.life[i] = 26 + ((this.rng() * 34) | 0);
      } else if (type === EL.SMOKE) {
        this.life[i] = 55 + ((this.rng() * 65) | 0);
      } else if (type === EL.STEAM) {
        this.life[i] = 85 + ((this.rng() * 85) | 0);
      } else if (type === EL.TOXIC) {
        this.life[i] = 60 + ((this.rng() * 70) | 0);
      } else if (type === EL.SPARK) {
        this.life[i] = 8 + ((this.rng() * 14) | 0);
      } else if (type === EL.EMBER) {
        this.life[i] = 35 + ((this.rng() * 45) | 0);
      } else if (type === EL.ACID) {
        this.life[i] = 4 + ((this.rng() * 4) | 0);
      } else if (type === EL.NITROGEN) {
        this.life[i] = 160 + ((this.rng() * 80) | 0);
      } else if (type === EL.FIREWORK) {
        this.life[i] = 34 + ((this.rng() * 42) | 0);
        this.variant[i] = (this.rng() * FW_COLORS.length) | 0;
      } else if (type === EL.MITE) {
        this.life[i] = 1; // direction state
      } else {
        this.life[i] = 0;
      }
    }

    paintCircle(cx, cy, radius, type, scatter) {
      const r = Math.max(1, radius | 0);
      const r2 = r * r;
      const isSpray =
        scatter &&
        (type === EL.SAND ||
          type === EL.WATER ||
          type === EL.OIL ||
          type === EL.GUNPOWDER ||
          type === EL.SNOW ||
          type === EL.SALT ||
          type === EL.LAVA ||
          type === EL.ACID ||
          type === EL.NITROGEN ||
          type === EL.FIRE ||
          type === EL.MITE);
      const force = type === EL.EMPTY || type === EL.FIRE || type === EL.CLONER || type === EL.VOID;

      // Fireworks spawn as single discrete rockets rather than dense circles
      if (type === EL.FIREWORK) {
        this.setCell(cx, cy, EL.FIREWORK, true);
        this.emitEvent('firework_launch', 0.6, cx, cy);
        return;
      }

      for (let dy = -r; dy <= r; dy++) {
        const py = (cy + dy) | 0;
        if (py < 0 || py >= this.height) continue;
        for (let dx = -r; dx <= r; dx++) {
          if (dx * dx + dy * dy > r2) continue;
          const px = (cx + dx) | 0;
          if (px < 0 || px >= this.width) continue;
          if (isSpray && r > 1 && this.rng() > 0.56) continue;
          this.setCell(px, py, type, force);
        }
      }
    }

    paintLine(x0, y0, x1, y1, radius, type, scatter) {
      x0 |= 0; y0 |= 0; x1 |= 0; y1 |= 0;
      const dx = Math.abs(x1 - x0);
      const dy = Math.abs(y1 - y0);
      const sx = x0 < x1 ? 1 : -1;
      const sy = y0 < y1 ? 1 : -1;
      let err = dx - dy;

      while (true) {
        this.paintCircle(x0, y0, radius, type, scatter);
        if (x0 === x1 && y0 === y1) break;
        const e2 = err << 1;
        if (e2 > -dy) { err -= dy; x0 += sx; }
        if (e2 < dx) { err += dx; y0 += sy; }
      }
    }

    // Apply vortex / radial swirl force converting cells into flying ballistic debris!
    applyVortex(cx, cy, radius, pushOut) {
      const r = Math.max(8, radius | 0);
      const r2 = r * r;
      let spawned = 0;
      for (let dy = -r; dy <= r; dy++) {
        const py = (cy + dy) | 0;
        if (py < 0 || py >= this.height) continue;
        for (let dx = -r; dx <= r; dx++) {
          const d2 = dx * dx + dy * dy;
          if (d2 > r2 || d2 < 2) continue;
          const px = (cx + dx) | 0;
          if (px < 0 || px >= this.width) continue;
          const i = py * this.width + px;
          const t = this.grid[i];
          if (t === EL.EMPTY || IS_STATIC[t]) continue;
          if (this.particles.length > 1400 || spawned > 55) return;
          if (this.rng() > 0.22) continue;

          const dist = Math.sqrt(d2);
          const nx = dx / dist;
          const ny = dy / dist;
          const power = (1 - dist / r) * 3.8 + 1.2;
          // Tangential swirl + slight lift
          const vx = pushOut ? nx * power * 1.4 : (-ny * power + nx * 0.6);
          const vy = pushOut ? ny * power * 1.4 - 1.1 : (nx * power - 1.5);

          this.grid[i] = EL.EMPTY;
          this.spawnParticle(px, py, vx, vy, t, null, 45 + ((this.rng() * 30) | 0));
          spawned++;
        }
      }
      if (spawned > 4) {
        this.emitEvent('wind', Math.min(1, spawned / 30), cx, cy);
      }
    }

    // Launch a physical bouncing bomb
    throwBomb(x, y, vx, vy) {
      if (this.bombs.length >= 20) return;
      this.bombs.push({
        x,
        y,
        vx: vx || (this.rng() - 0.5) * 2.2,
        vy: vy !== undefined ? vy : -1.8,
        fuse: 68,
        radius: 22,
      });
    }

    // Remote detonate all C4 in the world!
    detonateAllC4() {
      const w = this.width;
      const h = this.height;
      const grid = this.grid;
      let triggered = 0;
      for (let y = 0; y < h; y += 3) {
        for (let x = 0; x < w; x += 3) {
          if (grid[y * w + x] === EL.C4) {
            this.queueExplosion(x, y, 24);
            triggered++;
          }
        }
      }
      if (triggered === 0) {
        // Fine scan for sparse C4 pixels
        for (let i = 0; i < this.size; i++) {
          if (grid[i] === EL.C4) {
            this.queueExplosion(i % w, (i / w) | 0, 22);
            triggered++;
            break;
          }
        }
      }
      return triggered;
    }

    spawnParticle(x, y, vx, vy, element, customRGB, maxLife) {
      if (this.particles.length >= 1600) return;
      this.particles.push({
        x,
        y,
        vx,
        vy,
        element,
        rgb: customRGB || null,
        life: maxLife || 60,
        maxLife: maxLife || 60,
      });
    }

    burstFirework(cx, cy, colorIndex) {
      const baseRgb = FW_COLORS[colorIndex % FW_COLORS.length];
      const altRgb = FW_COLORS[(colorIndex + 2) % FW_COLORS.length];
      const count = 42 + ((this.rng() * 24) | 0);
      for (let k = 0; k < count; k++) {
        const angle = (k / count) * Math.PI * 2 + (this.rng() - 0.5) * 0.14;
        const speed = 1.4 + this.rng() * 3.1;
        const useAlt = (k & 3) === 0;
        const rgb = useAlt ? altRgb : baseRgb;
        this.spawnParticle(
          cx,
          cy,
          Math.cos(angle) * speed,
          Math.sin(angle) * speed - 0.35,
          EL.EMBER,
          rgb,
          28 + ((this.rng() * 34) | 0)
        );
      }
      this.shockwaves.push({
        x: cx,
        y: cy,
        r: 2,
        maxR: 26,
        alpha: 0.9,
        color: `rgb(${baseRgb[0]},${baseRgb[1]},${baseRgb[2]})`,
      });
      this.shake = Math.min(10, this.shake + 2.4);
      this.emitEvent('firework_burst', 0.9, cx, cy);
    }

    strikeLightning(startX, startY) {
      this.emitEvent('lightning', 1.0, startX, startY);
      this.shake = Math.min(12, this.shake + 3.2);
      const bolts = [{ x: startX | 0, y: Math.max(0, startY | 0), steps: this.height - (startY | 0) + 24, branch: 0 }];

      while (bolts.length > 0) {
        const b = bolts.pop();
        let x = b.x;
        let y = b.y;
        for (let s = 0; s < b.steps; s++) {
          if (!this.inBounds(x, y)) break;
          const i = y * this.width + x;
          const cur = this.grid[i];

          if (cur === EL.GUNPOWDER || cur === EL.C4) {
            this.queueExplosion(x, y, cur === EL.C4 ? 24 : 17);
            break;
          } else if (cur === EL.OIL || cur === EL.WOOD || cur === EL.PLANT || cur === EL.FUSE) {
            this.setCell(x, y, EL.FIRE, true);
          } else if (cur === EL.SAND) {
            this.setCell(x, y, EL.GLASS, true);
            this.temp[i] = 900;
          } else if (cur === EL.ICE || cur === EL.SNOW) {
            this.setCell(x, y, EL.WATER, true);
          } else if (cur === EL.METAL) {
            this.electrifyConductor(x, y);
            break;
          } else if (cur === EL.WATER) {
            this.electrifyConductor(x, y);
            break;
          } else if (cur === EL.STONE || cur === EL.GLASS || cur === EL.VOID) {
            this.setCell(x, Math.max(0, y - 1), EL.SPARK, true);
            for (let k = 0; k < 6; k++) {
              this.spawnParticle(x, y - 1, (this.rng() - 0.5) * 3.5, -1 - this.rng() * 2.5, EL.SPARK, [160, 235, 255], 18);
            }
            break;
          } else {
            this.setCell(x, y, EL.SPARK, true);
            if (this.inBounds(x + 1, y) && this.grid[i + 1] === EL.EMPTY && this.rng() < 0.35) {
              this.setCell(x + 1, y, EL.SPARK, true);
            }
          }

          const drift = this.rng();
          if (drift < 0.38) x -= 1;
          else if (drift > 0.62) x += 1;
          y += 1;

          if (b.branch < 2 && this.rng() < 0.085) {
            bolts.push({ x, y, steps: (b.steps * 0.48) | 0, branch: b.branch + 1 });
          }
        }
      }
    }

    electrifyConductor(sx, sy) {
      const w = this.width;
      const queue = [sx, sy];
      const visited = new Set();
      let budget = 260;

      while (queue.length > 0 && budget-- > 0) {
        const y = queue.pop();
        const x = queue.pop();
        const idx = y * w + x;
        if (visited.has(idx)) continue;
        visited.add(idx);

        const t = this.grid[idx];
        if (t === EL.METAL) {
          this.charge[idx] = 16;
          this.temp[idx] = Math.min(900, this.temp[idx] + 45);
        } else if (t === EL.WATER) {
          if (this.rng() < 0.32) this.setCell(x, y, EL.SPARK, true);
          else if (this.rng() < 0.14) this.setCell(x, y, EL.STEAM, true);
        }

        const dirs = [[1, 0], [-1, 0], [0, 1], [0, -1]];
        for (let d = 0; d < 4; d++) {
          const nx = x + dirs[d][0];
          const ny = y + dirs[d][1];
          if (!this.inBounds(nx, ny)) continue;
          const ni = ny * w + nx;
          const nt = this.grid[ni];
          if (nt === EL.METAL || nt === EL.WATER) {
            queue.push(nx, ny);
          } else if (nt === EL.GUNPOWDER || nt === EL.C4) {
            this.queueExplosion(nx, ny, nt === EL.C4 ? 24 : 16);
          } else if (nt === EL.FUSE && this.life[ni] === 0) {
            this.life[ni] = 1;
          } else if (nt === EL.OIL) {
            this.setCell(nx, ny, EL.FIRE, true);
          } else if (nt === EL.FIREWORK) {
            this.burstFirework(nx, ny, this.variant[ni]);
            this.setCell(nx, ny, EL.EMPTY, true);
          }
        }
      }
    }

    queueExplosion(x, y, radius) {
      if (this.pendingExplosions.length < 48) {
        this.pendingExplosions.push({ x, y, radius });
      }
    }

    detonate(cx, cy, radius) {
      const r2 = radius * radius;
      this.recentExplosions.push({ x: cx, y: cy, radius });
      this.shake = Math.min(14, this.shake + radius * 0.32);
      this.shockwaves.push({
        x: cx,
        y: cy,
        r: 3,
        maxR: radius * 2.1,
        alpha: 0.95,
        color: '#ffbe55',
      });
      this.emitEvent('explosion', Math.min(1, radius / 22), cx, cy);

      let debrisBudget = 34;

      for (let dy = -radius; dy <= radius; dy++) {
        const py = cy + dy;
        if (py < 0 || py >= this.height) continue;
        for (let dx = -radius; dx <= radius; dx++) {
          const dist2 = dx * dx + dy * dy;
          if (dist2 > r2) continue;
          const px = cx + dx;
          if (px < 0 || px >= this.width) continue;
          const i = py * this.width + px;
          const t = this.grid[i];
          if (t === EL.VOID || t === EL.CLONER) continue;

          if ((t === EL.GUNPOWDER || t === EL.C4) && dist2 > 6) {
            this.grid[i] = EL.EMPTY;
            this.queueExplosion(px, py, t === EL.C4 ? Math.max(18, radius) : Math.max(11, radius - 2));
            continue;
          }

          if (t === EL.METAL && dist2 > r2 * 0.25) {
            this.temp[i] = Math.min(1000, this.temp[i] + 320);
            continue;
          }

          const ratio = dist2 / r2;
          if (t === EL.STONE && ratio > 0.5 && this.rng() < 0.6) continue;

          // Launch real ballistic debris outward!
          if (
            debrisBudget > 0 &&
            t !== EL.EMPTY &&
            t !== EL.FIRE &&
            t !== EL.SMOKE &&
            ratio > 0.35 &&
            this.rng() < 0.14
          ) {
            const dist = Math.max(1, Math.sqrt(dist2));
            const speed = 2.2 + this.rng() * 3.6;
            const ejectedType = t === EL.STONE || t === EL.GLASS ? EL.SAND : t === EL.WOOD ? EL.EMBER : t;
            this.spawnParticle(
              px,
              py,
              (dx / dist) * speed + (this.rng() - 0.5) * 0.8,
              (dy / dist) * speed - 1.2,
              ejectedType,
              ejectedType === EL.EMBER ? [255, 175, 65] : null,
              45 + ((this.rng() * 40) | 0)
            );
            debrisBudget--;
          }

          const roll = this.rng();
          if (ratio < 0.52) {
            this.setCell(px, py, roll < 0.58 ? EL.FIRE : roll < 0.82 ? EL.SPARK : EL.SMOKE, true);
            this.temp[i] = 850;
          } else if (roll < 0.48) {
            this.setCell(px, py, roll < 0.26 ? EL.FIRE : EL.SMOKE, true);
            this.temp[i] = 450;
          } else if (t === EL.GLASS || t === EL.ICE || t === EL.WOOD || t === EL.PLANT || t === EL.FUSE) {
            this.setCell(px, py, roll < 0.65 ? EL.FIRE : EL.EMPTY, true);
          }
        }
      }
    }

    swap(i1, i2) {
      const g = this.grid, l = this.life, v = this.variant, u = this.updated, tp = this.temp, ch = this.charge;
      const tg = g[i1]; g[i1] = g[i2]; g[i2] = tg;
      const tl = l[i1]; l[i1] = l[i2]; l[i2] = tl;
      const tv = v[i1]; v[i1] = v[i2]; v[i2] = tv;
      const tt = tp[i1]; tp[i1] = tp[i2]; tp[i2] = tt;
      const tc = ch[i1]; ch[i1] = ch[i2]; ch[i2] = tc;
      u[i1] = this.tick;
      u[i2] = this.tick;
    }

    moveTo(fromIdx, toIdx) {
      this.grid[toIdx] = this.grid[fromIdx];
      this.life[toIdx] = this.life[fromIdx];
      this.variant[toIdx] = this.variant[fromIdx];
      this.temp[toIdx] = this.temp[fromIdx];
      this.charge[toIdx] = this.charge[fromIdx];
      this.updated[toIdx] = this.tick;

      this.grid[fromIdx] = EL.EMPTY;
      this.life[fromIdx] = 0;
      this.charge[fromIdx] = 0;
      this.temp[fromIdx] = AMBIENT_TEMP;
      this.updated[fromIdx] = this.tick;
    }

    canDisplace(moverType, targetType) {
      if (targetType === EL.EMPTY) return true;
      if (IS_STATIC[targetType]) return false;
      if (moverType === targetType) return false;
      return DENSITY[moverType] > DENSITY[targetType];
    }

    updateBombs() {
      const g = this.gravityY === 0 ? 0.02 : 0.16 * this.gravityY;
      for (let i = this.bombs.length - 1; i >= 0; i--) {
        const b = this.bombs[i];
        b.vy += g;
        b.vx += this.windX * 0.03;
        b.vx *= 0.992;
        const nx = b.x + b.vx;
        const ny = b.y + b.vy;

        const gx = nx | 0;
        const gy = ny | 0;
        if (!this.inBounds(gx, gy) || (this.grid[gy * this.width + gx] !== EL.EMPTY && !IS_LIQUID[this.grid[gy * this.width + gx]])) {
          b.vx *= -0.45;
          b.vy *= -0.45;
        } else {
          b.x = nx;
          b.y = ny;
        }

        // Trailing sparks from bomb fuse
        if (this.rng() < 0.65) {
          this.spawnParticle(b.x, b.y - 2, (this.rng() - 0.5) * 1.4, -0.8 - this.rng(), EL.SPARK, [255, 220, 110], 10);
        }

        b.fuse--;
        if (b.fuse <= 0) {
          this.queueExplosion(b.x | 0, b.y | 0, b.radius);
          this.bombs.splice(i, 1);
        }
      }
    }

    updateParticles() {
      const w = this.width;
      const h = this.height;
      const g = this.gravityY === 0 ? 0.01 : 0.11 * this.gravityY;

      for (let i = this.particles.length - 1; i >= 0; i--) {
        const p = this.particles[i];
        p.vy += g;
        p.vx += this.windX * 0.04;
        p.vx *= 0.988;
        p.vy *= 0.992;
        p.x += p.vx;
        p.y += p.vy;
        p.life--;

        const gx = p.x | 0;
        const gy = p.y | 0;

        if (p.life <= 0 || gx < 0 || gx >= w || gy < 0 || gy >= h) {
          this.particles.splice(i, 1);
          continue;
        }

        const cellIdx = gy * w + gx;
        const hit = this.grid[cellIdx];

        // Hot embers / firework sparks can ignite flammables on impact
        if ((p.element === EL.EMBER || p.element === EL.SPARK) && hit !== EL.EMPTY) {
          if (hit === EL.GUNPOWDER || hit === EL.C4) {
            this.queueExplosion(gx, gy, hit === EL.C4 ? 22 : 15);
          } else if (hit === EL.OIL || hit === EL.PLANT || hit === EL.FUSE) {
            this.setCell(gx, gy, EL.FIRE, true);
          } else if (hit === EL.WOOD && this.life[cellIdx] === 0 && this.rng() < 0.35) {
            this.life[cellIdx] = 1;
          }
          this.particles.splice(i, 1);
          continue;
        }

        // Physical material particles re-enter the cellular grid on collision
        if (p.element !== EL.EMBER && p.element !== EL.SPARK && hit !== EL.EMPTY) {
          const px = (p.x - p.vx) | 0;
          const py = (p.y - p.vy) | 0;
          if (this.inBounds(px, py) && this.grid[py * w + px] === EL.EMPTY) {
            this.setCell(px, py, p.element, true);
          }
          this.particles.splice(i, 1);
        }
      }
    }

    updateShockwaves() {
      for (let i = this.shockwaves.length - 1; i >= 0; i--) {
        const s = this.shockwaves[i];
        s.r += (s.maxR - s.r) * 0.24 + 1.2;
        s.alpha *= 0.84;
        if (s.alpha < 0.04 || s.r >= s.maxR) {
          this.shockwaves.splice(i, 1);
        }
      }
      this.shake *= 0.84;
      if (this.shake < 0.1) this.shake = 0;
    }

    // Fast localized thermal conduction + phase transitions
    stepThermal(x, y, i, t) {
      const temp = this.temp;
      let curT = temp[i];

      // Ambient relaxation for empty or neutral cells
      if (t === EL.LAVA) curT = Math.max(curT, 1020);
      else if (t === EL.NITROGEN) curT = Math.min(curT, -175);
      else if (t === EL.FIRE) curT = Math.max(curT, 580);
      else curT += (AMBIENT_TEMP - curT) * 0.008;

      const cond = CONDUCTIVITY[t];
      // Exchange heat with one random orthogonal neighbor per tick (fast Monte Carlo diffusion)
      const dir = (this.frameCount + x + y) & 3;
      const nx = x + (dir === 0 ? 1 : dir === 1 ? -1 : 0);
      const ny = y + (dir === 2 ? 1 : dir === 3 ? -1 : 0);
      if (nx >= 0 && nx < this.width && ny >= 0 && ny < this.height) {
        const ni = ny * this.width + nx;
        const nt = this.grid[ni];
        const k = Math.min(cond, CONDUCTIVITY[nt]) * 0.65;
        const diff = (temp[ni] - curT) * k;
        curT += diff;
        temp[ni] -= diff;
      }
      temp[i] = curT;

      // Temperature-driven phase transitions
      if (t === EL.WATER) {
        if (curT > 102 && this.rng() < 0.14) {
          this.setCell(x, y, EL.STEAM, true);
          return true;
        }
        if (curT < -2 && this.rng() < 0.2) {
          this.setCell(x, y, EL.ICE, true);
          return true;
        }
      } else if (t === EL.ICE && curT > 8 && this.rng() < 0.18) {
        this.setCell(x, y, EL.WATER, true);
        return true;
      } else if (t === EL.SNOW && curT > 5 && this.rng() < 0.3) {
        this.setCell(x, y, EL.WATER, true);
        return true;
      } else if (t === EL.WOOD && curT > 260 && this.life[i] === 0 && this.rng() < 0.08) {
        this.life[i] = 1;
      } else if (t === EL.OIL && curT > 220 && this.rng() < 0.15) {
        this.setCell(x, y, EL.FIRE, true);
        return true;
      } else if (t === EL.GUNPOWDER && curT > 240) {
        this.queueExplosion(x, y, 16);
        return true;
      } else if (t === EL.SAND && curT > 780 && this.rng() < 0.05) {
        this.setCell(x, y, EL.GLASS, true);
        return true;
      } else if (t === EL.LAVA && curT < 260 && this.rng() < 0.22) {
        this.setCell(x, y, EL.STONE, true);
        return true;
      }

      return false;
    }

    step() {
      this.frameCount++;
      this.recentExplosions.length = 0;
      this.tick = (this.tick + 1) & 255;
      if (this.tick === 0) {
        this.updated.fill(0);
        this.tick = 1;
      }

      if (this.pendingExplosions.length > 0) {
        const list = this.pendingExplosions.splice(0, this.pendingExplosions.length);
        for (let k = 0; k < list.length; k++) {
          this.detonate(list[k].x, list[k].y, list[k].radius);
        }
      }

      this.updateBombs();
      this.updateParticles();
      this.updateShockwaves();

      const w = this.width;
      const h = this.height;
      const grid = this.grid;
      const updated = this.updated;
      const tick = this.tick;
      let count = 0;

      const leftToRight = (this.frameCount & 1) === 0;
      const inverted = this.gravityY < 0;

      const yStart = inverted ? 0 : h - 1;
      const yEnd = inverted ? h : -1;
      const yStep = inverted ? 1 : -1;

      for (let y = yStart; y !== yEnd; y += yStep) {
        const rowOffset = y * w;
        if (leftToRight) {
          for (let x = 0; x < w; x++) {
            const i = rowOffset + x;
            const t = grid[i];
            if (t === EL.EMPTY) {
              // Cool empty air gradually
              if (Math.abs(this.temp[i] - AMBIENT_TEMP) > 1) {
                this.temp[i] += (AMBIENT_TEMP - this.temp[i]) * 0.04;
              }
              continue;
            }
            count++;
            if (updated[i] === tick) continue;
            if (this.stepThermal(x, y, i, t)) continue;
            this.updateCell(x, y, i, t);
          }
        } else {
          for (let x = w - 1; x >= 0; x--) {
            const i = rowOffset + x;
            const t = grid[i];
            if (t === EL.EMPTY) {
              if (Math.abs(this.temp[i] - AMBIENT_TEMP) > 1) {
                this.temp[i] += (AMBIENT_TEMP - this.temp[i]) * 0.04;
              }
              continue;
            }
            count++;
            if (updated[i] === tick) continue;
            if (this.stepThermal(x, y, i, t)) continue;
            this.updateCell(x, y, i, t);
          }
        }
      }

      this.activeCount = count + this.particles.length;
    }

    updateCell(x, y, i, t) {
      switch (t) {
        case EL.SAND:
        case EL.GUNPOWDER:
        case EL.SALT:
          this.updatePowder(x, y, i, t);
          break;
        case EL.SNOW:
          this.updateSnow(x, y, i);
          break;
        case EL.MITE:
          this.updateMite(x, y, i);
          break;
        case EL.WATER:
          this.updateLiquidFlow(x, y, i, EL.WATER, 6);
          break;
        case EL.OIL:
          this.updateLiquidFlow(x, y, i, EL.OIL, 4);
          break;
        case EL.LAVA:
          this.updateLava(x, y, i);
          break;
        case EL.ACID:
          this.updateAcid(x, y, i);
          break;
        case EL.NITROGEN:
          this.updateNitrogen(x, y, i);
          break;
        case EL.FIRE:
          this.updateFire(x, y, i);
          break;
        case EL.EMBER:
          this.updateEmber(x, y, i);
          break;
        case EL.FIREWORK:
          this.updateFirework(x, y, i);
          break;
        case EL.SMOKE:
        case EL.STEAM:
        case EL.TOXIC:
          this.updateGas(x, y, i, t);
          break;
        case EL.SPARK:
          this.updateSpark(x, y, i);
          break;
        case EL.METAL:
          this.updateMetal(x, y, i);
          break;
        case EL.WOOD:
          this.updateWood(x, y, i);
          break;
        case EL.FUSE:
          this.updateFuse(x, y, i);
          break;
        case EL.PLANT:
          this.updatePlant(x, y, i);
          break;
        case EL.ICE:
          this.updateIce(x, y, i);
          break;
        case EL.CLONER:
          this.updateCloner(x, y, i);
          break;
        case EL.VOID:
          this.updateVoid(x, y, i);
          break;
        default:
          break;
      }
    }

    updatePowder(x, y, i, t) {
      const w = this.width;
      const h = this.height;
      const grid = this.grid;

      if (t === EL.GUNPOWDER) {
        const dirs = [[0, -1], [0, 1], [-1, 0], [1, 0]];
        for (let d = 0; d < 4; d++) {
          const nx = x + dirs[d][0];
          const ny = y + dirs[d][1];
          if (!this.inBounds(nx, ny)) continue;
          const nt = grid[ny * w + nx];
          if (nt === EL.FIRE || nt === EL.LAVA || nt === EL.SPARK || nt === EL.EMBER) {
            this.queueExplosion(x, y, 16);
            return;
          }
        }
      }

      if (t === EL.SALT && this.rng() < 0.03) {
        const dirs = [[0, 1], [0, -1], [1, 0], [-1, 0]];
        for (let d = 0; d < 4; d++) {
          const nx = x + dirs[d][0];
          const ny = y + dirs[d][1];
          if (!this.inBounds(nx, ny)) continue;
          const ni = ny * w + nx;
          if (grid[ni] === EL.ICE) {
            this.setCell(nx, ny, EL.WATER, true);
            this.setCell(x, y, EL.EMPTY, true);
            return;
          }
          if (grid[ni] === EL.WATER && this.rng() < 0.25) {
            this.setCell(x, y, EL.EMPTY, true);
            return;
          }
        }
      }

      if (this.gravityY === 0) {
        // Gentle zero-G drift + wind
        if (this.rng() < 0.25) {
          const wx = this.windX !== 0 ? Math.sign(this.windX) : (((this.rng() * 3) | 0) - 1);
          const wy = ((this.rng() * 3) | 0) - 1;
          const nx = x + wx;
          const ny = y + wy;
          if (this.inBounds(nx, ny) && grid[ny * w + nx] === EL.EMPTY) {
            this.moveTo(i, ny * w + nx);
          }
        }
        return;
      }

      const gy = this.gravityY > 0 ? 1 : -1;
      const ny = y + gy;
      if (ny < 0 || ny >= h) return;

      const below = ny * w + x;
      const bt = grid[below];

      // Wind push while airborne
      if (bt === EL.EMPTY && this.windX !== 0 && this.rng() < Math.abs(this.windX) * 0.45) {
        const wx = x + Math.sign(this.windX);
        if (wx >= 0 && wx < w && grid[ny * w + wx] === EL.EMPTY) {
          this.moveTo(i, ny * w + wx);
          return;
        }
      }

      if (this.canDisplace(t, bt)) {
        if (bt === EL.EMPTY) this.moveTo(i, below);
        else if (this.rng() < 0.55) this.swap(i, below);
        return;
      }

      const dir = this.rng() < 0.5 ? -1 : 1;
      for (let k = 0; k < 2; k++) {
        const dx = k === 0 ? dir : -dir;
        const nx = x + dx;
        if (nx < 0 || nx >= w) continue;
        const diag = below + dx;
        const dt = grid[diag];
        if (this.canDisplace(t, dt)) {
          if (dt === EL.EMPTY) this.moveTo(i, diag);
          else if (this.rng() < 0.5) this.swap(i, diag);
          return;
        }
      }
    }

    updateSnow(x, y, i) {
      const w = this.width;
      const h = this.height;
      const grid = this.grid;
      if (this.gravityY === 0) return;

      const gy = this.gravityY > 0 ? 1 : -1;
      const ny = y + gy;
      if (ny < 0 || ny >= h) return;
      const below = ny * w + x;

      if (grid[below] === EL.EMPTY) {
        const windBias = this.windX !== 0 && this.rng() < Math.abs(this.windX) * 0.65 ? Math.sign(this.windX) : (this.rng() < 0.5 ? -1 : 1);
        if (this.rng() < 0.52) {
          const nx = x + windBias;
          if (nx >= 0 && nx < w && grid[below + windBias] === EL.EMPTY) {
            this.moveTo(i, below + windBias);
            return;
          }
        }
        if (this.rng() < 0.72) this.moveTo(i, below);
        return;
      }

      if (this.canDisplace(EL.SNOW, grid[below])) {
        if (this.rng() < 0.3) this.swap(i, below);
        return;
      }

      const dir = this.rng() < 0.5 ? -1 : 1;
      const nx = x + dir;
      if (nx >= 0 && nx < w && grid[below + dir] === EL.EMPTY) {
        this.moveTo(i, below + dir);
      }
    }

    updateMite(x, y, i) {
      const w = this.width;
      const h = this.height;
      const grid = this.grid;

      // Dies in lava/acid/fire/extreme heat
      if (this.temp[i] > 85) {
        this.setCell(x, y, EL.FIRE, true);
        return;
      }

      // Check 4 neighbors to eat wood or plant
      const dirs = [[1, 0], [-1, 0], [0, 1], [0, -1]];
      for (let d = 0; d < 4; d++) {
        const nx = x + dirs[d][0];
        const ny = y + dirs[d][1];
        if (!this.inBounds(nx, ny)) continue;
        const ni = ny * w + nx;
        const nt = grid[ni];
        if (nt === EL.LAVA || nt === EL.ACID || nt === EL.FIRE) {
          this.setCell(x, y, EL.SMOKE, true);
          return;
        }
        if ((nt === EL.WOOD || nt === EL.PLANT) && this.rng() < 0.24) {
          // Devour wood/plant and move into it (small chance to reproduce!)
          if (this.rng() < 0.06) {
            this.setCell(nx, ny, EL.MITE, true);
          } else {
            this.setCell(nx, ny, EL.EMPTY, true);
            this.moveTo(i, ni);
          }
          return;
        }
      }

      // Gravity if airborne
      const gy = this.gravityY >= 0 ? 1 : -1;
      if (this.gravityY !== 0 && y + gy >= 0 && y + gy < h) {
        const below = (y + gy) * w + x;
        if (grid[below] === EL.EMPTY) {
          this.moveTo(i, below);
          return;
        }
      }

      // Crawl left/right, climb 1px ledges
      let dir = this.life[i] === 2 ? -1 : 1;
      if (this.rng() < 0.06) {
        dir = -dir;
        this.life[i] = dir === -1 ? 2 : 1;
      }
      const nx = x + dir;
      if (nx >= 0 && nx < w) {
        const side = y * w + nx;
        if (grid[side] === EL.EMPTY) {
          this.moveTo(i, side);
          return;
        }
        if (y > 0 && grid[(y - 1) * w + nx] === EL.EMPTY) {
          this.moveTo(i, (y - 1) * w + nx);
          return;
        }
      }
      this.life[i] = dir === -1 ? 1 : 2;
    }

    updateLiquidFlow(x, y, i, t, dispersion) {
      const w = this.width;
      const h = this.height;
      const grid = this.grid;

      if (this.gravityY === 0) {
        if (this.rng() < 0.35) {
          const dx = this.windX !== 0 ? Math.sign(this.windX) : (((this.rng() * 3) | 0) - 1);
          const dy = ((this.rng() * 3) | 0) - 1;
          const nx = x + dx;
          const ny = y + dy;
          if (this.inBounds(nx, ny) && grid[ny * w + nx] === EL.EMPTY) {
            this.moveTo(i, ny * w + nx);
          }
        }
        return;
      }

      const gy = this.gravityY > 0 ? 1 : -1;
      const ny = y + gy;

      if (ny >= 0 && ny < h) {
        const below = ny * w + x;
        const bt = grid[below];
        if (bt === EL.EMPTY) {
          this.moveTo(i, below);
          return;
        }
        if (this.canDisplace(t, bt) && this.rng() < 0.65) {
          this.swap(i, below);
          return;
        }

        const dir = this.rng() < 0.5 ? -1 : 1;
        for (let k = 0; k < 2; k++) {
          const dx = k === 0 ? dir : -dir;
          const nx = x + dx;
          if (nx < 0 || nx >= w) continue;
          const diag = below + dx;
          const dt = grid[diag];
          if (dt === EL.EMPTY) {
            this.moveTo(i, diag);
            return;
          }
          if (this.canDisplace(t, dt) && this.rng() < 0.45) {
            this.swap(i, diag);
            return;
          }
        }
      }

      const dir = this.windX !== 0 && this.rng() < 0.65 ? Math.sign(this.windX) : (this.rng() < 0.5 ? -1 : 1);
      for (let side = 0; side < 2; side++) {
        const d = side === 0 ? dir : -dir;
        let bestIdx = -1;
        for (let step = 1; step <= dispersion; step++) {
          const nx = x + d * step;
          if (nx < 0 || nx >= w) break;
          const ni = y * w + nx;
          const nt = grid[ni];
          if (nt === EL.EMPTY) {
            bestIdx = ni;
          } else if (IS_LIQUID[nt] && DENSITY[t] > DENSITY[nt] && step === 1) {
            this.swap(i, ni);
            return;
          } else {
            break;
          }
        }
        if (bestIdx !== -1) {
          this.moveTo(i, bestIdx);
          return;
        }
      }
    }

    updateLava(x, y, i) {
      const w = this.width;
      const grid = this.grid;

      const dirs = [[0, -1], [0, 1], [-1, 0], [1, 0]];
      for (let d = 0; d < 4; d++) {
        const nx = x + dirs[d][0];
        const ny = y + dirs[d][1];
        if (!this.inBounds(nx, ny)) continue;
        const ni = ny * w + nx;
        const nt = grid[ni];

        if (nt === EL.WATER) {
          this.setCell(x, y, EL.STONE, true);
          this.setCell(nx, ny, EL.STEAM, true);
          return;
        } else if (nt === EL.NITROGEN) {
          this.setCell(x, y, EL.STONE, true);
          this.setCell(nx, ny, EL.STEAM, true);
          return;
        } else if (nt === EL.ICE || nt === EL.SNOW) {
          this.setCell(nx, ny, EL.WATER, true);
          if (this.rng() < 0.35) {
            this.setCell(x, y, EL.STONE, true);
            return;
          }
        } else if (nt === EL.GUNPOWDER || nt === EL.C4) {
          this.queueExplosion(nx, ny, nt === EL.C4 ? 22 : 16);
          return;
        } else if (nt === EL.OIL || nt === EL.PLANT) {
          this.setCell(nx, ny, EL.FIRE, true);
        } else if (nt === EL.WOOD || nt === EL.FUSE) {
          if (this.life[ni] === 0 && this.rng() < 0.35) this.life[ni] = 1;
        } else if (nt === EL.SAND && this.rng() < 0.05) {
          this.setCell(nx, ny, EL.GLASS, true);
        } else if (nt === EL.METAL) {
          this.temp[ni] = Math.min(1000, this.temp[ni] + 35);
        }
      }

      if (y > 0 && grid[i - w] === EL.EMPTY && this.rng() < 0.025) {
        this.setCell(x, y - 1, EL.FIRE, true);
      }

      if (this.rng() < 0.56) {
        this.updateLiquidFlow(x, y, i, EL.LAVA, 2);
      }
    }

    updateAcid(x, y, i) {
      const w = this.width;
      const grid = this.grid;

      const dirs = [[0, 1], [-1, 0], [1, 0], [0, -1]];
      for (let d = 0; d < 4; d++) {
        const nx = x + dirs[d][0];
        const ny = y + dirs[d][1];
        if (!this.inBounds(nx, ny)) continue;
        const ni = ny * w + nx;
        const nt = grid[ni];
        if (
          nt === EL.EMPTY ||
          nt === EL.ACID ||
          nt === EL.GLASS ||
          nt === EL.CLONER ||
          nt === EL.VOID ||
          nt === EL.TOXIC ||
          nt === EL.SMOKE ||
          nt === EL.STEAM
        ) {
          continue;
        }

        const dissolveRate = nt === EL.STONE || nt === EL.METAL ? 0.055 : nt === EL.LAVA ? 0.25 : 0.22;
        if (this.rng() < dissolveRate) {
          this.setCell(nx, ny, this.rng() < 0.35 ? EL.TOXIC : EL.EMPTY, true);
          if (this.life[i] > 1) {
            this.life[i]--;
          } else {
            this.setCell(x, y, EL.TOXIC, true);
            return;
          }
        }
      }

      this.updateLiquidFlow(x, y, i, EL.ACID, 4);
    }

    updateNitrogen(x, y, i) {
      const w = this.width;
      const grid = this.grid;

      if (this.life[i] <= 1) {
        this.setCell(x, y, this.rng() < 0.55 ? EL.STEAM : EL.EMPTY, true);
        return;
      }
      if (this.rng() < 0.45) this.life[i]--;

      const dirs = [[0, -1], [0, 1], [-1, 0], [1, 0]];
      for (let d = 0; d < 4; d++) {
        const nx = x + dirs[d][0];
        const ny = y + dirs[d][1];
        if (!this.inBounds(nx, ny)) continue;
        const ni = ny * w + nx;
        const nt = grid[ni];
        this.temp[ni] = Math.max(-196, this.temp[ni] - 32);

        if (nt === EL.WATER && this.rng() < 0.45) {
          this.setCell(nx, ny, EL.ICE, true);
        } else if (nt === EL.LAVA) {
          this.setCell(nx, ny, EL.STONE, true);
          this.setCell(x, y, EL.STEAM, true);
          return;
        } else if (nt === EL.FIRE || nt === EL.EMBER) {
          this.setCell(nx, ny, EL.STEAM, true);
        } else if (nt === EL.WOOD && this.life[ni] > 0) {
          this.life[ni] = 0;
        }
      }

      // Emit cold vapor mist above
      if (y > 0 && grid[i - w] === EL.EMPTY && this.rng() < 0.04) {
        this.setCell(x, y - 1, EL.STEAM, true);
      }

      this.updateLiquidFlow(x, y, i, EL.NITROGEN, 5);
    }

    updateFire(x, y, i) {
      const w = this.width;
      const grid = this.grid;

      if (this.life[i] <= 1) {
        this.setCell(x, y, this.rng() < 0.32 ? EL.SMOKE : EL.EMPTY, true);
        return;
      }
      this.life[i]--;

      const dirs = [[0, -1], [0, 1], [-1, 0], [1, 0]];
      for (let d = 0; d < 4; d++) {
        const nx = x + dirs[d][0];
        const ny = y + dirs[d][1];
        if (!this.inBounds(nx, ny)) continue;
        const ni = ny * w + nx;
        const nt = grid[ni];

        if (nt === EL.WATER) {
          this.setCell(x, y, EL.STEAM, true);
          if (this.rng() < 0.4) this.setCell(nx, ny, EL.STEAM, true);
          return;
        } else if (nt === EL.GUNPOWDER || nt === EL.C4) {
          this.queueExplosion(nx, ny, nt === EL.C4 ? 22 : 16);
          return;
        } else if (nt === EL.OIL) {
          this.setCell(nx, ny, EL.FIRE, true);
          this.life[ni] = 55 + ((this.rng() * 35) | 0);
        } else if (nt === EL.PLANT && this.rng() < 0.38) {
          this.setCell(nx, ny, EL.FIRE, true);
        } else if (nt === EL.WOOD && this.life[ni] === 0 && this.rng() < 0.065) {
          this.life[ni] = 1;
        } else if (nt === EL.FUSE && this.life[ni] === 0) {
          this.life[ni] = 1;
        } else if (nt === EL.ICE && this.rng() < 0.18) {
          this.setCell(nx, ny, EL.WATER, true);
          this.setCell(x, y, EL.STEAM, true);
          return;
        } else if (nt === EL.SNOW && this.rng() < 0.42) {
          this.setCell(nx, ny, EL.WATER, true);
        } else if (nt === EL.METAL) {
          this.temp[ni] = Math.min(800, this.temp[ni] + 18);
        }
      }

      if (y > 0) {
        const windDx = this.windX !== 0 && this.rng() < Math.abs(this.windX) * 0.7 ? Math.sign(this.windX) : (((this.rng() * 3) | 0) - 1);
        const nx = x + windDx;
        if (nx >= 0 && nx < w) {
          const up = (y - 1) * w + nx;
          if (grid[up] === EL.EMPTY || grid[up] === EL.SMOKE) {
            this.swap(i, up);
          }
        }
      }
    }

    updateEmber(x, y, i) {
      if (this.life[i] <= 1) {
        this.setCell(x, y, EL.SMOKE, true);
        return;
      }
      this.life[i]--;
      this.updatePowder(x, y, i, EL.EMBER);
    }

    updateFirework(x, y, i) {
      const w = this.width;
      const grid = this.grid;

      if (this.life[i] <= 1 || y <= 14) {
        const colIdx = this.variant[i];
        this.setCell(x, y, EL.EMPTY, true);
        this.burstFirework(x, y, colIdx);
        return;
      }
      this.life[i]--;

      // Rocket flies upward 2 cells per tick with slight sway and sparkling tail
      const sway = this.rng() < 0.25 ? (this.rng() < 0.5 ? -1 : 1) : 0;
      const nx = Math.max(2, Math.min(w - 3, x + sway));
      const ny = y - 2;
      if (ny < 4 || grid[ny * w + nx] !== EL.EMPTY) {
        const colIdx = this.variant[i];
        this.setCell(x, y, EL.EMPTY, true);
        this.burstFirework(x, y, colIdx);
        return;
      }

      const dest = ny * w + nx;
      this.moveTo(i, dest);
      // Leave fiery exhaust behind
      this.setCell(x, y, this.rng() < 0.65 ? EL.SPARK : EL.FIRE, true);
      if (y + 1 < this.height && grid[(y + 1) * w + x] === EL.EMPTY && this.rng() < 0.4) {
        this.setCell(x, y + 1, EL.SMOKE, true);
      }
    }

    updateGas(x, y, i, t) {
      const w = this.width;
      const grid = this.grid;

      if (this.life[i] <= 1) {
        if (t === EL.STEAM && y < 14 && this.rng() < 0.2) {
          this.setCell(x, y, EL.WATER, true);
        } else {
          this.setCell(x, y, EL.EMPTY, true);
        }
        return;
      }
      this.life[i]--;

      if (t === EL.TOXIC && this.rng() < 0.08 && y + 1 < this.height && grid[i + w] === EL.PLANT) {
        this.setCell(x, y + 1, EL.EMPTY, true);
      }

      const windDx = this.windX !== 0 && this.rng() < Math.abs(this.windX) * 0.7 ? Math.sign(this.windX) : (((this.rng() * 3) | 0) - 1);
      const dy = this.rng() < 0.72 ? -1 : 0;
      const nx = x + windDx;
      const ny = y + dy;
      if (this.inBounds(nx, ny)) {
        const ni = ny * w + nx;
        const nt = grid[ni];
        if (nt === EL.EMPTY) this.moveTo(i, ni);
        else if (IS_LIQUID[nt] && this.rng() < 0.25) this.swap(i, ni);
      }
    }

    updateSpark(x, y, i) {
      if (this.life[i] <= 1) {
        this.setCell(x, y, EL.EMPTY, true);
        return;
      }
      this.life[i]--;

      const dx = ((this.rng() * 3) | 0) - 1;
      const dy = ((this.rng() * 3) | 0) - 1;
      const nx = x + dx;
      const ny = y + dy;
      if (this.inBounds(nx, ny)) {
        const ni = ny * this.width + nx;
        const nt = this.grid[ni];
        if (nt === EL.GUNPOWDER || nt === EL.C4) {
          this.queueExplosion(nx, ny, nt === EL.C4 ? 22 : 15);
        } else if (nt === EL.OIL || nt === EL.PLANT) {
          this.setCell(nx, ny, EL.FIRE, true);
        } else if (nt === EL.FUSE && this.life[ni] === 0) {
          this.life[ni] = 1;
        } else if (nt === EL.METAL && this.charge[ni] === 0) {
          this.electrifyConductor(nx, ny);
        } else if (nt === EL.EMPTY && this.rng() < 0.5) {
          this.moveTo(i, ni);
        }
      }
    }

    updateMetal(x, y, i) {
      if (this.charge[i] > 0) {
        this.charge[i]--;
      }
    }

    updateWood(x, y, i) {
      const burn = this.life[i];
      if (burn === 0) return;
      this.temp[i] = Math.max(this.temp[i], 480);

      const w = this.width;
      const grid = this.grid;
      const dirs = [[0, -1], [0, 1], [-1, 0], [1, 0]];
      for (let d = 0; d < 4; d++) {
        const nx = x + dirs[d][0];
        const ny = y + dirs[d][1];
        if (!this.inBounds(nx, ny)) continue;
        const ni = ny * w + nx;
        const nt = grid[ni];
        if (nt === EL.WATER) {
          this.life[i] = 0;
          this.setCell(nx, ny, EL.STEAM, true);
          return;
        } else if (nt === EL.WOOD && this.life[ni] === 0 && this.rng() < 0.025) {
          this.life[ni] = 1;
        } else if (nt === EL.GUNPOWDER || nt === EL.C4) {
          this.queueExplosion(nx, ny, nt === EL.C4 ? 22 : 15);
          return;
        } else if (nt === EL.OIL || nt === EL.PLANT) {
          this.setCell(nx, ny, EL.FIRE, true);
        } else if (nt === EL.FUSE && this.life[ni] === 0) {
          this.life[ni] = 1;
        }
      }

      if (y > 0 && grid[i - w] === EL.EMPTY && this.rng() < 0.22) {
        this.setCell(x, y - 1, EL.FIRE, true);
      }

      this.life[i] = burn + 1;
      if (burn > 140 && this.rng() < 0.08) {
        this.setCell(x, y, this.rng() < 0.5 ? EL.FIRE : EL.SMOKE, true);
      }
    }

    updateFuse(x, y, i) {
      const burn = this.life[i];
      if (burn === 0) return;

      const w = this.width;
      const grid = this.grid;
      this.life[i] = burn + 1;
      if (burn < 2) return;

      for (let dy = -1; dy <= 1; dy++) {
        for (let dx = -1; dx <= 1; dx++) {
          if (dx === 0 && dy === 0) continue;
          const nx = x + dx;
          const ny = y + dy;
          if (!this.inBounds(nx, ny)) continue;
          const ni = ny * w + nx;
          const nt = grid[ni];
          if (nt === EL.FUSE && this.life[ni] === 0) {
            this.life[ni] = 1;
          } else if (nt === EL.GUNPOWDER || nt === EL.C4) {
            this.queueExplosion(nx, ny, nt === EL.C4 ? 23 : 16);
          } else if (nt === EL.OIL || nt === EL.PLANT) {
            this.setCell(nx, ny, EL.FIRE, true);
          } else if (nt === EL.WOOD && this.life[ni] === 0 && this.rng() < 0.4) {
            this.life[ni] = 1;
          } else if (nt === EL.METAL && this.charge[ni] === 0) {
            this.electrifyConductor(nx, ny);
          } else if (nt === EL.FIREWORK) {
            this.burstFirework(nx, ny, this.variant[ni]);
            this.setCell(nx, ny, EL.EMPTY, true);
          }
        }
      }

      this.setCell(x, y, this.rng() < 0.7 ? EL.SPARK : EL.FIRE, true);
    }

    updatePlant(x, y, i) {
      if (this.rng() > 0.045) return;
      const w = this.width;
      const grid = this.grid;
      const dirs = [[0, -1], [0, 1], [-1, 0], [1, 0]];

      for (let d = 0; d < 4; d++) {
        const nx = x + dirs[d][0];
        const ny = y + dirs[d][1];
        if (!this.inBounds(nx, ny)) continue;
        const ni = ny * w + nx;
        if (grid[ni] === EL.WATER) {
          this.setCell(nx, ny, EL.PLANT, true);
          const gx = x + (((this.rng() * 3) | 0) - 1);
          const gy = y + (this.rng() < 0.68 ? -1 : 0);
          if (this.inBounds(gx, gy) && grid[gy * w + gx] === EL.EMPTY && this.rng() < 0.58) {
            this.setCell(gx, gy, EL.PLANT, true);
          }
          return;
        }
      }
    }

    updateIce(x, y, i) {
      if (this.rng() > 0.01) return;
      const w = this.width;
      const grid = this.grid;
      const dirs = [[0, -1], [0, 1], [-1, 0], [1, 0]];
      const d = (this.rng() * 4) | 0;
      const nx = x + dirs[d][0];
      const ny = y + dirs[d][1];
      if (!this.inBounds(nx, ny)) return;
      if (grid[ny * w + nx] === EL.WATER) {
        this.setCell(nx, ny, EL.ICE, true);
      }
    }

    updateCloner(x, y, i) {
      const w = this.width;
      const grid = this.grid;
      const dirs = [[0, -1], [0, 1], [-1, 0], [1, 0]];

      let target = this.life[i];
      if (target === 0) {
        for (let d = 0; d < 4; d++) {
          const nx = x + dirs[d][0];
          const ny = y + dirs[d][1];
          if (!this.inBounds(nx, ny)) continue;
          const nt = grid[ny * w + nx];
          if (nt !== EL.EMPTY && nt !== EL.CLONER && nt !== EL.VOID && !IS_STATIC[nt]) {
            this.life[i] = nt;
            target = nt;
            break;
          }
        }
        return;
      }

      const rate = target === EL.FIREWORK ? 0.015 : 0.26;
      if (this.rng() > rate) return;

      const emitDirs = target === EL.FIREWORK ? [[0, -1]] : [[0, 1], [-1, 0], [1, 0], [0, -1]];
      for (let d = 0; d < emitDirs.length; d++) {
        const nx = x + emitDirs[d][0];
        const ny = y + emitDirs[d][1];
        if (!this.inBounds(nx, ny)) continue;
        const ni = ny * w + nx;
        if (grid[ni] === EL.EMPTY) {
          this.setCell(nx, ny, target, true);
          return;
        }
      }
    }

    updateVoid(x, y, i) {
      const w = this.width;
      const grid = this.grid;
      const dirs = [[0, -1], [0, 1], [-1, 0], [1, 0]];
      for (let d = 0; d < 4; d++) {
        const nx = x + dirs[d][0];
        const ny = y + dirs[d][1];
        if (!this.inBounds(nx, ny)) continue;
        const ni = ny * w + nx;
        const nt = grid[ni];
        if (nt !== EL.EMPTY && nt !== EL.VOID && nt !== EL.CLONER && nt !== EL.STONE && nt !== EL.GLASS) {
          this.setCell(nx, ny, EL.EMPTY, true);
        }
      }
    }

    // Build smooth 2D quarter-res dynamic lightmap from emissive cells, particles & external entities
    buildLightmap(extraLights) {
      const lw = this.lw;
      const lh = this.lh;
      const lSize = lw * lh;
      const lr = this.lightR;
      const lg = this.lightG;
      const lb = this.lightB;

      // Ambient moonlight base so unlit caves feel atmospheric (not pitch black)
      lr.fill(0.46);
      lg.fill(0.51);
      lb.fill(0.62);

      const w = this.width;
      const h = this.height;
      const grid = this.grid;
      const life = this.life;
      const charge = this.charge;
      const temp = this.temp;

      for (let ly = 0; ly < lh; ly++) {
        const y0 = ly << 2;
        const lRow = ly * lw;
        for (let lx = 0; lx < lw; lx++) {
          const x0 = lx << 2;
          let er = 0, eg = 0, eb = 0;

          // Sample 2x2 stride inside 4x4 block for speed
          for (let dy = 0; dy < 4 && y0 + dy < h; dy += 2) {
            const row = (y0 + dy) * w;
            for (let dx = 0; dx < 4 && x0 + dx < w; dx += 2) {
              const i = row + x0 + dx;
              const t = grid[i];
              if (t === EL.FIRE) {
                er += 1.5; eg += 0.85; eb += 0.22;
              } else if (t === EL.LAVA) {
                er += 1.65; eg += 0.56; eb += 0.14;
              } else if (t === EL.SPARK) {
                er += 0.9; eg += 1.45; eb += 1.8;
              } else if (t === EL.ACID) {
                er += 0.3; eg += 0.95; eb += 0.25;
              } else if (t === EL.NITROGEN) {
                er += 0.22; eg += 0.65; eb += 0.85;
              } else if (t === EL.CLONER) {
                er += 0.65; eg += 0.22; eb += 0.85;
              } else if (t === EL.WOOD && life[i] > 0) {
                er += 1.1; eg += 0.45; eb += 0.1;
              } else if (t === EL.FUSE && life[i] > 0) {
                er += 1.3; eg += 0.95; eb += 0.35;
              } else if (t === EL.METAL && (charge[i] > 0 || temp[i] > 350)) {
                if (charge[i] > 0) { er += 0.55; eg += 1.1; eb += 1.5; }
                else { er += 0.9; eg += 0.32; eb += 0.08; }
              } else if (t === EL.FIREWORK) {
                er += 1.3; eg += 0.55; eb += 1.1;
              }
            }
          }

          if (er > 0 || eg > 0 || eb > 0) {
            const li = lRow + lx;
            lr[li] = Math.min(2.6, lr[li] + er);
            lg[li] = Math.min(2.6, lg[li] + eg);
            lb[li] = Math.min(2.6, lb[li] + eb);
          }
        }
      }

      // Add light from ballistic glowing particles (firework bursts / flying embers)
      for (let k = 0; k < this.particles.length; k++) {
        const p = this.particles[k];
        if (!p.rgb && p.element !== EL.FIRE && p.element !== EL.LAVA && p.element !== EL.SPARK) continue;
        const lx = (p.x >> 2);
        const ly = (p.y >> 2);
        if (lx < 0 || lx >= lw || ly < 0 || ly >= lh) continue;
        const li = ly * lw + lx;
        const rgb = p.rgb || [255, 160, 60];
        lr[li] = Math.min(2.8, lr[li] + rgb[0] / 180);
        lg[li] = Math.min(2.8, lg[li] + rgb[1] / 180);
        lb[li] = Math.min(2.8, lb[li] + rgb[2] / 180);
      }

      // Add light from external entities (wizard wand, spell projectiles, black holes, monsters)
      if (extraLights && extraLights.length > 0) {
        for (let k = 0; k < extraLights.length; k++) {
          const L = extraLights[k];
          const clx = (L.x >> 2);
          const cly = (L.y >> 2);
          const rad = Math.max(1, (L.radius || 8) >> 2);
          for (let dy = -rad; dy <= rad; dy++) {
            const ly = cly + dy;
            if (ly < 0 || ly >= lh) continue;
            for (let dx = -rad; dx <= rad; dx++) {
              const lx = clx + dx;
              if (lx < 0 || lx >= lw) continue;
              const d = Math.sqrt(dx * dx + dy * dy);
              if (d > rad) continue;
              const falloff = 1 - d / (rad + 0.5);
              const li = ly * lw + lx;
              lr[li] = Math.min(3.0, lr[li] + L.r * falloff);
              lg[li] = Math.min(3.0, lg[li] + L.g * falloff);
              lb[li] = Math.min(3.0, lb[li] + L.b * falloff);
            }
          }
        }
      }

      // 3-pass separable diffusion blur for creamy wide light falloff
      const tr = this.lightTmpR, tg = this.lightTmpG, tb = this.lightTmpB;
      for (let pass = 0; pass < 3; pass++) {
        // Horizontal
        for (let y = 0; y < lh; y++) {
          const row = y * lw;
          for (let x = 0; x < lw; x++) {
            const xm = x > 0 ? x - 1 : 0;
            const xp = x < lw - 1 ? x + 1 : lw - 1;
            const i = row + x;
            tr[i] = (lr[row + xm] + lr[i] * 2 + lr[row + xp]) * 0.246;
            tg[i] = (lg[row + xm] + lg[i] * 2 + lg[row + xp]) * 0.246;
            tb[i] = (lb[row + xm] + lb[i] * 2 + lb[row + xp]) * 0.246;
          }
        }
        // Vertical
        for (let y = 0; y < lh; y++) {
          const ym = (y > 0 ? y - 1 : 0) * lw;
          const yc = y * lw;
          const yp = (y < lh - 1 ? y + 1 : lh - 1) * lw;
          for (let x = 0; x < lw; x++) {
            const i = yc + x;
            lr[i] = (tr[ym + x] + tr[i] * 2 + tr[yp + x]) * 0.246;
            lg[i] = (tg[ym + x] + tg[i] * 2 + tg[yp + x]) * 0.246;
            lb[i] = (tb[ym + x] + tb[i] * 2 + tb[yp + x]) * 0.246;
          }
        }
      }
      void lSize;
    }

    render(mainBuf32, glowBuf32, options) {
      const opts = options || {};
      const thermalMode = !!opts.thermal;
      const lighting = opts.lighting !== false && !thermalMode;

      const size = this.size;
      const w = this.width;
      const h = this.height;
      const grid = this.grid;
      const life = this.life;
      const variant = this.variant;
      const temp = this.temp;
      const charge = this.charge;
      const frame = this.frameCount;

      if (thermalMode) {
        for (let i = 0; i < size; i++) {
          const t = temp[i];
          // Map -196..900C smoothly onto 0..255 LUT
          const norm = Math.max(0, Math.min(255, ((t + 160) * 0.26) | 0));
          mainBuf32[i] = THERMAL_LUT[norm];
          if (glowBuf32) {
            glowBuf32[i] = norm > 185 ? THERMAL_LUT[norm] : 0;
          }
        }
        this.renderParticlesIntoBuffer(mainBuf32, glowBuf32, true);
        return;
      }

      if (lighting) {
        this.buildLightmap(opts.extraLights);
      }

      const lw = this.lw;
      const lr = this.lightR;
      const lg = this.lightG;
      const lb = this.lightB;

      for (let i = 0; i < size; i++) {
        const x = i % w;
        const y = (i / w) | 0;
        const t = grid[i];

        const li = lighting ? (y >> 2) * lw + (x >> 2) : 0;
        const multR = lighting ? lr[li] : 1;
        const multG = lighting ? lg[li] : 1;
        const multB = lighting ? lb[li] : 1;

        if (t === EL.EMPTY) {
          // Deep atmospheric night sky / cave gradient illuminated by dynamic lightmap!
          const sky = 12 + ((y / h) * 14);
          const gridLine = ((x & 15) === 0 || (y & 15) === 0) ? 3 : 0;
          const br = clampByte((sky * 0.72 + gridLine) * multR);
          const bg = clampByte((sky * 0.9 + gridLine) * multG);
          const bb = clampByte((sky * 1.38 + gridLine) * multB);
          mainBuf32[i] = packABGR(br, bg, bb, 255);
          if (glowBuf32) glowBuf32[i] = 0;
          continue;
        }

        const v = variant[i];
        const dv = (v & 31) - 16;
        let r = 0, g = 0, b = 0;
        let gr = 0, gg = 0, gb = 0, ga = 0;
        let emissive = false;

        switch (t) {
          case EL.SAND:
            r = clampByte(234 + dv);
            g = clampByte(196 + dv * 0.8);
            b = clampByte(106 + dv * 0.6);
            break;
          case EL.GUNPOWDER:
            r = clampByte(74 + dv);
            g = clampByte(78 + dv);
            b = clampByte(90 + dv);
            break;
          case EL.SNOW:
            r = clampByte(234 + (dv >> 1));
            g = clampByte(245 + (dv >> 2));
            b = 255;
            break;
          case EL.SALT:
            r = clampByte(242 + (dv >> 1));
            g = clampByte(238 + (dv >> 1));
            b = clampByte(226 + (dv >> 1));
            break;
          case EL.MITE: {
            const leg = ((frame >> 1) + x) & 1 ? 25 : -10;
            r = clampByte(255);
            g = clampByte(96 + leg);
            b = clampByte(154 + leg);
            gr = 255; gg = 90; gb = 160; ga = 95;
            emissive = true;
            break;
          }
          case EL.WATER: {
            const surface = y > 0 && grid[i - w] === EL.EMPTY ? 44 : 0;
            const shimmer = (((frame >> 2) + v + (x & 7)) & 15) === 0 ? 30 : 0;
            const depthShade = (y > 4 && grid[i - w * 4] === EL.WATER) ? -22 : 0;
            r = clampByte(28 + surface + shimmer + (dv >> 2));
            g = clampByte(138 + surface + shimmer + depthShade + (dv >> 1));
            b = clampByte(248 + (shimmer >> 1) + (depthShade >> 1));
            break;
          }
          case EL.OIL: {
            const sheen = (((frame >> 3) + x + y) & 15) === 0 ? 16 : 0;
            r = clampByte(70 + (dv >> 1) + sheen);
            g = clampByte(46 + (dv >> 2) + (sheen >> 1));
            b = clampByte(36 + (dv >> 2) + sheen);
            break;
          }
          case EL.LAVA: {
            const pulse = (((frame >> 2) + v) & 31) < 12 ? 36 : 0;
            r = 255;
            g = clampByte(82 + (v & 63) + pulse);
            b = clampByte(14 + (pulse >> 1));
            gr = 255; gg = clampByte(100 + pulse); gb = 24; ga = 230;
            emissive = true;
            break;
          }
          case EL.ACID: {
            const fizz = (((frame >> 1) + v) & 15) === 0 ? 48 : 0;
            r = clampByte(96 + (dv >> 1) + fizz);
            g = 255;
            b = clampByte(56 + fizz);
            gr = 100; gg = 255; gb = 62; ga = 195;
            emissive = true;
            break;
          }
          case EL.NITROGEN: {
            const frost = (((frame >> 2) + v) & 15) < 4 ? 32 : 0;
            r = clampByte(120 + frost);
            g = clampByte(232 + (frost >> 1));
            b = 255;
            gr = 120; gg = 235; gb = 255; ga = 140;
            emissive = true;
            break;
          }
          case EL.STONE: {
            const strata = ((y >> 2) + ((x >> 4) & 1)) & 1 ? 10 : -8;
            const edge = (y > 0 && grid[i - w] === EL.EMPTY) ? 24 : 0;
            r = clampByte(108 + strata + edge + (dv >> 1));
            g = clampByte(116 + strata + edge + (dv >> 1));
            b = clampByte(132 + strata + edge + (dv >> 1));
            break;
          }
          case EL.METAL: {
            if (charge[i] > 0) {
              r = 165; g = 236; b = 255;
              gr = 110; gg = 220; gb = 255; ga = 240;
              emissive = true;
            } else {
              const hot = Math.max(0, Math.min(1, (temp[i] - 180) / 600));
              const brush = ((x + y) & 3) === 0 ? 12 : -4;
              r = clampByte(142 + brush + hot * 115 + (dv >> 2));
              g = clampByte(156 + brush - hot * 40 + (dv >> 2));
              b = clampByte(174 + brush - hot * 125 + (dv >> 2));
              if (hot > 0.2) {
                gr = 255; gg = clampByte(90 * hot); gb = 18; ga = clampByte(hot * 220);
                emissive = true;
              }
            }
            break;
          }
          case EL.WOOD: {
            if (life[i] > 0) {
              const flick = ((frame + v) & 7) * 14;
              r = clampByte(242 + (flick >> 2));
              g = clampByte(92 + flick);
              b = 22;
              gr = 255; gg = 105; gb = 22; ga = 210;
              emissive = true;
            } else {
              const grain = (((x >> 2) ^ y) & 3) ? 9 : -9;
              r = clampByte(140 + grain + (dv >> 1));
              g = clampByte(86 + grain + (dv >> 2));
              b = clampByte(48 + (dv >> 2));
            }
            break;
          }
          case EL.PLANT:
            r = clampByte(42 + (dv >> 1));
            g = clampByte(184 + dv);
            b = clampByte(80 + (dv >> 1));
            break;
          case EL.GLASS: {
            const spec = (x + y) % 9 === 0 ? 40 : 0;
            r = clampByte(132 + spec);
            g = clampByte(216 + (spec >> 1));
            b = clampByte(246 + (spec >> 2));
            break;
          }
          case EL.ICE:
            r = clampByte(146 + (dv >> 1));
            g = clampByte(230 + (dv >> 2));
            b = 255;
            break;
          case EL.FUSE:
            if (life[i] > 0) {
              r = 255; g = 236; b = 128;
              gr = 255; gg = 195; gb = 65; ga = 245;
              emissive = true;
            } else {
              const twist = ((x + y) & 2) ? 18 : -12;
              r = clampByte(198 + twist);
              g = clampByte(132 + twist);
              b = clampByte(86 + (twist >> 1));
            }
            break;
          case EL.C4: {
            const blink = (((frame >> 3) + (x >> 2)) & 7) === 0 && ((x & 3) === 1 && (y & 3) === 1);
            if (blink) {
              r = 255; g = 48; b = 62;
              gr = 255; gg = 40; gb = 60; ga = 220;
              emissive = true;
            } else {
              r = clampByte(208 + (dv >> 1));
              g = clampByte(200 + (dv >> 1));
              b = clampByte(174 + (dv >> 1));
            }
            break;
          }
          case EL.CLONER: {
            const glow = ((frame >> 2) & 15) * 4;
            r = clampByte(204 + glow);
            g = clampByte(76 + (glow >> 1));
            b = 255;
            gr = 215; gg = 85; gb = 255; ga = 180;
            emissive = true;
            break;
          }
          case EL.VOID: {
            const ring = ((frame + v) & 31) < 6 ? 42 : 0;
            r = 46 + ring;
            g = 22 + (ring >> 1);
            b = 82 + ring;
            break;
          }
          case EL.FIRE: {
            const heat = life[i];
            if (heat > 38) { r = 255; g = 250; b = 192; }
            else if (heat > 20) { r = 255; g = clampByte(148 + (heat - 20) * 5); b = 32; }
            else { r = clampByte(180 + heat * 4); g = clampByte(42 + heat * 3); b = 12; }
            gr = r; gg = g; gb = b; ga = 240;
            emissive = true;
            break;
          }
          case EL.EMBER:
            r = 255; g = 186; b = 72;
            gr = 255; gg = 160; gb = 50; ga = 225;
            emissive = true;
            break;
          case EL.FIREWORK: {
            const col = FW_COLORS[v % FW_COLORS.length];
            r = col[0]; g = col[1]; b = col[2];
            gr = r; gg = g; gb = b; ga = 255;
            emissive = true;
            break;
          }
          case EL.SPARK:
            r = 220; g = 248; b = 255;
            gr = 145; gg = 228; gb = 255; ga = 255;
            emissive = true;
            break;
          case EL.SMOKE: {
            const fade = Math.min(1, life[i] / 65);
            const c = clampByte(46 + fade * 48 + (dv >> 2));
            r = c; g = c + 2; b = c + 8;
            break;
          }
          case EL.STEAM: {
            const fade = Math.min(1, life[i] / 95);
            r = clampByte(150 + fade * 78);
            g = clampByte(168 + fade * 76);
            b = clampByte(192 + fade * 62);
            break;
          }
          case EL.TOXIC: {
            const fade = Math.min(1, life[i] / 75);
            r = clampByte(76 + fade * 55);
            g = clampByte(165 + fade * 80);
            b = clampByte(56 + fade * 35);
            gr = 90; gg = 240; gb = 60; ga = 120;
            emissive = true;
            break;
          }
          default:
            r = 255; g = 0; b = 255;
        }

        if (lighting && !emissive) {
          r = clampByte(r * multR);
          g = clampByte(g * multG);
          b = clampByte(b * multB);
        }

        mainBuf32[i] = packABGR(r, g, b, 255);
        if (glowBuf32) {
          glowBuf32[i] = ga > 0 ? packABGR(gr, gg, gb, ga) : 0;
        }
      }

      this.renderParticlesIntoBuffer(mainBuf32, glowBuf32, false);
    }

    renderParticlesIntoBuffer(mainBuf32, glowBuf32, thermalMode) {
      const w = this.width;
      const h = this.height;

      // Flying debris & firework star bursts with short streak trail
      for (let k = 0; k < this.particles.length; k++) {
        const p = this.particles[k];
        const x = p.x | 0;
        const y = p.y | 0;
        if (x < 0 || x >= w || y < 0 || y >= h) continue;

        let r = 240, g = 205, b = 120;
        let glow = false;
        if (thermalMode) {
          const lutCol = p.rgb || p.element === EL.EMBER || p.element === EL.SPARK ? THERMAL_LUT[245] : THERMAL_LUT[140];
          mainBuf32[y * w + x] = lutCol;
          continue;
        }

        if (p.rgb) {
          const fade = Math.min(1, p.life / (p.maxLife * 0.45));
          r = clampByte(p.rgb[0] * fade + 40);
          g = clampByte(p.rgb[1] * fade + 40);
          b = clampByte(p.rgb[2] * fade + 40);
          glow = true;
        } else if (p.element === EL.WATER) {
          r = 72; g = 178; b = 255;
        } else if (p.element === EL.LAVA || p.element === EL.EMBER) {
          r = 255; g = 135; b = 40; glow = true;
        } else if (p.element === EL.ACID) {
          r = 110; g = 255; b = 70; glow = true;
        } else if (p.element === EL.SPARK) {
          r = 215; g = 245; b = 255; glow = true;
        }

        const col = packABGR(r, g, b, 255);
        mainBuf32[y * w + x] = col;
        if (glow && glowBuf32) {
          glowBuf32[y * w + x] = packABGR(r, g, b, 245);
        }
        // 1px motion trail behind fast particles
        const tx = (p.x - p.vx * 0.5) | 0;
        const ty = (p.y - p.vy * 0.5) | 0;
        if (tx >= 0 && tx < w && ty >= 0 && ty < h) {
          mainBuf32[ty * w + tx] = packABGR(r >> 1, g >> 1, b >> 1, 255);
          if (glow && glowBuf32) glowBuf32[ty * w + tx] = packABGR(r, g, b, 150);
        }
      }

      // Draw bouncing bombs as crisp 3x3 icons with pulsing red core
      for (let k = 0; k < this.bombs.length; k++) {
        const b = this.bombs[k];
        const bx = b.x | 0;
        const by = b.y | 0;
        const flash = (b.fuse & 7) < 4;
        for (let dy = -1; dy <= 1; dy++) {
          for (let dx = -1; dx <= 1; dx++) {
            const px = bx + dx;
            const py = by + dy;
            if (px < 0 || px >= w || py < 0 || py >= h) continue;
            const center = dx === 0 && dy === 0;
            const col = center
              ? packABGR(255, flash ? 80 : 210, 48, 255)
              : packABGR(56, 62, 74, 255);
            mainBuf32[py * w + px] = col;
            if (center && glowBuf32) {
              glowBuf32[py * w + px] = packABGR(255, 110, 40, 255);
            }
          }
        }
      }
    }
  }

  return {
    EL,
    ELEMENT_META,
    ELEMENT_NAMES,
    SandWorld,
  };
});
