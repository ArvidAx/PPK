let allData = [];
let filteredData = [];
let sortCol = 'ppk';
let sortDesc = true;
let shoppingList = [];

// DOM Elements
const tableBody = document.getElementById('tableBody');
const categorySelect = document.getElementById('category');
const storeSelect = document.getElementById('store');
const searchInput = document.getElementById('search');
const maxPriceInput = document.getElementById('maxPrice');
const maxPriceLabel = document.getElementById('maxPriceLabel');
const minProteinInput = document.getElementById('minProtein');
const minProteinLabel = document.getElementById('minProteinLabel');
const totalProductsEl = document.getElementById('totalProducts');
const bestPPKEl = document.getElementById('bestPPK');
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

// Safe number formatting — handles null/undefined without crashing
function fmt(val, decimals = 1, suffix = '') {
    if (val == null || isNaN(val)) return '–';
    return Number(val).toFixed(decimals) + suffix;
}

// Init
async function init() {
    try {
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

        populateCategories();
        setupEventListeners();
        loadShoppingList();
        applyFilters();
    } catch (error) {
        console.error(error);
        tableBody.innerHTML = `<tr><td colspan="10" style="text-align:center; padding: 2rem; color:#e11d48;">
            Kunde inte ladda produktdata. Kör skrapan och försök igen.
        </td></tr>`;
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
    const categories = [...new Set(allData.map(d => d.category))].filter(Boolean).sort();
    categories.forEach(cat => {
        const option = document.createElement('option');
        option.value = cat;
        option.textContent = slugToName[cat] || cat;
        categorySelect.appendChild(option);
    });
}

function setupEventListeners() {
    searchInput.addEventListener('input', applyFilters);
    categorySelect.addEventListener('change', applyFilters);
    storeSelect.addEventListener('change', applyFilters);

    maxPriceInput.addEventListener('input', e => {
        maxPriceLabel.textContent = e.target.value + ' kr';
        applyFilters();
    });

    minProteinInput.addEventListener('input', e => {
        minProteinLabel.textContent = e.target.value + ' g';
        applyFilters();
    });

    tableHeaders.forEach(th => {
        th.addEventListener('click', () => {
            const col = th.dataset.sort;
            if (!col) return; // Ignore columns without sorting
            if (sortCol === col) {
                sortDesc = !sortDesc;
            } else {
                sortCol = col;
                // Descending by default for efficiency metrics, ascending for others
                sortDesc = (col === 'ppk' || col === 'ppkcal' || col === 'protein_per_100g');
            }
            updateSortHeaders();
            renderTable();
        });
    });

    // Modal close listeners
    closeModalBtn.addEventListener('click', closeModal);
    window.addEventListener('click', e => {
        if (e.target === productModal) closeModal();
    });
    window.addEventListener('keydown', e => {
        if (e.key === 'Escape') closeModal();
    });

    // Clear List listener
    clearListBtn.addEventListener('click', clearShoppingList);
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

function applyFilters() {
    const search = searchInput.value.toLowerCase().trim();
    const cat = categorySelect.value;
    const store = storeSelect.value;
    const maxPrice = parseFloat(maxPriceInput.value);
    const minProtein = parseFloat(minProteinInput.value);

    filteredData = allData.filter(item => {
        if (cat && item.category !== cat) return false;
        if (store && item.store !== store) return false;
        if (item.price_sek > maxPrice) return false;
        if ((item.protein_per_100g || 0) < minProtein) return false;
        if (search) {
            const nameMatch = item.name && item.name.toLowerCase().includes(search);
            const brandMatch = item.brand && item.brand.toLowerCase().includes(search);
            if (!nameMatch && !brandMatch) return false;
        }
        return true;
    });

    filteredData.sort((a, b) => {
        let valA = a[sortCol];
        let valB = b[sortCol];
        // Handle nulls — push to bottom regardless of sort direction
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
}

function renderTable() {
    tableBody.innerHTML = '';

    if (filteredData.length === 0) {
        tableBody.innerHTML = `<tr><td colspan="10" style="text-align:center; padding: 3rem; color: #64748b;">
            Inga produkter matchar dina filter.
        </td></tr>`;
        return;
    }

    const displayData = filteredData.slice(0, 200);

    displayData.forEach(item => {
        const tr = document.createElement('tr');
        const ppkClass = item.ppk >= 2 ? 'ppk-value' : '';
        const ppkcalClass = item.ppkcal >= 10 ? 'ppk-value' : '';
        const url = esc(item.url || `https://www.hemkop.se/produkt/${item.code}`);
        const storeClass = (item.store || '').toLowerCase() === 'willys' ? 'willys' : 'hemkop';

        tr.innerHTML = `
            <td style="text-align: center;"><button class="add-to-list-btn" title="Lägg till i shoppinglistan">+</button></td>
            <td data-label="Produkt"><strong>${esc(item.name)}</strong></td>
            <td data-label="Märke">${esc(item.brand) || '–'}</td>
            <td data-label="Butik"><span class="store-badge ${storeClass}">${esc(item.store) || 'Hemköp'}</span></td>
            <td data-label="Pris">${fmt(item.price_sek, 2)} kr</td>
            <td data-label="Storlek">${esc(item.display_volume) || '–'}</td>
            <td data-label="Protein/100g">${fmt(item.protein_per_100g, 1)} g</td>
            <td data-label="PPK (g/kr)" class="${ppkClass}">${fmt(item.ppk, 2)}</td>
            <td data-label="Prot/100 kcal" class="${ppkcalClass}">${fmt(item.ppkcal, 1)} g</td>
            <td></td>
        `;

        // Add to list button functionality
        tr.querySelector('.add-to-list-btn').addEventListener('click', (e) => {
            e.stopPropagation(); // Avoid triggering row click modal
            addToShoppingList(item);
        });

        // Row click functionality
        tr.addEventListener('click', (e) => {
            const cell = e.target.closest('td');
            if (!cell) return;
            const cells = Array.from(cell.parentNode.children);
            const index = cells.indexOf(cell);
            
            if (index === 0) {
                return; // Plus button column
            }
            if (index === 9) {
                // Link column clicked - trigger anchor link click
                const anchor = cell.querySelector('.store-link');
                if (anchor) anchor.click();
                return;
            }
            // Anywhere else: open modal
            openModal(item);
        });

        // Build link safely via DOM to prevent URL injection
        const linkCell = tr.querySelector('td:last-child');
        linkCell.style.cursor = 'pointer';
        
        const a = document.createElement('a');
        a.href = url;
        a.target = '_blank';
        a.rel = 'noopener noreferrer';
        a.className = 'store-link';
        a.textContent = 'Butik →';
        
        // Prevent row click modal when clicking the button directly
        a.addEventListener('click', (e) => {
            e.stopPropagation();
        });

        // Clicking anywhere in the cell triggers the link
        linkCell.addEventListener('click', (e) => {
            e.stopPropagation();
            a.click();
        });

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
        totalCost += item.price_sek * qty;

        const weight = item.package_weight_g || 0;
        const itemProtein = (item.protein_per_100g / 100) * weight;
        totalProtein += itemProtein * qty;

        const li = document.createElement('li');
        li.className = 'shopping-item';
        li.innerHTML = `
            <div class="shopping-item-info">
                <span class="shopping-item-name">${esc(item.name)}</span>
                <span class="shopping-item-sub">${esc(item.brand)} | ${esc(item.store)}</span>
            </div>
            <div class="shopping-item-controls">
                <button class="btn-qty btn-minus">-</button>
                <span class="shopping-item-qty">${qty}</span>
                <button class="btn-qty btn-plus">+</button>
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
    summaryProteinEl.textContent = `${totalProtein.toFixed(1)} g`;
    summaryPPKEl.textContent = `${combinedPPK.toFixed(2)} g/kr`;
}

// Modal Details Populator
function openModal(item) {
    const protein = item.protein_per_100g || 0;
    const fat = item.fat_per_100g || 0;
    const carbs = item.carbohydrates_per_100g || 0;
    const salt = item.salt_per_100g || 0;
    const calories = item.calories_per_100g || 0;
    
    const protPct = Math.min((protein / 100) * 100, 100);
    const fatPct = Math.min((fat / 100) * 100, 100);
    const carbsPct = Math.min((carbs / 100) * 100, 100);
    const saltPct = Math.min((salt / 100) * 100, 100);

    const storeBadgeClass = (item.store || '').toLowerCase() === 'willys' ? 'willys' : 'hemkop';
    const url = esc(item.url || `https://www.hemkop.se/produkt/${item.code}`);

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
            <a class="btn btn-primary" href="${url}" target="_blank" rel="noopener noreferrer">Visa på ${esc(item.store) || 'butiken'} →</a>
        </div>
    `;

    document.getElementById('closeModalFooterBtn').onclick = closeModal;

    productModal.classList.add('show');
    productModal.setAttribute('aria-hidden', 'false');
    
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

function closeModal() {
    productModal.classList.remove('show');
    productModal.setAttribute('aria-hidden', 'true');
}

init();
