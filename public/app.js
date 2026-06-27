let allData = [];
let filteredData = [];
let sortCol = 'ppk';
let sortDesc = true;
let shoppingList = [];
let activeBasket = null;
let currentLimit = 20;
let clickCount = 0;

const BASKETS = {
    studentpaketet: {
        title: "Studentpaketet - Maxat protein för under 200 kr/vecka",
        emoji: "🎓",
        description: "De 5 absolut billigaste basvarorna i Sverige för dig som vill bygga muskler på en CSN-budget.",
        filter_criteria: {
            max_price: 40,
            min_ppk: 10.0,
            keywords: ["Vetemjöl", "Gula ärter", "Havregryn", "Linser", "Jordnötter"]
        }
    },
    clean_bulking: {
        title: "Clean Bulking-paketet - Högoktanigt protein utan fettet",
        emoji: "💪",
        description: "För dig som vill lägga på dig ren muskelmassa. Maxat med protein, minimalt med kalorier från fett och socker.",
        filter_criteria: {
            min_protein_100g: 10.0,
            max_price: 150,
            keywords: ["Kycklingfilé", "Kvarg", "Torsk", "Nötfärs 5%", "Tofu"]
        }
    }
};

// DOM Elements
const tableBody = document.getElementById('tableBody');
let selectedCategories = [];
const storeSelect = document.getElementById('store');
const searchInput = document.getElementById('search');
const maxPriceInput = document.getElementById('maxPrice');
const maxPriceLabel = document.getElementById('maxPriceLabel');
const minProteinInput = document.getElementById('minProtein');
const minProteinLabel = document.getElementById('minProteinLabel');
const totalProductsEl = document.getElementById('totalProducts');
const bestPPKEl = document.getElementById('bestPPK');
const resultCountEl = document.getElementById('resultCount');
const tableHeaders = document.querySelectorAll('th[data-sort]');

// Shopping List Elements
const shoppingListEl = document.getElementById('shoppingList');
const shoppingListEmptyEl = document.getElementById('shoppingListEmpty');
const shoppingListSummaryEl = document.getElementById('shoppingListSummary');
const summaryCountEl = document.getElementById('summaryCount');
const summaryPriceEl = document.getElementById('summaryPrice');
const summaryProteinEl = document.getElementById('summaryProtein');
const summaryPPKEl = document.getElementById('summaryPPK');
const clearListBtn = document.getElementById('clearListBtn');

// Modal Elements
const productModal = document.getElementById('productModal');
const closeModalBtn = document.getElementById('closeModalBtn');
const modalBody = document.getElementById('modalBody');

