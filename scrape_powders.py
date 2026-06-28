import os
import re
import json
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont

# Brand color mapping for placeholders
BRAND_COLORS = {
    "core": (30, 41, 59),       # slate-800
    "tyngre": (225, 29, 72),    # rose-600
    "star": (217, 119, 6),      # amber-600
    "body science": (15, 23, 42), # dark navy
    "gaam": (16, 185, 129),     # emerald-500
}

def generate_placeholder(brand_name, filename):
    """Genererar en snygg märkesplaceholder om bildhämtningen misslyckas."""
    print(f"Genererar placeholder-bild för {brand_name} -> {filename}")
    color = BRAND_COLORS.get(brand_name.lower(), (100, 116, 139))
    
    # Skapa 400x400 bild med gradient-liknande cirklar
    img = Image.new("RGBA", (400, 400), color=color)
    draw = ImageDraw.Draw(img)
    
    # Rita snygga cirklar i bakgrunden
    draw.ellipse([30, 30, 370, 370], outline=(255, 255, 255, 25), width=6)
    draw.ellipse([60, 60, 340, 340], outline=(255, 255, 255, 40), width=4)
    draw.ellipse([90, 90, 310, 310], outline=(255, 255, 255, 60), width=2)
    
    # Skriv märkesnamnet i mitten
    text = brand_name.upper()
    
    # Försök ladda en standardtypsnitt, annars rita med standardtecken
    draw.text((200, 200), text, fill="white", align="center", anchor="mm")
    
    img.save(filename, "PNG")

def download_image(url, filename, brand_name):
    """Laddar ner en bild eller faller tillbaka på att generera en placeholder."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    try:
        print(f"Försöker ladda ner bild från {url}...")
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            with open(filename, 'wb') as f:
                f.write(r.content)
            print(f"[OK] Bild sparad till {filename}")
            return
        else:
            print(f"[VARNING] Fick HTTP {r.status_code} vid bildhämtning.")
    except Exception as e:
        print(f"[VARNING] Kunde inte hämta bild: {e}")
        
    # Skapa placeholder vid fel
    generate_placeholder(brand_name, filename)

def scrape_product(url, brand_name, fallback_price):
    """Skrapar pris och bild-URL för en produkt med fallback-värden vid fel."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "sv-SE,sv;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    
    price = fallback_price
    image_url = None
    
    try:
        print(f"\nSkrapar {url}...")
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            html = r.text
            
            def _clean(val_str):
                cleaned = val_str.replace(",", ".").strip()
                cleaned = re.sub(r'[^\d\.]', '', cleaned)
                if cleaned.endswith("."):
                    cleaned = cleaned[:-1]
                return float(cleaned)

            # 1. Prissökning (og:price, product:price, JSON-LD, CSS)
            price_match = re.search(r'property="(?:og|product):price:amount"\s+content="([\d\.,\s]+)"', html)
            if price_match:
                price = _clean(price_match.group(1))
                print(f"Hittade pris via meta-tagg: {price}")
            else:
                json_ld_matches = re.findall(r'"price":\s*"([\d\.,\s]+)"', html)
                if json_ld_matches:
                    price = _clean(json_ld_matches[0])
                    print(f"Hittade pris via JSON-LD string: {price}")
                else:
                    json_ld_num = re.findall(r'"price":\s*([\d\.,\s]+)', html)
                    if json_ld_num:
                        price = _clean(json_ld_num[0])
                        print(f"Hittade pris via JSON-LD number: {price}")
                    else:
                        # Försök hitta kr-text
                        text_price = re.search(r'class="[^"]*price[^"]*"\s*[^>]*>\s*([\d\s\.,]+)(?:kr|:-|\b)', html, re.IGNORECASE)
                        if text_price:
                            price = _clean(text_price.group(1))
                            print(f"Hittade pris via CSS/Text match: {price}")
            
            # 2. Bildsökning med BeautifulSoup (Mycket mer robust!)
            soup = BeautifulSoup(html, 'html.parser')
            meta_img = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "og:image"})
            if meta_img and meta_img.get("content"):
                image_url = meta_img["content"]
                
            # Om Gymgrossisten, kolla efter produktbilden med query params
            if "gymgrossisten.com" in url:
                for img in soup.find_all("img"):
                    src = img.get("src") or ""
                    if "Star_Nutrition" in src and "Whey80" in src:
                        image_url = src
                        break
                        
            # Om Tyngre, kolla efter centracdn-bilder
            elif "tyngre.se" in url:
                for img in soup.find_all("img"):
                    src = img.get("src") or ""
                    if "tyngre.centracdn.net" in src and "original" in src:
                        image_url = src
                        break
            
            if image_url:
                print(f"Hittade bild-URL: {image_url}")
        else:
            print(f"[VARNING] Kunde inte hämta sidan, HTTP-kod {r.status_code}. Använder fallback-pris.")
    except Exception as e:
        print(f"[FEL] Fel vid skrapning: {e}")
        
    return price, image_url

