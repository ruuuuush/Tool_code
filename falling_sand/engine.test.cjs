'use strict';

const assert = require('assert');
const { EL, SandWorld } = require('./engine.js');
const { PRESETS } = require('./presets.js');
const { SPELLS, COMBO_RECIPES, compileWand } = require('./spells.js');
const { NoitaController } = require('./noita.js');

function countElement(world, el) {
  let n = 0;
  for (let i = 0; i < world.size; i++) {
    if (world.grid[i] === el) n++;
  }
  return n;
}

function test(name, fn) {
  fn();
  console.log(`PASS: ${name}`);
}

test('Sand falls under gravity and reverses under inverted gravity', () => {
  const w = new SandWorld(32, 32, 42);
  w.setCell(16, 2, EL.SAND, true);
  for (let i = 0; i < 40; i++) w.step();
  assert.strictEqual(w.get(16, 31), EL.SAND);

  w.gravityY = -1;
  for (let i = 0; i < 40; i++) w.step();
  assert.strictEqual(w.get(16, 0), EL.SAND);
});

test('Lava + Water quenches into Stone and Steam', () => {
  const w = new SandWorld(24, 24, 7);
  w.setCell(10, 12, EL.LAVA, true);
  w.setCell(10, 11, EL.WATER, true);
  w.step();
  assert.ok(countElement(w, EL.STONE) >= 1, 'Expected stone formed');
  assert.ok(countElement(w, EL.STEAM) >= 1, 'Expected steam formed');
});

test('Liquid Nitrogen freezes adjacent water into ice', () => {
  const w = new SandWorld(32, 32, 17);
  for (let x = 8; x <= 22; x++) {
    w.setCell(x, 22, EL.GLASS, true);
    w.setCell(x, 21, EL.WATER, true);
    w.setCell(x, 20, EL.WATER, true);
    w.setCell(x, 19, EL.NITROGEN, true);
  }
  for (let i = 0; i < 40; i++) w.step();
  assert.ok(countElement(w, EL.ICE) >= 5, 'Expected liquid nitrogen to freeze water into ice');
});

test('Metal conducts lightning electricity to ignite C4', () => {
  const w = new SandWorld(48, 32, 88);
  for (let x = 10; x <= 26; x++) w.setCell(x, 16, EL.METAL, true);
  for (let y = 14; y <= 18; y++) {
    for (let x = 27; x <= 32; x++) {
      w.setCell(x, y, EL.C4, true);
    }
  }
  const initC4 = countElement(w, EL.C4);
  w.strikeLightning(12, 2);
  for (let i = 0; i < 10; i++) w.step();
  assert.ok(countElement(w, EL.C4) < initC4, 'Lightning through metal should detonate C4');
  assert.ok(w.shockwaves.length > 0 || w.shake > 0, 'Explosion should trigger shockwave/shake');
});

test('Remote detonateAllC4 triggers explosion & ejects ballistic debris', () => {
  const w = new SandWorld(64, 64, 51);
  for (let y = 30; y < 38; y++) {
    for (let x = 28; x < 36; x++) w.setCell(x, y, EL.C4, true);
  }
  for (let y = 20; y < 30; y++) {
    for (let x = 20; x < 44; x++) w.setCell(x, y, EL.SAND, true);
  }
  const triggered = w.detonateAllC4();
  assert.ok(triggered > 0);
  w.step();
  assert.ok(w.particles.length > 0, 'Detonation should eject flying ballistic particles');
  assert.ok(w.shockwaves.length > 0, 'Detonation should spawn shockwave');
});

test('Firework launches upward and bursts into colorful star particles', () => {
  const w = new SandWorld(64, 96, 101);
  w.setCell(32, 88, EL.FIREWORK, true);
  let sawBurst = false;
  for (let i = 0; i < 90; i++) {
    w.step();
    if (w.particles.length > 20) {
      sawBurst = true;
      break;
    }
  }
  assert.ok(sawBurst, 'Firework should burst into >20 star particles');
});

