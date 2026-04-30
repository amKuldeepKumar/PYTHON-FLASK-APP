(function () {
  function getThemeVar(name, fallback) {
    const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return value || fallback;
  }

  function getNumberVar(name, fallback) {
    const value = parseFloat(getThemeVar(name, String(fallback)));
    return Number.isFinite(value) ? value : fallback;
  }

  function isEnabled() {
    return getThemeVar('--alphabet-background-enabled', '0') === '1';
  }

  function trailsEnabled() {
    return getThemeVar('--alphabet-trails-enabled', '1') === '1';
  }

  function outlineOnlyEnabled() {
    return getThemeVar('--alphabet-outline-only', '0') === '1';
  }

  function settings() {
    const themeMode = document.documentElement.getAttribute('data-theme') || 'dark';
    return {
      themeMode,
      speed: Math.max(0.30, Math.min(2.4, getNumberVar('--alphabet-speed', 90) / 100)),
      rotationDepth: Math.max(0.4, Math.min(2.4, getNumberVar('--alphabet-rotation-depth', 95) / 55)),
      minSize: Math.max(22, getNumberVar('--alphabet-min-size', 34)),
      maxSize: Math.max(42, getNumberVar('--alphabet-max-size', 96)),
      count: Math.max(8, Math.min(180, Math.round(getNumberVar('--alphabet-count', 52)))),
      motionMode: getThemeVar('--alphabet-motion-mode', 'float'),
      dx: getNumberVar('--alphabet-direction-x', 0) / 100,
      dy: getNumberVar('--alphabet-direction-y', 100) / 100,
      opacity: Math.max(0.1, Math.min(1, getNumberVar('--alphabet-opacity', 82) / 100)),
      trailLength: Math.max(4, Math.min(30, getNumberVar('--alphabet-trail-length', 16))),
      tiltXStrength: Math.max(4, Math.min(40, getNumberVar('--alphabet-tilt-x', 18))),
      tiltYStrength: Math.max(4, Math.min(30, getNumberVar('--alphabet-tilt-y', 12))),
      tiltZStrength: Math.max(0.05, Math.min(0.8, getNumberVar('--alphabet-tilt-z', getNumberVar('--alphabet-skew', 30)) / 100)),
      outlineOnly: outlineOnlyEnabled(),
      outlineColor: getThemeVar('--alphabet-outline-color', '#ffffff'),
      trails: trailsEnabled(),
    };
  }

  function boot() {
    const existing = document.querySelector('.alphabet-bg-canvas');
    if (existing) existing.remove();

    document.body.classList.remove('alphabet-bg-active');

    if (!isEnabled() || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      return;
    }

    const canvas = document.createElement('canvas');
    canvas.className = 'alphabet-bg-canvas';
    document.body.prepend(canvas);
    document.body.classList.add('alphabet-bg-active');

    const ctx = canvas.getContext('2d');
    const letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
    let opts = settings();
    let width = 0;
    let height = 0;
    let raf = null;
    const particles = [];

    function palette() {
      const styles = getComputedStyle(document.documentElement);
      return [
        styles.getPropertyValue('--primary').trim() || '#0d6efd',
        styles.getPropertyValue('--fluid-color-1').trim() || '#00b7ff',
        styles.getPropertyValue('--fluid-color-2').trim() || '#7c3aed',
        styles.getPropertyValue('--fluid-color-3').trim() || '#00f5d4',
        styles.getPropertyValue('--text').trim() || '#ffffff',
      ];
    }

    function rgba(color, alpha) {
      const c = (color || '').trim();

      if (c.startsWith('#')) {
        let hex = c.slice(1);
        if (hex.length === 3) hex = hex.split('').map((x) => x + x).join('');
        const num = parseInt(hex, 16);
        const r = (num >> 16) & 255;
        const g = (num >> 8) & 255;
        const b = num & 255;
        return `rgba(${r},${g},${b},${alpha})`;
      }

      if (c.startsWith('rgb(')) {
        return c.replace('rgb(', 'rgba(').replace(')', `,${alpha})`);
      }

      if (c.startsWith('rgba(')) {
        return c.replace(
          /rgba\(([^,]+),([^,]+),([^,]+),[^)]+\)/,
          `rgba($1,$2,$3,${alpha})`
        );
      }

      return c || `rgba(255,255,255,${alpha})`;
    }

    function seed() {
      particles.length = 0;
      const colors = palette();
      const shooting = opts.motionMode === 'shooting';

      for (let i = 0; i < opts.count; i += 1) {
        const z = Math.random();

        particles.push({
          x: shooting ? Math.random() * width * 1.2 : Math.random() * width,
          y: shooting ? Math.random() * height * 0.5 : Math.random() * height,
          z,
          size: opts.minSize + Math.random() * Math.max(4, opts.maxSize - opts.minSize),
          char: letters[Math.floor(Math.random() * letters.length)],
          color: colors[Math.floor(Math.random() * colors.length)],
          rotation: Math.random() * Math.PI * 2,
          rotationSpeed: (Math.random() - 0.5) * 0.03,
          drift: (Math.random() - 0.5) * 0.35,
          vx: shooting ? (2.8 + Math.random() * 2.6) : ((Math.random() - 0.5) * 0.6 + opts.dx),
          vy: shooting ? (1.2 + Math.random() * 1.8) : (0.22 + Math.random() * 0.55 + opts.dy),
          wobble: Math.random() * Math.PI * 2,
          wobbleSpeed: 0.004 + Math.random() * 0.016,
        });
      }
    }

    function resize() {
      width = window.innerWidth;
      height = window.innerHeight;

      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      seed();
    }

    function clearFrame() {
      if (opts.trails) {
        const fade = Math.max(0.04, 0.18 - opts.trailLength / 200);
        ctx.fillStyle = opts.themeMode === 'light'
          ? `rgba(255,255,255,${Math.max(0.02, fade * 0.8)})`
          : `rgba(8,12,20,${fade})`;
        ctx.fillRect(0, 0, width, height);
      } else {
        ctx.clearRect(0, 0, width, height);
      }
    }

    function recycle(p) {
      const shooting = opts.motionMode === 'shooting';
      p.x = shooting ? -80 : Math.random() * width;
      p.y = shooting ? Math.random() * height * 0.3 : -80;
      p.z = Math.random();
      p.size = opts.minSize + Math.random() * Math.max(4, opts.maxSize - opts.minSize);
    }

    function renderParticle(p) {
      const perspective = 0.5 + p.z * 1.2;
      const alpha = (0.08 + p.z * 0.42) * opts.opacity;
      const tiltX = Math.sin(p.wobble * 1.2) * opts.rotationDepth * opts.tiltXStrength;
      const tiltY = Math.cos(p.wobble) * opts.rotationDepth * opts.tiltYStrength;
      const skewTilt = Math.sin(p.rotation) * opts.tiltZStrength * opts.rotationDepth;
      const accentColor = opts.outlineOnly ? opts.outlineColor : p.color;

      if (opts.trails) {
        ctx.save();
        ctx.translate(
          p.x - tiltX * 0.30 - p.vx * opts.trailLength,
          p.y - tiltY * 0.20 - p.vy * opts.trailLength
        );
        ctx.rotate(p.rotation * 0.9);
        ctx.transform(1, 0, skewTilt * 0.65, 1, 0, 0);
        ctx.scale(perspective * 0.95, perspective * 0.95);
        ctx.font = `800 ${p.size}px var(--heading-font-family), sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        if (opts.outlineOnly) {
          ctx.strokeStyle = rgba(accentColor, 0.05 + p.z * 0.10);
          ctx.lineWidth = 1 + p.z * 0.8;
          ctx.strokeText(p.char, 0, 0);
        } else {
          ctx.fillStyle = rgba(accentColor, 0.05 + p.z * 0.10);
          ctx.fillText(p.char, 0, 0);
        }
        ctx.restore();
      }

      ctx.save();
      ctx.translate(p.x + tiltX, p.y + tiltY);
      ctx.transform(1, 0, skewTilt, 1, 0, 0);
      ctx.rotate(p.rotation);
      ctx.scale(perspective, perspective);
      ctx.font = `800 ${p.size}px var(--heading-font-family), sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.shadowBlur = 18 + p.z * 30 + opts.rotationDepth * 8;
      ctx.shadowColor = rgba(accentColor, 0.70);
      ctx.globalAlpha = alpha;
      ctx.strokeStyle = rgba(opts.outlineColor, 0.26 + p.z * 0.42);
      ctx.lineWidth = opts.outlineOnly ? (1.4 + p.z * 1.8) : 1.2;
      ctx.fillStyle = rgba(p.color, 0.90);
      ctx.strokeText(p.char, 0, 0);
      if (!opts.outlineOnly) {
        ctx.fillText(p.char, 0, 0);
      }
      ctx.restore();
    }

    function render() {
      clearFrame();

      for (const p of particles) {
        p.wobble += p.wobbleSpeed * opts.speed;

        if (opts.motionMode === 'diagonal') {
          p.x += (0.8 + p.z + opts.dx) * opts.speed;
          p.y += (0.5 + p.z + opts.dy) * opts.speed;
        } else if (opts.motionMode === 'drift') {
          p.x += (p.drift + Math.sin(p.wobble) * 0.35 + opts.dx) * (0.6 + p.z) * opts.speed;
          p.y += (0.2 + p.z + opts.dy) * opts.speed;
        } else if (opts.motionMode === 'shooting') {
          p.x += p.vx * opts.speed * 2.2;
          p.y += p.vy * opts.speed * 1.8;
        } else {
          p.x += (p.drift + opts.dx * 0.5) * (0.7 + p.z) * opts.speed;
          p.y += (p.vy * 0.6 + opts.dy) * (0.45 + p.z) * opts.speed;
        }

        p.rotation += p.rotationSpeed * (0.7 + opts.rotationDepth) * opts.speed;

        if (p.y > height + 120 || p.x > width + 140 || p.x < -140) {
          recycle(p);
        }

        renderParticle(p);
      }

      raf = window.requestAnimationFrame(render);
    }

    resize();
    render();

    let resizeTimer = null;

    window.addEventListener('resize', function () {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(function () {
        opts = settings();
        resize();
      }, 120);
    });

    const observer = new MutationObserver(function () {
      const next = settings();
      if (next.themeMode !== opts.themeMode) {
        opts = next;
        seed();
        return;
      }
      opts = next;
    });

    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme'],
    });

    document.addEventListener('visibilitychange', function () {
      if (document.hidden && raf) {
        cancelAnimationFrame(raf);
        raf = null;
      } else if (!document.hidden && !raf && document.body.contains(canvas)) {
        opts = settings();
        render();
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