def main():
    print("=== STARTAR SKRAPNING AV PROTEINPULVER ===")
    
    # Skapa bildmapp
    img_dir = "public/images/pulver"
    os.makedirs(img_dir, exist_ok=True)
    
    products = [
        {
            "brand": "Core",
            "name": "Core Whey Protein",
            "weight_g": 1000,
            "protein_100g": 77.0,
            "kcal_100g": 390.0,
            "url": "https://www.svensktkosttillskott.se/core-whey-protein?da=1-7847,14-8",
            "fallback_price": 399.0,
            "img_filename": os.path.join(img_dir, "core.png"),
            "img_rel_path": "images/pulver/core.png",
            "store": "Svenskt Kosttillskott",
        },
        {
            "brand": "Tyngre",
            "name": "Vassle Kladdkaka",
            "weight_g": 900,
            "protein_100g": 74.0,
            "kcal_100g": 370.0,
            "url": "https://tyngre.se/kosttillskott/proteinpulver/vassle/vassle-kladdkaka",
            "fallback_price": 249.0,
            "img_filename": os.path.join(img_dir, "tyngre.png"),
            "img_rel_path": "images/pulver/tyngre.png",
            "store": "Tyngre",
        },
        {
            "brand": "Star Nutrition",
            "name": "Whey-80",
            "weight_g": 1000,
            "protein_100g": 76.0,
            "kcal_100g": 390.0,
            "url": "https://www.gymgrossisten.com/whey-80-vassleprotein-1-kg/585R.html",
            "fallback_price": 299.0,
            "img_filename": os.path.join(img_dir, "star.png"),
            "img_rel_path": "images/pulver/star.png",
            "store": "Gymgrossisten",
        },
        {
            "brand": "Body Science",
            "name": "Whey 100%",
            "weight_g": 1000,
            "protein_100g": 76.0,
            "kcal_100g": 380.0,
            "url": "https://www.mmsports.se/kosttillskott/protein/proteinpulver/body-science-whey-80-procent.html",
            "fallback_price": 269.0,
            "img_filename": os.path.join(img_dir, "mmsports.png"),
            "img_rel_path": "images/pulver/mmsports.png",
            "store": "MM Sports",
        },
        {
            "brand": "GAAM",
            "name": "100% Premium Protein",
            "weight_g": 900,
            "protein_100g": 75.0,
            "kcal_100g": 380.0,
            "url": "https://proteinbolaget.se/products/gaam-protein-900-g?variant=53576436351314",
            "fallback_price": 219.0,
            "img_filename": os.path.join(img_dir, "gaam.png"),
            "img_rel_path": "images/pulver/gaam.png",
            "store": "Proteinbolaget",
        }
    ]
    
    for p in products:
        price, img_url = scrape_product(p["url"], p["brand"], p["fallback_price"])
        
        # Ladda ner bild
        if img_url:
            download_image(img_url, p["img_filename"], p["brand"])
        else:
            generate_placeholder(p["brand"], p["img_filename"])
            
        # Beräkna PPK: (total protein i gram) / pris
        total_protein = (p["protein_100g"] / 100.0) * p["weight_g"]
        ppk = total_protein / price
        p["ppk"] = round(ppk, 2)
        p["price"] = price

    # Sortera efter PPK i fallande ordning
    products.sort(key=lambda x: x["ppk"], reverse=True)

    cards_html = []
    for p in products:
        # Skapa HTML-kort för produkten
        card = f"""
        <article class="recipe-card" style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); display: flex; flex-direction: column; transition: transform 0.2s;">
            <div class="recipe-img" style="height: 200px; display: flex; align-items: center; justify-content: center; overflow: hidden; background: #fafafa; border-radius: 8px;">
                <img src="{p["img_rel_path"]}" style="max-height: 100%; max-width: 100%; object-fit: contain;" alt="{p["name"]}">
            </div>
            <div class="recipe-content" style="padding: 1rem 0 0 0; display: flex; flex-direction: column; flex-grow: 1; gap: 0.5rem; text-align: left;">
                <div style="display: flex; justify-content: space-between; align-items: baseline;">
                    <span style="font-size: 0.8rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase;">{p["brand"]}</span>
                    <span style="font-size: 0.8rem; color: var(--text-muted);">{p["weight_g"]}g</span>
                </div>
                <h2 style="font-size: 1.2rem; font-weight: 800; color: var(--text-main); margin: 0; line-height: 1.3;">{p["name"]}</h2>
                
                <div style="display: flex; gap: 0.5rem; margin: 0.5rem 0; flex-wrap: wrap;">
                    <span style="background: #fee2e2; color: #e11d48; padding: 0.25rem 0.5rem; border-radius: 6px; font-weight: 700; font-size: 0.85rem;">🏆 {p["ppk"]} g/kr</span>
                    <span style="background: #f1f5f9; color: var(--text-main); padding: 0.25rem 0.5rem; border-radius: 6px; font-weight: 600; font-size: 0.85rem;">💰 {p["price"]} kr</span>
                </div>
                
                <div style="font-size: 0.85rem; color: var(--text-muted); line-height: 1.5; margin-bottom: 1rem;">
                    <div style="display: flex; justify-content: space-between; border-bottom: 1px dashed var(--border-color); padding: 0.25rem 0;">
                        <span>💪 Protein per 100g</span>
                        <span style="font-weight: 600; color: var(--text-main);">{p["protein_100g"]}g</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 0.25rem 0;">
                        <span>🔥 Kalorier per 100g</span>
                        <span style="font-weight: 600; color: var(--text-main);">{p["kcal_100g"]} kcal</span>
                    </div>
                </div>
                
                <div style="margin-top: auto; padding-top: 0.75rem; border-top: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-size: 0.8rem; color: var(--text-muted);">{p["store"]}</span>
                    <a href="{p["url"]}" target="_blank" rel="noopener" style="font-size: 0.85rem; font-weight: 700; color: var(--accent-red); text-decoration: none; display: inline-flex; align-items: center; gap: 0.25rem;">Köp här →</a>
                </div>
            </div>
        </article>"""
        cards_html.append(card)

    cards_joint = "\n".join(cards_html)
    
    # Skapa hela HTML-sidan
    html_page = f"""<!DOCTYPE html>
<html lang="sv">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" type="image/png" href="favicon.png">
    <title>Jämför Proteinpulver - Bästa PPK Online | PPK</title>
    <meta name="description" content="Jämför och hitta marknadens billigaste proteinpulver utifrån Protein Per Krona (PPK). Vi analyserar priser och näringsvärden för populära märken.">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <nav class="navbar" aria-label="Huvudnavigation">
        <a href="index.html" class="logo" aria-label="PPK proteinpriser.se startsida">
            <span class="logo-main">PPK</span>
            <span class="logo-domain">proteinpriser.se<span class="logo-dot">.</span></span>
        </a>
        <button class="hamburger-menu" aria-label="Öppna meny">☰</button>
        <nav class="nav-links">
            <ul role="list">
                <li><a href="index.html">Kalkylator</a></li>
                <li><a href="recept.html">Recept</a></li>
                <li><a href="kunskap.html">Kunskapsbank</a></li>
                <li><a href="pulver.html" class="active" aria-current="page">Proteinpulver</a></li>
            </ul>
        </nav>
    </nav>

    <div class="app-container single-column">
        <main class="main-content" style="max-width: 1000px; padding: 2.5rem 1.5rem; width: 100%; display: flex; flex-direction: column; gap: 2rem;">
            <header class="page-header hero-section" style="text-align: center; display: flex; flex-direction: column; align-items: center; background: var(--card-bg); border: 1px solid var(--border-color); border-radius: var(--radius-lg); padding: 3rem 2rem; box-shadow: var(--shadow-sm); width: 100%;">
                <h1 class="app-title" style="font-size: 2.5rem; margin-bottom: 0.75rem;">Jämför <span class="accent-red">Proteinpulver</span></h1>
                <p class="app-subtitle" style="font-size: 1.05rem; color: var(--text-muted); max-width: 750px; line-height: 1.6; margin: 0;">
                    Vi har manuellt valt ut och analyserat några av marknadens absolut populäraste proteinpulver online för att räkna ut deras exakta PPK-värde.
                </p>
            </header>

            <div class="recipe-grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 2rem; margin-top: 1rem;">
                {cards_joint}
            </div>
        </main>
    </div>

    <footer class="app-footer" style="text-align: center; padding: 2rem 0; border-top: 1px solid var(--border-color); margin-top: 4rem; font-size: 0.85rem; color: var(--text-muted);">
        <p>&copy; 2026 proteinpriser.se. Alla rättigheter reserverade. | <a href="integritetspolicy.html" style="color: var(--accent-red); text-decoration: none;">Integritetspolicy</a></p>
    </footer>

    <div id="cookie-banner" class="cookie-banner hidden" role="dialog" aria-labelledby="cookie-title" aria-describedby="cookie-desc">
        <div class="cookie-content">
            <h3 id="cookie-title">Vi använder cookies 🍪</h3>
            <p id="cookie-desc">proteinpriser.se använder cookies för att spara din inköpslista samt för anonym trafikanalys och anpassad annonsering via Google AdSense. Läs mer i vår <a href="integritetspolicy.html">integritetspolicy</a>.</p>
            <div class="cookie-buttons">
                <button id="cookie-decline" class="btn-cookie-secondary">Neka</button>
                <button id="cookie-accept" class="btn-cookie-primary">Godkänn alla</button>
            </div>
        </div>
    </div>

    <script>
        // Hamburgarmeny funktionalitet
        document.querySelector('.hamburger-menu').addEventListener('click', function() {{
            document.querySelector('.nav-links').classList.toggle('active');
        }});
    </script>
</body>
</html>"""
    
    with open("public/pulver.html", "w", encoding="utf-8") as f:
        f.write(html_page)
        
    print("\n[OK] Proteinpulversida skapad: public/pulver.html")

if __name__ == "__main__":
    main()
