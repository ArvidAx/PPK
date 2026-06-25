let allData = [];
let filteredData = [];
let sortCol = 'ppk';
let sortDesc = true;

// DOM Elements
const tableBody = document.getElementById('tableBody');
const categorySelect = document.getElementById('category');
const searchInput = document.getElementById('search');
const maxPriceInput = document.getElementById('maxPrice');
const maxPriceLabel = document.getElementById('maxPriceLabel');
const minProteinInput = document.getElementById('minProtein');
const minProteinLabel = document.getElementById('minProteinLabel');
const totalProductsEl = document.getElementById('totalProducts');
const bestPPKEl = document.getElementById('bestPPK');
const tableHeaders = document.querySelectorAll('th[data-sort]');

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

        allData = rawData.map(item => ({
            ...item,
            ppk: item.protein_per_krona || 0
        })).filter(item => item.price_sek != null && item.protein_per_100g != null);

        populateCategories();
        setupEventListeners();
        applyFilters();
    } catch (error) {
        console.error(error);
        tableBody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding: 2rem; color:#e11d48;">
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
            if (sortCol === col) {
                sortDesc = !sortDesc;
            } else {
                sortCol = col;
                sortDesc = (col === 'ppk' || col === 'protein_per_100g' || col === 'price_sek');
            }
            updateSortHeaders();
            renderTable();
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

function applyFilters() {
    const search = searchInput.value.toLowerCase().trim();
    const cat = categorySelect.value;
    const maxPrice = parseFloat(maxPriceInput.value);
    const minProtein = parseFloat(minProteinInput.value);

    filteredData = allData.filter(item => {
        if (cat && item.category !== cat) return false;
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
        tableBody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding: 3rem; color: #64748b;">
            Inga produkter matchar dina filter.
        </td></tr>`;
        return;
    }

    const displayData = filteredData.slice(0, 200);

    displayData.forEach(item => {
        const tr = document.createElement('tr');
        const ppkClass = item.ppk >= 2 ? 'ppk-value' : '';
        const url = esc(item.url || `https://www.hemkop.se/produkt/${item.code}`);

        // Use DOM methods for the link cell to avoid XSS
        tr.innerHTML = `
            <td data-label="Produkt"><strong>${esc(item.name)}</strong></td>
            <td data-label="Märke">${esc(item.brand) || '–'}</td>
            <td data-label="Pris">${fmt(item.price_sek, 2)} kr</td>
            <td data-label="Storlek">${esc(item.display_volume) || '–'}</td>
            <td data-label="Protein/100g">${fmt(item.protein_per_100g, 1)} g</td>
            <td data-label="PPK (g/kr)" class="${ppkClass}">${fmt(item.ppk, 2)}</td>
            <td></td>
        `;
        // Build link safely via DOM (not innerHTML) to prevent URL injection
        const linkCell = tr.querySelector('td:last-child');
        const a = document.createElement('a');
        a.href = url;
        a.target = '_blank';
        a.rel = 'noopener noreferrer';
        a.className = 'store-link';
        a.textContent = 'Hemköp →';
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

init();
