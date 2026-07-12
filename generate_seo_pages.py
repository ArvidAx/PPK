import json
import os
import hashlib

def generate_html(item):
    name = item.get("name", "Okänd produkt")
    brand = item.get("brand", "Okänt märke")
    if not brand:
        brand = "Okänt märke"
    price = item.get("price_sek", 0)
    ppk = item.get("protein_per_krona", 0)
    protein = item.get("protein_per_100g", 0)
    kcal = item.get("kcal_per_100g", 0)
    store = item.get("store", "")
    
    # Använd befintlig seo_slug eller generera en säker fallback
    slug = item.get("seo_slug")
    if not slug:
        slug_raw = f"{brand}-{name}".lower().replace(" ", "-")
        slug = "".join(c for c in slug_raw if c.isalnum() or c == '-')

    html = f"""<!DOCTYPE html>
<html lang="sv">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" type="image/png" href="../favicon.png">
    <title>{name} från {brand} - Pris & Näringsvärde | PPK</title>
    <meta name="description" content="Köp {name} från {brand} billigast på {store}. Ger hela {ppk}g protein per krona. Innehåller {protein}g protein and {kcal} kcal per 100g.">
    <link rel="stylesheet" href="../style.css">
    <script type="application/ld+json">
    {{
        "@context": "https://schema.org/",
        "@type": "Product",
        "name": "{name}",
        "brand": {{
            "@type": "Brand",
            "name": "{brand}"
        }},
        "offers": {{
            "@type": "Offer",
            "priceCurrency": "SEK",
            "price": "{price}"
        }}
    }}
    </script>
    <!-- Google AdSense -->
    <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-8697286347339622"
     crossorigin="anonymous"></script>
</head>
<body>
    <nav class="navbar" aria-label="Huvudnavigation">
        <a href="../index.html" class="logo" aria-label="PPK proteinpriser.se startsida">
            <span class="logo-main">PPK</span>
            <span class="logo-domain">proteinpriser.se<span class="logo-dot">.</span></span>
        </a>
    </nav>
    <main>
        <div class="page-content" style="max-width: 800px; margin: 2rem auto; padding: 1rem;">
            <a href="../index.html" style="text-decoration: none; color: var(--accent-red); font-weight: 700; font-size: 0.95rem; display: inline-flex; align-items: center; margin-bottom: 2rem;">← Tillbaka till kalkylatorn</a>
            
            <article class="recipe-data-box" style="margin-top: 0;">
                <h1 style="font-size: 2rem; font-weight: 800; color: var(--text-main); margin-bottom: 0.5rem;">{name}</h1>
                <p style="color: var(--text-muted); margin-bottom: 2rem;">Märke: <strong>{brand}</strong> | Säljs på: <strong>{store}</strong></p>
                
                <h3 style="font-size: 1.1rem; font-weight: 800; color: var(--text-main); margin: 0 0 1rem 0;">Sammanfattning</h3>
                <div class="recipe-nutrition-grid" style="margin-bottom: 2rem;">
                    <div class="recipe-nutrition-card highlight">
                        <span class="recipe-nutrition-label">🏆 PPK</span>
                        <span class="recipe-nutrition-value highlight-red">{ppk} g/kr</span>
                    </div>
                    <div class="recipe-nutrition-card">
                        <span class="recipe-nutrition-label">💰 Pris</span>
                        <span class="recipe-nutrition-value">{price} kr</span>
                    </div>
                </div>

                <h3 style="font-size: 1.1rem; font-weight: 800; color: var(--text-main); margin: 0 0 1rem 0;">Näringsvärde (per 100g)</h3>
                <div class="recipe-nutrition-grid">
                    <div class="recipe-nutrition-card">
                        <span class="recipe-nutrition-label">💪 Protein</span>
                        <span class="recipe-nutrition-value">{protein} g</span>
                    </div>
                    <div class="recipe-nutrition-card">
                        <span class="recipe-nutrition-label">🔥 Kalorier</span>
                        <span class="recipe-nutrition-value">{kcal} kcal</span>
                    </div>
                </div>
            </article>

            <footer class="app-footer"
                style="text-align: center; padding: 2.5rem 0; border-top: 1px solid var(--border-color); margin-top: 4rem; font-size: 0.85rem; color: var(--text-muted);">
                <p>&copy; 2026 proteinpriser.se. Alla rättigheter reserverade.</p>
                <p style="margin-top: 0.5rem;">
                    <a href="../integritetspolicy.html" style="color: var(--accent-red); text-decoration: none; font-weight: 600;">Integritetspolicy</a> |
                    <a href="../anvandarvillkor.html" style="color: var(--accent-red); text-decoration: none; font-weight: 600;">Användarvillkor</a> |
                    <a href="../om-oss.html" style="color: var(--accent-red); text-decoration: none; font-weight: 600;">Om oss</a>
                </p>
            </footer>
        </div>
    </main>
</body>
</html>"""
    return slug, html

def main():
    data_path = "public/data.json"
    out_dir = "public/produkter"
    hash_path = os.path.join(out_dir, "hash_state.json")

    if not os.path.exists(data_path):
        print(f"Hittade inte {data_path}, avbryter.")
        return

    os.makedirs(out_dir, exist_ok=True)

    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Deduplicera produkter på slug, behåll den med högst protein_per_krona
    deduped_data = {}
    for item in data:
        # Generera slug
        slug = item.get("seo_slug")
        if not slug:
            brand = item.get("brand", "Okänt märke") or "Okänt märke"
            name = item.get("name", "Okänd produkt")
            slug_raw = f"{brand}-{name}".lower().replace(" ", "-")
            slug = "".join(c for c in slug_raw if c.isalnum() or c == '-')
        
        ppk = item.get("protein_per_krona", 0) or 0
        existing = deduped_data.get(slug)
        if not existing or ppk > existing.get("protein_per_krona", 0):
            item["generated_slug"] = slug
            deduped_data[slug] = item

    hash_state = {}
    if os.path.exists(hash_path):
        with open(hash_path, "r", encoding="utf-8") as f:
            hash_state = json.load(f)

    updated_count = 0

    for slug, item in deduped_data.items():
        # Skapa en stabil hash av dictionaryn
        item_str = json.dumps(item, sort_keys=True)
        item_hash = hashlib.md5(item_str.encode('utf-8')).hexdigest()

        # Jämför med sparat state (Delta-caching på slug-nivå)
        if hash_state.get(slug) == item_hash:
            continue

        # Om datan är ny eller ändrad, bygg om HTML-filen
        _, html_content = generate_html(item)
        file_path = os.path.join(out_dir, f"{slug}.html")
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        # Uppdatera statet
        hash_state[slug] = item_hash
        updated_count += 1

    # Spara ner det nya statet för morgondagens körning
    with open(hash_path, "w", encoding="utf-8") as f:
        json.dump(hash_state, f, indent=2)

    print(f"Genererade/uppdaterade {updated_count} statiska SEO-sidor.")

if __name__ == "__main__":
    main()