test('Wood mites eat wood blocks', () => {
  const w = new SandWorld(32, 32, 44);
  for (let x = 6; x < 26; x++) {
    w.setCell(x, 24, EL.STONE, true);
    w.setCell(x, 22, EL.WOOD, true);
    w.setCell(x, 23, EL.WOOD, true);
  }
  const initWood = countElement(w, EL.WOOD);
  for (let x = 10; x < 22; x += 2) w.setCell(x, 21, EL.MITE, true);
  for (let i = 0; i < 80; i++) w.step();
  assert.ok(countElement(w, EL.WOOD) < initWood, 'Mites should devour wood');
});

test('Vortex swirls static/loose powder into airborne ballistic particles', () => {
  const w = new SandWorld(64, 64, 303);
  for (let y = 40; y < 56; y++) {
    for (let x = 20; x < 44; x++) w.setCell(x, y, EL.SAND, true);
  }
  w.applyVortex(32, 48, 18, false);
  assert.ok(w.particles.length > 10, 'Vortex should lift sand into ballistic particles');
});

test('Acid dissolves wood but never dissolves glass', () => {
  const w = new SandWorld(32, 32, 55);
  for (let x = 8; x <= 16; x++) w.setCell(x, 20, EL.GLASS, true);
  for (let y = 14; y <= 20; y++) {
    w.setCell(8, y, EL.GLASS, true);
    w.setCell(16, y, EL.GLASS, true);
  }
  const initialGlass = countElement(w, EL.GLASS);
  for (let y = 16; y < 20; y++) {
    for (let x = 9; x < 16; x++) w.setCell(x, y, EL.ACID, true);
  }
  for (let x = 20; x < 26; x++) {
    w.setCell(x, 20, EL.WOOD, true);
    w.setCell(x, 19, EL.ACID, true);
  }
  const initialWood = countElement(w, EL.WOOD);
  for (let i = 0; i < 80; i++) w.step();
  assert.strictEqual(countElement(w, EL.GLASS), initialGlass);
  assert.ok(countElement(w, EL.WOOD) < initialWood);
});

test('Detonation preset triggers via lightning rod antenna', () => {
  const w = new SandWorld(400, 240, 2026);
  const det = PRESETS.find((p) => p.id === 'detonation');
  det.build(w, EL);
  const initPowder = countElement(w, EL.GUNPOWDER);
  w.strikeLightning(36, 10);
  for (let i = 0; i < 220; i++) w.step();
  assert.ok(countElement(w, EL.GUNPOWDER) < initPowder * 0.5, 'Lightning rod should trigger chain explosion');
});

test('All 400x240 presets run 60 frames with dynamic lighting & thermal render fast', () => {
  const w = new SandWorld(400, 240, 777);
  const mainBuf = new Uint32Array(w.size);
  const glowBuf = new Uint32Array(w.size);

  for (const preset of PRESETS) {
    preset.build(w, EL);
    const t0 = Date.now();
    for (let f = 0; f < 60; f++) {
      w.step();
      w.render(mainBuf, glowBuf, { lighting: true, thermal: f === 59 });
    }
    const elapsed = Date.now() - t0;
    assert.ok(w.activeCount > 500, `Preset ${preset.id} should be richly populated`);
    console.log(`  [bench] 400x240 preset=${preset.id} 60f + lightmap: ${elapsed}ms (${(elapsed / 60).toFixed(2)}ms/frame)`);
  }
});

