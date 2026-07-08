/**
 * ASCII Hero Animation for proteinpriser.se
 * Renders "PPK" with ASCII particle characters on canvas.
 * Mouse-reactive on desktop, static glow on mobile.
 */
(function () {
    'use strict';

    const CHARS = '@#$%&WMBNOQRSXZAHKDPGFELIJTYUVCwmb8690oahkdpqe*+=-:·.'.split('');
    const AMBER = { r: 232, g: 146, b: 47 };
    const AMBER_DIM = { r: 180, g: 100, b: 30 };
    const FONT_SIZE = 10;
    const LETTER_SPACING = 0.15; // relative to text width

    let canvas, ctx, particles = [], mouse = { x: -9999, y: -9999 }, animId;
    let canvasW, canvasH, textImageData;
    let isMobile = false;
    let lastTime = 0;
    const TARGET_FPS = 30;
    const FRAME_INTERVAL = 1000 / TARGET_FPS;

    function init() {
        canvas = document.getElementById('ascii-hero-canvas');
        if (!canvas) return;

        isMobile = window.innerWidth <= 768;

        if (isMobile) {
            // On mobile, don't run canvas animation — CSS handles the fallback
            canvas.style.display = 'none';
            return;
        }

        ctx = canvas.getContext('2d', { alpha: true });
        resize();

        canvas.addEventListener('mousemove', (e) => {
            const rect = canvas.getBoundingClientRect();
            mouse.x = e.clientX - rect.left;
            mouse.y = e.clientY - rect.top;
        });
        canvas.addEventListener('mouseleave', () => {
            mouse.x = -9999;
            mouse.y = -9999;
        });

        window.addEventListener('resize', debounce(() => {
            isMobile = window.innerWidth <= 768;
            if (isMobile) {
                canvas.style.display = 'none';
                if (animId) cancelAnimationFrame(animId);
                return;
            }
            canvas.style.display = '';
            resize();
        }, 250));

        createParticles();
        animate(0);
    }

    function debounce(fn, ms) {
        let timer;
        return function (...args) {
            clearTimeout(timer);
            timer = setTimeout(() => fn.apply(this, args), ms);
        };
    }

    function resize() {
        const wrapper = document.getElementById('ascii-hero-wrapper');
        if (!wrapper) return;
        const w = wrapper.clientWidth;
        const h = wrapper.clientHeight || 180;
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        canvas.width = w * dpr;
        canvas.height = h * dpr;
        canvas.style.width = w + 'px';
        canvas.style.height = h + 'px';
        ctx.scale(dpr, dpr);
        canvasW = w;
        canvasH = h;
        createParticles();
    }

    function getTextPixels(text, fontSize, maxW, maxH) {
        // Create offscreen canvas to render text and sample pixels
        const off = document.createElement('canvas');
        off.width = maxW;
        off.height = maxH;
        const offCtx = off.getContext('2d');

        offCtx.fillStyle = '#000';
        offCtx.fillRect(0, 0, maxW, maxH);

        // Compute font size to fit nicely
        let fSize = fontSize;
        offCtx.font = `900 ${fSize}px 'JetBrains Mono', 'Courier New', monospace`;
        let metrics = offCtx.measureText(text);
        // Scale up to fill about 70% of width
        const targetW = maxW * 0.65;
        fSize = Math.floor(fSize * (targetW / metrics.width));
        fSize = Math.min(fSize, maxH * 0.85); // Don't exceed height
        offCtx.font = `900 ${fSize}px 'JetBrains Mono', 'Courier New', monospace`;
        metrics = offCtx.measureText(text);

        const textW = metrics.width;
        const x = (maxW - textW) / 2;
        const y = maxH * 0.72; // baseline

        offCtx.fillStyle = '#fff';
        offCtx.fillText(text, x, y);

        return offCtx.getImageData(0, 0, maxW, maxH);
    }

    function createParticles() {
        particles = [];
        if (!canvasW || !canvasH) return;

        textImageData = getTextPixels('PPK', 100, canvasW, canvasH);
        const data = textImageData.data;
        const gap = FONT_SIZE; // spacing between particles

        for (let y = 0; y < canvasH; y += gap) {
            for (let x = 0; x < canvasW; x += gap) {
                const i = (y * canvasW + x) * 4;
                if (data[i] > 128) { // white pixel = part of text
                    const brightness = data[i] / 255;
                    particles.push({
                        x: x,
                        y: y,
                        originX: x,
                        originY: y,
                        char: CHARS[Math.floor(Math.random() * CHARS.length)],
                        size: FONT_SIZE * (0.7 + brightness * 0.3),
                        brightness: brightness,
                        vx: 0,
                        vy: 0,
                        friction: 0.85 + Math.random() * 0.1,
                        springBack: 0.03 + Math.random() * 0.02,
                        charTimer: Math.random() * 200,
                        opacity: 0, // Start invisible for entrance animation
                        targetOpacity: 0.5 + brightness * 0.5,
                    });
                }
            }
        }

        // Scatter particles initially for entrance animation
        particles.forEach(p => {
            p.x = p.originX + (Math.random() - 0.5) * canvasW * 0.8;
            p.y = p.originY + (Math.random() - 0.5) * canvasH * 1.5;
        });
    }

    function animate(timestamp) {
        animId = requestAnimationFrame(animate);

        if (timestamp - lastTime < FRAME_INTERVAL) return;
        lastTime = timestamp;

        ctx.clearRect(0, 0, canvasW, canvasH);

        const mouseRadius = 80;
        const mouseForce = 8;

        for (let i = 0; i < particles.length; i++) {
            const p = particles[i];

            // Mouse repulsion
            const dx = p.x - mouse.x;
            const dy = p.y - mouse.y;
            const dist = Math.sqrt(dx * dx + dy * dy);

            if (dist < mouseRadius && dist > 0) {
                const force = (mouseRadius - dist) / mouseRadius;
                p.vx += (dx / dist) * force * mouseForce;
                p.vy += (dy / dist) * force * mouseForce;
            }

            // Spring back to origin
            p.vx += (p.originX - p.x) * p.springBack;
            p.vy += (p.originY - p.y) * p.springBack;

            // Apply friction
            p.vx *= p.friction;
            p.vy *= p.friction;

            // Update position
            p.x += p.vx;
            p.y += p.vy;

            // Fade in
            if (p.opacity < p.targetOpacity) {
                p.opacity = Math.min(p.targetOpacity, p.opacity + 0.015);
            }

            // Cycle characters occasionally
            p.charTimer--;
            if (p.charTimer <= 0) {
                p.char = CHARS[Math.floor(Math.random() * CHARS.length)];
                p.charTimer = 100 + Math.random() * 300;
            }

            // Calculate distance from origin for color shift
            const distFromOrigin = Math.sqrt(
                (p.x - p.originX) ** 2 + (p.y - p.originY) ** 2
            );
            const colorMix = Math.min(distFromOrigin / 60, 1);
            const r = Math.floor(AMBER.r + (AMBER_DIM.r - AMBER.r) * colorMix);
            const g = Math.floor(AMBER.g + (AMBER_DIM.g - AMBER.g) * colorMix);
            const b = Math.floor(AMBER.b + (AMBER_DIM.b - AMBER.b) * colorMix);

            // Subtle breathing animation
            const breathe = Math.sin(timestamp * 0.001 + i * 0.1) * 0.08;
            const finalOpacity = Math.max(0, Math.min(1, p.opacity + breathe));

            ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${finalOpacity})`;
            ctx.font = `${p.size}px 'JetBrains Mono', monospace`;
            ctx.fillText(p.char, p.x, p.y);
        }
    }

    // Wait for fonts to load, then init
    if (document.fonts && document.fonts.ready) {
        document.fonts.ready.then(() => {
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', init);
            } else {
                init();
            }
        });
    } else {
        document.addEventListener('DOMContentLoaded', init);
    }
})();
