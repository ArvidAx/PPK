let allProducts = [];

const recipesData = {
    chicken_pasta: {
        title: "Krämig Kycklingpasta",
        category: "middag",
        time: "20 min",
        badgeClass: "middag",
        badgeName: "Middag",
        protein: 45,
        calories: 650,
        fat: 15,
        carbs: 75,
        cost: 18,
        image: "img_chicken_pasta.png",
        desc: "Snabb vardagsrätt med kycklingfilé, kvarg och riven parmesan. Enkel, mättande och budgetvänlig.",
        ingredientsList: [
            { name: "Kycklingfilé", amount: "150 g", search: "kyckling", defaultWeight: 150 },
            { name: "Pasta (t.ex. Penne)", amount: "80 g", search: "pasta", defaultWeight: 80 },
            { name: "Kvarg (naturell)", amount: "75 g", search: "kvarg", defaultWeight: 75 },
            { name: "Riven ost / Parmesan", amount: "15 g", search: "ost", defaultWeight: 15 }
        ],
        instructions: [
            "Koka pastan i saltat vatten enligt anvisningarna på förpackningen.",
            "Skär kycklingfilén i tärningar och stek i lite olja till fin färg. Salta och krydda efter smak.",
            "Sänk värmen och blanda ner kvargen och den kokta pastan. Rör om på svag värme så kvargen blir krämig (låt ej koka för mycket då kan kvargen skära sig). Späd med lite pastavatten vid behov.",
            "Servera direkt och toppa med riven ost."
        ]
    },
    overnight_oats: {
        title: "Overnight Oats med Kvarg",
        category: "frukost",
        time: "5 min + natt",
        badgeClass: "frukost",
        badgeName: "Frukost",
        protein: 30,
        calories: 420,
        fat: 6,
        carbs: 55,
        cost: 8,
        image: "img_overnight_oats.png",
        desc: "Förbered kvällen innan. Havregryn, kvarg och bär ger en proteinrik start på dagen utan att ta en minut av morgonen.",
        ingredientsList: [
            { name: "Havregryn", amount: "50 g", search: "havregryn", defaultWeight: 50 },
            { name: "Kvarg (naturell)", amount: "150 g", search: "kvarg", defaultWeight: 150 },
            { name: "Mjölk eller Havredryck", amount: "100 ml", search: "mjölk", defaultWeight: 100 }
        ],
        instructions: [
            "Mät upp havregryn, kvarg och valfri mjölk/havredryck i en glasburk eller skål.",
            "Rör om ordentligt så att kvargen löses upp helt i vätskan.",
            "Förslut burken/täck skålen och ställ i kylskåpet över natten.",
            "Toppa på morgonen med lite bär eller kanel och ät kall direkt ur burken."
        ]
    },
    lentil_halloumi: {
        title: "Linsgryta med Halloumi",
        category: "lunch",
        time: "25 min",
        badgeClass: "lunch",
        badgeName: "Lunch",
        protein: 38,
        calories: 580,
        fat: 22,
        carbs: 50,
        cost: 14,
        image: "img_lentil_halloumi.png",
        desc: "En mustig och värmande gryta med röda linser, krossade tomater och gyllenstekt halloumi. Vegetarisk favorit.",
        ingredientsList: [
            { name: "Röda linser (torkade)", amount: "80 g", search: "linser", defaultWeight: 80 },
            { name: "Krossade tomater", amount: "200 g", search: "tomat", defaultWeight: 200 },
            { name: "Grillost eller Halloumi", amount: "80 g", search: "grillost", defaultWeight: 80 }
        ],
        instructions: [
            "Skölj linserna i kallt vatten.",
            "Koka linserna tillsammans med krossade tomater och lite vatten eller grönsaksbuljong under lock i ca 15 minuter.",
            "Skär grillosten/halloumin i små kuber och stek i en torr stekpanna på medelhög värme tills bitarna är gyllenbruna.",
            "Rör ner osten i linsgrytan och låt allt bli varmt. Krydda med spiskummin, paprika och lite salt."
        ]
    }
};

// DOM Elements
const recipeModal = document.getElementById('recipeModal');
const closeRecipeModalBtn = document.getElementById('closeRecipeModalBtn');
const recipeModalBody = document.getElementById('recipeModalBody');

