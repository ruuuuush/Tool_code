(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.SandAudio = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  class SandAudioEngine {
    constructor() {
      this.ctx = null;
      this.noiseBuf = null;
      this.enabled = true;
      this.lastPlay = Object.create(null);
    }

    ensureContext() {
      if (!this.enabled) return null;
      if (!this.ctx) {
        const AC = window.AudioContext || window.webkitAudioContext;
        if (!AC) return null;
        this.ctx = new AC();
        this.noiseBuf = this.createNoiseBuffer(this.ctx);
      }
      if (this.ctx.state === 'suspended') {
        this.ctx.resume().catch(() => {});
      }
      return this.ctx;
    }

    createNoiseBuffer(ctx) {
      const length = ctx.sampleRate * 1.2;
      const buf = ctx.createBuffer(1, length, ctx.sampleRate);
      const data = buf.getChannelData(0);
      for (let i = 0; i < length; i++) {
        data[i] = Math.random() * 2 - 1;
      }
      return buf;
    }

    canTrigger(key, minGapMs) {
      const now = performance.now();
      if (this.lastPlay[key] && now - this.lastPlay[key] < minGapMs) return false;
      this.lastPlay[key] = now;
      return true;
    }

    playEvents(events) {
      if (!this.enabled || !events || events.length === 0) return;
      const ctx = this.ensureContext();
      if (!ctx) return;

      for (let i = 0; i < events.length; i++) {
        const ev = events[i];
        if (ev.type === 'explosion') this.playExplosion(ctx, ev.intensity || 0.7);
        else if (ev.type === 'lightning') this.playLightning(ctx);
        else if (ev.type === 'firework_launch') this.playFireworkLaunch(ctx);
        else if (ev.type === 'firework_burst') this.playFireworkBurst(ctx);
        else if (ev.type === 'wind') this.playWind(ctx, ev.intensity || 0.5);
        else if (ev.type === 'spell_fire') this.playSpellFire(ctx);
        else if (ev.type === 'spell_blackhole') this.playBlackHole(ctx);
        else if (ev.type === 'spell_plasma') this.playPlasma(ctx);
        else if (ev.type === 'spell_acid') this.playAcidSpray(ctx);
        else if (ev.type === 'teleport') this.playTeleport(ctx);
        else if (ev.type === 'player_hurt') this.playHurt(ctx);
        else if (ev.type === 'enemy_die') this.playEnemyDie(ctx);
        else if (ev.type === 'nuke') this.playNuke(ctx);
        else if (ev.type === 'heal') this.playHeal(ctx);
      }
    }

    playExplosion(ctx, intensity) {
      if (!this.canTrigger('explosion', 55)) return;
      const t = ctx.currentTime;
      const vol = Math.min(0.28, 0.1 + intensity * 0.16);

      // Sub bass punch
      const osc = ctx.createOscillator();
      const oscGain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(118, t);
      osc.frequency.exponentialRampToValueAtTime(28, t + 0.34);
      oscGain.gain.setValueAtTime(vol, t);
      oscGain.gain.exponentialRampToValueAtTime(0.001, t + 0.38);
      osc.connect(oscGain).connect(ctx.destination);
      osc.start(t);
      osc.stop(t + 0.4);

      // Filtered rumble noise
      const src = ctx.createBufferSource();
      src.buffer = this.noiseBuf;
      const filter = ctx.createBiquadFilter();
      filter.type = 'lowpass';
      filter.frequency.setValueAtTime(720 + intensity * 600, t);
      filter.frequency.exponentialRampToValueAtTime(90, t + 0.45);
      const gain = ctx.createGain();
      gain.gain.setValueAtTime(vol * 0.85, t);
      gain.gain.exponentialRampToValueAtTime(0.001, t + 0.48);
      src.connect(filter).connect(gain).connect(ctx.destination);
      src.start(t);
      src.stop(t + 0.5);
    }

    playLightning(ctx) {
      if (!this.canTrigger('lightning', 70)) return;
      const t = ctx.currentTime;
      const src = ctx.createBufferSource();
      src.buffer = this.noiseBuf;

      const bp = ctx.createBiquadFilter();
      bp.type = 'bandpass';
      bp.frequency.setValueAtTime(2600, t);
      bp.frequency.exponentialRampToValueAtTime(180, t + 0.28);
      bp.Q.value = 1.4;

      const gain = ctx.createGain();
      gain.gain.setValueAtTime(0.2, t);
      gain.gain.exponentialRampToValueAtTime(0.001, t + 0.32);

      src.connect(bp).connect(gain).connect(ctx.destination);
      src.start(t);
      src.stop(t + 0.34);
    }

    playFireworkLaunch(ctx) {
      if (!this.canTrigger('fw_launch', 90)) return;
      const t = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(420, t);
      osc.frequency.exponentialRampToValueAtTime(1350, t + 0.24);
      gain.gain.setValueAtTime(0.05, t);
      gain.gain.exponentialRampToValueAtTime(0.001, t + 0.26);
      osc.connect(gain).connect(ctx.destination);
      osc.start(t);
      osc.stop(t + 0.27);
    }

    playFireworkBurst(ctx) {
      if (!this.canTrigger('fw_burst', 65)) return;
      const t = ctx.currentTime;
      const src = ctx.createBufferSource();
      src.buffer = this.noiseBuf;

      const hp = ctx.createBiquadFilter();
      hp.type = 'bandpass';
      hp.frequency.setValueAtTime(1800, t);
      hp.frequency.exponentialRampToValueAtTime(420, t + 0.26);
      hp.Q.value = 0.8;

      const gain = ctx.createGain();
      gain.gain.setValueAtTime(0.14, t);
      gain.gain.exponentialRampToValueAtTime(0.001, t + 0.28);

      src.connect(hp).connect(gain).connect(ctx.destination);
      src.start(t);
      src.stop(t + 0.3);
    }

    playWind(ctx, intensity) {
      if (!this.canTrigger('wind', 110)) return;
      const t = ctx.currentTime;
      const src = ctx.createBufferSource();
      src.buffer = this.noiseBuf;
      const bp = ctx.createBiquadFilter();
      bp.type = 'bandpass';
      bp.frequency.setValueAtTime(460 + intensity * 380, t);
      bp.Q.value = 2.4;
      const gain = ctx.createGain();
      gain.gain.setValueAtTime(0.03 + intensity * 0.05, t);
      gain.gain.exponentialRampToValueAtTime(0.001, t + 0.16);
      src.connect(bp).connect(gain).connect(ctx.destination);
      src.start(t);
      src.stop(t + 0.18);
    }

    playSpellFire(ctx) {
      if (!this.canTrigger('spell_fire', 65)) return;
      const t = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(310, t);
      osc.frequency.exponentialRampToValueAtTime(92, t + 0.16);
      gain.gain.setValueAtTime(0.09, t);
      gain.gain.exponentialRampToValueAtTime(0.001, t + 0.17);
      osc.connect(gain).connect(ctx.destination);
      osc.start(t);
      osc.stop(t + 0.18);
    }

    playBlackHole(ctx) {
      if (!this.canTrigger('blackhole', 180)) return;
      const t = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(84, t);
      osc.frequency.exponentialRampToValueAtTime(36, t + 0.55);
      gain.gain.setValueAtTime(0.18, t);
      gain.gain.exponentialRampToValueAtTime(0.001, t + 0.58);
      osc.connect(gain).connect(ctx.destination);
      osc.start(t);
      osc.stop(t + 0.6);
    }

    playPlasma(ctx) {
      if (!this.canTrigger('plasma', 75)) return;
      const t = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'square';
      osc.frequency.setValueAtTime(760 + Math.random() * 180, t);
      osc.frequency.exponentialRampToValueAtTime(380, t + 0.08);
      gain.gain.setValueAtTime(0.035, t);
      gain.gain.exponentialRampToValueAtTime(0.001, t + 0.09);
      osc.connect(gain).connect(ctx.destination);
      osc.start(t);
      osc.stop(t + 0.095);
    }

    playAcidSpray(ctx) {
      if (!this.canTrigger('acid_spray', 80)) return;
      const t = ctx.currentTime;
      const src = ctx.createBufferSource();
      src.buffer = this.noiseBuf;
      const bp = ctx.createBiquadFilter();
      bp.type = 'bandpass';
      bp.frequency.setValueAtTime(1400, t);
      bp.frequency.exponentialRampToValueAtTime(620, t + 0.14);
      bp.Q.value = 2.0;
      const gain = ctx.createGain();
      gain.gain.setValueAtTime(0.09, t);
      gain.gain.exponentialRampToValueAtTime(0.001, t + 0.15);
      src.connect(bp).connect(gain).connect(ctx.destination);
      src.start(t);
      src.stop(t + 0.16);
    }

    playTeleport(ctx) {
      if (!this.canTrigger('teleport', 80)) return;
      const t = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(540, t);
      osc.frequency.exponentialRampToValueAtTime(1680, t + 0.12);
      gain.gain.setValueAtTime(0.11, t);
      gain.gain.exponentialRampToValueAtTime(0.001, t + 0.15);
      osc.connect(gain).connect(ctx.destination);
      osc.start(t);
      osc.stop(t + 0.16);
    }

    playHurt(ctx) {
      if (!this.canTrigger('hurt', 160)) return;
      const t = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(190, t);
      osc.frequency.exponentialRampToValueAtTime(62, t + 0.16);
      gain.gain.setValueAtTime(0.14, t);
      gain.gain.exponentialRampToValueAtTime(0.001, t + 0.18);
      osc.connect(gain).connect(ctx.destination);
      osc.start(t);
      osc.stop(t + 0.19);
    }

    playEnemyDie(ctx) {
      if (!this.canTrigger('enemy_die', 60)) return;
      const t = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(280, t);
      osc.frequency.exponentialRampToValueAtTime(720, t + 0.11);
      gain.gain.setValueAtTime(0.12, t);
      gain.gain.exponentialRampToValueAtTime(0.001, t + 0.14);
      osc.connect(gain).connect(ctx.destination);
      osc.start(t);
      osc.stop(t + 0.15);
    }

    playNuke(ctx) {
      if (!this.canTrigger('nuke', 240)) return;
      const t = ctx.currentTime;
      // Massive sub-bass boom
      const osc = ctx.createOscillator();
      const oscGain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(92, t);
      osc.frequency.exponentialRampToValueAtTime(18, t + 1.05);
      oscGain.gain.setValueAtTime(0.38, t);
      oscGain.gain.exponentialRampToValueAtTime(0.001, t + 1.1);
      osc.connect(oscGain).connect(ctx.destination);
      osc.start(t);
      osc.stop(t + 1.15);

      // Long roaring blast wave
      const src = ctx.createBufferSource();
      src.buffer = this.noiseBuf;
      const lp = ctx.createBiquadFilter();
      lp.type = 'lowpass';
      lp.frequency.setValueAtTime(1400, t);
      lp.frequency.exponentialRampToValueAtTime(65, t + 1.1);
      const gain = ctx.createGain();
      gain.gain.setValueAtTime(0.32, t);
      gain.gain.exponentialRampToValueAtTime(0.001, t + 1.15);
      src.connect(lp).connect(gain).connect(ctx.destination);
      src.start(t);
      src.stop(t + 1.18);
    }

    playHeal(ctx) {
      if (!this.canTrigger('heal', 120)) return;
      const t = ctx.currentTime;
      const freqs = [523.25, 659.25, 783.99];
      freqs.forEach((f, idx) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(f, t + idx * 0.045);
        gain.gain.setValueAtTime(0.06, t + idx * 0.045);
        gain.gain.exponentialRampToValueAtTime(0.001, t + idx * 0.045 + 0.22);
        osc.connect(gain).connect(ctx.destination);
        osc.start(t + idx * 0.045);
        osc.stop(t + idx * 0.045 + 0.24);
      });
    }
  }

  return { SandAudioEngine };
});
