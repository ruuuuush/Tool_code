(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.SandPresets = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  function fillRect(world, x0, y0, w, h, type, force) {
    for (let y = y0; y < y0 + h; y++) {
      for (let x = x0; x < x0 + w; x++) {
        world.setCell(x, y, type, force !== false);
      }
    }
  }

  function strokeBeaker(world, x, y, w, h, wall, type) {
    fillRect(world, x, y, wall, h, type, true);
    fillRect(world, x + w - wall, y, wall, h, type, true);
    fillRect(world, x, y + h - wall, w, wall, type, true);
  }

  function drawForcedLine(world, x0, y0, x1, y1, type, thickness) {
    x0 |= 0; y0 |= 0; x1 |= 0; y1 |= 0;
    const r = thickness || 1;
    const dx = Math.abs(x1 - x0);
    const dy = Math.abs(y1 - y0);
    const sx = x0 < x1 ? 1 : -1;
    const sy = y0 < y1 ? 1 : -1;
    let err = dx - dy;
    while (true) {
      for (let oy = -r; oy <= r; oy++) {
        for (let ox = -r; ox <= r; ox++) {
          if (ox * ox + oy * oy <= r * r) {
            world.setCell(x0 + ox, y0 + oy, type, true);
          }
        }
      }
      if (x0 === x1 && y0 === y1) break;
      const e2 = err << 1;
      if (e2 > -dy) { err -= dy; x0 += sx; }
      if (e2 < dx) { err += dx; y0 += sy; }
    }
  }

  function setClonerWith(world, x, y, w, h, targetType, EL) {
    for (let dy = 0; dy < h; dy++) {
      for (let dx = 0; dx < w; dx++) {
        const px = x + dx;
        const py = y + dy;
        world.setCell(px, py, EL.CLONER, true);
        if (world.inBounds(px, py)) {
          world.life[py * world.width + px] = targetType;
        }
      }
    }
  }

  const PRESETS = [
    {
      id: 'noita_mine',
      name: '诺伊塔矿坑',
      hint: 'WASD 移动/浮空，左键魔杖，右键传送弹闪现！按 1-5 切魔杖，炸穿多层暗穴',
      spawn: { x: 42, y: 46 },
      hasEnemies: true,
      build(world, EL) {
        world.clear();
        const w = world.width;
        const h = world.height;

        // Fill solid rocky underground first, then carve atmospheric caverns!
        fillRect(world, 0, 0, w, h, EL.STONE, true);

        // Carve upper entrance hall & wide horizontal gallery
        world.paintCircle(46, 48, 28, EL.EMPTY, false);
        world.paintCircle(96, 50, 26, EL.EMPTY, false);
        world.paintCircle(148, 52, 28, EL.EMPTY, false);
        world.paintCircle(206, 52, 28, EL.EMPTY, false);
        world.paintCircle(266, 54, 28, EL.EMPTY, false);
        world.paintCircle(332, 54, 30, EL.EMPTY, false);
        fillRect(world, 42, 34, 294, 26, EL.EMPTY, true);

        // Vertical drop shafts connecting level 1 -> level 2 -> level 3
        fillRect(world, 118, 58, 26, 74, EL.EMPTY, true);
        fillRect(world, 252, 62, 24, 72, EL.EMPTY, true);
        fillRect(world, 330, 68, 24, 96, EL.EMPTY, true);

        // Level 2: underground river, wooden bridge & explosive barrels
        world.paintCircle(66, 126, 26, EL.EMPTY, false);
        world.paintCircle(128, 128, 30, EL.EMPTY, false);
        world.paintCircle(196, 126, 32, EL.EMPTY, false);
        world.paintCircle(266, 128, 28, EL.EMPTY, false);
        world.paintCircle(332, 130, 28, EL.EMPTY, false);

        // Level 3: magma vault, gold treasure room & cryo chamber
        world.paintCircle(82, 194, 28, EL.EMPTY, false);
        world.paintCircle(156, 194, 34, EL.EMPTY, false);
        world.paintCircle(238, 196, 30, EL.EMPTY, false);
        world.paintCircle(320, 194, 32, EL.EMPTY, false);
        fillRect(world, 100, 184, 224, 26, EL.EMPTY, true);
        fillRect(world, 182, 146, 24, 42, EL.EMPTY, true);

        // Keep outer bedrock frame intact
        fillRect(world, 0, 0, w, 10, EL.STONE, true);
        fillRect(world, 0, h - 10, w, 10, EL.STONE, true);
        fillRect(world, 0, 0, 10, h, EL.STONE, true);
        fillRect(world, w - 10, 0, 10, h, EL.STONE, true);

        // Entrance temple platform & wooden scaffolds
        fillRect(world, 16, 62, 58, 5, EL.WOOD, true);
        fillRect(world, 114, 92, 34, 4, EL.WOOD, true);
        fillRect(world, 168, 136, 56, 4, EL.WOOD, true);

        // Conductive metal catwalk on upper right + explosive barrels
        fillRect(world, 184, 68, 94, 4, EL.METAL, true);
        strokeBeaker(world, 210, 48, 20, 20, 2, EL.GLASS);
        fillRect(world, 212, 52, 16, 14, EL.GUNPOWDER, true);
        strokeBeaker(world, 294, 52, 22, 20, 2, EL.WOOD);
        fillRect(world, 296, 56, 18, 14, EL.OIL, true);

        // Hanging C4 cluster with fuse in mid-level
        fillRect(world, 190, 108, 18, 8, EL.C4, true);
        drawForcedLine(world, 174, 112, 192, 112, EL.FUSE, 1);

        // Underground water pond (jump in if you catch fire!)
        fillRect(world, 114, 142, 66, 16, EL.WATER, true);
        fillRect(world, 46, 138, 42, 12, EL.PLANT, true);

        // Bottom left: Cryo liquid nitrogen & ice pocket
        fillRect(world, 56, 206, 50, 14, EL.ICE, true);
        fillRect(world, 64, 198, 34, 8, EL.NITROGEN, true);

        // Bottom center: Magma pit & glowing torches
        fillRect(world, 132, 212, 92, 18, EL.LAVA, true);
        fillRect(world, 174, 194, 10, 20, EL.METAL, true);

        // Bottom right: Golden sand treasure vault behind glass & wood barrier!
        fillRect(world, 286, 176, 5, 44, EL.GLASS, true);
        fillRect(world, 294, 192, 58, 28, EL.SAND, true);
        fillRect(world, 310, 184, 24, 8, EL.GUNPOWDER, true);

        // Hanging cavern vine lanterns (wood + gentle fire braziers)
        const torches = [[78, 36], [198, 34], [312, 34], [92, 108], [286, 108]];
        for (const [tx, ty] of torches) {
          fillRect(world, tx - 2, ty, 5, 3, EL.METAL, true);
          world.setCell(tx, ty - 1, EL.LAVA, true);
        }
      },
    },
    {
      id: 'cavern',
      name: '暗穴火山遗迹',
      hint: '观察岩浆动态照亮石窟、烤红金属桥把水烧开；试试按 T 切热成像视角！',
      build(world, EL) {
        world.clear();
        const w = world.width;
        const h = world.height;

        // Rocky cavern ceiling with stalactites
        for (let x = 0; x < w; x++) {
          const roof = 10 + Math.round(Math.sin(x * 0.045) * 6 + Math.cos(x * 0.13) * 4);
          fillRect(world, x, 0, 1, Math.max(4, roof), EL.STONE, true);
        }

        // Bedrock floor
        fillRect(world, 0, h - 12, w, 12, EL.STONE, true);

        // Left volcanic peak
        for (let row = 0; row < 108; row++) {
          const y = h - 12 - row;
          const half = Math.max(11, Math.round(74 - row * 0.56));
          const cx = 86;
          for (let x = cx - half; x <= cx + half; x++) {
            const dist = Math.abs(x - cx);
            if (dist > 8 || row < 32) {
              world.setCell(x, y, EL.STONE, true);
            }
          }
        }
        // Magma conduit + cloner
        fillRect(world, 80, h - 114, 12, 66, EL.LAVA, true);
        setClonerWith(world, 84, h - 78, 4, 4, EL.LAVA, EL);

        // Conductive metal bridge anchored in volcano slope extending over water basin!
        fillRect(world, 118, h - 54, 62, 5, EL.METAL, true);
        fillRect(world, 174, h - 54, 5, 22, EL.METAL, true);

        // Central lake & sandy bed
        fillRect(world, 152, h - 48, 134, 36, EL.WATER, true);
        for (let i = 0; i < 48; i++) {
          fillRect(world, 154 + i, h - 18 - ((i * 0.18) | 0), 2, 7, EL.SAND, true);
        }

        // Central sanctuary island with glowing lantern (wood + tree)
        fillRect(world, 212, h - 56, 32, 8, EL.STONE, true);
        fillRect(world, 225, h - 82, 5, 26, EL.WOOD, true);
        world.paintCircle(227, h - 88, 13, EL.PLANT, false);
        fillRect(world, 214, h - 62, 28, 6, EL.PLANT, true);

        // Right glacier wall + waterfall cloner
        for (let row = 0; row < 118; row++) {
          const y = h - 12 - row;
          const left = w - 108 + Math.round(row * 0.54);
          for (let x = left; x < w; x++) {
            world.setCell(x, y, row > 90 ? EL.SNOW : EL.ICE, true);
          }
        }
        setClonerWith(world, w - 68, 28, 4, 3, EL.WATER, EL);
      },
    },
    {
      id: 'detonation',
      name: '赛博电路爆破厂',
      hint: '用「闪电」劈击左上角金属天线，或直接按 X 遥控引爆全图 C4 阵列！',
      build(world, EL) {
        world.clear();
        const w = world.width;
        const h = world.height;

        fillRect(world, 0, h - 12, w, 12, EL.STONE, true);
        fillRect(world, 28, h - 76, w - 56, 6, EL.WOOD, true);

        // Support steel pillars
        fillRect(world, 54, h - 70, 6, 58, EL.METAL, true);
        fillRect(world, 168, h - 70, 6, 58, EL.METAL, true);
        fillRect(world, 282, h - 70, 6, 58, EL.METAL, true);

        // Three glass explosive vaults
        const chambers = [
          { x: 74,  y: h - 134, w: 62, h: 58, fill: EL.GUNPOWDER },
          { x: 174, y: h - 142, w: 64, h: 66, fill: EL.OIL },
          { x: 278, y: h - 138, w: 64, h: 62, fill: EL.GUNPOWDER },
        ];
        for (const c of chambers) {
          strokeBeaker(world, c.x, c.y, c.w, c.h, 3, EL.GLASS);
          fillRect(world, c.x + 3, c.y + 14, c.w - 6, c.h - 17, c.fill, true);
          fillRect(world, c.x + 8, c.y - 10, c.w - 16, 10, EL.SAND, true);
        }

        // C4 clusters planted on pillars & vaults
        fillRect(world, 146, h - 84, 16, 8, EL.C4, true);
        fillRect(world, 250, h - 84, 16, 8, EL.C4, true);
        fillRect(world, 198, h - 42, 22, 12, EL.C4, true);

        // Lower oil & gunpowder trench
        fillRect(world, 66, h - 38, 96, 26, EL.OIL, true);
        fillRect(world, 180, h - 36, 98, 24, EL.GUNPOWDER, true);
        fillRect(world, 294, h - 38, 66, 26, EL.GUNPOWDER, true);

        // Left lightning rod metal antenna -> fuse -> vault 1 -> metal bus -> vault 2 -> fuse -> vault 3
        fillRect(world, 34, 48, 5, h - 146, EL.METAL, true);
        fillRect(world, 26, 48, 21, 4, EL.METAL, true);
        drawForcedLine(world, 36, h - 98, 86, h - 98, EL.FUSE, 1);

        drawForcedLine(world, 128, h - 98, 186, h - 98, EL.FUSE, 1);
        drawForcedLine(world, 232, h - 98, 292, h - 98, EL.FUSE, 1);

        // Downward fuse branch to lower trench
        drawForcedLine(world, 154, h - 98, 154, h - 30, EL.FUSE, 1);
        drawForcedLine(world, 154, h - 30, 196, h - 30, EL.FUSE, 1);
      },
    },
    {
      id: 'fireworks',
      name: '霓虹烟花之夜',
      hint: '三座自动烟花炮台持续点亮夜空；试试用「旋风」把漫天星火卷成星云！',
      build(world, EL) {
        world.clear();
        const w = world.width;
        const h = world.height;

        // Calm night lake + stone basin
        fillRect(world, 0, h - 10, w, 10, EL.STONE, true);
        fillRect(world, 0, h - 34, w, 24, EL.WATER, true);

        // Three elevated stone launch islands with firework cloners
        const launchers = [86, 200, 314];
        for (const lx of launchers) {
          fillRect(world, lx - 16, h - 42, 32, 32, EL.STONE, true);
          strokeBeaker(world, lx - 6, h - 54, 12, 12, 2, EL.METAL);
          setClonerWith(world, lx - 2, h - 46, 4, 2, EL.FIREWORK, EL);
        }

        // Two wooden lakeside pavilions with vine roofs
        const pavs = [132, 244];
        for (const px of pavs) {
          fillRect(world, px, h - 40, 28, 30, EL.STONE, true);
          fillRect(world, px + 3, h - 66, 3, 26, EL.WOOD, true);
          fillRect(world, px + 22, h - 66, 3, 26, EL.WOOD, true);
          fillRect(world, px - 4, h - 71, 36, 5, EL.WOOD, true);
          fillRect(world, px, h - 76, 28, 5, EL.PLANT, true);
        }

        // Launch 3 initial fireworks immediately for instant wow
        world.setCell(86, h - 64, EL.FIREWORK, true);
        world.setCell(200, h - 74, EL.FIREWORK, true);
        world.setCell(314, h - 60, EL.FIREWORK, true);
      },
    },
    {
      id: 'cryo_lab',
      name: '液氮强酸炼金塔',
      hint: '左侧强酸溢流蚀桥、中间液氮瞬冻水池、右侧噬木蚁正疯狂啃食木屋！',
      build(world, EL) {
        world.clear();
        const w = world.width;
        const h = world.height;

        // Left acid beaker & glass chute
        strokeBeaker(world, 28, 34, 68, 44, 3, EL.GLASS);
        fillRect(world, 31, 56, 62, 19, EL.ACID, true);
        setClonerWith(world, 60, 14, 3, 3, EL.ACID, EL);
        fillRect(world, 93, 34, 3, 20, EL.EMPTY, true);
        drawForcedLine(world, 94, 56, 134, 80, EL.GLASS, 2);

        // Acid test bridges
        fillRect(world, 102, 102, 92, 8, EL.WOOD, true);
        fillRect(world, 94, 144, 112, 9, EL.STONE, true);
        fillRect(world, 118, 90, 44, 12, EL.SAND, true);

        // Center liquid nitrogen cryo tank dripping into heated pool
        strokeBeaker(world, 184, 30, 62, 40, 3, EL.GLASS);
        fillRect(world, 187, 46, 56, 21, EL.NITROGEN, true);
        setClonerWith(world, 213, 12, 3, 3, EL.NITROGEN, EL);
        fillRect(world, 213, 67, 4, 3, EL.EMPTY, true); // tiny nozzle

        // Pool below nitrogen tank
        strokeBeaker(world, 174, 172, 96, 48, 3, EL.GLASS);
        fillRect(world, 177, 190, 90, 27, EL.WATER, true);

        // Right wooden terrarium infested with mites!
        strokeBeaker(world, 286, 62, 92, 148, 3, EL.GLASS);
        fillRect(world, 289, 126, 86, 8, EL.WOOD, true);
        fillRect(world, 289, 170, 86, 10, EL.WOOD, true);
        fillRect(world, 312, 88, 8, 82, EL.WOOD, true);
        fillRect(world, 346, 92, 8, 78, EL.WOOD, true);
        world.paintCircle(332, 102, 18, EL.PLANT, false);
        for (let m = 0; m < 18; m++) {
          world.setCell(298 + m * 4, 118, EL.MITE, true);
        }

        // Bottom glass floor & void drain
        fillRect(world, 0, h - 10, w, 10, EL.GLASS, true);
        fillRect(world, 26, h - 10, 34, 4, EL.VOID, true);
      },
    },
  ];

  return { PRESETS };
});
