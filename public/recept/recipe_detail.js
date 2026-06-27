document.addEventListener("DOMContentLoaded", async () => {
    // =========================================
    // Hamburger menu — hardened version
    // (app.js also runs on these pages and calls initHamburgerMenu;
    // dataset.initialized guard prevents double-binding if load order varies)
    // =========================================
    const hamburger = document.querySelector('.hamburger-menu');
    const navLinks = document.querySelector('.nav-links');
    if (hamburger && navLinks && !hamburger.dataset.initialized) {
        hamburger.dataset.initialized = 'true';
        hamburger.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = navLinks.classList.toggle('active');
            hamburger.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
            hamburger.textContent = isOpen ? '\u2715' : '\u2630';
        });
        document.addEventListener('click', (e) => {
            if (!navLinks.contains(e.target) && !hamburger.contains(e.target)) {
                navLinks.classList.remove('active');
                hamburger.setAttribute('aria-expanded', 'false');
                hamburger.textContent = '\u2630';
            }
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && navLinks.classList.contains('active')) {
                navLinks.classList.remove('active');
                hamburger.setAttribute('aria-expanded', 'false');
                hamburger.textContent = '\u2630';
            }
        });
    }

    // =========================================
    // Live price matching from data.json
    // =========================================
    const container = document.getElementById("cheapest-ingredients");
    if (!container) return;

    // Sanitize keywords from data-attribute (XSS guard)
    let keywords = [];
    try {
        const raw = JSON.parse(container.getAttribute("data-keywords") || "[]");
        if (Array.isArray(raw)) {
            keywords = raw
                .map(k => String(k).toLowerCase().trim().replace(/[^\w\s\u00c5\u00c4\u00d6\u00e5\u00e4\u00f6\-]/g, ''))
                .filter(k => k.length > 0 && k.length < 50);
        }
    } catch (e) {
        console.warn("Invalid data-keywords attribute:", e);
        return;
    }

    if (keywords.length === 0) return;

    // XSS escape helper
    const esc = (str) => {
        if (str == null) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    };

    try {
        const response = await fetch("../data.json");
        if (!response.ok) throw new Error(`HTTP ${response.status}: Kunde inte h\u00e4mta data.json`);
        const allProducts = await response.json();
        if (!Array.isArray(allProducts) || allProducts.length === 0) throw new Error("Tom produktlista");

        const findCheapestProduct = (searchKeyword) => {
            const kw = searchKeyword.toLowerCase().trim();
            if (!kw) return null;

            let matches = allProducts.filter(p => {
                const name = (p.name || '').toLowerCase();
                const brand = (p.brand || '').toLowerCase();
                return name.includes(kw) || brand.includes(kw);
            });

            if (matches.length === 0) {
                matches = allProducts.filter(p => {
                    const category = (p.category || '').toLowerCase();
                    return category.includes(kw);
                });
            }

            if (matches.length === 0) return null;

            const validMatches = matches.filter(p => p.protein_per_krona != null && p.protein_per_krona > 0);
            const pool = validMatches.length > 0 ? validMatches : matches;
            pool.sort((a, b) => (b.protein_per_krona || 0) - (a.protein_per_krona || 0));

            return pool[0];
        };

        const matchedProducts = [];
        keywords.forEach(kw => {
            const match = findCheapestProduct(kw);
            if (match) matchedProducts.push(match);
        });

        if (matchedProducts.length === 0) {
            container.innerHTML = `<div class="recipe-matched-none" style="font-size: 0.85rem; color: var(--text-muted);">Inga matchade produkter hittades just nu.</div>`;
            return;
        }

        container.innerHTML = `
            <ul class="recipe-matched-list" style="list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 0.75rem;">
                ${matchedProducts.map(p => {
                    const storeClass = (p.store || '').toLowerCase() === 'willys' ? 'willys' : 'hemkop';
                    const storeColor = storeClass === 'willys' ? '#0284c7' : '#e11d48';
                    const storeBg = storeClass === 'willys' ? '#e0f2fe' : '#fee2e2';
                    const price = (p.price_sek != null && !isNaN(p.price_sek)) ? Number(p.price_sek).toFixed(2) : '\u2013';
                    return `
                        <li class="recipe-matched-item" style="display: flex; justify-content: space-between; align-items: center; padding: 0.75rem; background: var(--bg-color); border: 1px solid var(--border-color); border-radius: var(--radius-md);">
                            <div style="display: flex; flex-direction: column; max-width: 65%;">
                                <span class="recipe-matched-name" style="font-weight: 600; font-size: 0.9rem; color: var(--text-main); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${esc(p.name)}">${esc(p.name)}</span>
                                <span class="recipe-matched-meta" style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.15rem;">
                                    ${esc(p.brand)} |
                                    <span class="store-badge ${storeClass}" style="padding: 0.1rem 0.4rem; font-size: 0.65rem; font-weight: 700; border-radius: 4px; background: ${storeBg}; color: ${storeColor};">${esc(p.store)}</span>
                                </span>
                            </div>
                            <span class="recipe-matched-price" style="font-weight: 700; font-size: 0.95rem; color: var(--text-main);">${price} kr</span>
                        </li>
                    `;
                }).join('')}
            </ul>
        `;
    } catch (e) {
        console.error("recipe_detail.js error:", e);
        container.innerHTML = `<div class="recipe-matched-none" style="font-size: 0.85rem; color: var(--accent-red);">Kunde inte h\u00e4mta live-priser just nu. F\u00f6rs\u00f6k igen senare.</div>`;
    }
});