// Safe text helper — prevents XSS from scraped product names/brands
function esc(str) {
    if (str == null) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

// Safe URL validator — only allow http/https to prevent javascript: XSS
function safeUrl(url, fallback) {
    if (url && (url.startsWith('https://') || url.startsWith('http://'))) {
        return url;
    }
    return fallback || '#';
}

// Safe number formatting — handles null/undefined without crashing
function fmt(val, decimals = 1, suffix = '') {
    if (val == null || isNaN(val)) return '–';
    return Number(val).toFixed(decimals) + suffix;
}

function setFiltersEnabled(enabled) {
    const inputs = [searchInput, storeSelect, maxPriceInput, minProteinInput];
    inputs.forEach(input => {
        if (input) input.disabled = !enabled;
    });

    document.querySelectorAll('.basket-btn, .quick-search-btn').forEach(btn => {
        btn.disabled = !enabled;
        btn.style.opacity = enabled ? '1' : '0.6';
        btn.style.cursor = enabled ? 'pointer' : 'not-allowed';
    });

    const categoryBtn = document.getElementById('categorySelectBtn');
    if (categoryBtn) {
        categoryBtn.disabled = !enabled;
        categoryBtn.style.opacity = enabled ? '1' : '0.6';
        categoryBtn.style.cursor = enabled ? 'pointer' : 'not-allowed';
    }
}

// Init
async function init() {
    try {
        // Setup event listeners, load existing shopping list and dynamic values immediately (non-blocking)
        setupEventListeners();
        loadShoppingList();
        updateDynamicPPK();
        setFiltersEnabled(false);

        // Show a loading indicator in the table body
        if (tableBody) {
            tableBody.innerHTML = `<tr><td colspan="10" style="text-align:center; padding: 4rem 2rem; color: var(--text-muted);">
                <div class="loading-spinner"></div>
                <div style="font-weight: 600; font-size: 1.05rem; margin-top: 0.5rem;">Laddar över 12 000 produkter...</div>
                <div style="font-size: 0.85rem; margin-top: 0.25rem;">Hämtar färska proteindata från Hemköp och Willys</div>
            </td></tr>`;
        }

        // Fetch and display last updated time (non-blocking, async background check)
        fetch('last_updated.json')
            .then(res => {
                if (!res.ok) throw new Error();
                return res.json();
            })
            .then(data => {
                if (data && data.updated_at) {
                    const date = new Date(data.updated_at);
                    const formatted = date.toLocaleString('sv-SE', {
                        timeZone: 'Europe/Stockholm',
                        year: 'numeric',
                        month: '2-digit',
                        day: '2-digit',
                        hour: '2-digit',
                        minute: '2-digit'
                    });
                    const lastUpdatedEl = document.getElementById('lastUpdated');
                    if (lastUpdatedEl) lastUpdatedEl.textContent = `Priserna uppdaterades: ${formatted}`;
                    const lastUpdatedTimeEl = document.getElementById('lastUpdatedTime');
                    if (lastUpdatedTimeEl) lastUpdatedTimeEl.textContent = `Senaste uppdatering: ${formatted}`;
                }
            })
            .catch(() => {
                const lastUpdatedEl = document.getElementById('lastUpdated');
                if (lastUpdatedEl) lastUpdatedEl.textContent = '';
            });

        // Fetch and load products database in the background without blocking main UI thread
        const response = await fetch('data.json');
        if (!response.ok) throw new Error('Kunde inte hämta data.json');
        const rawData = await response.json();

        allData = rawData.map(item => {
            const protein = item.protein_per_100g || 0;
            const calories = item.calories_per_100g || 0;
            return {
                ...item,
                ppk: item.protein_per_krona || 0,
                ppkcal: calories > 0 ? (protein / calories) * 100 : 0
            };
        }).filter(item => item.price_sek != null && item.protein_per_100g != null);

        // Populate filters, re-render shopping list (to resolve store comparisons), enable filters and show data
        populateCategories();
        renderShoppingList();
        setFiltersEnabled(true);
        
        // Check for url param to pre-select basket
        const urlParams = new URLSearchParams(window.location.search);
        const basketParam = urlParams.get('basket');
        if (basketParam && BASKETS[basketParam]) {
            selectBasket(basketParam);
        } else {
            applyFilters(true);
        }
    } catch (error) {
        console.error(error);
        if (tableBody) {
            tableBody.innerHTML = `<tr><td colspan="10" style="text-align:center; padding: 2rem; color:#e11d48; font-weight:600;">
                Kunde inte ladda produktdata. Kör skrapan och försök igen.
            </td></tr>`;
        }
    }
}

function updateCategorySelectBtnText() {
    const btn = document.getElementById('categorySelectBtn');
    if (!btn) return;
    if (selectedCategories.length === 0) {
        btn.textContent = 'Alla kategorier';
    } else if (selectedCategories.length === 1) {
        const slugToName = {
            'kott-fagel-och-chark': 'Kött, fågel & chark',
            'frukt-och-gront': 'Frukt & grönt',
            'mejeri-ost-och-agg': 'Mejeri, ost & ägg',
            'skafferi': 'Skafferiet',
            'fryst': 'Fryst',
            'brod-och-kakor': 'Bröd & kakor',
            'fisk-och-skaldjur': 'Fisk & skaldjur',
            'vegetariskt': 'Vegetariskt',
            'fardigmat': 'Färdigmat',
            'delikatessen': 'Delikatessen',
            'godis-snacks-och-glass': 'Godis, snacks & glass',
        };
        btn.textContent = slugToName[selectedCategories[0]] || selectedCategories[0];
    } else {
        btn.textContent = `${selectedCategories.length} valda`;
    }
}

function populateCategories() {
    const slugToName = {
        'kott-fagel-och-chark': 'Kött, fågel & chark',
        'frukt-och-gront': 'Frukt & grönt',
        'mejeri-ost-och-agg': 'Mejeri, ost & ägg',
        'skafferi': 'Skafferiet',
        'fryst': 'Fryst',
        'brod-och-kakor': 'Bröd & kakor',
        'fisk-och-skaldjur': 'Fisk & skaldjur',
        'vegetariskt': 'Vegetariskt',
        'fardigmat': 'Färdigmat',
        'delikatessen': 'Delikatessen',
        'godis-snacks-och-glass': 'Godis, snacks & glass',
    };
    const dropdown = document.getElementById('categorySelectDropdown');
    if (!dropdown) return;
    dropdown.innerHTML = '';

    const categories = [...new Set(allData.map(d => d.category))].filter(Boolean).sort();
    categories.forEach(cat => {
        const label = document.createElement('label');
        label.className = 'checkbox-label';

        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.value = cat;
        checkbox.className = 'category-checkbox';
        checkbox.addEventListener('change', () => {
            if (checkbox.checked) {
                selectedCategories.push(cat);
            } else {
                selectedCategories = selectedCategories.filter(c => c !== cat);
            }
            updateCategorySelectBtnText();
            applyFilters(true);
        });

        label.appendChild(checkbox);
        label.appendChild(document.createTextNode(' ' + (slugToName[cat] || cat)));
        dropdown.appendChild(label);
    });
}

function setupEventListeners() {
    searchInput.addEventListener('input', () => applyFilters(true));
    storeSelect.addEventListener('change', () => applyFilters(true));

    const categorySelectBtn = document.getElementById('categorySelectBtn');
    const categorySelectDropdown = document.getElementById('categorySelectDropdown');
    const categoryMultiSelect = document.getElementById('categoryMultiSelect');

    if (categorySelectBtn && categorySelectDropdown) {
        categorySelectBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = categorySelectDropdown.style.display === 'flex';
            categorySelectDropdown.style.display = isOpen ? 'none' : 'flex';
            categorySelectBtn.classList.toggle('active', !isOpen);
        });

        document.addEventListener('click', (e) => {
            if (categoryMultiSelect && !categoryMultiSelect.contains(e.target)) {
                categorySelectDropdown.style.display = 'none';
                categorySelectBtn.classList.remove('active');
            }
        });
    }

    maxPriceInput.addEventListener('input', e => {
        maxPriceLabel.textContent = e.target.value + ' kr';
        applyFilters(true);
    });

    minProteinInput.addEventListener('input', e => {
        minProteinLabel.textContent = e.target.value + ' g';
        applyFilters(true);
    });

    tableHeaders.forEach(th => {
        th.addEventListener('click', () => {
            const col = th.dataset.sort;
            if (!col) return;
            if (sortCol === col) {
                sortDesc = !sortDesc;
            } else {
                sortCol = col;
                sortDesc = (col === 'ppk' || col === 'ppkcal' || col === 'protein_per_100g');
            }
            updateSortHeaders();
            applyFilters(false);
        });
    });

    // Modal close listeners
    closeModalBtn.addEventListener('click', closeModal);
    closeModalBtn.addEventListener('keydown', e => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); closeModal(); }
    });
    window.addEventListener('click', e => {
        if (e.target === productModal) closeModal();
    });
    window.addEventListener('keydown', e => {
        if (e.key === 'Escape') closeModal();
    });

    // Clear List listener
    clearListBtn.addEventListener('click', clearShoppingList);

    // Basket Button listeners
    document.querySelectorAll('.basket-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const basketId = btn.dataset.basket;
            selectBasket(basketId);
        });
    });

    // Basket Banner clear listener
    const clearBasketBtn = document.getElementById('clearBasketBtn');
    if (clearBasketBtn) {
        clearBasketBtn.addEventListener('click', clearActiveBasket);
    }

    // Add Basket to Cart listener
    const addBasketToCartBtn = document.getElementById('addBasketToCartBtn');
    if (addBasketToCartBtn) {
        addBasketToCartBtn.addEventListener('click', addActiveBasketToCart);
    }

    // Load more listener
    const loadMoreBtn = document.getElementById('loadMoreBtn');
    if (loadMoreBtn) {
        loadMoreBtn.addEventListener('click', handleLoadMore);
    }

    // Quick-search choice buttons
    document.querySelectorAll('.quick-search-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            if (searchInput) {
                searchInput.value = btn.dataset.search;
                searchInput.dispatchEvent(new Event('input'));
            }
        });
    });
}