// Safe escaping helper
function esc(str) {
    if (str == null) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

// Init
async function init() {
    try {
        const response = await fetch('data.json');
        if (!response.ok) throw new Error('Kunde inte hämta data.json');
        allProducts = await response.json();
    } catch (e) {
        console.error("Kunde ej ladda produktdata för ingrediensmatchning:", e);
    }
    setupRecipeEvents();
}

function setupRecipeEvents() {
    // Click recipe card to open modal
    document.querySelectorAll('.recipe-card').forEach(card => {
        card.addEventListener('click', () => {
            const recipeId = card.id;
            if (recipeId && recipesData[recipeId]) {
                openRecipeModal(recipeId);
            }
        });
    });

    // Close modal triggers
    closeRecipeModalBtn.addEventListener('click', closeRecipeModal);
    window.addEventListener('click', e => {
        if (e.target === recipeModal) closeRecipeModal();
    });
    window.addEventListener('keydown', e => {
        if (e.key === 'Escape') closeRecipeModal();
    });

    // Tab filter logic
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const filter = btn.dataset.filter;
            document.querySelectorAll('.recipe-card').forEach(card => {
                card.style.display = (filter === 'alla' || card.dataset.cat === filter) ? '' : 'none';
            });
        });
    });
}

function closeRecipeModal() {
    recipeModal.classList.remove('show');
    recipeModal.setAttribute('aria-hidden', 'true');
}

// Substring matching to find the cheapest product containing key string, sorted by PPK (highest first)
function findCheapestProduct(searchKeyword) {
    if (!allProducts || allProducts.length === 0) return null;
    const kw = searchKeyword.toLowerCase();
    
    // Exact or partial name match
    let matches = allProducts.filter(p => {
        const name = (p.name || '').toLowerCase();
        const brand = (p.brand || '').toLowerCase();
        return name.includes(kw) || brand.includes(kw);
    });

    // Fallback search: broaden keyword if nothing matched
    if (matches.length === 0) {
        matches = allProducts.filter(p => {
            const category = (p.category || '').toLowerCase();
            return category.includes(kw);
        });
    }

    if (matches.length === 0) return null;

    // Filter only those with valid protein per krona
    const validMatches = matches.filter(p => p.protein_per_krona != null && p.protein_per_krona > 0);
    const pool = validMatches.length > 0 ? validMatches : matches;

    // Sort by PPK descending (highest g/kr first)
    pool.sort((a, b) => (b.protein_per_krona || 0) - (a.protein_per_krona || 0));

    return pool[0];
}

