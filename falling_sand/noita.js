(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory(require('./spells.js'));
  } else {
    root.NoitaMode = factory(root.WandSpells);
  }
})(typeof self !== 'undefined' ? self : this, function (WandSpells) {
  'use strict';

  class NoitaController {
    constructor(world, EL) {
      this.world = world;
      this.EL = EL;
      this.enabled = false;
      this.selectedWand = 0;
      this.wands = WandSpells.createDefaultWands();
      this.compiledWands = this.wands.map((w) => WandSpells.compileWand(w.slots));

      this.aimX = world.width * 0.5 + 30;
      this.aimY = world.height * 0.3;

      this.keys = { left: false, right: false, up: false, down: false };
      this.firing = false;
      this.projectiles = [];
      this.blackHoles = [];
      this.plasmaCrosses = [];
      this.clouds = [];
      this.lightningArcs = [];
      this.afterimages = [];
      this.enemies = [];
      this.kills = 0;
      this.flashAlpha = 0;

      this.player = this.createPlayer(54, 48);
    }

    recompileWand(index) {
      const i = index !== undefined ? index : this.selectedWand;
      const wand = this.wands[i];
      if (!wand) return null;
      this.compiledWands[i] = WandSpells.compileWand(wand.slots);
      const firstProj = wand.slots.map((id) => WandSpells.SPELLS[id]).find((s) => s && s.kind === 'projectile');
      if (firstProj) wand.color = firstProj.color;
      return this.compiledWands[i];
    }

    getActiveWand() {
      return this.wands[this.selectedWand];
    }

    getActiveCompiled() {
      return this.compiledWands[this.selectedWand];
    }

    createPlayer(x, y) {
      const cape = [];
      for (let i = 0; i < 6; i++) cape.push({ x: x - i * 1.6, y: y + i * 1.2 });
      return {
        x, y, vx: 0, vy: 0, w: 6, h: 11,
        facing: 1, grounded: false,
        hp: 100, maxHp: 100,
        mana: 100, maxMana: 100,
        flight: 100, maxFlight: 100,
        cooldown: 0, tpCooldown: 0, invuln: 30,
        dead: false, deathCause: '',
        wet: 0, oiled: 0, burning: 0, acid: 0, frozen: 0,
        walkPhase: 0, cape,
      };
    }

    isSolidForBody(el) {
      const EL = this.EL;
      return (
        el === EL.STONE || el === EL.WOOD || el === EL.METAL || el === EL.GLASS ||
        el === EL.ICE || el === EL.C4 || el === EL.CLONER || el === EL.SAND ||
        el === EL.SNOW || el === EL.SALT || el === EL.GUNPOWDER || el === EL.FUSE
      );
    }

    isHardTerrain(el) {
      const EL = this.EL;
      return (
        el === EL.STONE || el === EL.WOOD || el === EL.METAL || el === EL.GLASS ||
        el === EL.ICE || el === EL.C4 || el === EL.CLONER || el === EL.VOID
      );
    }

    findSafeSpawn(preferredX, preferredY) {
      const w = this.world.width;
      const h = this.world.height;
      const sx = Math.max(12, Math.min(w - 12, (preferredX || 52) | 0));
      const sy = Math.max(16, Math.min(h - 24, (preferredY || 44) | 0));

      for (let rad = 0; rad < 90; rad += 4) {
        for (let dy = -rad; dy <= rad; dy += 4) {
          for (let dx = -rad; dx <= rad; dx += 4) {
            const tx = sx + dx;
            const ty = sy + dy;
            if (tx < 12 || tx > w - 12 || ty < 16 || ty > h - 20) continue;
            if (!this.collidesBox(tx, ty, 6, 11)) return { x: tx, y: ty };
          }
        }
      }
      this.world.paintCircle(sx, sy, 8, this.EL.EMPTY, false);
      return { x: sx, y: sy };
    }

    spawnPlayer(x, y) {
      const pos = this.findSafeSpawn(x, y);
      this.player = this.createPlayer(pos.x, pos.y);
      this.world.shockwaves.push({ x: pos.x, y: pos.y, r: 2, maxR: 18, alpha: 0.9, color: '#b87cff' });
    }

    clearEntities() {
      this.projectiles.length = 0;
      this.blackHoles.length = 0;
      this.plasmaCrosses.length = 0;
      this.clouds.length = 0;
      this.lightningArcs.length = 0;
      this.afterimages.length = 0;
      this.enemies.length = 0;
      this.flashAlpha = 0;
    }

    spawnEnemy(type, x, y) {
      const pos = this.findSafeSpawn(x, y);
      if (type === 'spirit') {
        this.enemies.push({
          type: 'spirit', x: pos.x, y: pos.y, vx: 0, vy: 0,
          hp: 45, maxHp: 45, radius: 4.5,
          timer: (Math.random() * 60) | 0,
          shootCd: 70 + ((Math.random() * 60) | 0), hurtFlash: 0,
        });
      } else {
        this.enemies.push({
          type: 'slime', x: pos.x, y: pos.y,
          vx: (Math.random() < 0.5 ? -1 : 1) * 0.5, vy: 0,
          hp: 36, maxHp: 36, radius: 4.5,
          hopCd: 25 + ((Math.random() * 35) | 0), hurtFlash: 0,
        });
      }
    }

    populateDungeonEnemies() {
      this.enemies.length = 0;
      const w = this.world.width, h = this.world.height;
      this.spawnEnemy('slime', Math.round(w * 0.38), Math.round(h * 0.44));
      this.spawnEnemy('slime', Math.round(w * 0.62), Math.round(h * 0.42));
      this.spawnEnemy('slime', Math.round(w * 0.82), Math.round(h * 0.48));
      this.spawnEnemy('spirit', Math.round(w * 0.48), Math.round(h * 0.72));
      this.spawnEnemy('spirit', Math.round(w * 0.78), Math.round(h * 0.72));
    }

    collidesBox(cx, cy, bw, bh) {
      const halfW = bw * 0.5, halfH = bh * 0.5;
      const x0 = Math.floor(cx - halfW), x1 = Math.floor(cx + halfW);
      const y0 = Math.floor(cy - halfH), y1 = Math.floor(cy + halfH);
      let solidHits = 0;
      for (let y = y0; y <= y1; y++) {
        for (let x = x0; x <= x1; x++) {
          if (!this.world.inBounds(x, y)) return true;
          const el = this.world.grid[y * this.world.width + x];
          if (this.isSolidForBody(el)) {
            solidHits++;
            if (this.isHardTerrain(el) || solidHits >= 2) return true;
          }
        }
      }
      return false;
    }

    healPlayer(amount) {
      const p = this.player;
      if (p.dead) return;
      p.hp = Math.min(p.maxHp, p.hp + amount);
      p.burning = 0;
      p.acid = 0;
      p.frozen = 0;
      this.world.shockwaves.push({ x: p.x, y: p.y, r: 2, maxR: 16, alpha: 0.9, color: '#4dff9b' });
      this.world.emitEvent('heal', 0.9, p.x, p.y);
      for (let k = 0; k < 10; k++) {
        this.world.spawnParticle(
          p.x + (Math.random() - 0.5) * 6, p.y + (Math.random() - 0.5) * 8,
          (Math.random() - 0.5) * 0.8, -0.8 - Math.random() * 0.8,
          this.EL.SPARK, [90, 255, 165], 18
        );
      }
    }

    damagePlayer(amount, cause) {
      const p = this.player;
      if (p.dead || p.invuln > 0) return;
      p.hp = Math.max(0, p.hp - amount);
      p.invuln = amount >= 8 ? 22 : 8;
      this.world.shake = Math.min(14, this.world.shake + Math.min(6, amount * 0.25));
      this.world.emitEvent('player_hurt', 0.8, p.x, p.y);
      if (p.hp <= 0) {
        p.dead = true;
        p.deathCause = cause || '神秘的炼金事故';
        for (let k = 0; k < 38; k++) {
          const ang = (k / 38) * Math.PI * 2;
          const spd = 1.2 + Math.random() * 3.2;
          this.world.spawnParticle(
            p.x, p.y, Math.cos(ang) * spd, Math.sin(ang) * spd - 1.0,
            this.EL.SPARK, k % 2 === 0 ? [196, 108, 255] : [255, 214, 92], 45
          );
        }
        this.world.shockwaves.push({ x: p.x, y: p.y, r: 2, maxR: 32, alpha: 1, color: '#d96bff' });
      }
    }

    castPrimary() {
      const p = this.player;
      if (p.dead || p.cooldown > 0) return;
      const compiled = this.compiledWands[this.selectedWand];
      if (!compiled || compiled.actions.length === 0) return;
      if (p.mana < compiled.totalMana) return;

      const dx = this.aimX - p.x;
      const dy = this.aimY - (p.y - 1);
      const baseAngle = Math.atan2(dy, dx);
      const nx = Math.cos(baseAngle);
      const ny = Math.sin(baseAngle);
      const muzzleX = p.x + nx * 6.5;
      const muzzleY = p.y - 1 + ny * 6.5;

      p.mana = Math.max(0, p.mana - compiled.totalMana);
      p.cooldown = compiled.totalDelay;
      p.facing = nx >= 0 ? 1 : -1;

      this.executeActions(compiled.actions, muzzleX, muzzleY, baseAngle, false);

      const recoil = Math.min(2.2, 0.35 + compiled.actions.length * 0.22);
      p.vx -= nx * recoil;
      p.vy -= ny * recoil * 0.7;
    }

    executeActions(actions, originX, originY, baseAngle, isPayload) {
      if (!actions || actions.length === 0) return;
      if (this.projectiles.length > 240) return;

      for (let i = 0; i < actions.length; i++) {
        const act = actions[i];
        const spell = act.spell;
        const mods = act.mods || {};
        const ang = baseAngle + (act.angleOffset || 0);
        const nx = Math.cos(ang);
        const ny = Math.sin(ang);

        if (spell.id === 'chain_bolt') {
          this.castDirectedLightning(originX, originY, nx, ny, mods);
          this.world.shake = Math.min(12, this.world.shake + 3.2);
          this.world.emitEvent('lightning', 0.9, originX, originY);
          continue;
        }

        if (spell.id === 'blackhole') {
          const spd = spell.speed * (mods.speedMult || 1);
          this.blackHoles.push({
            x: originX, y: originY,
            vx: nx * spd, vy: ny * spd,
            radius: 10, life: spell.life, spin: 0, age: 0,
            mods,
            triggerType: act.triggerType || null,
            payload: act.payload || null,
            timerLeft: act.triggerType === 'timer' ? 32 : 0,
            payloadFired: false,
          });
          this.world.emitEvent('spell_blackhole', 0.9, originX, originY);
          continue;
        }

        // Meteor plunges down from high altitude toward target!
        if (spell.id === 'meteor') {
          const targetX = isPayload ? originX + (Math.random() - 0.5) * 40 : this.aimX + (act.angleOffset || 0) * 65;
          const targetY = isPayload ? originY : this.aimY;
          const startX = Math.max(12, Math.min(this.world.width - 12, targetX - 38 + (Math.random() - 0.5) * 26));
          const startY = 12;
          const mdx = targetX - startX;
          const mdy = Math.max(20, targetY - startY);
          const md = Math.hypot(mdx, mdy);
          const spd = spell.speed * (mods.speedMult || 1);
          this.projectiles.push({
            kind: 'meteor', color: spell.color,
            damage: Math.round((spell.damage || 52) * (mods.powerMult || 1)),
            x: startX, y: startY,
            vx: (mdx / md) * spd, vy: (mdy / md) * spd,
            age: 0, life: spell.life, owner: 'player', mods,
            bouncesLeft: mods.bounces || 0, pierceLeft: (mods.pierce || 0) + 2,
            splitLeft: mods.splitAir ? 1 : 0,
            triggerType: act.triggerType || null, payload: act.payload || null,
            timerLeft: act.triggerType === 'timer' ? 22 : 0, payloadFired: false,
          });
          this.world.emitEvent('spell_fire', 1.0, startX, startY);
          continue;
        }

        const spd = (spell.speed || 5.2) * (mods.speedMult || 1);
        const spreadJitter = spell.id === 'flamethrower' ? (Math.random() - 0.5) * 0.24 : 0;
        const jx = Math.cos(ang + spreadJitter);
        const jy = Math.sin(ang + spreadJitter);

        this.projectiles.push({
          kind: spell.id,
          color: spell.color,
          damage: Math.round((spell.damage || 14) * (mods.powerMult || 1)),
          x: originX,
          y: originY,
          vx: jx * spd,
          vy: jy * spd,
          age: 0,
          life: spell.life || 75,
          owner: 'player',
          mods,
          bouncesLeft: mods.bounces || 0,
          pierceLeft: mods.pierce || 0,
          splitLeft: mods.splitAir ? 1 : 0,
          triggerType: act.triggerType || null,
          payload: act.payload || null,
          timerLeft: act.triggerType === 'timer' ? 22 : 0,
          payloadFired: false,
        });

        if (!isPayload || i === 0) {
          if (spell.id === 'firebolt' || spell.id === 'flamethrower') this.world.emitEvent('spell_fire', 0.7, originX, originY);
          else if (spell.id === 'acid_ball' || spell.id === 'acid_cloud') this.world.emitEvent('spell_acid', 0.7, originX, originY);
          else if (spell.id === 'firework_spell') this.world.emitEvent('firework_launch', 0.7, originX, originY);
          else if (spell.id === 'teleport_spell') this.world.emitEvent('teleport', 0.8, originX, originY);
          else if (spell.id === 'heal_bolt') this.world.emitEvent('heal', 0.6, originX, originY);
          else this.world.emitEvent('spell_plasma', 0.55, originX, originY);
        }
      }
    }

    castTeleport() {
      const p = this.player;
      if (p.dead || p.tpCooldown > 0 || p.mana < 14) return;
      const dx = this.aimX - p.x;
      const dy = this.aimY - (p.y - 1);
      const dist = Math.max(1, Math.hypot(dx, dy));
      const nx = dx / dist, ny = dy / dist;
      p.mana -= 14;
      p.tpCooldown = 20;
      p.facing = nx >= 0 ? 1 : -1;

      this.projectiles.push({
        kind: 'teleport_spell', color: '#7bf5ff', damage: 0,
        x: p.x + nx * 6, y: p.y - 1 + ny * 6,
        vx: nx * 7.4, vy: ny * 7.4,
        age: 0, life: 24, owner: 'player', mods: {},
        bouncesLeft: 0, pierceLeft: 0, splitLeft: 0,
        triggerType: null, payload: null, timerLeft: 0, payloadFired: false,
      });
      this.world.emitEvent('teleport', 0.8, p.x, p.y);
    }

    detonateNuke(cx, cy, powerMult) {
      const world = this.world;
      const EL = this.EL;
      const radius = Math.min(54, Math.round(40 * (powerMult || 1)));

      this.flashAlpha = 0.95;
      world.shake = 18;
      world.emitEvent('nuke', 1.0, cx, cy);
      world.detonate(cx, cy, radius);

      // Extra shockwave rings for dramatic nuclear mushroom punch
      world.shockwaves.push({ x: cx, y: cy, r: 4, maxR: radius * 2.5, alpha: 1.0, color: '#fff6b0' });
      world.shockwaves.push({ x: cx, y: cy, r: 2, maxR: radius * 1.8, alpha: 0.95, color: '#ff6622' });

      // Melt crater floor into glowing lava + blast burning debris everywhere!
      for (let k = 0; k < 42; k++) {
        const ang = (k / 42) * Math.PI * 2;
        const spd = 2.6 + Math.random() * 4.4;
        world.spawnParticle(
          cx + Math.cos(ang) * 8, cy + Math.sin(ang) * 8,
          Math.cos(ang) * spd, Math.sin(ang) * spd - 1.5,
          k % 3 === 0 ? EL.LAVA : EL.EMBER, [255, 196, 72], 55
        );
      }
      world.paintCircle(cx, Math.min(world.height - 6, cy + (radius >> 1)), 10, EL.LAVA, true);

      // Heavy blast damage to enemies & wizard
      this.damageEnemiesInRadius(cx, cy, radius * 1.5, 120, 0, -3.5);
    }

    emitTrailElements(x, y, trails) {
      if (!trails || trails.length === 0) return;
      const world = this.world;
      const EL = this.EL;
      const gx = x | 0, gy = y | 0;
      for (let t = 0; t < trails.length; t++) {
        const elId = EL[trails[t]];
        if (!elId) continue;
        if (world.inBounds(gx, gy) && world.grid[gy * world.width + gx] === EL.EMPTY) {
          world.setCell(gx, gy, elId, true);
        }
        const ox = gx + (Math.random() < 0.5 ? -1 : 1);
        if (world.inBounds(ox, gy) && world.grid[gy * world.width + ox] === EL.EMPTY && Math.random() < 0.6) {
          world.setCell(ox, gy, elId, true);
        }
      }
    }

    pulseElectricArc(x, y) {
      const world = this.world;
      const EL = this.EL;
      const ang = Math.random() * Math.PI * 2;
      const len = 14 + Math.random() * 10;
      const ex = x + Math.cos(ang) * len;
      const ey = y + Math.sin(ang) * len;
      const midX = (x + ex) * 0.5 + (Math.random() - 0.5) * 6;
      const midY = (y + ey) * 0.5 + (Math.random() - 0.5) * 6;

      this.lightningArcs.push({
        points: [{ x, y }, { x: midX, y: midY }, { x: ex, y: ey }],
        branches: [],
        life: 5,
        maxLife: 5,
      });

      this.damageEnemiesInRadius(ex, ey, 10, 12, 0, -0.8);
      const gx = ex | 0, gy = ey | 0;
      if (world.inBounds(gx, gy)) {
        const el = world.grid[gy * world.width + gx];
        if (el === EL.METAL || el === EL.WATER) world.electrifyConductor(gx, gy);
        else if (el === EL.GUNPOWDER || el === EL.C4) world.queueExplosion(gx, gy, el === EL.C4 ? 22 : 15);
        else if (el === EL.OIL || el === EL.FUSE) world.setCell(gx, gy, EL.FIRE, true);
      }
    }

    castDirectedLightning(sx, sy, nx, ny, mods) {
      const EL = this.EL;
      const world = this.world;
      const mainPoints = [{ x: sx, y: sy }];
      const branches = [];

      let x = sx, y = sy;
      const px = -ny, py = nx;

      for (let step = 0; step < 34; step++) {
        const jitter = (Math.random() - 0.5) * 4.4;
        x += nx * 5.2 + px * jitter;
        y += ny * 5.2 + py * jitter;
        mainPoints.push({ x, y });

        if (mods && mods.trails && mods.trails.length > 0 && (step & 1) === 0) {
          this.emitTrailElements(x, y, mods.trails);
        }

        this.damageEnemiesInRadius(x, y, 12, Math.round(34 * ((mods && mods.powerMult) || 1)), nx * 2.5, ny * 2.5);

        const gx = x | 0, gy = y | 0;
        if (!world.inBounds(gx, gy)) break;

        const cell = world.grid[gy * world.width + gx];
        if (cell !== EL.EMPTY && cell !== EL.SMOKE && cell !== EL.STEAM && cell !== EL.FIRE && cell !== EL.SPARK) {
          if (cell === EL.GUNPOWDER || cell === EL.C4) world.queueExplosion(gx, gy, cell === EL.C4 ? 24 : 18);
          else if (cell === EL.METAL || cell === EL.WATER) world.electrifyConductor(gx, gy);
          else if (cell === EL.SAND) world.paintCircle(gx, gy, 3, EL.GLASS, false);
          else if (cell === EL.WOOD || cell === EL.OIL || cell === EL.PLANT || cell === EL.FUSE) world.paintCircle(gx, gy, 3, EL.FIRE, false);
          else world.queueExplosion(gx, gy, 10);
          break;
        } else if (Math.random() < 0.45) {
          world.setCell(gx, gy, EL.SPARK, true);
        }

        if (step > 3 && step < 26 && Math.random() < 0.24) {
          const bPts = [{ x, y }];
          let bx = x, by = y;
          const bSign = Math.random() < 0.5 ? 1 : -1;
          for (let k = 0; k < 6; k++) {
            bx += nx * 3.5 + px * bSign * (2.5 + Math.random() * 2.5);
            by += ny * 3.5 + py * bSign * (2.5 + Math.random() * 2.5);
            bPts.push({ x: bx, y: by });
          }
          branches.push(bPts);
        }
      }

      this.lightningArcs.push({ points: mainPoints, branches, life: 9, maxLife: 9 });
    }

    damageEnemiesInRadius(cx, cy, radius, damage, pushX, pushY) {
      const r2 = radius * radius;
      for (let i = this.enemies.length - 1; i >= 0; i--) {
        const e = this.enemies[i];
        const dx = e.x - cx, dy = e.y - cy;
        if (dx * dx + dy * dy <= r2) {
          e.hp -= damage;
          e.hurtFlash = 8;
          e.vx += pushX || 0;
          e.vy += pushY || -1.2;
          if (e.hp <= 0) this.killEnemy(i);
        }
      }
    }

    killEnemy(index) {
      const e = this.enemies[index];
      this.enemies.splice(index, 1);
      this.kills++;
      this.world.emitEvent('enemy_die', 0.9, e.x, e.y);

      const EL = this.EL;
      for (let k = 0; k < 22; k++) {
        const ang = (k / 22) * Math.PI * 2;
        const spd = 1.0 + Math.random() * 2.6;
        const dropEl = k % 3 === 0 ? EL.SAND : (e.type === 'slime' ? EL.ACID : EL.EMBER);
        const rgb = dropEl === EL.SAND ? [255, 215, 76] : (e.type === 'slime' ? [110, 255, 75] : [255, 130, 42]);
        this.world.spawnParticle(e.x, e.y, Math.cos(ang) * spd, Math.sin(ang) * spd - 1.2, dropEl, rgb, 34);
      }
      this.world.shockwaves.push({
        x: e.x, y: e.y, r: 2, maxR: 16, alpha: 0.9,
        color: e.type === 'slime' ? '#6aff44' : '#ff8c2e',
      });
    }

    step() {
      if (!this.enabled) return;

      if (this.flashAlpha > 0) {
        this.flashAlpha *= 0.82;
        if (this.flashAlpha < 0.02) this.flashAlpha = 0;
      }

      this.updatePlayer();
      this.updateProjectiles();
      this.updateBlackHoles();
      this.updatePlasmaCrosses();
      this.updateClouds();
      this.updateEnemies();

      for (let i = this.lightningArcs.length - 1; i >= 0; i--) {
        this.lightningArcs[i].life--;
        if (this.lightningArcs[i].life <= 0) this.lightningArcs.splice(i, 1);
      }
      for (let i = this.afterimages.length - 1; i >= 0; i--) {
        this.afterimages[i].life--;
        if (this.afterimages[i].life <= 0) this.afterimages.splice(i, 1);
      }
    }

    updatePlayer() {
      const p = this.player;
      const world = this.world;
      const EL = this.EL;

      if (p.dead) return;
      if (p.cooldown > 0) p.cooldown--;
      if (p.tpCooldown > 0) p.tpCooldown--;
      if (p.invuln > 0) p.invuln--;

      p.mana = Math.min(p.maxMana, p.mana + 0.72);
      p.facing = this.aimX >= p.x ? 1 : -1;

      if (this.firing && p.cooldown === 0) this.castPrimary();

      let inWater = false, inOil = false, inLava = false, inAcid = false, inFire = false, inNitrogen = false;
      const x0 = Math.floor(p.x - 3), x1 = Math.floor(p.x + 3);
      const y0 = Math.floor(p.y - 5), y1 = Math.floor(p.y + 5);

      for (let y = y0; y <= y1; y++) {
        for (let x = x0; x <= x1; x++) {
          if (!world.inBounds(x, y)) continue;
          const el = world.grid[y * world.width + x];
          if (el === EL.WATER) inWater = true;
          else if (el === EL.OIL) inOil = true;
          else if (el === EL.LAVA) inLava = true;
          else if (el === EL.ACID || el === EL.TOXIC) inAcid = true;
          else if (el === EL.FIRE || el === EL.EMBER) inFire = true;
          else if (el === EL.NITROGEN) inNitrogen = true;
        }
      }

      if (inWater) {
        p.wet = 140; p.burning = 0; p.oiled = Math.max(0, p.oiled - 4);
      } else if (p.wet > 0) {
        p.wet--;
        if (Math.random() < 0.08) world.spawnParticle(p.x + (Math.random() - 0.5) * 4, p.y + 3, 0, 0.5, EL.WATER, null, 24);
      }

      if (inOil) p.oiled = 180; else if (p.oiled > 0) p.oiled--;
      if (inNitrogen) { p.frozen = 120; p.burning = 0; } else if (p.frozen > 0) p.frozen--;

      if (inLava) { p.burning = 180; this.damagePlayer(14, '葬身滚烫岩浆'); }
      else if (inFire && p.wet <= 0) { p.burning = Math.max(p.burning, p.oiled > 0 ? 220 : 120); }

      if (inAcid) { p.acid = 90; this.damagePlayer(7, '被强酸腐蚀殆尽'); }
      else if (p.acid > 0) { p.acid--; if ((p.acid & 15) === 0) this.damagePlayer(2, '死于残留强酸'); }

      if (p.burning > 0) {
        p.burning--;
        if (Math.random() < 0.45) world.setCell((p.x + (Math.random() - 0.5) * 5) | 0, (p.y - 5) | 0, EL.FIRE, true);
        if ((p.burning & 15) === 0) this.damagePlayer(p.oiled > 0 ? 5 : 2, '被熊熊烈火烧成灰烬');
      }

      for (let k = 0; k < world.recentExplosions.length; k++) {
        const ex = world.recentExplosions[k];
        const dx = p.x - ex.x, dy = p.y - ex.y;
        const dist = Math.hypot(dx, dy);
        const blastR = ex.radius * 1.45;
        if (dist < blastR) {
          const factor = 1 - dist / blastR;
          const nx = dist > 0.1 ? dx / dist : 0;
          const ny = dist > 0.1 ? dy / dist : -1;
          p.vx += nx * (3.5 + factor * 5.0);
          p.vy += ny * (3.5 + factor * 5.0) - 1.4;
          const cause = ex.radius >= 35 ? '在自己的核弹蘑菇云中化作星尘' : '被自己的法术爆炸送上了天';
          this.damagePlayer(Math.round(8 + factor * (ex.radius >= 35 ? 65 : 24)), cause);
        }
      }

      const speedMult = p.frozen > 0 ? 0.55 : inWater ? 0.72 : 1.0;
      const moveAcc = (p.grounded ? 0.42 : 0.24) * speedMult;
      if (this.keys.left) { p.vx -= moveAcc; p.walkPhase += 0.35; }
      if (this.keys.right) { p.vx += moveAcc; p.walkPhase += 0.35; }
      p.vx *= p.grounded ? 0.76 : 0.91;
      const maxVx = 2.4 * speedMult;
      if (p.vx > maxVx) p.vx = maxVx;
      if (p.vx < -maxVx) p.vx = -maxVx;

      const g = world.gravityY === 0 ? 0.01 : 0.18 * world.gravityY;
      p.vy += inWater ? g * 0.35 : g;

      if (this.keys.up && p.flight > 0) {
        p.vy = Math.max(-2.6, p.vy - (inWater ? 0.32 : 0.42));
        p.flight = Math.max(0, p.flight - 1.55);
        if (Math.random() < 0.85) {
          world.spawnParticle(
            p.x + (Math.random() - 0.5) * 4, p.y + 5.5,
            (Math.random() - 0.5) * 1.1 - p.vx * 0.2, 1.4 + Math.random() * 1.4,
            EL.SPARK, [255, 224, 110], 14
          );
        }
      } else if (this.keys.down) {
        p.vy = Math.min(4.2, p.vy + 0.16);
      }

      if (p.vy > 4.6) p.vy = 4.6;
      if (p.vy < -4.2) p.vy = -4.2;

      if (this.collidesBox(p.x, p.y, p.w, p.h)) {
        const gx = p.x | 0, gy = p.y | 0;
        for (let oy = -5; oy <= 4; oy++) {
          for (let ox = -3; ox <= 3; ox++) {
            const tx = gx + ox, ty = gy + oy;
            if (!world.inBounds(tx, ty)) continue;
            const el = world.grid[ty * world.width + tx];
            if (!this.isHardTerrain(el) && el !== EL.EMPTY) world.setCell(tx, ty, EL.EMPTY, true);
          }
        }
      }

      const nextX = p.x + p.vx;
      if (!this.collidesBox(nextX, p.y, p.w, p.h)) {
        p.x = nextX;
      } else {
        let stepped = false;
        for (let step = 1; step <= 4; step++) {
          if (!this.collidesBox(nextX, p.y - step, p.w, p.h)) {
            p.x = nextX; p.y -= step; stepped = true; break;
          }
        }
        if (!stepped) p.vx = 0;
      }

      p.grounded = false;
      const nextY = p.y + p.vy;
      if (!this.collidesBox(p.x, nextY, p.w, p.h)) {
        p.y = nextY;
      } else {
        if (p.vy > 0) p.grounded = true;
        const sign = Math.sign(p.vy);
        for (let k = 0; k < Math.ceil(Math.abs(p.vy)); k++) {
          if (!this.collidesBox(p.x, p.y + sign * 0.5, p.w, p.h)) p.y += sign * 0.5;
          else break;
        }
        p.vy = 0;
      }

      p.x = Math.max(5, Math.min(world.width - 5, p.x));
      p.y = Math.max(8, Math.min(world.height - 8, p.y));

      if (p.grounded || inWater) p.flight = Math.min(p.maxFlight, p.flight + 4.2);

      const cape = p.cape;
      cape[0].x = p.x - p.facing * 1.5;
      cape[0].y = p.y - 1.5;
      for (let i = 1; i < cape.length; i++) {
        const prev = cape[i - 1], cur = cape[i];
        cur.y += 0.25;
        cur.x += -p.facing * 0.22 - p.vx * 0.18 + world.windX * 0.25;
        const cdx = cur.x - prev.x, cdy = cur.y - prev.y;
        const cdist = Math.max(0.01, Math.hypot(cdx, cdy));
        if (cdist > 1.85) {
          cur.x = prev.x + (cdx / cdist) * 1.85;
          cur.y = prev.y + (cdy / cdist) * 1.85;
        }
      }
    }

    firePayload(pr, x, y, angle) {
      if (!pr.payload || pr.payloadFired) return;
      pr.payloadFired = true;
      this.executeActions(pr.payload, x, y, angle, true);
      if (pr.triggerType === 'double_hit') {
        this.executeActions(pr.payload, x, y, angle + 0.28, true);
      }
    }

    triggerProjectileImpact(pr, gx, gy) {
      const world = this.world;
      const EL = this.EL;
      const pm = (pr.mods && pr.mods.powerMult) || 1;

      if (pr.kind === 'nuke') {
        this.detonateNuke(gx, gy, pm);
      } else if (pr.kind === 'meteor') {
        world.queueExplosion(gx, gy, Math.round(24 * pm));
        world.paintCircle(gx, gy, 7, EL.LAVA, true);
        this.damageEnemiesInRadius(pr.x, pr.y, 28, pr.damage || 52, 0, -2.5);
      } else if (pr.kind === 'plasma_cross') {
        if (this.plasmaCrosses.length < 18) {
          this.plasmaCrosses.push({ x: pr.x, y: pr.y, angle: Math.random() * Math.PI, radius: Math.round(22 * pm), life: 68 });
          this.world.emitEvent('spell_plasma', 0.9, pr.x, pr.y);
        }
      } else if (pr.kind === 'rain_cloud' || pr.kind === 'acid_cloud') {
        if (this.clouds.length < 10) {
          let cy = pr.y;
          for (let up = 1; up <= 10; up++) {
            const ty = (pr.y - up) | 0;
            if (!world.inBounds(pr.x | 0, ty) || world.grid[ty * world.width + (pr.x | 0)] !== EL.EMPTY) break;
            cy = ty;
          }
          // If hit ceiling, nudge slightly down into open air
          if (world.inBounds(pr.x | 0, (cy + 2) | 0) && world.grid[(cy | 0) * world.width + (pr.x | 0)] !== EL.EMPTY) {
            cy = Math.min(world.height - 16, cy + 6);
          }
          this.clouds.push({
            kind: pr.kind === 'acid_cloud' ? 'acid' : 'rain',
            x: pr.x, y: Math.max(14, cy), width: 32, life: 220,
          });
        }
      } else if (pr.kind === 'firebolt' || pr.kind === 'enemy_fire') {
        world.queueExplosion(gx, gy, pr.kind === 'firebolt' ? Math.round(15 * pm) : 9);
        this.damageEnemiesInRadius(pr.x, pr.y, 18, pr.damage || 24, 0, -1.5);
      } else if (pr.kind === 'acid_ball') {
        world.paintCircle(gx, gy, Math.round(5 * pm), EL.ACID, true);
        this.damageEnemiesInRadius(pr.x, pr.y, 12, pr.damage || 14, 0, -0.5);
      } else if (pr.kind === 'cryo_orb') {
        world.paintCircle(gx, gy, Math.round(6 * pm), EL.NITROGEN, true);
        world.shockwaves.push({ x: pr.x, y: pr.y, r: 2, maxR: 16, alpha: 0.9, color: '#8af5ff' });
        this.damageEnemiesInRadius(pr.x, pr.y, 14, pr.damage || 14, 0, 0);
      } else if (pr.kind === 'firework_spell') {
        world.burstFirework(gx, gy, (Math.random() * 6) | 0);
        this.damageEnemiesInRadius(pr.x, pr.y, 20, pr.damage || 18, 0, -1.5);
      } else if (pr.kind === 'flamethrower') {
        world.paintCircle(gx, gy, 3, EL.FIRE, true);
        this.damageEnemiesInRadius(pr.x, pr.y, 8, pr.damage || 8, 0, 0);
      } else if (pr.kind === 'spark_bolt') {
        world.paintCircle(gx, gy, 2, EL.SPARK, true);
        this.damageEnemiesInRadius(pr.x, pr.y, 8, pr.damage || 12, pr.vx * 0.2, pr.vy * 0.2);
      } else if (pr.kind === 'sawblade') {
        world.paintCircle(gx, gy, 3, EL.EMPTY, false);
        world.spawnParticle(pr.x, pr.y, -pr.vx * 0.4, -pr.vy * 0.4, EL.SPARK, [255, 225, 130], 14);
      } else if (pr.kind === 'heal_bolt') {
        world.shockwaves.push({ x: pr.x, y: pr.y, r: 1, maxR: 10, alpha: 0.85, color: '#4dff9b' });
      }

      if ((pr.triggerType === 'hit' || pr.triggerType === 'double_hit') && pr.payload && !pr.payloadFired) {
        this.firePayload(pr, pr.x - pr.vx * 0.6, pr.y - pr.vy * 0.6, Math.atan2(-pr.vy, -pr.vx));
      }
    }

    updateProjectiles() {
      const world = this.world;
      const EL = this.EL;

      for (let i = this.projectiles.length - 1; i >= 0; i--) {
        const pr = this.projectiles[i];
        pr.life--;
        pr.age++;
        const mods = pr.mods || {};

        if (pr.kind === 'acid_ball' || pr.kind === 'cryo_orb' || pr.kind === 'nuke') pr.vy += 0.09;
        if (pr.kind === 'enemy_fire') pr.vy += 0.03;
        if (mods.heavyGrav) pr.vy += 0.16;

        // Air split modifier: divide into 3 fan projectiles mid-flight!
        if (pr.splitLeft > 0 && pr.age === 14 && this.projectiles.length < 220) {
          pr.splitLeft = 0;
          const baseAng = Math.atan2(pr.vy, pr.vx);
          const spd = Math.hypot(pr.vx, pr.vy);
          const offsets = [-0.28, 0.28];
          for (let k = 0; k < 2; k++) {
            const a = baseAng + offsets[k];
            this.projectiles.push({
              ...pr,
              vx: Math.cos(a) * spd,
              vy: Math.sin(a) * spd,
              splitLeft: 0,
              payload: null,
              payloadFired: true,
              life: Math.max(18, pr.life),
            });
          }
        }

        // Homing modifier
        if (mods.homing && pr.owner === 'player' && this.enemies.length > 0 && pr.kind !== 'heal_bolt') {
          let best = null, bestD = 140;
          for (let k = 0; k < this.enemies.length; k++) {
            const e = this.enemies[k];
            const d = Math.hypot(e.x - pr.x, e.y - pr.y);
            if (d < bestD) { bestD = d; best = e; }
          }
          if (best) {
            const spd = Math.max(2, Math.hypot(pr.vx, pr.vy));
            pr.vx += (((best.x - pr.x) / bestD) * spd - pr.vx) * 0.16;
            pr.vy += (((best.y - pr.y) / bestD) * spd - pr.vy) * 0.16;
          }
        }

        // Orbit spiral wave modifier
        if (mods.orbit) {
          const spd = Math.max(0.5, Math.hypot(pr.vx, pr.vy));
          const osc = Math.cos(pr.age * 0.55) * 0.85;
          pr.x += (-pr.vy / spd) * osc;
          pr.y += (pr.vx / spd) * osc;
        }

        // Boomerang modifier OR innate sawblade return curve!
        if ((pr.kind === 'sawblade' || mods.boomerang) && pr.age > 16 && !this.player.dead) {
          const dx = this.player.x - pr.x, dy = this.player.y - pr.y;
          const d = Math.max(1, Math.hypot(dx, dy));
          const pull = mods.boomerang ? 0.38 : 0.3;
          pr.vx += (dx / d) * pull;
          pr.vy += (dy / d) * pull;
          const spd = Math.hypot(pr.vx, pr.vy);
          if (spd > 6.5) { pr.vx = (pr.vx / spd) * 6.5; pr.vy = (pr.vy / spd) * 6.5; }
        }

        // Electric arc modifier zaps nearby conductors/enemies while flying!
        if (mods.electricArc && (pr.age % 5) === 0) {
          this.pulseElectricArc(pr.x, pr.y);
        }

        // Timer trigger detonation mid-air
        if (pr.triggerType === 'timer' && pr.payload && !pr.payloadFired) {
          pr.timerLeft--;
          if (pr.timerLeft <= 0) {
            this.firePayload(pr, pr.x, pr.y, Math.atan2(pr.vy, pr.vx));
          }
        }

        // Trail modifiers pour real elements into the cellular world
        if (mods.trails && mods.trails.length > 0) {
          this.emitTrailElements(pr.x, pr.y, mods.trails);
        }

        // Innate trails for meteor & flamethrower
        if (pr.kind === 'meteor') {
          this.emitTrailElements(pr.x, pr.y, ['LAVA', 'FIRE']);
        } else if (pr.kind === 'flamethrower' && Math.random() < 0.7) {
          world.setCell(pr.x | 0, pr.y | 0, EL.FIRE, true);
        }

        const steps = Math.max(1, Math.ceil(Math.hypot(pr.vx, pr.vy)));
        const sx = pr.vx / steps, sy = pr.vy / steps;
        let dead = false;

        for (let s = 0; s < steps; s++) {
          const prevX = pr.x, prevY = pr.y;
          pr.x += sx; pr.y += sy;
          const gx = pr.x | 0, gy = pr.y | 0;

          if (!world.inBounds(gx, gy)) { dead = true; break; }

          // Self-interactions: enemy fire, boomerang sawblade, and HEAL BOLT!
          if (!this.player.dead) {
            const distP = Math.hypot(pr.x - this.player.x, pr.y - this.player.y);
            if (pr.owner === 'enemy' && distP < 6) {
              this.damagePlayer(12, '被暗穴火灵的火球击中');
              world.queueExplosion(gx, gy, 8);
              dead = true; break;
            }
            if (pr.kind === 'sawblade' && pr.age > 24 && distP < 5.5) {
              this.damagePlayer(22, '被自己射出的回旋锯片切成两半');
              dead = true; break;
            }
            if (pr.kind === 'heal_bolt' && pr.age > 8 && distP < 7.5) {
              this.healPlayer(22);
              dead = true; break;
            }
          }

          // Player projectiles hit enemies
          if (pr.owner === 'player' && pr.kind !== 'teleport_spell' && pr.kind !== 'heal_bolt') {
            for (let eIdx = this.enemies.length - 1; eIdx >= 0; eIdx--) {
              const e = this.enemies[eIdx];
              if (Math.hypot(pr.x - e.x, pr.y - e.y) < e.radius + 3.4) {
                this.triggerProjectileImpact(pr, gx, gy);
                if (pr.pierceLeft > 0) pr.pierceLeft--;
                else dead = true;
                break;
              }
            }
            if (dead) break;
          }

          const cell = world.grid[gy * world.width + gx];
          const solidHit =
            cell !== EL.EMPTY && cell !== EL.FIRE && cell !== EL.SMOKE &&
            cell !== EL.STEAM && cell !== EL.SPARK && cell !== EL.TOXIC;

          if (solidHit) {
            if (pr.kind === 'teleport_spell') {
              this.executeTeleport(prevX - sx * 2, prevY - sy * 2);
              if ((pr.triggerType === 'hit' || pr.triggerType === 'double_hit') && pr.payload && !pr.payloadFired) {
                this.firePayload(pr, this.player.x, this.player.y, Math.atan2(pr.vy, pr.vx));
              }
              dead = true;
              break;
            }

            if (pr.kind === 'sawblade' && (cell === EL.WOOD || cell === EL.PLANT)) {
              world.paintCircle(gx, gy, 2, EL.EMPTY, false);
              continue;
            }

            if (pr.pierceLeft > 0 && cell !== EL.VOID && cell !== EL.CLONER) {
              pr.pierceLeft--;
              world.paintCircle(gx, gy, 2, EL.EMPTY, false);
              world.spawnParticle(pr.x, pr.y, -sx * 2 + (Math.random() - 0.5) * 2, -sy * 2, EL.SPARK, [255, 220, 120], 10);
              continue;
            }

            if (pr.bouncesLeft > 0) {
              pr.bouncesLeft--;
              const pGx = prevX | 0, pGy = prevY | 0;
              const hitX = world.inBounds(gx, pGy) && world.grid[pGy * world.width + gx] !== EL.EMPTY;
              const hitY = world.inBounds(pGx, gy) && world.grid[gy * world.width + pGx] !== EL.EMPTY;
              if (hitX) pr.vx = -pr.vx * 0.92;
              if (hitY) pr.vy = -pr.vy * 0.92;
              if (!hitX && !hitY) { pr.vx = -pr.vx * 0.9; pr.vy = -pr.vy * 0.9; }
              pr.x = prevX; pr.y = prevY;
              if ((pr.triggerType === 'hit' || pr.triggerType === 'double_hit') && pr.payload && !pr.payloadFired) {
                this.firePayload(pr, pr.x, pr.y, Math.atan2(pr.vy, pr.vx));
              }
              break;
            }

            this.triggerProjectileImpact(pr, gx, gy);
            dead = true;
            break;
          }
        }

        // Visual trails
        if (!dead && Math.random() < 0.65) {
          if (pr.kind === 'firebolt' || pr.kind === 'enemy_fire' || pr.kind === 'meteor' || pr.kind === 'nuke') {
            world.spawnParticle(pr.x, pr.y, (Math.random() - 0.5) * 0.8, -0.4, EL.EMBER, [255, 165, 55], 12);
          } else if (pr.kind === 'teleport_spell') {
            world.spawnParticle(pr.x, pr.y, 0, 0, EL.SPARK, [100, 245, 255], 10);
          } else if (pr.kind === 'heal_bolt') {
            world.spawnParticle(pr.x, pr.y, 0, -0.2, EL.SPARK, [80, 255, 165], 10);
          } else if (pr.kind === 'spark_bolt') {
            world.spawnParticle(pr.x, pr.y, 0, 0, EL.SPARK, [205, 130, 255], 8);
          } else if (pr.kind === 'firework_spell' || pr.kind === 'plasma_cross') {
            world.spawnParticle(pr.x, pr.y, (Math.random() - 0.5) * 0.7, 0.2, EL.SPARK, [255, 120, 220], 11);
          } else if (pr.kind === 'cryo_orb') {
            world.spawnParticle(pr.x, pr.y, 0, 0.2, EL.SPARK, [145, 246, 255], 10);
          }
        }

        if (dead || pr.life <= 0) {
          if (!dead) {
            if (pr.kind === 'teleport_spell') {
              this.executeTeleport(pr.x, pr.y);
            } else if (pr.kind === 'plasma_cross' || pr.kind === 'rain_cloud' || pr.kind === 'acid_cloud' || pr.kind === 'firework_spell' || pr.kind === 'nuke') {
              this.triggerProjectileImpact(pr, pr.x | 0, pr.y | 0);
            }
          }
          // Death trigger (or fallback for expired triggers) fires right at demise!
          if (pr.payload && !pr.payloadFired && (pr.triggerType === 'death' || !dead)) {
            this.firePayload(pr, pr.x, pr.y, Math.atan2(pr.vy, pr.vx));
          }
          this.projectiles.splice(i, 1);
        }
      }
    }

    updatePlasmaCrosses() {
      const world = this.world;
      const EL = this.EL;

      for (let i = this.plasmaCrosses.length - 1; i >= 0; i--) {
        const pc = this.plasmaCrosses[i];
        pc.angle += 0.085;
        pc.life--;

        for (let arm = 0; arm < 4; arm++) {
          const ang = pc.angle + (arm * Math.PI) * 0.5;
          const ca = Math.cos(ang), sa = Math.sin(ang);
          for (let d = 3; d <= pc.radius; d += 2) {
            const px = pc.x + ca * d;
            const py = pc.y + sa * d;
            const gx = px | 0, gy = py | 0;
            if (!world.inBounds(gx, gy)) break;

            const idx = gy * world.width + gx;
            const cell = world.grid[idx];
            if (cell !== EL.EMPTY && cell !== EL.VOID && cell !== EL.CLONER) {
              if (cell === EL.GUNPOWDER || cell === EL.C4) world.queueExplosion(gx, gy, 18);
              else if (cell === EL.METAL) world.temp[idx] = Math.min(1000, world.temp[idx] + 150);
              else world.setCell(gx, gy, EL.EMPTY, true);
              if (Math.random() < 0.2) {
                world.spawnParticle(px, py, (Math.random() - 0.5) * 2.5, -1, EL.SPARK, [255, 110, 235], 10);
              }
            }

            if ((d & 3) === 3) {
              this.damageEnemiesInRadius(px, py, 5, 5, ca, sa);
              if (!this.player.dead && Math.hypot(px - this.player.x, py - this.player.y) < 5) {
                this.damagePlayer(6, '被自己的等离子十字切成像素块');
              }
            }
          }
        }

        if (pc.life <= 0) this.plasmaCrosses.splice(i, 1);
      }
    }

    updateClouds() {
      const world = this.world;
      const EL = this.EL;

      for (let i = this.clouds.length - 1; i >= 0; i--) {
        const c = this.clouds[i];
        c.life--;
        c.x += Math.sin(c.life * 0.05) * 0.18 + world.windX * 0.25;
        c.x = Math.max(16, Math.min(world.width - 16, c.x));

        // Pour rain or acid droplets downward into first open air cell below cloud
        const drops = c.kind === 'acid' ? 3 : 5;
        for (let k = 0; k < drops; k++) {
          const rx = (c.x + (Math.random() - 0.5) * c.width) | 0;
          for (let dy = 3; dy <= 9; dy++) {
            const ry = (c.y + dy) | 0;
            if (!world.inBounds(rx, ry)) break;
            if (world.grid[ry * world.width + rx] === EL.EMPTY) {
              world.setCell(rx, ry, c.kind === 'acid' ? EL.ACID : EL.WATER, true);
              break;
            }
          }
        }

        // Rain cloud periodically strikes downward lightning!
        if (c.kind === 'rain' && (c.life % 36) === 0) {
          const lx = c.x + (Math.random() - 0.5) * c.width * 0.7;
          this.castDirectedLightning(lx, c.y + 5, (Math.random() - 0.5) * 0.25, 1, null);
          world.emitEvent('lightning', 0.65, lx, c.y);
        }

        if (c.life <= 0) this.clouds.splice(i, 1);
      }
    }

    executeTeleport(tx, ty) {
      const p = this.player;
      if (p.dead) return;
      this.afterimages.push({ x: p.x, y: p.y, life: 14, maxLife: 14 });
      const safe = this.findSafeSpawn(tx, ty);
      p.x = safe.x; p.y = safe.y; p.vy *= 0.25;
      for (let i = 0; i < p.cape.length; i++) { p.cape[i].x = p.x; p.cape[i].y = p.y; }
      this.world.shockwaves.push({ x: p.x, y: p.y, r: 2, maxR: 16, alpha: 0.95, color: '#6cf0ff' });
      this.world.emitEvent('teleport', 0.9, p.x, p.y);
    }

    updateBlackHoles() {
      const world = this.world;
      const EL = this.EL;

      for (let i = this.blackHoles.length - 1; i >= 0; i--) {
        const bh = this.blackHoles[i];
        const mods = bh.mods || {};
        bh.age++;

        if (mods.homing && this.enemies.length > 0) {
          let best = null, bestD = 140;
          for (let k = 0; k < this.enemies.length; k++) {
            const e = this.enemies[k];
            const d = Math.hypot(e.x - bh.x, e.y - bh.y);
            if (d < bestD) { bestD = d; best = e; }
          }
          if (best) {
            bh.vx += (((best.x - bh.x) / bestD) * 1.5 - bh.vx) * 0.08;
            bh.vy += (((best.y - bh.y) / bestD) * 1.5 - bh.vy) * 0.08;
          }
        }

        if (mods.boomerang && bh.age > 28 && !this.player.dead) {
          const dx = this.player.x - bh.x, dy = this.player.y - bh.y;
          const d = Math.max(1, Math.hypot(dx, dy));
          bh.vx += (dx / d) * 0.14;
          bh.vy += (dy / d) * 0.14;
        }

        if (mods.electricArc && (bh.age % 7) === 0) {
          this.pulseElectricArc(bh.x, bh.y);
        }

        bh.x += bh.vx;
        bh.y += bh.vy;
        bh.spin += 0.26;
        bh.life--;

        const cx = bh.x | 0, cy = bh.y | 0;
        const eatR = bh.radius | 0;
        const pullR = eatR + 12;

        for (let dy = -eatR; dy <= eatR; dy++) {
          const py = cy + dy;
          if (py < 2 || py >= world.height - 2) continue;
          for (let dx = -eatR; dx <= eatR; dx++) {
            if (dx * dx + dy * dy > eatR * eatR) continue;
            const px = cx + dx;
            if (px < 2 || px >= world.width - 2) continue;
            const idx = py * world.width + px;
            if (world.grid[idx] !== EL.EMPTY) {
              world.grid[idx] = EL.EMPTY;
              world.life[idx] = 0;
            }
          }
        }

        if (mods.trails && mods.trails.length > 0) {
          const backX = bh.x - bh.vx * 7;
          const backY = bh.y - bh.vy * 7;
          this.emitTrailElements(backX, backY, mods.trails);
          this.emitTrailElements(backX + (Math.random() - 0.5) * 6, backY + (Math.random() - 0.5) * 6, mods.trails);
        }

        for (let k = 0; k < 14; k++) {
          const ang = Math.random() * Math.PI * 2;
          const dist = eatR + 2 + Math.random() * (pullR - eatR);
          const sx = (bh.x + Math.cos(ang) * dist) | 0;
          const sy = (bh.y + Math.sin(ang) * dist) | 0;
          if (!world.inBounds(sx, sy)) continue;
          const idx = sy * world.width + sx;
          const el = world.grid[idx];
          if (el !== EL.EMPTY && !this.isHardTerrain(el)) {
            world.grid[idx] = EL.EMPTY;
            world.spawnParticle(sx, sy, -Math.cos(ang) * 2.2, -Math.sin(ang) * 2.2, el, [195, 118, 255], 12);
          }
        }

        this.damageEnemiesInRadius(bh.x, bh.y, eatR + 5, 6, 0, 0);

        if (bh.triggerType === 'timer' && bh.payload && !bh.payloadFired) {
          bh.timerLeft--;
          if (bh.timerLeft <= 0) {
            this.firePayload(bh, bh.x, bh.y, Math.atan2(bh.vy, bh.vx));
          }
        }

        if (bh.life <= 0 || !world.inBounds(cx, cy)) {
          if (bh.payload && !bh.payloadFired) {
            this.firePayload(bh, bh.x, bh.y, Math.atan2(bh.vy, bh.vx));
          }
          world.shockwaves.push({ x: bh.x, y: bh.y, r: 4, maxR: 22, alpha: 0.9, color: '#c96bff' });
          this.blackHoles.splice(i, 1);
        }
      }
    }

    updateEnemies() {
      const world = this.world;
      const EL = this.EL;
      const p = this.player;

      for (let i = this.enemies.length - 1; i >= 0; i--) {
        const e = this.enemies[i];
        if (e.hurtFlash > 0) e.hurtFlash--;

        const gx = e.x | 0, gy = e.y | 0;
        if (world.inBounds(gx, gy)) {
          const cell = world.grid[gy * world.width + gx];
          if (e.type === 'slime' && (cell === EL.LAVA || cell === EL.FIRE)) { e.hp -= 2.5; e.hurtFlash = 4; }
          else if (e.type === 'spirit' && (cell === EL.WATER || cell === EL.NITROGEN)) { e.hp -= 3.5; e.hurtFlash = 4; }
          else if (cell === EL.ACID && e.type !== 'slime') { e.hp -= 2.5; e.hurtFlash = 4; }
        }

        for (let k = 0; k < world.recentExplosions.length; k++) {
          const ex = world.recentExplosions[k];
          const dist = Math.hypot(e.x - ex.x, e.y - ex.y);
          if (dist < ex.radius * 1.4) {
            e.hp -= 36 * (1 - dist / (ex.radius * 1.4));
            e.hurtFlash = 8;
          }
        }

        if (e.hp <= 0) { this.killEnemy(i); continue; }

        if (e.type === 'slime') {
          e.vy += 0.16;
          e.hopCd--;
          const distToP = Math.hypot(p.x - e.x, p.y - e.y);
          if (e.hopCd <= 0) {
            e.hopCd = 38 + ((Math.random() * 32) | 0);
            const dir = !p.dead && distToP < 110 ? Math.sign(p.x - e.x) || 1 : (Math.random() < 0.5 ? -1 : 1);
            e.vx = dir * (1.2 + Math.random() * 0.7);
            e.vy = -2.4 - Math.random() * 0.9;
          }
          e.vx *= 0.92;
          const nx = e.x + e.vx;
          if (!this.collidesBox(nx, e.y, 7, 7)) e.x = nx; else e.vx *= -0.7;
          const ny = e.y + e.vy;
          if (!this.collidesBox(e.x, ny, 7, 7)) e.y = ny; else e.vy = 0;
        } else {
          e.timer++;
          const distToP = Math.hypot(p.x - e.x, p.y - e.y);
          const targetVx = !p.dead && distToP < 135 ? Math.sign(p.x - e.x) * 0.55 : Math.sin(e.timer * 0.03) * 0.5;
          const targetVy = Math.cos(e.timer * 0.05) * 0.45 + (!p.dead && distToP < 135 && e.y > p.y + 8 ? -0.35 : 0);
          e.vx += (targetVx - e.vx) * 0.08;
          e.vy += (targetVy - e.vy) * 0.08;
          if (!this.collidesBox(e.x + e.vx, e.y, 7, 7)) e.x += e.vx;
          if (!this.collidesBox(e.x, e.y + e.vy, 7, 7)) e.y += e.vy;

          if (Math.random() < 0.25) {
            world.spawnParticle(e.x, e.y - 3, (Math.random() - 0.5) * 0.5, -0.8, EL.EMBER, [255, 130, 42], 12);
          }

          e.shootCd--;
          if (!p.dead && distToP < 125 && e.shootCd <= 0) {
            e.shootCd = 95 + ((Math.random() * 45) | 0);
            const dx = p.x - e.x, dy = p.y - e.y;
            const d = Math.max(1, Math.hypot(dx, dy));
            this.projectiles.push({
              kind: 'enemy_fire', color: '#ff6a1f', damage: 12,
              x: e.x + (dx / d) * 6, y: e.y + (dy / d) * 6,
              vx: (dx / d) * 3.1, vy: (dy / d) * 3.1 - 0.4,
              age: 0, life: 85, owner: 'enemy', mods: {},
              bouncesLeft: 0, pierceLeft: 0, splitLeft: 0,
              triggerType: null, payload: null, timerLeft: 0, payloadFired: false,
            });
          }
        }

        if (!p.dead && Math.hypot(e.x - p.x, e.y - p.y) < 7.5) {
          this.damagePlayer(12, e.type === 'slime' ? '被暗穴史莱姆撞翻' : '被浮空火灵灼烧');
          p.vx += Math.sign(p.x - e.x) * 2.4;
          p.vy = -2.2;
        }
      }
    }

    collectLights() {
      if (!this.enabled) return null;
      const lights = [];
      const p = this.player;
      if (!p.dead) {
        lights.push({ x: p.x, y: p.y - 2, r: 0.95, g: 0.82, b: 1.15, radius: 34 });
        if (p.burning > 0) lights.push({ x: p.x, y: p.y - 3, r: 1.5, g: 0.72, b: 0.2, radius: 28 });
      }

      for (let i = 0; i < this.projectiles.length; i++) {
        const pr = this.projectiles[i];
        if (pr.kind === 'nuke' || pr.kind === 'meteor') {
          lights.push({ x: pr.x, y: pr.y, r: 2.0, g: 1.2, b: 0.3, radius: 34 });
        } else if (pr.kind === 'firebolt' || pr.kind === 'enemy_fire' || pr.kind === 'flamethrower') {
          lights.push({ x: pr.x, y: pr.y, r: 1.7, g: 0.85, b: 0.25, radius: 24 });
        } else if (pr.kind === 'heal_bolt') {
          lights.push({ x: pr.x, y: pr.y, r: 0.4, g: 1.7, b: 0.9, radius: 24 });
        } else if (pr.kind === 'teleport_spell' || pr.kind === 'cryo_orb') {
          lights.push({ x: pr.x, y: pr.y, r: 0.5, g: 1.4, b: 1.8, radius: 22 });
        } else if (pr.kind === 'acid_ball') {
          lights.push({ x: pr.x, y: pr.y, r: 0.35, g: 1.25, b: 0.3, radius: 16 });
        } else {
          lights.push({ x: pr.x, y: pr.y, r: 1.0, g: 0.65, b: 1.5, radius: 18 });
        }
      }

      for (let i = 0; i < this.blackHoles.length; i++) {
        const bh = this.blackHoles[i];
        lights.push({ x: bh.x, y: bh.y, r: 1.2, g: 0.4, b: 1.8, radius: 36 });
      }

      for (let i = 0; i < this.plasmaCrosses.length; i++) {
        const pc = this.plasmaCrosses[i];
        lights.push({ x: pc.x, y: pc.y, r: 1.8, g: 0.5, b: 1.6, radius: 38 });
      }

      for (let i = 0; i < this.clouds.length; i++) {
        const c = this.clouds[i];
        if (c.kind === 'acid') lights.push({ x: c.x, y: c.y, r: 0.4, g: 1.2, b: 0.35, radius: 28 });
        else lights.push({ x: c.x, y: c.y, r: 0.35, g: 0.65, b: 1.1, radius: 26 });
      }

      for (let i = 0; i < this.enemies.length; i++) {
        const e = this.enemies[i];
        if (e.type === 'spirit') lights.push({ x: e.x, y: e.y, r: 1.4, g: 0.65, b: 0.2, radius: 24 });
        else lights.push({ x: e.x, y: e.y, r: 0.25, g: 0.85, b: 0.3, radius: 16 });
      }

      return lights;
    }

    renderOverlay(ctx) {
      if (!this.enabled) return;

      // 1. Floating storm & acid clouds
      for (let i = 0; i < this.clouds.length; i++) {
        const c = this.clouds[i];
        const fade = Math.min(1, c.life / 25);
        ctx.save();
        ctx.globalAlpha = fade * 0.88;
        ctx.fillStyle = c.kind === 'acid' ? '#2c6b22' : '#263854';
        ctx.beginPath();
        ctx.arc(c.x - 10, c.y, 8, 0, Math.PI * 2);
        ctx.arc(c.x, c.y - 3, 10, 0, Math.PI * 2);
        ctx.arc(c.x + 10, c.y, 8, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = c.kind === 'acid' ? '#7dff4a' : '#7ec2ff';
        ctx.globalAlpha = fade * 0.45;
        ctx.fillRect(c.x - 12, c.y + 4, 24, 2);
        ctx.restore();
      }

      // 2. Teleport afterimages
      for (let i = 0; i < this.afterimages.length; i++) {
        const a = this.afterimages[i];
        ctx.save();
        ctx.globalAlpha = (a.life / a.maxLife) * 0.65;
        ctx.fillStyle = '#7bf2ff';
        ctx.fillRect(a.x - 2.5, a.y - 5, 5, 10);
        ctx.restore();
      }

      // 3. Rotating Plasma Crosses!
      for (let i = 0; i < this.plasmaCrosses.length; i++) {
        const pc = this.plasmaCrosses[i];
        const fade = Math.min(1, pc.life / 14);
        ctx.save();
        ctx.globalAlpha = fade;
        ctx.translate(pc.x, pc.y);
        ctx.rotate(pc.angle);
        ctx.lineCap = 'round';

        ctx.strokeStyle = 'rgba(255, 72, 214, 0.72)';
        ctx.lineWidth = 4.2;
        ctx.beginPath();
        ctx.moveTo(-pc.radius, 0); ctx.lineTo(pc.radius, 0);
        ctx.moveTo(0, -pc.radius); ctx.lineTo(0, pc.radius);
        ctx.stroke();

        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 1.4;
        ctx.stroke();
        ctx.restore();
      }

      // 4. Lightning arcs
      for (let i = 0; i < this.lightningArcs.length; i++) {
        const arc = this.lightningArcs[i];
        const alpha = arc.life / arc.maxLife;
        ctx.save();
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        ctx.strokeStyle = `rgba(92, 224, 255, ${alpha * 0.65})`;
        ctx.lineWidth = 3.2;
        ctx.beginPath();
        arc.points.forEach((pt, idx) => (idx === 0 ? ctx.moveTo(pt.x, pt.y) : ctx.lineTo(pt.x, pt.y)));
        ctx.stroke();

        ctx.strokeStyle = `rgba(240, 252, 255, ${alpha})`;
        ctx.lineWidth = 1.1;
        ctx.stroke();

        ctx.strokeStyle = `rgba(125, 232, 255, ${alpha * 0.75})`;
        ctx.lineWidth = 1;
        for (const br of arc.branches) {
          ctx.beginPath();
          br.forEach((pt, idx) => (idx === 0 ? ctx.moveTo(pt.x, pt.y) : ctx.lineTo(pt.x, pt.y)));
          ctx.stroke();
        }
        ctx.restore();
      }

      // 5. Spinning Black Holes
      for (let i = 0; i < this.blackHoles.length; i++) {
        const bh = this.blackHoles[i];
        ctx.save();
        ctx.translate(bh.x, bh.y);
        ctx.strokeStyle = 'rgba(198, 102, 255, 0.85)';
        ctx.lineWidth = 1.8;
        ctx.beginPath();
        ctx.arc(0, 0, bh.radius, 0, Math.PI * 2);
        ctx.stroke();

        ctx.rotate(bh.spin);
        ctx.strokeStyle = 'rgba(244, 198, 255, 0.85)';
        ctx.lineWidth = 1.1;
        for (let a = 0; a < 3; a++) {
          ctx.rotate((Math.PI * 2) / 3);
          ctx.beginPath();
          ctx.arc(0, 0, bh.radius * 0.75, 0, 1.3);
          ctx.stroke();
        }

        ctx.fillStyle = '#07030f';
        ctx.beginPath();
        ctx.arc(0, 0, bh.radius * 0.58, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      }

      // 6. Projectiles
      for (let i = 0; i < this.projectiles.length; i++) {
        const pr = this.projectiles[i];
        ctx.save();
        if (pr.kind === 'nuke') {
          ctx.translate(pr.x, pr.y);
          ctx.rotate(Math.atan2(pr.vy, pr.vx));
          ctx.fillStyle = '#404856';
          ctx.fillRect(-4.5, -2.2, 7.5, 4.4);
          ctx.fillStyle = '#ffe84a';
          ctx.fillRect(2, -1.6, 2.5, 3.2);
          ctx.fillStyle = '#ff4f24';
          ctx.fillRect(-5.5, -1.2, 1.5, 2.4);
        } else if (pr.kind === 'meteor') {
          ctx.fillStyle = '#ff4414';
          ctx.beginPath();
          ctx.arc(pr.x, pr.y, 4.6, 0, Math.PI * 2);
          ctx.fill();
          ctx.fillStyle = '#fff0a8';
          ctx.beginPath();
          ctx.arc(pr.x, pr.y, 2.2, 0, Math.PI * 2);
          ctx.fill();
        } else if (pr.kind === 'sawblade') {
          ctx.translate(pr.x, pr.y);
          ctx.rotate(pr.age * 0.7);
          ctx.strokeStyle = '#e8f0ff';
          ctx.lineWidth = 1.3;
          ctx.beginPath();
          ctx.arc(0, 0, 3.2, 0, Math.PI * 2);
          ctx.moveTo(-4, 0); ctx.lineTo(4, 0);
          ctx.moveTo(0, -4); ctx.lineTo(0, 4);
          ctx.stroke();
          ctx.fillStyle = '#ff5468';
          ctx.fillRect(-1, -1, 2, 2);
        } else if (pr.kind === 'heal_bolt') {
          ctx.strokeStyle = '#4dff9b';
          ctx.lineWidth = 1.5;
          ctx.beginPath();
          ctx.arc(pr.x, pr.y, 3.2, 0, Math.PI * 2);
          ctx.stroke();
          ctx.fillStyle = '#d4ffe8';
          ctx.fillRect(pr.x - 1, pr.y - 2.2, 2, 4.4);
          ctx.fillRect(pr.x - 2.2, pr.y - 1, 4.4, 2);
        } else if (pr.kind === 'firebolt' || pr.kind === 'enemy_fire' || pr.kind === 'flamethrower') {
          ctx.fillStyle = '#ff6b1a';
          ctx.beginPath();
          ctx.arc(pr.x, pr.y, pr.kind === 'firebolt' ? 2.6 : 2.0, 0, Math.PI * 2);
          ctx.fill();
          ctx.fillStyle = '#fff5bd';
          ctx.beginPath();
          ctx.arc(pr.x, pr.y, 1.1, 0, Math.PI * 2);
          ctx.fill();
        } else if (pr.kind === 'acid_ball' || pr.kind === 'acid_cloud') {
          ctx.fillStyle = '#6aff44';
          ctx.beginPath();
          ctx.arc(pr.x, pr.y, 2.3, 0, Math.PI * 2);
          ctx.fill();
        } else if (pr.kind === 'cryo_orb' || pr.kind === 'rain_cloud') {
          ctx.fillStyle = '#8ef5ff';
          ctx.beginPath();
          ctx.arc(pr.x, pr.y, 2.4, 0, Math.PI * 2);
          ctx.fill();
          ctx.fillStyle = '#ffffff';
          ctx.fillRect(pr.x - 0.8, pr.y - 0.8, 1.6, 1.6);
        } else if (pr.kind === 'firework_spell' || pr.kind === 'plasma_cross') {
          ctx.fillStyle = '#ff52c8';
          ctx.beginPath();
          ctx.arc(pr.x, pr.y, 2.4, 0, Math.PI * 2);
          ctx.fill();
        } else if (pr.kind === 'teleport_spell') {
          ctx.fillStyle = '#7bf5ff';
          ctx.beginPath();
          ctx.arc(pr.x, pr.y, 2.2, 0, Math.PI * 2);
          ctx.fill();
          ctx.fillStyle = '#ffffff';
          ctx.fillRect(pr.x - 0.8, pr.y - 0.8, 1.6, 1.6);
        } else {
          ctx.strokeStyle = '#d48cff';
          ctx.lineWidth = 2.0;
          ctx.beginPath();
          ctx.moveTo(pr.x - pr.vx * 0.8, pr.y - pr.vy * 0.8);
          ctx.lineTo(pr.x, pr.y);
          ctx.stroke();
          ctx.fillStyle = '#ffffff';
          ctx.fillRect(pr.x - 1, pr.y - 1, 2, 2);
        }
        ctx.restore();
      }

      // 7. Enemies
      for (let i = 0; i < this.enemies.length; i++) {
        const e = this.enemies[i];
        ctx.save();
        if (e.type === 'slime') {
          ctx.fillStyle = e.hurtFlash > 0 ? '#ffffff' : '#58e842';
          ctx.fillRect(e.x - 4, e.y - 2, 8, 6);
          ctx.fillRect(e.x - 3, e.y - 4, 6, 2);
          ctx.fillStyle = '#0c1f0a';
          ctx.fillRect(e.x - 2, e.y - 1, 1.4, 1.8);
          ctx.fillRect(e.x + 1, e.y - 1, 1.4, 1.8);
        } else {
          ctx.fillStyle = e.hurtFlash > 0 ? '#ffffff' : '#ff6a1f';
          ctx.beginPath();
          ctx.arc(e.x, e.y, 4.2, 0, Math.PI * 2);
          ctx.fill();
          ctx.fillStyle = '#ffe985';
          ctx.fillRect(e.x - 2.2, e.y - 1.2, 1.4, 1.6);
          ctx.fillRect(e.x + 0.8, e.y - 1.2, 1.4, 1.6);
        }

        if (e.hp < e.maxHp) {
          const bw = 9;
          ctx.fillStyle = 'rgba(0,0,0,0.65)';
          ctx.fillRect(e.x - bw * 0.5, e.y - 8, bw, 1.8);
          ctx.fillStyle = '#ff5468';
          ctx.fillRect(e.x - bw * 0.5, e.y - 8, bw * Math.max(0, e.hp / e.maxHp), 1.8);
        }
        ctx.restore();
      }

      // 8. Wizard
      const p = this.player;
      if (!p.dead) {
        const blink = p.invuln > 0 && ((p.invuln >> 1) & 1);
        ctx.save();
        if (blink) ctx.globalAlpha = 0.55;

        ctx.strokeStyle = p.frozen > 0 ? '#6ad4ff' : '#5b2ba6';
        ctx.lineWidth = 3.2;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        ctx.beginPath();
        for (let i = 0; i < p.cape.length; i++) {
          const c = p.cape[i];
          if (i === 0) ctx.moveTo(c.x, c.y);
          else ctx.lineTo(c.x, c.y);
        }
        ctx.stroke();

        const x = Math.round(p.x), y = Math.round(p.y);
        const legSwing = Math.sin(p.walkPhase) * (Math.abs(p.vx) > 0.2 ? 1.4 : 0);

        ctx.fillStyle = '#33165e';
        ctx.fillRect(x - 2.5 + legSwing * 0.4, y + 3, 2, 2.5);
        ctx.fillRect(x + 0.5 - legSwing * 0.4, y + 3, 2, 2.5);

        ctx.fillStyle = p.wet > 0 ? '#5b39b8' : '#7a3be0';
        ctx.fillRect(x - 3, y - 2, 6, 5.5);

        ctx.fillStyle = '#f2c14e';
        ctx.fillRect(x - 3, y + 1, 6, 1.1);

        ctx.fillStyle = '#140b24';
        ctx.fillRect(x - 2.2, y - 5, 4.4, 3);
        ctx.fillStyle = '#ffe999';
        const eyeOff = p.facing > 0 ? 0.8 : -1.8;
        ctx.fillRect(x + eyeOff, y - 4, 1.2, 1.2);
        ctx.fillRect(x + eyeOff + 1.5 * p.facing, y - 4, 1.0, 1.2);

        ctx.fillStyle = '#8b46f5';
        ctx.beginPath();
        ctx.moveTo(x - 4.2, y - 4.6);
        ctx.lineTo(x + 4.2, y - 4.6);
        ctx.lineTo(x - p.facing * 1.4, y - 9.8);
        ctx.closePath();
        ctx.fill();

        const wand = this.getActiveWand();
        const wandColor = (wand && wand.color) || '#c47bff';
        const ang = Math.atan2(this.aimY - (p.y - 1), this.aimX - p.x);
        ctx.save();
        ctx.translate(p.x, p.y - 1);
        ctx.rotate(ang);
        ctx.fillStyle = '#c9975b';
        ctx.fillRect(1, -0.8, 6.5, 1.6);
        ctx.fillStyle = wandColor;
        ctx.fillRect(6.8, -1.2, 2.2, 2.4);
        ctx.restore();

        if (p.flight < p.maxFlight) {
          const barW = 10;
          ctx.fillStyle = 'rgba(0,0,0,0.6)';
          ctx.fillRect(x - barW * 0.5, y + 7.5, barW, 1.8);
          ctx.fillStyle = '#ffd65c';
          ctx.fillRect(x - barW * 0.5, y + 7.5, barW * (p.flight / p.maxFlight), 1.8);
        }

        ctx.strokeStyle = wandColor;
        ctx.lineWidth = 0.9;
        ctx.beginPath();
        ctx.arc(this.aimX, this.aimY, 3.6, 0, Math.PI * 2);
        ctx.moveTo(this.aimX - 6, this.aimY); ctx.lineTo(this.aimX - 2.5, this.aimY);
        ctx.moveTo(this.aimX + 2.5, this.aimY); ctx.lineTo(this.aimX + 6, this.aimY);
        ctx.moveTo(this.aimX, this.aimY - 6); ctx.lineTo(this.aimX, this.aimY - 2.5);
        ctx.moveTo(this.aimX, this.aimY + 2.5); ctx.lineTo(this.aimX, this.aimY + 6);
        ctx.stroke();

        ctx.restore();
      }

      // 9. Nuclear blinding white flash overlay
      if (this.flashAlpha > 0.02) {
        ctx.save();
        ctx.fillStyle = `rgba(255, 250, 224, ${this.flashAlpha})`;
        ctx.fillRect(0, 0, this.world.width, this.world.height);
        ctx.restore();
      }
    }
  }

  return { NoitaController };
});