function updateSortHeaders() {
    tableHeaders.forEach(th => {
        th.classList.remove('sort-active', 'desc');
        if (th.dataset.sort === sortCol) {
            th.classList.add('sort-active');
            if (sortDesc) th.classList.add('desc');
        }
    });
}

function isSmartMatch(text, query) {
    text = text.toLowerCase();
    query = query.toLowerCase().trim();
    
    // Special case: Kycklingbröst synonym expansion
    if (query === 'kycklingbröst') {
        return text.includes('kycklingbröst') || text.includes('kycklingfilé') || text.includes('kycklinginnerfilé') || (text.includes('kyckling') && text.includes('filé'));
    }
    
    // Sök efter "ost" - undvik ord som "rostade", "frukost", "kosttillskott", "ostronskivling"
    if (query === 'ost') {
        if (!text.includes('ost')) return false;
        const words = text.split(/[\s,.\-()]+/);
        return words.some(word => {
            if (word.includes('ost')) {
                const isExcluded = word.includes('rostad') || 
                                   word.includes('rosta') || 
                                   word.includes('rostat') || 
                                   word.includes('frukost') || 
                                   word.includes('kosttillskott') || 
                                   word.includes('ostron') ||
                                   word.includes('frost');
                return !isExcluded;
            }
            return false;
        });
    }
    
    return text.includes(query);
}

