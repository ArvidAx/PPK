"""
Streamlit Frontend Application for Swedish "Protein Per Krona" (PPK).
This module renders the main dashboard, handles interactive user input,
applies advanced visual styling, and displays price comparisons.
"""

import streamlit as st
import pandas as pd
import database

# Initialize database schema and seed mock data if empty
# This ensures that the application runs completely out-of-the-box.
database.init_db()

# Set up page configurations
st.set_page_config(
    page_title="Protein Per Krona (PPK)",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inject custom modern CSS styling
# Uses Google Font 'Inter', clean card styling, subtle borders and a red accent color.
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* Apply typography */
    html, body, [class*="css"], .stApp {
        font-family: 'Inter', sans-serif;
        background-color: #F9FAFB;
        color: #111827;
    }
    
    /* Main title layout styling */
    .app-title {
        font-size: 2.5rem;
        font-weight: 700;
        color: #111827;
        margin-bottom: 0.2rem;
        padding-top: 0.5rem;
        letter-spacing: -0.02em;
    }
    
    .app-subtitle {
        font-size: 1.05rem;
        color: #4B5563;
        margin-bottom: 2rem;
        font-weight: 400;
    }
    
    /* Collapsible expander header styling */
    .stExpander {
        border-radius: 6px !important;
        border: 1px solid #E5E7EB !important;
        box-shadow: none !important;
        background-color: #FFFFFF !important;
    }
    
    /* Card design for top 3 protein sources */
    .kpi-card {
        background: #FFFFFF;
        border-radius: 8px;
        padding: 1.5rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05), 0 1px 2px rgba(0,0,0,0.03);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        margin-bottom: 1rem;
        border: 1px solid #E5E7EB;
        position: relative;
    }
    
    .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 6px rgba(0,0,0,0.05), 0 2px 4px rgba(0,0,0,0.03);
    }
    
    .kpi-rank-badge {
        position: absolute;
        top: -10px;
        left: -10px;
        background-color: #E52421;
        color: #FFFFFF;
        width: 28px;
        height: 28px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.85rem;
        font-weight: 700;
        box-shadow: 0 2px 4px rgba(229, 36, 33, 0.3);
    }
    
    .kpi-title {
        font-size: 1.1rem;
        font-weight: 600;
        color: #111827;
        margin-bottom: 0.2rem;
        margin-top: 0.5rem;
    }
    
    .kpi-brand {
        font-size: 0.85rem;
        color: #6B7280;
        margin-bottom: 1rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-weight: 500;
    }
    
    .kpi-value-container {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        margin-top: 1rem;
        padding-top: 1rem;
        border-top: 1px solid #F3F4F6;
    }
    
    .kpi-ppk-label {
        font-size: 0.85rem;
        color: #4B5563;
        font-weight: 500;
    }
    
    .kpi-ppk-value {
        font-size: 1.4rem;
        font-weight: 700;
        color: #E52421;
    }
    
    .kpi-meta-item {
        font-size: 0.9rem;
        color: #374151;
        margin-bottom: 0.4rem;
        display: flex;
        justify-content: space-between;
    }
    
    .kpi-meta-label {
        color: #6B7280;
    }
    
    .kpi-meta-value {
        font-weight: 500;
    }
    
    /* Styling for sidebar custom elements */
    .sidebar-header {
        font-weight: 600;
        font-size: 1.1rem;
        color: #111827;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid #E5E7EB;
    }
    
    /* Detail View Styling */
    .detail-card {
        background-color: #FFFFFF;
        border-top: 4px solid #E52421;
        border-radius: 6px;
        padding: 2rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        border-left: 1px solid #E5E7EB;
        border-right: 1px solid #E5E7EB;
        border-bottom: 1px solid #E5E7EB;
        height: 100%;
    }
    
    .detail-store {
        font-size: 0.75rem;
        font-weight: 700;
        color: #E52421;
        text-transform: uppercase;
        margin-bottom: 0.5rem;
        letter-spacing: 0.05em;
    }
    
    .detail-title {
        font-size: 1.5rem;
        font-weight: 700;
        color: #111827;
        margin-bottom: 0.2rem;
    }
    
    .detail-brand {
        font-size: 0.85rem;
        color: #6B7280;
        margin-bottom: 1.5rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .detail-row {
        display: flex;
        justify-content: space-between;
        margin-bottom: 0.75rem;
        font-size: 0.95rem;
        border-bottom: 1px solid #F9FAFB;
        padding-bottom: 0.5rem;
    }
    
    .detail-label {
        color: #4B5563;
    }
    
    .detail-value {
        font-weight: 500;
        color: #111827;
    }
    
    .detail-footer {
        margin-top: 1.5rem;
        padding-top: 1rem;
        border-top: 1px solid #E5E7EB;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    .detail-ppk-label {
        font-weight: 500;
        color: #4B5563;
        font-size: 0.95rem;
    }
    
    .detail-ppk-value {
        font-weight: 700;
        color: #10B981;
        font-size: 1.5rem;
    }
</style>
""", unsafe_allow_html=True)


# --- APPLICATION STATE & DATA FETCHING ---
try:
    df_all = database.get_all_products_prices()
except Exception as e:
    st.error(f"Ett fel uppstod vid inläsning av databasen: {e}")
    df_all = pd.DataFrame()


# --- SIDEBAR CONTROLS ---
with st.sidebar:
    st.markdown('<div class="sidebar-header">Filtrering</div>', unsafe_allow_html=True)
    
    # 1. Text Search
    search_query = st.text_input(
        "Fritextsökning",
        value="",
        placeholder="Sök på produkt eller märke...",
        help="Filtrerar tabellen baserat på produktnamn och varumärke."
    )
    
    # 2. Store Selection
    st.markdown("**Vald butik:** Hemköp")
    selected_stores = ["Hemköp"]
        
    # 3. Category Multi-select
    if not df_all.empty and "Kategori" in df_all.columns:
        all_categories = sorted(df_all["Kategori"].dropna().unique().tolist())
    else:
        all_categories = []
        
    selected_categories = st.multiselect(
        "Kategorier",
        options=all_categories,
        default=all_categories
    )
    
    # 5. Numerical Sliders
    max_price = st.slider(
        "Maxpris (SEK)",
        min_value=5.0,
        max_value=150.0,
        value=120.0,
        step=5.0
    )
    
    min_protein = st.slider(
        "Minsta protein per 100g (g)",
        min_value=0.0,
        max_value=30.0,
        value=0.0,
        step=1.0
    )


# --- MAIN HEADER PANEL ---
st.markdown('<h1 class="app-title">Protein Per Krona (PPK)</h1>', unsafe_allow_html=True)
total_products = len(df_all) if not df_all.empty else 0
st.markdown(f'<p class="app-subtitle">Ett oberoende verktyg för att jämföra kostnadseffektiviteten hos marknadens proteinkällor. Just nu jämförs <b>{total_products}</b> analyserade produkter.</p>', unsafe_allow_html=True)


# --- COLLAPSIBLE MATHEMATICAL EXPLAINER ---
with st.expander("Beräkningsmetodik (PPK)"):
    st.markdown("""
    Protein per Krona (PPK) är ett standardiserat mätetal för att utvärdera den verkliga kostnaden för protein i en produkt.
    Det möjliggör en objektiv jämförelse mellan produkter oavsett förpackningsstorlek eller kilopris.
    """)
    st.latex(r"PPK = \frac{\text{Vikt (g)} \times \text{Protein/100g}}{100 \times \text{Pris (kr)}}")


# --- DATA FILTERING LOGIC ---
df_filtered = df_all.copy()

if not df_filtered.empty:
    if selected_categories:
        df_filtered = df_filtered[df_filtered["Kategori"].isin(selected_categories)]
    else:
        df_filtered = pd.DataFrame(columns=df_filtered.columns)
        
    if selected_stores and not df_filtered.empty:
        df_filtered = df_filtered[df_filtered["Butik"].isin(selected_stores)]
    else:
        df_filtered = pd.DataFrame(columns=df_filtered.columns)
        
    if search_query and not df_filtered.empty:
        df_filtered = df_filtered[
            df_filtered["Produkt"].str.contains(search_query, case=False, na=False) |
            df_filtered["Märke"].str.contains(search_query, case=False, na=False)
        ]
        
    if not df_filtered.empty:
        df_filtered = df_filtered[df_filtered["Pris"] <= max_price]
        df_filtered = df_filtered[df_filtered["Protein/100g"] >= min_protein]
        
    if not df_filtered.empty:
        df_filtered = df_filtered.sort_values(by="PPK", ascending=False)


# --- 1. KPI CARDS SECTION ---
st.markdown("### Topp 3 mest kostnadseffektiva valen")

if df_filtered.empty:
    st.info("Inga produkter matchar dina valda filter.")
else:
    top_3 = df_filtered.head(3)
    kpi_cols = st.columns(3)
    
    for i, (_, row) in enumerate(top_3.iterrows()):
        rank = i + 1
        with kpi_cols[i]:
            st.markdown(f"""
<div class="kpi-card">
<div class="kpi-rank-badge">{rank}</div>
<div class="kpi-title">{row['Produkt']}</div>
<div class="kpi-brand">{row['Märke']}</div>
<div class="kpi-meta-item"><span class="kpi-meta-label">Butik:</span> <span class="kpi-meta-value">{row['Butik']}</span></div>
<div class="kpi-meta-item"><span class="kpi-meta-label">Pris:</span> <span class="kpi-meta-value">{row['Pris']:.2f} kr ({row['Storlek (g)']:.0f}g)</span></div>
<div class="kpi-meta-item"><span class="kpi-meta-label">Protein/100g:</span> <span class="kpi-meta-value">{row['Protein/100g']:.1f}g</span></div>
<div class="kpi-value-container">
<span class="kpi-ppk-label">Protein per krona:</span>
<span class="kpi-ppk-value">{row['PPK']:.2f} g/kr</span>
</div>
</div>
""", unsafe_allow_html=True)


# --- 2. INTERACTIVE DATA TABLE ---
st.markdown("### Tabellöversikt")
if not df_filtered.empty:
    presentation_df = df_filtered[[
        "Produkt", "Märke", "Butik", "Pris", "Storlek (g)", "Protein/100g", "Kategori", "PPK"
    ]].copy()
    
    st.dataframe(
        presentation_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Pris": st.column_config.NumberColumn("Pris", format="%.2f kr"),
            "Storlek (g)": st.column_config.NumberColumn("Storlek (g)", format="%d g"),
            "Protein/100g": st.column_config.NumberColumn("Protein/100g", format="%.1f g"),
            "PPK": st.column_config.NumberColumn("PPK (g/kr)", format="%.2f"),
            "Kategori": st.column_config.TextColumn("Kategori")
        }
    )


# --- 3. DETAILED PRODUCT VIEW ---
st.markdown("### Detaljerad information")

if not df_all.empty:
    unique_product_names = sorted(df_all["Produkt"].unique())
    
    selected_product = st.selectbox(
        "Välj en produkt för fullständig pris- och näringsinformation:",
        options=unique_product_names,
        index=0
    )
    
    if selected_product:
        prod_df = df_all[(df_all["Produkt"] == selected_product) & (df_all["Butik"] == "Hemköp")].copy()
        
        if not prod_df.empty:
            row = prod_df.iloc[0]
            
            detail_cols = st.columns([1, 1])
            
            with detail_cols[0]:
                st.markdown(f"""
<div class="detail-card">
<div class="detail-store">Hemköp</div>
<div class="detail-title">{row['Produkt']}</div>
<div class="detail-brand">{row['Märke']}</div>

<div class="detail-row"><span class="detail-label">Konsumentpris</span><span class="detail-value">{row['Pris']:.2f} kr</span></div>
<div class="detail-row"><span class="detail-label">Förpackningsstorlek</span><span class="detail-value">{row['Storlek (g)']:.0f} g</span></div>
<div class="detail-row"><span class="detail-label">Protein per 100g</span><span class="detail-value">{row['Protein/100g']:.1f} g</span></div>
<div class="detail-row"><span class="detail-label">EAN-kod</span><span class="detail-value"><code>{row['EAN']}</code></span></div>
<div class="detail-row"><span class="detail-label">Kategori</span><span class="detail-value">{row['Kategori']}</span></div>

<div class="detail-footer">
<span class="detail-ppk-label">Protein per krona (PPK):</span>
<span class="detail-ppk-value">{row['PPK']:.2f} g/kr</span>
</div>
</div>
""", unsafe_allow_html=True)
                
            with detail_cols[1]:
                st.markdown("<p style='font-size:1rem; font-weight:500; color:#4B5563; text-align:center; margin-bottom:1rem;'>Nyckeltalsjämförelse</p>", unsafe_allow_html=True)
                chart_data = pd.DataFrame({
                    "Värde": [row['Protein/100g'], row['PPK']],
                    "Metrik": ["Protein per 100g (g)", "PPK (g/kr)"]
                })
                # Using a red color hex for the bar chart
                st.bar_chart(
                    data=chart_data,
                    x="Metrik",
                    y="Värde",
                    color="#E52421",
                    use_container_width=True
                )
        else:
            st.warning("Produkten saknas eller säljs inte på Hemköp.")
else:
    st.info("Databasen innehåller ingen information att visa.")