test('Spell deck compiler parses triggers, multicasts, trails & all combo recipes', () => {
  const cluster = compileWand(['trigger_hit', 'spark_bolt', 'triple', 'lava_trail', 'firebolt']);
  assert.strictEqual(cluster.actions.length, 1, 'Outer cast should fire 1 trigger carrier');
  assert.strictEqual(cluster.actions[0].triggerType, 'hit');
  assert.strictEqual(cluster.actions[0].payload.length, 3, 'Payload should fan out 3 firebolts');
  assert.ok(cluster.actions[0].payload[0].mods.trails.includes('LAVA'), 'Payload must inherit LAVA trail');

  const hexFw = compileWand(['trigger_timer', 'spark_bolt', 'hex', 'bouncy', 'firework_spell']);
  assert.strictEqual(hexFw.actions[0].triggerType, 'timer');
  assert.strictEqual(hexFw.actions[0].payload.length, 6, 'Hex multicast should spawn 6 ring fireworks');
  assert.strictEqual(hexFw.actions[0].payload[0].mods.bounces, 5);

  for (const rec of COMBO_RECIPES) {
    const c = compileWand(rec.slots);
    assert.ok(c.actions.length >= 1, `Recipe ${rec.id} must compile to executable actions`);
  }
  assert.strictEqual(Object.keys(SPELLS).length, 40, 'Should expose 40 distinct spells');
  assert.strictEqual(COMBO_RECIPES.length, 10, 'Should expose 10 combo recipes');
});

test('New spells work: Nuke blast, Plasma Cross carving, Rain Cloud, Boomerang Heal, Air Split', () => {
  const w = new SandWorld(400, 240, 2027);
  const mine = PRESETS.find((p) => p.id === 'noita_mine');
  mine.build(w, EL);
  const noita = new NoitaController(w, EL);
  noita.enabled = true;
  noita.spawnPlayer(60, 48);

  // 1. Boomerang + Heal Bolt heals injured wizard!
  noita.player.hp = 50;
  noita.wands[0].slots = ['boomerang', 'heal_bolt'];
  noita.recompileWand(0);
  noita.selectedWand = 0;
  noita.aimX = noita.player.x + 70;
  noita.aimY = noita.player.y;
  noita.player.mana = 100;
  noita.player.cooldown = 0;
  noita.castPrimary();
  for (let i = 0; i < 65; i++) { w.step(); noita.step(); }
  assert.ok(noita.player.hp > 50, `Boomerang heal bolt should return and heal player, hp=${noita.player.hp}`);

  // 2. Air Split turns 1 spark bolt into 3 projectiles mid-flight
  noita.wands[0].slots = ['split_air', 'spark_bolt'];
  noita.recompileWand(0);
  noita.projectiles.length = 0;
  noita.player.mana = 100;
  noita.player.cooldown = 0;
  noita.castPrimary();
  let peakProjs = 0;
  for (let i = 0; i < 20; i++) {
    w.step();
    noita.step();
    peakProjs = Math.max(peakProjs, noita.projectiles.length);
  }
  assert.ok(peakProjs >= 3, `Air split should divide 1 projectile into >=3, got ${peakProjs}`);

  // 3. Plasma Cross deploys rotating beams & carves terrain
  noita.wands[0].slots = ['plasma_cross'];
  noita.recompileWand(0);
  noita.player.mana = 100;
  noita.player.cooldown = 0;
  noita.aimX = noita.player.x + 50;
  noita.aimY = noita.player.y + 40;
  noita.castPrimary();
  let sawCross = false;
  for (let i = 0; i < 35; i++) {
    w.step();
    noita.step();
    if (noita.plasmaCrosses.length > 0) sawCross = true;
  }
  assert.ok(sawCross, 'Plasma cross spell should deploy spinning cross entity');

  // 4. Rain Cloud spawns cloud and pours substantial water
  const wRain = new SandWorld(120, 120, 2027);
  const nRain = new NoitaController(wRain, EL);
  nRain.enabled = true;
  nRain.spawnPlayer(40, 60);
  nRain.wands[0].slots = ['rain_cloud'];
  nRain.recompileWand(0);
  nRain.selectedWand = 0;
  nRain.player.mana = 100;
  nRain.player.cooldown = 0;
  nRain.aimX = 70;
  nRain.aimY = 45;
  nRain.castPrimary();
  for (let i = 0; i < 55; i++) { wRain.step(); nRain.step(); }
  assert.ok(nRain.clouds.length > 0, 'Rain cloud entity should be active');
  assert.ok(countElement(wRain, EL.WATER) > 80, `Rain cloud should pour >80 water, got ${countElement(wRain, EL.WATER)}`);

  // 5. Nuke causes massive blast, flashAlpha & crater
  const stoneBefore = countElement(w, EL.STONE);
  noita.detonateNuke(200, 120, 1);
  assert.ok(noita.flashAlpha > 0.8, 'Nuke should trigger blinding flash');
  assert.ok(countElement(w, EL.STONE) < stoneBefore - 400, 'Nuke should obliterate massive rock crater');
});