function applyFilters(resetPage = false) {
    if (resetPage) {
        currentLimit = 20;
        clickCount = 0;
    }

    const search = searchInput.value.toLowerCase().trim();
    const store = storeSelect.value;
    const maxPrice = parseFloat(maxPriceInput.value);
    const minProtein = parseFloat(minProteinInput.value);

    filteredData = allData.filter(item => {
        if (activeBasket && BASKETS[activeBasket]) {
            const criteria = BASKETS[activeBasket].filter_criteria;
            
            // Filter keywords
            if (criteria.keywords && criteria.keywords.length > 0) {
                const nameAndBrand = ((item.name || '') + ' ' + (item.brand || '')).toLowerCase();
                const matchesKeyword = criteria.keywords.some(kw => nameAndBrand.includes(kw.toLowerCase()));
                if (!matchesKeyword) return false;
            }
            
            // Filter min ppk
            if (criteria.min_ppk != null && (item.ppk || 0) < criteria.min_ppk) return false;
        }

        if (selectedCategories.length > 0 && !selectedCategories.includes(item.category)) return false;
        if (store && item.store !== store) return false;
        if (item.price_sek > maxPrice) return false;
        if ((item.protein_per_100g || 0) < minProtein) return false;
        if (search) {
            const nameMatch = item.name && isSmartMatch(item.name, search);
            const brandMatch = item.brand && isSmartMatch(item.brand, search);
            if (!nameMatch && !brandMatch) return false;
        }
        return true;
    });

    filteredData.sort((a, b) => {
        let valA = a[sortCol];
        let valB = b[sortCol];
        if (valA == null) return 1;
        if (valB == null) return -1;
        if (typeof valA === 'string') valA = valA.toLowerCase();
        if (typeof valB === 'string') valB = valB.toLowerCase();
        if (valA < valB) return sortDesc ? 1 : -1;
        if (valA > valB) return sortDesc ? -1 : 1;
        return 0;
    });

    updateKPIs();
    renderTable();
    updateLoadMoreButton();
}

function renderTable() {
    tableBody.innerHTML = '';

    if (filteredData.length === 0) {
        tableBody.innerHTML = `<tr><td colspan="10" style="text-align:center; padding: 3rem; color: #64748b;">
            Inga produkter matchar dina filter.
        </td></tr>`;
        if (resultCountEl) resultCountEl.textContent = '(0 produkter)';
        return;
    }

    const displayData = filteredData.slice(0, currentLimit);
    if (resultCountEl) {
        resultCountEl.textContent = filteredData.length > currentLimit
            ? `(visar ${currentLimit} av ${filteredData.length})`
            : `(${filteredData.length} produkter)`;
    }

    displayData.forEach(item => {
        const tr = document.createElement('tr');

        // Color-code PPK: green >= 2, yellow >= 1, neutral otherwise
        let ppkClass = '';
        if (item.ppk >= 2) ppkClass = 'ppk-high';
        else if (item.ppk >= 1) ppkClass = 'ppk-mid';

        // Color-code PPKcal: green >= 10g/100kcal
        const ppkcalClass = item.ppkcal >= 10 ? 'ppk-value' : '';

        const fallbackUrl = (item.store || '').toLowerCase() === 'willys'
            ? `https://www.willys.se/produkt/${item.code}`
            : `https://www.hemkop.se/produkt/${item.code}`;
        const validUrl = safeUrl(item.url, fallbackUrl);
        const storeClass = (item.store || '').toLowerCase() === 'willys' ? 'willys' : 'hemkop';

        tr.innerHTML = `
            <td data-label="PPK (g/kr)" class="${ppkClass}"><strong>${fmt(item.ppk, 2)}</strong></td>
            <td>
                <button class="add-to-list-btn" aria-label="Lägg till ${esc(item.name)} i shoppinglistan" title="Lägg till i shoppinglistan">+</button>
            </td>
            <td data-label="Produkt"><strong>${esc(item.name)}</strong></td>
            <td data-label="Märke">${esc(item.brand) || '–'}</td>
            <td data-label="Butik"><span class="store-badge ${storeClass}">${esc(item.store) || 'Hemköp'}</span></td>
            <td data-label="Pris">${fmt(item.price_sek, 2)} kr</td>
            <td data-label="Storlek">${esc(item.display_volume) || '–'}</td>
            <td data-label="Protein/100g">${fmt(item.protein_per_100g, 1)} g</td>
            <td data-label="Prot/100 kcal" class="${ppkcalClass}">${fmt(item.ppkcal, 1)} g</td>
            <td data-label="Länk"></td>
        `;

        // Add to list button with visual feedback
        const addBtn = tr.querySelector('.add-to-list-btn');
        addBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            addToShoppingList(item);
            addBtn.textContent = '✓';
            addBtn.classList.add('added');
            setTimeout(() => {
                addBtn.textContent = '+';
                addBtn.classList.remove('added');
            }, 1200);
        });

        // Row click: open modal (except Korg and Länk columns)
        tr.addEventListener('click', (e) => {
            const cell = e.target.closest('td');
            if (!cell) return;
            const cells = Array.from(cell.parentNode.children);
            const index = cells.indexOf(cell);
            if (index === 1) return; // bypass Korg add button
            if (index === 9) { // bypass Länk button
                const anchor = cell.querySelector('.store-link');
                if (anchor) anchor.click();
                return;
            }
            openModal(item);
        });

        // Build link via DOM (safe against URL injection)
        const linkCell = tr.querySelector('td:last-child');
        linkCell.style.cursor = 'pointer';
        const a = document.createElement('a');
        a.href = validUrl;
        a.target = '_blank';
        a.rel = 'noopener noreferrer';
        a.className = 'store-link';
        a.textContent = 'Butik →';
        a.addEventListener('click', e => e.stopPropagation());
        linkCell.addEventListener('click', (e) => { e.stopPropagation(); a.click(); });
        linkCell.appendChild(a);

        tableBody.appendChild(tr);
    });
}

