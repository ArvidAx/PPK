import json
import os

def main():
    data_path = "public/data.json"
    html_path = "public/index.html"

    if not os.path.exists(data_path):
        print(f"Hittade inte {data_path}, avbryter för-rendering.")
        return

    with open(data_path, "r", encoding="utf-8") as f:
        products = json.load(f)

    # Sortera ut de 50 bästa produkterna baserat på PPK (protein_per_krona)
    top_products = sorted(
        products, 
        key=lambda x: x.get("protein_per_krona", 0) or x.get("ppk", 0), 
        reverse=True
    )[:50]

    html_rows = []
    for item in top_products:
        name = item.get("name", "Okänd produkt")
        brand = item.get("brand", "-")
        store = item.get("store", "-")
        price = item.get("price_sek", 0)
        volume = item.get("display_volume", "-")
        p_100 = item.get("protein_per_100g", 0)
        p_kcal = item.get("protein_per_100kcal", item.get("ppkcal", 0))
        ppk = item.get("protein_per_krona", item.get("ppk", 0))
        url = item.get("url", "#")
        code = item.get("code", "")
        
        # Generera matchande slug för produktsidan
        slug = item.get("seo_slug")
        if not slug:
            brand_slug = item.get("brand", "Okänt märke") or "Okänt märke"
            name_slug = item.get("name", "Okänd produkt")
            slug_raw = f"{brand_slug}-{name_slug}".lower().replace(" ", "-")
            slug = "".join(c for c in slug_raw if c.isalnum() or c == '-')
        
        detail_url = f"produkter/{slug}.html"
        store_class = "willys" if store.lower() == "willys" else "hemkop"
        ppk_class = "ppk-high" if ppk >= 2 else ("ppk-mid" if ppk >= 1 else "")

        row = f"""            <tr>
                <td><button class="add-to-list-btn" aria-label="Lägg till {name} i shoppinglistan" title="Lägg till i shoppinglistan">+</button></td>
                <td data-label="Produkt">
                    <div style="display: flex; align-items: center; gap: 8px; text-align: left;">
                        <div class="table-product-placeholder">💪</div>
                        <a href="{detail_url}" class="table-product-link" style="color: var(--text-main); font-weight: 700; text-decoration: none;">{name}</a>
                    </div>
                </td>
                <td data-label="Märke">{brand}</td>
                <td data-label="Butik"><span class="store-badge {store_class}">{store}</span></td>
                <td data-label="Pris">{price:.2f} kr</td>
                <td data-label="Storlek">{volume}</td>
                <td data-label="Protein/100g">{p_100:.1f} g</td>
                <td data-label="Prot/100 kcal">{p_kcal:.1f} g</td>
                <td data-label="PPK (g/kr)" class="{ppk_class}"><strong>{ppk:.2f}</strong></td>
                <td data-label="Länk" style="cursor: pointer;"><a href="{url}" target="_blank" rel="noopener noreferrer sponsored" class="store-link">Butik →</a></td>
            </tr>"""
        html_rows.append(row)

    joined_rows = "\n".join(html_rows)

    if not os.path.exists(html_path):
        print(f"Hittade inte {html_path}, avbryter.")
        return

    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    # Hitta positionerna för tbody-taggarna
    start_tag = '<tbody id="tableBody">'
    end_tag = '</tbody>'
    
    start_idx = html_content.find(start_tag)
    end_idx = html_content.find(end_tag, start_idx)

    if start_idx == -1 or end_idx == -1:
        print("Kunde inte hitta tbody-taggarna i index.html.")
        return

    # Injektera de nya raderna
    new_html = (
        html_content[:start_idx + len(start_tag)] + 
        "\n" + joined_rows + "\n" + 
        html_content[end_idx:]
    )

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(new_html)

    print(f"SEO-optimering klar: Investerade {len(top_products)} produkter direkt i index.html.")

if __name__ == "__main__":
    main()
