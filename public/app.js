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

// Init
async function init() {
    try {
        const response = await fetch('data.json');
        if (!response.ok) throw new Error("Kunde inte hämta data.json");
        const rawData = await response.json();
        
        // Calculate PPK and ensure data structure
        allData = rawData.map(item => {
            return {
                ...item,
                ppk: item.protein_per_krona || 0
            };
        });

        populateCategories();
        applyFilters();
        setupEventListeners();
    } catch (error) {
        console.error(error);
        tableBody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:red;">Kunde inte ladda data. Har du kört skrapan?</td></tr>`;
    }
}

function populateCategories() {
    const categories = [...new Set(allData.map(d => d.category))].filter(Boolean).sort();
    categories.forEach(cat => {
        const option = document.createElement('option');
        option.value = cat;
        option.textContent = cat;
        categorySelect.appendChild(option);
    });
}

function setupEventListeners() {
    searchInput.addEventListener('input', applyFilters);
    categorySelect.addEventListener('change', applyFilters);
    
    maxPriceInput.addEventListener('input', (e) => {
        maxPriceLabel.textContent = e.target.value;
        applyFilters();
    });
    
    minProteinInput.addEventListener('input', (e) => {
        minProteinLabel.textContent = e.target.value;
        applyFilters();
    });

    tableHeaders.forEach(th => {
        th.addEventListener('click', () => {
            const col = th.dataset.sort;
            if (sortCol === col) {
                sortDesc = !sortDesc;
            } else {
                sortCol = col;
                sortDesc = (col === 'ppk' || col === 'protein_per_100g'); // Default desc for these
            }
            updateSortHeaders();
            applyFilters();
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
    const search = searchInput.value.toLowerCase();
    const cat = categorySelect.value;
    const maxPrice = parseFloat(maxPriceInput.value);
    const minProtein = parseFloat(minProteinInput.value);

    filteredData = allData.filter(item => {
        if (cat && item.category !== cat) return false;
        if (item.price_sek > maxPrice) return false;
        if (item.protein_per_100g < minProtein) return false;
        
        if (search) {
            const nameMatch = item.name && item.name.toLowerCase().includes(search);
            const brandMatch = item.brand && item.brand.toLowerCase().includes(search);
            if (!nameMatch && !brandMatch) return false;
        }
        
        return true;
    });

    // Sort
    filteredData.sort((a, b) => {
        let valA = a[sortCol];
        let valB = b[sortCol];
        
        if (typeof valA === 'string') valA = valA.toLowerCase();
        if (typeof valB === 'string') valB = valB.toLowerCase();
        
        if (valA < valB) return sortDesc ? 1 : -1;
        if (valA > valB) return sortDesc ? -1 : 1;
        return 0;
    });

    renderTable();
    updateKPIs();
}

function renderTable() {
    tableBody.innerHTML = '';
    
    if (filteredData.length === 0) {
        tableBody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding: 3rem; color: #64748b;">Inga produkter matchar dina filter.</td></tr>`;
        return;
    }

    // Limit to 100 to prevent DOM lag on huge lists
    const displayData = filteredData.slice(0, 200);

    displayData.forEach(item => {
        const tr = document.createElement('tr');
        
        const ppkClass = item.ppk > 2 ? 'ppk-value' : '';
        const url = item.url ? item.url : `https://www.hemkop.se/produkt/${item.ean}`;

        tr.innerHTML = `
            <td data-label="Produkt"><strong>${item.name || 'Okänd'}</strong></td>
            <td data-label="Märke">${item.brand || '-'}</td>
            <td data-label="Pris">${item.price_sek.toFixed(2)} kr</td>
            <td data-label="Storlek">${item.display_volume || '-'}</td>
            <td data-label="Protein/100g">${item.protein_per_100g.toFixed(1)} g</td>
            <td data-label="PPK (g/kr)" class="${ppkClass}">${item.ppk.toFixed(2)}</td>
            <td><a href="${url}" target="_blank" class="store-link">Hemköp →</a></td>
        `;
        tableBody.appendChild(tr);
    });
}

function updateKPIs() {
    totalProductsEl.textContent = filteredData.length;
    if (filteredData.length > 0) {
        // Find best PPK in filtered data
        const maxPPK = Math.max(...filteredData.map(d => d.ppk));
        bestPPKEl.innerHTML = `${maxPPK.toFixed(2)} <span class="unit">g/kr</span>`;
    } else {
        bestPPKEl.innerHTML = `0.00 <span class="unit">g/kr</span>`;
    }
}

// Run
init();