function updateKPIs() {
    const validPPK = filteredData.filter(d => d.ppk > 0);
    totalProductsEl.textContent = filteredData.length;
    if (validPPK.length > 0) {
        const maxPPK = Math.max(...validPPK.map(d => d.ppk));
        bestPPKEl.innerHTML = `${maxPPK.toFixed(2)} <span class="unit">g/kr</span>`;
    } else {
        bestPPKEl.innerHTML = `– <span class="unit">g/kr</span>`;
    }
}

// Shopping List Operations
function loadShoppingList() {
    try {
        const saved = localStorage.getItem('ppk_shopping_list');
        shoppingList = saved ? JSON.parse(saved) : [];
        // Sanitize loaded data - filter out items with missing required fields
        shoppingList = shoppingList.filter(item =>
            item && item.code && item.name && item.price_sek != null
        );
    } catch (e) {
        shoppingList = [];
    }
    renderShoppingList();
}

function saveShoppingList() {
    localStorage.setItem('ppk_shopping_list', JSON.stringify(shoppingList));
    renderShoppingList();
}

function addToShoppingList(item) {
    const existing = shoppingList.find(x => x.code === item.code && x.store === item.store);
    if (existing) {
        existing.qty = (existing.qty || 1) + 1;
    } else {
        shoppingList.push({
            code: item.code,
            name: item.name,
            brand: item.brand,
            store: item.store,
            price_sek: item.price_sek,
            protein_per_100g: item.protein_per_100g,
            package_weight_g: item.package_weight_g || 0,
            url: item.url || '',
            qty: 1
        });
    }
    saveShoppingList();
}

function removeFromShoppingList(code, store) {
    shoppingList = shoppingList.filter(x => !(x.code === code && x.store === store));
    saveShoppingList();
}

function updateQty(code, store, delta) {
    const existing = shoppingList.find(x => x.code === code && x.store === store);
    if (existing) {
        existing.qty = (existing.qty || 1) + delta;
        if (existing.qty <= 0) {
            removeFromShoppingList(code, store);
        } else {
            saveShoppingList();
        }
    }
}

function clearShoppingList() {
    shoppingList = [];
    saveShoppingList();
}

function renderShoppingList() {
    shoppingListEl.innerHTML = '';
    if (shoppingList.length === 0) {
        shoppingListEmptyEl.style.display = 'block';
        shoppingListSummaryEl.style.display = 'none';
        return;
    }
    shoppingListEmptyEl.style.display = 'none';
    shoppingListSummaryEl.style.display = 'block';

    let totalCost = 0;
    let totalProtein = 0;
    let totalQty = 0;

    shoppingList.forEach(item => {
        const qty = item.qty || 1;
        totalQty += qty;

        // Guard against null price_sek
        const price = item.price_sek != null ? item.price_sek : 0;
        totalCost += price * qty;

        // Guard against missing weight/protein data
        const weight = item.package_weight_g > 0 ? item.package_weight_g : null;
        if (weight && item.protein_per_100g) {
            const itemProtein = (item.protein_per_100g / 100) * weight;
            totalProtein += itemProtein * qty;
        }

        // Safe URL with validation
        const fallbackUrl = (item.store || '').toLowerCase() === 'willys'
            ? `https://www.willys.se/produkt/${item.code}`
            : `https://www.hemkop.se/produkt/${item.code}`;
        const itemUrl = safeUrl(item.url, fallbackUrl);

        const li = document.createElement('li');
        li.className = 'shopping-item';
        li.innerHTML = `
            <div class="shopping-item-info">
                <span class="shopping-item-name">${esc(item.name)}</span>
                <span class="shopping-item-sub">${esc(item.brand)} | ${esc(item.store)}</span>
                <span class="shopping-item-price-unit">${fmt(price, 2)} kr/st</span>
                <a href="${esc(itemUrl)}" target="_blank" rel="noopener noreferrer" class="shopping-item-store-link">Köp på ${esc(item.store || 'butiken')} →</a>
            </div>
            <div class="shopping-item-controls">
                <button class="btn-qty btn-minus" aria-label="Minska antal ${esc(item.name)}">−</button>
                <span class="shopping-item-qty" aria-label="Antal">${qty}</span>
                <button class="btn-qty btn-plus" aria-label="Öka antal ${esc(item.name)}">+</button>
            </div>
        `;

        li.querySelector('.btn-minus').addEventListener('click', (e) => {
            e.stopPropagation();
            updateQty(item.code, item.store, -1);
        });
        li.querySelector('.btn-plus').addEventListener('click', (e) => {
            e.stopPropagation();
            updateQty(item.code, item.store, 1);
        });

        shoppingListEl.appendChild(li);
    });

    const combinedPPK = totalCost > 0 ? totalProtein / totalCost : 0;

    summaryCountEl.textContent = `${totalQty} st`;
    summaryPriceEl.textContent = `${totalCost.toFixed(2)} kr`;
    summaryProteinEl.textContent = totalProtein > 0 ? `${totalProtein.toFixed(1)} g` : '– g';
    summaryPPKEl.textContent = `${combinedPPK.toFixed(2)} g/kr`;
    updateBasketUI(shoppingList, allData);
}

