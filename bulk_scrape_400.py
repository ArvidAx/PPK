import sys
import os
import re
import logging
import random
import time
from firecrawl import FirecrawlApp
from firecrawl.v2.types import JsonFormat

sys.path.append(r"c:\Users\arvid\Documents\PPK\PPK")
from scraper import HemkopProductExtractor, parse_package_size, enrich_product_with_off, upsert_scraped_data
from database import SessionLocal, Product, Store, Price

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def is_product_cached(url: str, session) -> bool:
    """
    Kontrollerar om produkten i URL:en redan har skrapats nyligen i databasen.
    """
    match = re.search(r'/produkt/[^/]+-(\w+)$', url)
    sku = None
    if match:
        sku = match.group(1).strip()
    else:
        match_num = re.search(r'/produkt/(\d+)(_\w+)?$', url)
        if match_num:
            suffix = match_num.group(2) or ""
            sku = match_num.group(1) + suffix
            
    if not sku:
        return False
        
    product = session.query(Product).filter(Product.ean == sku).first()
    if not product:
        return False
        
    store = session.query(Store).filter(Store.name == "Hemköp").first()
    if not store:
        return False
        
    price_entry = session.query(Price).filter(
        Price.product_id == product.id,
        Price.store_id == store.id
    ).first()
    
    if not price_entry:
        return False
        
    from datetime import datetime
    age = datetime.utcnow() - price_entry.last_updated
    # Om priset är nyare än 7 dagar, betrakta det som färskt
    return age.days < 7

