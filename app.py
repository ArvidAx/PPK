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
    page_title="Protein Per Krona (PPK) - Smart Proteinjakt",
    page_icon="💪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inject custom modern CSS styling to wow the user (premium Swedish grocery theme)
# Includes Google Font 'Outfit', card glassmorphic styling, hover micro-animations, and custom borders
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
    
    /* Apply typography */
    html, body, [class*="css"], .stApp {
        font-family: 'Outfit', sans-serif;
    }
    
    /* Main title layout styling */
    .app-title {
        font-size: 2.8rem;
        font-weight: 700;
        background: linear-gradient(135deg, #005B99 0%, #00B4DB 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
        padding-top: 0.5rem;
    }
    
    .app-subtitle {
        font-size: 1.1rem;
        color: #555;
        margin-bottom: 1.8rem;
    }
    
    /* Collapsible expander header styling */
    .stExpander {
        border-radius: 8px !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.03) !important;
        border: 1px solid #eef2f5 !important;
    }
    
    /* Card design for top 3 protein sources */
    .kpi-card {
        background: radial-gradient(circle at 10% 20%, rgba(248, 250, 252, 0.95) 0%, rgba(255, 255, 255, 0.95) 90%);
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.05);
        transition: transform 0.3s ease, box-shadow 0.3s ease;
        margin-bottom: 1rem;
        border: 1px solid #e2e8f0;
    }
    
    .kpi-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 15px 30px rgba(0, 91, 153, 0.1);
    }
    
    .kpi-rank-1 {
        border-left: 6px solid #FFD700; /* Gold */
    }
    
    .kpi-rank-2 {
        border-left: 6px solid #C0C0C0; /* Silver */
    }
    
    .kpi-rank-3 {
        border-left: 6px solid #CD7F32; /* Bronze */
    }
    
    .kpi-rank-badge {
        display: inline-block;
        padding: 0.2rem 0.6rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        margin-bottom: 0.6rem;
    }
    
    .badge-1 { background-color: #FFF9E6; color: #B78A00; }
    .badge-2 { background-color: #F1F3F5; color: #495057; }
    .badge-3 { background-color: #FDF2E9; color: #A04000; }
    
    .kpi-title {
        font-size: 1.2rem;
        font-weight: 700;
        color: #1e293b;
        margin-bottom: 0.2rem;
    }
    
    .kpi-brand {
        font-size: 0.9rem;
        color: #64748b;
        margin-bottom: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .kpi-value-container {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        margin-top: 0.5rem;
        padding-top: 0.5rem;
        border-top: 1px dashed #e2e8f0;
    }
    
    .kpi-ppk-label {
        font-size: 0.85rem;
        color: #64748b;
    }
    
    .kpi-ppk-value {
        font-size: 1.6rem;
        font-weight: 700;
        color: #005B99;
    }
    
    .kpi-meta-item {
        font-size: 0.9rem;
        color: #334155;
        margin-bottom: 0.3rem;
    }
    
    /* Styling for sidebar custom elements */
    .sidebar-header {
        font-weight: 700;
        font-size: 1.2rem;
        color: #0f172a;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)


# --- APPLICATION STATE & DATA FETCHING ---
try:
    df_all = database.get_all_products_prices()
except Exception as e:
    st.error(f"Ett fel uppstod vid hämtning av data från databasen: {e}")
    df_all = pd.DataFrame()


# --- SIDEBAR CONTROLS (Swedish UI) ---
with st.sidebar:
    st.markdown('<div class="sidebar-header">🔍 Filter och inställningar</div>', unsafe_allow_html=True)
    
    # 1. Text Search (Fuzzy filter)
    search_query = st.text_input(
        "Fritextsökning",
        value="",
        placeholder="Sök på produkt eller märke...",
        help="Filtrerar listan baserat på matchningar i produktnamn eller varumärke."
    )
    
    # 2. Store Selection (Disabled - Hemköp only)
    st.markdown("**Vald butik:** 🔴 Hemköp")
    selected_stores = ["Hemköp"]
        
    # 3. Category Multi-select
    all_categories = ["Kött & Fågel", "Mejeri", "Spannmål & Kolhydrater", "Vegetabiliskt", "Ägg", "Fisk & Skaldjur", "Vegetabiliska Proteiner"]
    selected_categories = st.multiselect(
        "Kategorier",
        options=all_categories,
        default=all_categories,
        help="Välj en eller flera livsmedelskategorier att visa."
    )
    
    # 4. Processing Filter (Simplified)
    nova_options = [
        "🟢 Naturligt / Oprocessat",
        "🟡 Köksprodukt / Tillsats",
        "🟠 Processat / Konserverat",
        "🔴 Ultraprocessat / Helfabrikat"
    ]
    selected_nova_labels = st.multiselect(
        "Bearbetningsgrad",
        options=nova_options,
        default=nova_options,
        help="Filtrera baserat på hur mycket livsmedlet har industriellt bearbetats."
    )
    
    # Map selected Swedish labels to numeric values
    selected_nova_nums = []
    for label in selected_nova_labels:
        if "Naturligt" in label:
            selected_nova_nums.append(1)
        elif "Köksprodukt" in label:
            selected_nova_nums.append(2)
        elif "Processat" in label:
            selected_nova_nums.append(3)
        elif "Ultraprocessat" in label:
            selected_nova_nums.append(4)
            
    # 5. Numerical Sliders
    max_price = st.slider(
        "Maxpris (SEK)",
        min_value=5.0,
        max_value=150.0,
        value=120.0,
        step=5.0,
        help="Visa endast produkter vars pris är under eller lika med detta värde."
    )
    
    min_protein = st.slider(
        "Minsta Protein per 100g (g)",
        min_value=0.0,
        max_value=30.0,
        value=0.0,
        step=1.0,
        help="Filtrera bort produkter som innehåller mindre protein än detta gränsvärde per 100 gram."
    )


# --- MAIN HEADER PANEL ---
st.markdown('<h1 class="app-title">Protein Per Krona (PPK)</h1>', unsafe_allow_html=True)
st.markdown('<p class="app-subtitle">Hitta butikernas mest prisvärda proteinkällor – optimerad för svenska konsumenter.</p>', unsafe_allow_html=True)


# --- COLLAPSIBLE MATHEMATICAL EXPLAINER (Swedish LaTeX) ---
with st.expander("🧮 Hur beräknas Protein per Krona (PPK)? Läs den matematiska formeln"):
    st.markdown("""
    Protein per Krona (PPK) är ett standardiserat nyckeltal för att mäta hur många gram protein du får för varje krona du spenderar. 
    Det gör det otroligt enkelt att jämföra billiga bulkvaror med dyrare premiumprodukter på ett rättvist sätt.
    """)
    st.latex(r"PPK = \frac{\text{Vikt (g)} \times \text{Protein/100g}}{100 \times \text{Pris (kr)}}")
    st.markdown("""
    **Räkneexempel:**
    Om en förpackning **Milbona Kvarg** väger **500g**, kostar **16,90 kr** på Lidl, och har **11,5g protein** per 100g, blir beräkningen:
    """)
    st.latex(r"PPK = \frac{500 \times 11.5}{100 \times 16.90} = \frac{5750}{1690} \approx 3.40\text{ g protein / kr}")


# --- DATA FILTERING LOGIC ---
df_filtered = df_all.copy()

if not df_filtered.empty:
    # Apply category filter
    if selected_categories:
        df_filtered = df_filtered[df_filtered["Kategori"].isin(selected_categories)]
    else:
        df_filtered = pd.DataFrame(columns=df_filtered.columns)  # Empty if no categories selected
        
    # Apply store filter
    if selected_stores and not df_filtered.empty:
        df_filtered = df_filtered[df_filtered["Butik"].isin(selected_stores)]
    else:
        df_filtered = pd.DataFrame(columns=df_filtered.columns)  # Empty if no stores checked
        
    # Apply NOVA filter
    if selected_nova_nums and not df_filtered.empty:
        df_filtered = df_filtered[df_filtered["NOVA-Grupp"].isin(selected_nova_nums)]
    else:
        df_filtered = pd.DataFrame(columns=df_filtered.columns)  # Empty if no NOVA groups selected

    # Apply text filter (fuzzy match on Product name or Brand)
    if search_query and not df_filtered.empty:
        df_filtered = df_filtered[
            df_filtered["Produkt"].str.contains(search_query, case=False, na=False) |
            df_filtered["Märke"].str.contains(search_query, case=False, na=False)
        ]
        
    # Apply sliders
    if not df_filtered.empty:
        df_filtered = df_filtered[df_filtered["Pris"] <= max_price]
        df_filtered = df_filtered[df_filtered["Protein/100g"] >= min_protein]
        
    # Sort by PPK descending (highest first)
    if not df_filtered.empty:
        df_filtered = df_filtered.sort_values(by="PPK", ascending=False)


# --- 1. KPI CARDS SECTION (Top 3 Protein Sources) ---
st.markdown("### 🏆 Topp 3 Mest Prisvärda Proteinkällor")

if df_filtered.empty:
    st.info("Inga produkter matchar dina valda filter. Justera filtren i sidofältet för att visa resultat.")
else:
    # Extract the top 3 products matching current filters
    top_3 = df_filtered.head(3)
    
    kpi_cols = st.columns(3)
    for i, (_, row) in enumerate(top_3.iterrows()):
        rank = i + 1
        rank_badge_text = f"🥇 {rank}:a plats" if rank == 1 else f"🥈 {rank}:a plats" if rank == 2 else f"🥉 {rank}:e plats"
        badge_class = f"badge-{rank}"
        rank_class = f"kpi-rank-{rank}"
        
        with kpi_cols[i]:
            st.markdown(f"""
            <div class="kpi-card {rank_class}">
                <div class="kpi-rank-badge {badge_class}">{rank_badge_text}</div>
                <div class="kpi-title">{row['Produkt']}</div>
                <div class="kpi-brand">{row['Märke']}</div>
                <div class="kpi-meta-item">📍 <b>Butik:</b> {row['Butik']}</div>
                <div class="kpi-meta-item">💰 <b>Pris:</b> {row['Pris']:.2f} kr ({row['Storlek (g)']:.0f}g)</div>
                <div class="kpi-meta-item">🍗 <b>Protein:</b> {row['Protein/100g']:.1f}g per 100g</div>
                <div class="kpi-value-container">
                    <span class="kpi-ppk-label">Protein per krona:</span>
                    <span class="kpi-ppk-value">{row['PPK']:.2f}g/kr</span>
                </div>
            </div>
            """, unsafe_allow_html=True)


# --- 2. INTERACTIVE DATA TABLE ---
st.markdown("### 📊 Alla Matchande Produkter (sorterade efter PPK)")
if not df_filtered.empty:
    # Function to map NOVA numbers to user-friendly Swedish labels
    def map_nova_group(group_num):
        if group_num == 1:
            return "🟢 Naturligt / Oprocessat"
        elif group_num == 2:
            return "🟡 Köksprodukt"
        elif group_num == 3:
            return "🟠 Processat"
        elif group_num == 4:
            return "🔴 Ultraprocessat"
        return "Okänt"

    # Select and reorder columns for visual presentation to Swedish users
    presentation_df = df_filtered[[
        "Produkt", "Märke", "Butik", "Pris", "Storlek (g)", "Protein/100g", "NOVA-Grupp", "PPK"
    ]].copy()
    
    # Map to simplified label
    presentation_df["Bearbetning"] = presentation_df["NOVA-Grupp"].apply(map_nova_group)
    presentation_df = presentation_df.drop(columns=["NOVA-Grupp"])
    
    # Reorder to put Bearbetning in a nice place
    presentation_df = presentation_df[[
        "Produkt", "Märke", "Butik", "Pris", "Storlek (g)", "Protein/100g", "Bearbetning", "PPK"
    ]]
    
    # Render interactive DataFrame styled with high performance
    st.dataframe(
        presentation_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Pris": st.column_config.NumberColumn("Pris", format="%.2f kr"),
            "Storlek (g)": st.column_config.NumberColumn("Storlek (g)", format="%d g"),
            "Protein/100g": st.column_config.NumberColumn("Protein/100g", format="%.1f g"),
            "PPK": st.column_config.NumberColumn("PPK (g/kr)", format="%.2f"),
            "Bearbetning": st.column_config.TextColumn("Bearbetningsgrad")
        }
    )


# --- 3. DETAILED PRODUCT VIEW ---
st.markdown("### 🔍 Detaljerad Produktvy")

if not df_all.empty:
    unique_product_names = sorted(df_all["Produkt"].unique())
    
    selected_product = st.selectbox(
        "Välj en produkt för att visa detaljerad närings- och prisinformation:",
        options=unique_product_names,
        index=0,
        help="Välj en produkt för att se dess näringsvärden, EAN-kod, NOVA-grupp och Protein per Krona."
    )
    
    if selected_product:
        # Filter details for the selected product
        prod_df = df_all[(df_all["Produkt"] == selected_product) & (df_all["Butik"] == "Hemköp")].copy()
        
        if not prod_df.empty:
            row = prod_df.iloc[0]
            
            # Map NOVA group to simplified label with emoji
            nova_val = row['NOVA-Grupp']
            if nova_val == 1:
                nova_label = "🟢 Naturligt / Oprocessat"
            elif nova_val == 2:
                nova_label = "🟡 Köksprodukt / Tillsats"
            elif nova_val == 3:
                nova_label = "🟠 Processat (konserverat)"
            elif nova_val == 4:
                nova_label = "🔴 Ultraprocessat / Helfabrikat"
            else:
                nova_label = "Okänt"
                
            # Show a beautiful detailed view in 2 columns
            detail_cols = st.columns([1, 1])
            
            with detail_cols[0]:
                st.markdown(f"""
<div style="background-color: #f8fafc; border-top: 4px solid #005B99; border-radius: 8px; padding: 1.5rem; box-shadow: 0 4px 15px rgba(0,0,0,0.03); height: 100%;">
    <div style="font-size: 0.8rem; font-weight: 700; color: #005B99; text-transform: uppercase; margin-bottom: 0.3rem;">🔴 Hemköp</div>
    <div style="font-size: 1.5rem; font-weight: 700; color: #1e293b; margin-bottom: 0.5rem;">{row['Produkt']}</div>
    <div style="font-size: 0.9rem; color: #64748b; margin-bottom: 1rem; text-transform: uppercase; letter-spacing: 0.05em;">VARUMÄRKE: {row['Märke']}</div>
    
    <p style="margin: 0.3rem 0; font-size: 1rem;">💸 <b>Konsumentpris:</b> {row['Pris']:.2f} kr</p>
    <p style="margin: 0.3rem 0; font-size: 1rem;">⚖️ <b>Förpackningsstorlek:</b> {row['Storlek (g)']:.0f}g</p>
    <p style="margin: 0.3rem 0; font-size: 1rem;">🍗 <b>Protein per 100g:</b> {row['Protein/100g']:.1f}g</p>
    <p style="margin: 0.3rem 0; font-size: 1rem;">🏷️ <b>EAN-kod:</b> <code>{row['EAN']}</code></p>
    <p style="margin: 0.3rem 0; font-size: 1rem;">⚙️ <b>Bearbetningsgrad:</b> {nova_label}</p>
    <p style="margin: 0.3rem 0; font-size: 1rem;">📁 <b>Kategori:</b> {row['Kategori']}</p>
    
    <div style="margin-top: 1.2rem; padding-top: 0.8rem; border-top: 1px dashed #e2e8f0; display: flex; justify-content: space-between; align-items: center;">
        <span style="font-weight: 600; color: #64748b; font-size: 1rem;">Protein per krona (PPK):</span>
        <span style="font-weight: 800; color: #10b981; font-size: 1.6rem;">{row['PPK']:.2f} g/kr</span>
    </div>
</div>
""", unsafe_allow_html=True)
                
            with detail_cols[1]:
                # Renders a bar chart comparing this product's metrics visually
                st.markdown("<p style='font-size:1.1rem; font-weight:600; text-align:center; margin-bottom:0.8rem;'>Produktens förhållande: Protein per 100g vs PPK (g/kr)</p>", unsafe_allow_html=True)
                chart_data = pd.DataFrame({
                    "Värde": [row['Protein/100g'], row['PPK']],
                    "Metrik": ["Protein per 100g (g)", "Protein per krona (g/kr)"]
                })
                st.bar_chart(
                    data=chart_data,
                    x="Metrik",
                    y="Värde",
                    use_container_width=True
                )
        else:
            st.warning("Produkten saknas eller säljs inte på Hemköp.")
else:
    st.warning("Ingen data hittades i databasen för att utföra detaljerad produktvy.")