// Modal Details Populator
function openModal(item) {
    const protein = item.protein_per_100g || 0;
    const fat = item.fat_per_100g || 0;
    const carbs = item.carbohydrates_per_100g || 0;
    const salt = item.salt_per_100g || 0;
    const calories = item.calories_per_100g || 0;

    // Calculate bar widths as % of 50g max (sensible max for visualization)
    const protPct = Math.min((protein / 50) * 100, 100);
    const fatPct = Math.min((fat / 50) * 100, 100);
    const carbsPct = Math.min((carbs / 50) * 100, 100);
    const saltPct = Math.min((salt / 5) * 100, 100);

    const storeBadgeClass = (item.store || '').toLowerCase() === 'willys' ? 'willys' : 'hemkop';
    const fallbackUrl = (item.store || '').toLowerCase() === 'willys'
        ? `https://www.willys.se/produkt/${item.code}`
        : `https://www.hemkop.se/produkt/${item.code}`;
    const validUrl = safeUrl(item.url, fallbackUrl);

    modalBody.innerHTML = `
        <div class="modal-header">
            <h2 class="modal-title">${esc(item.name)}</h2>
            <div class="modal-subtitle">
                ${esc(item.brand) || 'Okänt märke'} &nbsp;|&nbsp;
                <span class="store-badge ${storeBadgeClass}">${esc(item.store) || 'Hemköp'}</span>
            </div>
        </div>

        <div class="modal-grid">
            <div>
                <h3 class="modal-section-title">Näringsvärden (per 100g)</h3>
                <div class="macro-list">
                    <div class="macro-item macro-protein">
                        <div class="macro-info">
                            <span>💪 Protein</span>
                            <span>${fmt(protein, 1)} g</span>
                        </div>
                        <div class="macro-bar-bg">
                            <div class="macro-bar-fill" style="width: ${protPct}%"></div>
                        </div>
                    </div>
                    <div class="macro-item macro-fat">
                        <div class="macro-info">
                            <span>🥑 Fett</span>
                            <span>${fmt(fat, 1)} g</span>
                        </div>
                        <div class="macro-bar-bg">
                            <div class="macro-bar-fill" style="width: ${fatPct}%"></div>
                        </div>
                    </div>
                    <div class="macro-item macro-carbs">
                        <div class="macro-info">
                            <span>🌾 Kolhydrater</span>
                            <span>${fmt(carbs, 1)} g</span>
                        </div>
                        <div class="macro-bar-bg">
                            <div class="macro-bar-fill" style="width: ${carbsPct}%"></div>
                        </div>
                    </div>
                    <div class="macro-item macro-salt">
                        <div class="macro-info">
                            <span>🧂 Salt</span>
                            <span>${fmt(salt, 2)} g</span>
                        </div>
                        <div class="macro-bar-bg">
                            <div class="macro-bar-fill" style="width: ${saltPct}%"></div>
                        </div>
                    </div>
                </div>
            </div>

            <div>
                <h3 class="modal-section-title">Pris & Effektivitet</h3>
                <div class="modal-stats">
                    <div class="modal-stat-card">
                        <span class="modal-stat-label">💰 Konsumentpris</span>
                        <span class="modal-stat-value">${fmt(item.price_sek, 2)} kr</span>
                    </div>
                    <div class="modal-stat-card">
                        <span class="modal-stat-label">⚖️ Jämförpris</span>
                        <span class="modal-stat-value">${esc(item.compare_price) || fmt(item.compare_price_per_kg, 2, ' kr/kg')}</span>
                    </div>
                    <div class="modal-stat-card">
                        <span class="modal-stat-label">🏆 Protein per krona</span>
                        <span class="modal-stat-value highlight">${fmt(item.ppk, 2)} g/kr</span>
                    </div>
                    <div class="modal-stat-card">
                        <span class="modal-stat-label">⚡ Prot per 100 kcal</span>
                        <span class="modal-stat-value highlight">${fmt(item.ppkcal, 1)} g</span>
                    </div>
                    <div class="modal-stat-card">
                        <span class="modal-stat-label">🔥 Kalorier</span>
                        <span class="modal-stat-value highlight-red">${calories > 0 ? calories.toFixed(0) + ' kcal' : '–'}</span>
                    </div>
                </div>
            </div>
        </div>

        ${item.description ? `
            <h3 class="modal-section-title">Beskrivning</h3>
            <div class="modal-desc">${esc(item.description)}</div>
        ` : ''}

        <div class="modal-footer">
            <button class="btn btn-secondary" id="closeModalFooterBtn">Stäng</button>
            <a class="btn btn-primary" href="${esc(validUrl)}" target="_blank" rel="noopener noreferrer">Visa på ${esc(item.store) || 'butiken'} →</a>
        </div>
    `;

    document.getElementById('closeModalFooterBtn').onclick = closeModal;

    productModal.classList.add('show');
    productModal.setAttribute('aria-hidden', 'false');
    // Move focus to modal for accessibility
    productModal.querySelector('.close-btn').focus();

    // Animate progress bars
    setTimeout(() => {
        const fills = modalBody.querySelectorAll('.macro-bar-fill');
        fills.forEach(fill => {
            const width = fill.style.width;
            fill.style.width = '0';
            setTimeout(() => { fill.style.width = width; }, 50);
        });
    }, 100);
}