def run_bulk_scrape_400():
    logging.info("Startar storskalig optimerad skrapning för att nyttja 400 krediter (80 nya produkter)...")
    
    api_key = os.getenv("FIRECRAWL_API_KEY") or "fc-f8511c8ea4614b14a8e0f8f13c37b3ea"
    app = FirecrawlApp(api_key=api_key)
    
    # 1. Discover URLs cheaply using Map
    logging.info("Steg 1: Hittar produkt-URL:er via Firecrawl Map...")
    try:
        map_result = app.map(
            "https://www.hemkop.se",
            search="/produkt/",
            limit=300,
            ignore_query_parameters=True
        )
    except Exception as e:
        logging.error("Kunde inte köra map: %s", e)
        return
        
    if not map_result or not hasattr(map_result, "links") or not map_result.links:
        logging.warning("Inga länkar upptäcktes.")
        return
        
    product_urls = []
    for link in map_result.links:
        url_str = str(link.url)
        if "/produkt/" in url_str:
            product_urls.append(url_str)
            
    logging.info("Hittade %d produkt-URL:er på Hemköp. Filtrerar bort cachade produkter...", len(product_urls))
    
    # 2. Check cache and filter un-cached URLs
    session = SessionLocal()
    to_scrape_urls = []
    for url in product_urls:
        if not is_product_cached(url, session):
            to_scrape_urls.append(url)
    session.close()
    
    logging.info("Hittade %d okända eller gamla produkter som behöver skrapas.", len(to_scrape_urls))
    
    if not to_scrape_urls:
        logging.info("Alla upptäckta produkter är redan uppdaterade i databasen! Inga krediter förbrukades.")
        return
        
    # 3. Scrape up to 80 products (which consumes exactly 80 * 5 = 400 credits of JSON scrapes)
    max_new_scrapes = 80
    scraped_count = 0
    
    json_format = JsonFormat(
        prompt=(
            "Extrahera detaljerad produktinformation. Hitta näringsvärdestabellen (ofta under 'Näringsvärde per 100g' "
            "eller 'Innehållsdeklaration'). Hämta protein (protein_per_100g), fett (fat_per_100g), kolhydrater "
            "(carbs_per_100g) och kalorier i kcal (calories_100g) exakt som de står på sidan. "
            "Det är kritiskt att du bevarar exakta decimaler (t.ex. 9.6 istället för 9) och absolut INTE rundar av värdena."
        ),
        schema=HemkopProductExtractor.model_json_schema()
    )
    
    for url in to_scrape_urls:
        if scraped_count >= max_new_scrapes:
            logging.info("Nådde gränsen på %d nya skrapade produkter (400 krediter använda). Avbryter skrapning.", max_new_scrapes)
            break
            
        logging.info("Skrapar (%d/%d): %s", scraped_count + 1, max_new_scrapes, url)
        
        retries = 3
        document = None
        for attempt in range(retries):
            try:
                document = app.scrape(url=url, formats=[json_format])
                break
            except Exception as e:
                wait_time = 2 ** attempt + random.uniform(0, 1)
                logging.error("Skrapning misslyckades på försök %d: %s. Försöker igen...", attempt + 1, e)
                time.sleep(wait_time)
                
        if not document or not hasattr(document, "json") or not document.json:
            logging.warning("Kunde inte skrapa produkten. Hoppar över.")
            continue
            
        raw_data = document.json
        ean = raw_data.get("ean")
        if not ean:
            continue
            
        ean = str(ean).strip()
        package_size = parse_package_size(raw_data.get("package_size_grams"), url)
        
        protein = raw_data.get("protein_per_100g")
        fat = raw_data.get("fat_per_100g")
        carbs = raw_data.get("carbs_per_100g")
        calories = raw_data.get("calories_100g")
        
        # Fallback to Open Food Facts
        needs_enrichment = (protein is None or fat is None or carbs is None or calories is None)
        off_data = None
        if needs_enrichment:
            off_data = enrich_product_with_off(ean)
            
        protein_val = protein if protein is not None else (off_data.get("protein_100g") if off_data else None)
        fat_val = fat if fat is not None else (off_data.get("fat_100g") if off_data else None)
        carbs_val = carbs if carbs is not None else (off_data.get("carbs_100g") if off_data else None)
        calories_val = calories if calories is not None else (off_data.get("calories_100g") if off_data else None)
        
        nova_group_val = off_data.get("nova_group") if off_data else None
        if nova_group_val is None:
            nova_group_val = 3
            
        protein_val = float(protein_val) if protein_val is not None else 0.0
        fat_val = float(fat_val) if fat_val is not None else 0.0
        carbs_val = float(carbs_val) if carbs_val is not None else 0.0
        calories_val = int(calories_val) if calories_val is not None else int(protein_val * 4 + carbs_val * 4 + fat_val * 9)
        
        category_val = raw_data.get("category") or "Skafferi"
        if category_val == "Kött":
            category_val = "Kött & Fågel"
        elif category_val == "Skafferi":
            category_val = "Spannmål & Kolhydrater"
            
        try:
            upsert_scraped_data(
                ean=ean,
                name=raw_data.get("name") or "Okänd produkt",
                brand=raw_data.get("brand") or "Okänt märke",
                store_name="Hemköp",
                price_sek=float(raw_data.get("price_sek", 0.0)),
                package_size_grams=package_size,
                protein_per_100g=protein_val,
                fat_per_100g=fat_val,
                carbs_per_100g=carbs_val,
                calories_100g=calories_val,
                nova_group=nova_group_val,
                category=category_val
            )
            scraped_count += 1
        except Exception as e:
            logging.error("Fel vid sparning av %s: %s", raw_data.get("name"), e)
            
        # Respektera webbplatsens servrar
        time.sleep(1.0)
        
    logging.info("Skrapning klar! Sparade %d nya produkter.", scraped_count)
    
    # 4. Run database cleanup and optimization script automatically at the end!
    logging.info("Steg 4: Kör automatisk databasrensning och optimering...")
    try:
        from run_database_cleanup import run_cleanup
        run_cleanup()
    except Exception as e:
        logging.error("Kunde inte köra underhållsskript: %s", e)

if __name__ == "__main__":
    run_bulk_scrape_400()