function openRecipeModal(recipeId) {
    const recipe = recipesData[recipeId];
    if (!recipe) return;

    // Match cheapest ingredients
    const matchedProducts = [];
    recipe.ingredientsList.forEach(ing => {
        const match = findCheapestProduct(ing.search);
        if (match) {
            matchedProducts.push(match);
        }
    });

    // Populate modal body
    recipeModalBody.innerHTML = `
        <div class="modal-header" style="margin-bottom: 1rem;">
            <h2 class="modal-title">${esc(recipe.title)}</h2>
            <div class="modal-subtitle">
                ⏱ ${esc(recipe.time)} &nbsp;|&nbsp; 
                <span class="store-badge" style="background:#fee2e2; color:#e11d48;">${esc(recipe.badgeName)}</span>
            </div>
        </div>

        <div class="recipe-modal-grid">
            <div>
                <h3 class="modal-section-title">Ingredienser</h3>
                <ul class="recipe-ingredients-list">
                    ${recipe.ingredientsList.map(ing => `
                        <li><span>${esc(ing.name)}</span><strong>${esc(ing.amount)}</strong></li>
                    `).join('')}
                </ul>

                <h3 class="modal-section-title">Näringsvärden (per portion)</h3>
                <div class="modal-stats" style="margin-bottom: 1.5rem;">
                    <div class="modal-stat-card" style="padding: 0.5rem 0.75rem;">
                        <span class="modal-stat-label">💪 Protein</span>
                        <span class="modal-stat-value highlight" style="font-size: 1rem;">${recipe.protein} g</span>
                    </div>
                    <div class="modal-stat-card" style="padding: 0.5rem 0.75rem;">
                        <span class="modal-stat-label">🔥 Kalorier</span>
                        <span class="modal-stat-value highlight-red" style="font-size: 1rem;">${recipe.calories} kcal</span>
                    </div>
                    <div class="modal-stat-card" style="padding: 0.5rem 0.75rem;">
                        <span class="modal-stat-label">🌾 Kolhydrater / 🥑 Fett</span>
                        <span class="modal-stat-value" style="font-size: 0.95rem; font-weight: 700;">${recipe.carbs}g / ${recipe.fat}g</span>
                    </div>
                </div>
            </div>

            <div>
                <div class="recipe-matched-items">
                    <div class="recipe-matched-title">🏪 Billigaste varor i din butik</div>
                    <ul class="recipe-matched-list">
                        ${matchedProducts.map(p => {
                            const storeClass = (p.store || '').toLowerCase() === 'willys' ? 'willys' : 'hemkop';
                            return `
                                <li class="recipe-matched-item">
                                    <div style="display:flex; flex-direction:column; max-width: 65%;">
                                        <span class="recipe-matched-name" title="${esc(p.name)}">${esc(p.name)}</span>
                                        <span class="recipe-matched-meta">${esc(p.brand)} | <span class="store-badge ${storeClass}" style="padding: 0.05rem 0.35rem; font-size: 0.65rem;">${esc(p.store)}</span></span>
                                    </div>
                                    <span class="recipe-matched-price">${p.price_sek.toFixed(2)} kr</span>
                                </li>
                            `;
                        }).join('')}
                        ${matchedProducts.length === 0 ? `
                            <div class="recipe-matched-none">Kunde ej läsa in billigaste produkter just nu.</div>
                        ` : ''}
                    </ul>
                </div>

                <button class="btn-recipe-buy" id="btnRecipeBuy">🛒 Lägg till ingredienser i varukorg</button>
            </div>
        </div>

        <h3 class="modal-section-title">Gör så här</h3>
        <ol class="recipe-steps">
            ${recipe.instructions.map(step => `
                <li>${esc(step)}</li>
            `).join('')}
        </ol>

        <div class="modal-footer" style="padding-top: 1rem; border-top: 1px solid var(--border-color);">
            <button class="btn btn-secondary" id="closeRecipeModalFooterBtn">Stäng</button>
        </div>
    `;

    // Add to cart click event
    document.getElementById('btnRecipeBuy').onclick = (e) => {
        matchedProducts.forEach(product => {
            addToCart(product);
        });

        // Toggle button styling for feedback
        const btn = e.target;
        btn.classList.add('success');
        btn.textContent = 'Tillagda i shoppinglistan! ✓';
        btn.disabled = true;

        setTimeout(() => {
            btn.classList.remove('success');
            btn.textContent = '🛒 Lägg till ingredienser i varukorg';
            btn.disabled = false;
        }, 3000);
    };

    document.getElementById('closeRecipeModalFooterBtn').onclick = closeRecipeModal;

    recipeModal.classList.add('show');
    recipeModal.setAttribute('aria-hidden', 'false');
    
    // Animate progress bars width after modal opens
    setTimeout(() => {
        const fills = modalBody.querySelectorAll('.macro-bar-fill');
        fills.forEach(fill => {
            const width = fill.style.width;
            fill.style.width = '0';
            setTimeout(() => {
                fill.style.width = width;
            }, 50);
        });
    }, 100);
}

// Cart integration with localStorage
function addToCart(product) {
    let cart = [];
    try {
        const saved = localStorage.getItem('ppk_shopping_list');
        cart = saved ? JSON.parse(saved) : [];
    } catch (e) {
        cart = [];
    }

    const existing = cart.find(x => x.code === product.code && x.store === product.store);
    if (existing) {
        existing.qty = (existing.qty || 1) + 1;
    } else {
        cart.push({
            code: product.code,
            name: product.name,
            brand: product.brand,
            store: product.store,
            price_sek: product.price_sek,
            protein_per_100g: product.protein_per_100g,
            package_weight_g: product.package_weight_g || 0,
            url: product.url || '',
            qty: 1
        });
    }

    localStorage.setItem('ppk_shopping_list', JSON.stringify(cart));
}

init();