function closeModal() {
    productModal.classList.remove('show');
    productModal.setAttribute('aria-hidden', 'true');
}

function selectBasket(basketId) {
    if (activeBasket === basketId) {
        clearActiveBasket();
        return;
    }

    activeBasket = basketId;
    const basket = BASKETS[basketId];

    // Update sidebar buttons visual state
    document.querySelectorAll('.basket-btn').forEach(btn => {
        if (btn.dataset.basket === basketId) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    // Set slider values based on criteria
    if (basket.filter_criteria.max_price != null) {
        maxPriceInput.value = basket.filter_criteria.max_price;
        maxPriceLabel.textContent = basket.filter_criteria.max_price + ' kr';
    }
    if (basket.filter_criteria.min_protein_100g != null) {
        minProteinInput.value = basket.filter_criteria.min_protein_100g;
        minProteinLabel.textContent = basket.filter_criteria.min_protein_100g + ' g';
    } else {
        minProteinInput.value = 0;
        minProteinLabel.textContent = '0 g';
    }

    // Show banner
    const banner = document.getElementById('basketBanner');
    const bannerEmoji = document.getElementById('basketBannerEmoji');
    const bannerTitle = document.getElementById('basketBannerTitle');
    const bannerDesc = document.getElementById('basketBannerDesc');

    if (banner) {
        if (bannerEmoji) bannerEmoji.textContent = basket.emoji;
        if (bannerTitle) bannerTitle.textContent = basket.title;
        if (bannerDesc) bannerDesc.textContent = basket.description;
        banner.style.display = 'flex';
    }

    applyFilters(true);
}

function clearActiveBasket() {
    activeBasket = null;

    // Reset sidebar buttons
    document.querySelectorAll('.basket-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    // Reset sliders to default values
    maxPriceInput.value = 200;
    maxPriceLabel.textContent = '200 kr';
    minProteinInput.value = 0;
    minProteinLabel.textContent = '0 g';

    // Hide banner
    const banner = document.getElementById('basketBanner');
    if (banner) {
        banner.style.display = 'none';
    }

    applyFilters(true);
}

function addActiveBasketToCart() {
    if (!activeBasket || !BASKETS[activeBasket]) return;

    const basket = BASKETS[activeBasket];
    const criteria = basket.filter_criteria;

    let addedCount = 0;

    criteria.keywords.forEach(kw => {
        let matchingItems = allData.filter(item => {
            const nameAndBrand = ((item.name || '') + ' ' + (item.brand || '')).toLowerCase();
            if (!nameAndBrand.includes(kw.toLowerCase())) return false;

            if (criteria.max_price != null && item.price_sek > criteria.max_price) return false;
            if (criteria.min_ppk != null && (item.ppk || 0) < criteria.min_ppk) return false;
            if (criteria.min_protein_100g != null && (item.protein_per_100g || 0) < criteria.min_protein_100g) return false;

            return true;
        });

        if (matchingItems.length > 0) {
            // Sort by PPK descending (best value first)
            matchingItems.sort((a, b) => b.ppk - a.ppk);
            const bestItem = matchingItems[0];

            addToShoppingList(bestItem);
            addedCount++;
        }
    });

    if (addedCount > 0) {
        const btn = document.getElementById('addBasketToCartBtn');
        if (btn) {
            const originalText = btn.textContent;
            btn.textContent = '✓ Tillagd!';
            btn.style.backgroundColor = 'var(--accent-green)';
            btn.style.borderColor = 'var(--accent-green)';
            btn.style.color = '#fff';
            setTimeout(() => {
                btn.textContent = originalText;
                btn.style.backgroundColor = '';
                btn.style.borderColor = '';
                btn.style.color = '';
            }, 1500);
        }
    }
}

function updateDynamicPPK() {
    const price = 249; // kr
    const weightKg = 1; // kg
    const proteinPct = 0.75; // 75%
    const totalProtein = weightKg * 1000 * proteinPct; // 750g
    const ppk = totalProtein / price; // 3.012...
    
    const elements = document.querySelectorAll('.dynamic-ppk');
    elements.forEach(el => {
        el.textContent = `~${ppk.toFixed(1)} g/kr`;
    });
}

function updateLoadMoreButton() {
    const loadMoreBtn = document.getElementById('loadMoreBtn');
    if (!loadMoreBtn) return;
    
    if (filteredData.length === 0 || filteredData.length <= currentLimit) {
        loadMoreBtn.style.display = 'none';
    } else {
        loadMoreBtn.style.display = 'inline-block';
        const nextLoad = clickCount < 3 ? 20 : 100;
        loadMoreBtn.textContent = `Ladda ${nextLoad} till`;
    }
}

function handleLoadMore() {
    const increment = clickCount < 3 ? 20 : 100;
    currentLimit += increment;
    clickCount += 1;
    applyFilters(false);
}

const BasketOptimizer = {
    calculateTotalPPK(items) {
        let totalProteinGrams = 0;
        let totalCost = 0;

        items.forEach(item => {
            const price = parseFloat(item.price_sek);
            const proteinPer100g = parseFloat(item.protein_per_100g);
            const weightGrams = parseFloat(item.package_weight_g || 0);

            if (!isNaN(price) && !isNaN(proteinPer100g) && !isNaN(weightGrams)) {
                const qty = item.qty || 1;
                const totalProteinInProduct = (proteinPer100g / 100) * weightGrams;
                totalProteinGrams += totalProteinInProduct * qty;
                totalCost += price * qty;
            }
        });

        if (totalCost === 0) return 0;
        return (totalProteinGrams / totalCost).toFixed(2);
    },

    compareStores(items, allProductsDatabase) {
        let willysTotal = 0;
        let hemkopTotal = 0;
        let missingInWillys = 0;
        let missingInHemkop = 0;

        items.forEach(item => {
            const qty = item.qty || 1;
            const price = parseFloat(item.price_sek) || 0;

            const willysMatch = allProductsDatabase.find(p => 
                p.name === item.name && 
                p.brand === item.brand &&
                p.store.toLowerCase() === 'willys'
            );
            const hemkopMatch = allProductsDatabase.find(p => 
                p.name === item.name && 
                p.brand === item.brand &&
                p.store.toLowerCase() === 'hemköp'
            );

            if (willysMatch) {
                willysTotal += (parseFloat(willysMatch.price_sek) || price) * qty;
            } else {
                willysTotal += price * qty;
                missingInWillys++;
            }

            if (hemkopMatch) {
                hemkopTotal += (parseFloat(hemkopMatch.price_sek) || price) * qty;
            } else {
                hemkopTotal += price * qty;
                missingInHemkop++;
            }
        });

        return {
            willys: willysTotal.toFixed(2),
            hemkop: hemkopTotal.toFixed(2),
            cheapest: willysTotal < hemkopTotal ? 'Willys' : 'Hemköp',
            savings: Math.abs(willysTotal - hemkopTotal).toFixed(2)
        };
    }
};

function updateBasketUI(currentBasketItems, fullDatabase) {
    const totalPPK = BasketOptimizer.calculateTotalPPK(currentBasketItems);
    const comparison = BasketOptimizer.compareStores(currentBasketItems, fullDatabase);

    const totalBasketPpkEl = document.getElementById('total-basket-ppk');
    if (totalBasketPpkEl) {
        totalBasketPpkEl.innerText = `${totalPPK} g/kr`;
    }
    
    const summaryElement = document.getElementById('basket-store-comparison');
    if (!summaryElement) return;
    
    if (currentBasketItems.length > 0) {
        summaryElement.innerHTML = `
            <div style="padding: 12px; background: var(--bg-color); border: 1px solid var(--border-color); border-radius: var(--radius-md); margin-top: 10px; font-size: 0.85rem;">
                <p style="margin: 0 0 6px 0;"><strong>Butiksjämförelse:</strong></p>
                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                    <span>Willys total:</span> <span>${comparison.willys} kr</span>
                </div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
                    <span>Hemköp total:</span> <span>${comparison.hemkop} kr</span>
                </div>
                <p style="margin: 6px 0 0 0; color: var(--accent-red); font-weight: bold; font-size: 0.85rem;">
                    👉 Handla på ${comparison.cheapest} och spara ${comparison.savings} kr!
                </p>
            </div>
        `;
    } else {
        summaryElement.innerHTML = '';
    }
}

init();