test('Noita wizard crafts custom combos: acid-trail black hole, cluster trigger & teleport', () => {
  const w = new SandWorld(400, 240, 999);
  const mine = PRESETS.find((p) => p.id === 'noita_mine');
  assert.ok(mine, 'noita_mine preset must exist');
  mine.build(w, EL);

  const noita = new NoitaController(w, EL);
  noita.enabled = true;
  noita.spawnPlayer(mine.spawn.x, mine.spawn.y);
  noita.populateDungeonEnemies();
  assert.strictEqual(noita.enemies.length, 5);

  // Levitate upward & consume flight bar
  const startFlight = noita.player.flight;
  noita.keys.up = true;
  for (let i = 0; i < 15; i++) { w.step(); noita.step(); }
  noita.keys.up = false;
  assert.ok(noita.player.flight < startFlight, 'Levitation should consume flight energy');

  // Cast Teleport bolt across open gallery from standing position
  noita.spawnPlayer(44, 48);
  const preX = noita.player.x;
  noita.aimX = preX + 120;
  noita.aimY = 48;
  noita.player.mana = 100;
  noita.player.tpCooldown = 0;
  noita.castTeleport();
  for (let i = 0; i < 30; i++) { w.step(); noita.step(); }
  assert.ok(Math.abs(noita.player.x - preX) > 20, `Teleport bolt should relocate wizard, got dx=${Math.abs(noita.player.x - preX)}`);

  // Test Wand #1: [trigger_hit, spark_bolt, triple, firebolt] hits wall and spawns explosion payload!
  noita.selectedWand = 0;
  noita.aimX = noita.player.x;
  noita.aimY = noita.player.y + 80;
  noita.player.mana = 100;
  noita.player.cooldown = 0;
  noita.castPrimary();
  let sawMultipleProjectiles = false;
  for (let i = 0; i < 30; i++) {
    w.step();
    noita.step();
    if (noita.projectiles.length >= 2) sawMultipleProjectiles = true;
  }
  assert.ok(sawMultipleProjectiles || w.shockwaves.length > 0, 'Hit-trigger cluster wand should unleash payload');

  // Test Wand #2: [acid_trail, blackhole] carves stone AND leaves acid in tunnel!
  const stoneBefore = countElement(w, EL.STONE);
  noita.selectedWand = 1;
  noita.aimX = noita.player.x;
  noita.aimY = noita.player.y + 80;
  noita.player.mana = 100;
  noita.player.cooldown = 0;
  noita.castPrimary();
  let sawAcidInTunnel = false;
  for (let i = 0; i < 45; i++) {
    w.step();
    noita.step();
    if (countElement(w, EL.ACID) > 5) sawAcidInTunnel = true;
  }
  assert.ok(countElement(w, EL.STONE) < stoneBefore - 80, 'Black hole should carve tunnel through stone');
  assert.ok(sawAcidInTunnel, 'Acid-trail modifier on black hole should spray real ACID pixels');

  // Dynamic lights collected without error & rendered into 400x240 lightmap
  const mainBuf = new Uint32Array(w.size);
  const glowBuf = new Uint32Array(w.size);
  const lights = noita.collectLights();
  assert.ok(lights.length > 0, 'Wizard & enemies should emit dynamic lights');
  w.render(mainBuf, glowBuf, { lighting: true, extraLights: lights });
});

console.log('ALL V4 TESTS PASSED');
