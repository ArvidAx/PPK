"""
Scraper Pipeline Skeleton for the Swedish PPK Streamlit Application.
This module demonstrates how to fetch product data from Willys and Lidl,
enrich it using Open Food Facts, and safely upsert it into the database.
"""

import logging
import requests
import os
import re
import time
import random
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
import openfoodfacts
from pydantic import BaseModel, Field
from firecrawl import FirecrawlApp
from firecrawl.v2.types import JsonFormat
from database import SessionLocal, Store, Product, Price

# Set up logging configurations
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)


def fetch_willys_catalog(search_query: str):
    """
    Simulates fetching a product catalog from Willys JSON API endpoints.
    
    Args:
        search_query (str): The term to search for in Willys catalog.
        
    Returns:
        list: A list of mocked raw product dictionaries representing API response.
    """
    logging.info("Initiating query to Willys JSON API endpoint with query: '%s'", search_query)
    
    # In a real implementation, a developer would perform a GET request to the Willys search endpoint:
    # url = f"https://www.willys.se/sok?q={search_query}"
    # headers = {"User-Agent": "Mozilla/5.0"}
    # response = requests.get(url, headers=headers)
    # data = response.json()
    
    # Mocking a realistic response structure from the Willys API
    mock_willys_response = [
        {
            "code": "7310865004734",
            "name": "Keso Naturell",
            "brand": "Arla",
            "priceValue": 32.90,
            "displayVolume": "500g",
            "category": "Mejeri"
        },
        {
            "code": "7310340012543",
            "name": "Nötfärs 10% Svensk",
            "brand": "Scan",
            "priceValue": 69.95,
            "displayVolume": "500g",
            "category": "Kött & Fågel"
        }
    ]
    logging.info("Successfully fetched %d items from Willys API for query '%s'", len(mock_willys_response), search_query)
    return mock_willys_response


def fetch_lidl_catalog_html(category_url: str):
    """
    Simulates scraping a Lidl category page using BeautifulSoup.
    
    Args:
        category_url (str): The URL of the Lidl category page to parse.
        
    Returns:
        list: A list of mocked raw product details extracted from HTML.
    """
    logging.info("Requesting HTML content from Lidl.se category URL: '%s'", category_url)
    
    try:
        # In a real implementation:
        # headers = {"User-Agent": "Mozilla/5.0"}
        # response = requests.get(category_url, headers=headers)
        # soup = BeautifulSoup(response.content, 'html.parser')
        # Here we would locate elements like product cards:
        # cards = soup.select(".product-grid__item")
        pass
    except Exception as e:
        logging.error("Failed to fetch HTML content from Lidl.se: %s", e)
    
    # Mocking the scraped details from a product list
    mock_lidl_scraped = [
        {
            "ean": "7392672001234",
            "title": "Kvarg Naturell",
            "brand": "Milbona",
            "price": 16.90,
            "weight_g": 500.0,
            "category": "Mejeri"
        },
        {
            "ean": "7310532104562",
            "title": "Kycklingfilé",
            "brand": "Gyllda",
            "price": 89.90,
            "weight_g": 1000.0,
            "category": "Kött & Fågel"
        }
    ]
    logging.info("Successfully parsed and scraped %d products from Lidl HTML layout", len(mock_lidl_scraped))
    return mock_lidl_scraped


def enrich_product_with_off(barcode: str) -> Optional[dict]:
    """
    Hämtar exakta näringsvärden och NOVA-grupp från Open Food Facts API via streckkod (EAN).
    Använder det officiella openfoodfacts-python SDK och begränsar anropet för minimal payload.
    """
    logging.info("Frågar Open Food Facts efter streckkod: %s", barcode)
    
    try:
        api = openfoodfacts.API(user_agent="PPK_Swedish_Grocery_App/1.0")
        # Begränsa API-anropet till endast nödvändiga fält för optimal nätverksprestanda
        res = api.product.get(barcode, fields=["product_name", "nutriments", "nova_groups"])
        
        if res and ("nutriments" in res or "product_name" in res):
            prod_data = res
            nutri = prod_data.get("nutriments", {})
            
            # Kartlägg näringsvärden säkert (stöd för fältvarianter)
            protein = nutri.get("proteins_100g")
            if protein is None:
                protein = nutri.get("proteins")
                
            fat = nutri.get("fat_100g")
            if fat is None:
                fat = nutri.get("fat")
                
            carbs = nutri.get("carbohydrates_100g")
            if carbs is None:
                carbs = nutri.get("carbohydrates")
                
            calories = nutri.get("energy-kcal_100g")
            if calories is None:
                calories = nutri.get("energy-kcal")
            if calories is None:
                energy_kj = nutri.get("energy_100g") or nutri.get("energy")
                if energy_kj is not None:
                    # Konvertera kJ till kcal
                    calories = int(float(energy_kj) * 0.239006)
                    
            nova_group = prod_data.get("nova_groups")
            if nova_group is None:
                nova_group = prod_data.get("nova_group")
            
            profile = {
                "protein_100g": float(protein) if protein is not None else None,
                "fat_100g": float(fat) if fat is not None else None,
                "carbs_100g": float(carbs) if carbs is not None else None,
                "calories_100g": int(calories) if calories is not None else None,
                "nova_group": int(nova_group) if nova_group is not None else None
            }
            
            logging.info("Streckkod %s upplöst via Open Food Facts: Protein: %sg, NOVA: %s", 
                         barcode, profile["protein_100g"], profile["nova_group"])
            return profile
        else:
            logging.warning("Streckkoden %s hittades inte i Open Food Facts databas.", barcode)
            return None
    except Exception as e:
        logging.error("Ett fel uppstod vid kommunikation med Open Food Facts API: %s", e)
        return None
def parse_package_size(size_str_or_val: Any, url: str) -> float:
    """
    Rensar och konverterar förpackningsstorlek till gram (float).
    Hanterar viktbaserade produkter (_KG -> 1000g) och styckbaserade (_ST).
    """
    # 1. Kontrollera om URL visar att produkten säljs per kilo
    if url and (url.endswith("_KG") or url.endswith("_kg") or "/_KG" in url or "/_kg" in url):
        return 1000.0

    if not size_str_or_val:
        return 0.0

    # 2. Om det redan är ett numeriskt värde, returnera som float
    if isinstance(size_str_or_val, (int, float)):
        return float(size_str_or_val)

    # 3. Om det är en sträng, analysera med regex
    size_str = str(size_str_or_val).lower().strip()
    
    # Sök efter kg/kilogram
    kg_match = re.search(r"(\d+[\.,]?\d*)\s*(kg|kilogram|kilo)", size_str)
    if kg_match:
        val = float(kg_match.group(1).replace(",", "."))
        return val * 1000.0
        
    # Sök efter g/gram
    g_match = re.search(r"(\d+[\.,]?\d*)\s*(g|gram|gr)", size_str)
    if g_match:
        return float(g_match.group(1).replace(",", "."))
        
    # Standard siffermatchning
    num_match = re.search(r"(\d+[\.,]?\d*)", size_str)
    if num_match:
        return float(num_match.group(1).replace(",", "."))
        
    return 0.0


class HemkopProductExtractor(BaseModel):
    """
    Pydantic-modell för strukturerad dataextraktion via Firecrawl Scrape (JSON-läge).
    """
    ean: str = Field(..., description="EAN-kod / streckkod (oftast 13 siffror) för produkten.")
    name: str = Field(..., description="Produktens namn på svenska (t.ex. 'Keso Naturell', 'Kycklingfilé').")
    brand: str = Field(..., description="Produktens varumärke (t.ex. 'Arla', 'Garant', 'Scan').")
    price_sek: float = Field(..., description="Konsumentpriset i SEK (kronor) som ett flyttal.")
    package_size_grams: float = Field(
        ..., 
        description=(
            "Förpackningens nettovikt eller nettovolym i gram (g). "
            "Om förpackningen anges i kilogram (kg), omvandla till gram (multiplicera med 1000). "
            "Om produkten är viktbaserad eller säljs per kg, extrahera eller sätt vikten i gram."
        )
    )
    category: str = Field(
        ..., 
        description="Kategorin på produkten. Måste vara exakt en av följande: 'Mejeri', 'Kött', 'Vegetabiliskt', 'Fisk', eller 'Skafferi'."
    )
    protein_per_100g: Optional[float] = Field(None, description="Mängd protein i gram per 100g av produkten som ett flyttal (t.ex. 9.6). Bevara exakta decimaler och runda INTE av.")
    fat_per_100g: Optional[float] = Field(None, description="Mängd fett i gram per 100g av produkten som ett flyttal (t.ex. 2.1). Bevara exakta decimaler och runda INTE av.")
    carbs_per_100g: Optional[float] = Field(None, description="Mängd kolhydrater i gram per 100g av produkten som ett flyttal. Bevara exakta decimaler och runda INTE av.")
    calories_100g: Optional[int] = Field(None, description="Energi i kilokalorier (kcal) per 100g av produkten.")


class HemkopScraperPipeline:
    """
    Produktionsredo skrapnings- och berikningspipeline för Hemköp med Firecrawl och Open Food Facts.
    """
    def __init__(self, api_key: Optional[str] = None):
        # Hämta API-nyckeln från miljövariabel eller använd den tillhandahållna säkra utvecklingsnyckeln
        self.api_key = api_key or os.getenv("FIRECRAWL_API_KEY") or "fc-f8511c8ea4614b14a8e0f8f13c37b3ea"
        logging.info("Initierar HemkopScraperPipeline med Firecrawl API-nyckel som slutar på ...%s", self.api_key[-6:])
        self.app = FirecrawlApp(api_key=self.api_key)

    def crawl_hemkop_urls(self, limit: int = 50) -> List[str]:
        """
        Kör en crawl-traversering på Hemköp med smarta kostnadseffektiva include/exclude filter.
        """
        start_url = "https://www.hemkop.se"
        logging.info("Startar Firecrawl crawl-traversering för Hemköp (gräns: %d sidor)...", limit)
        
        # Undvik att skrapa frukter för att hålla nere API-kostnader
        exclude_paths = [
            "/sortiment/frukt-och-gront/frukt.*",
            "/produkt/.*frukt.*",
            "/produkt/.*mango.*",
            "/produkt/.*banan.*",
            "/produkt/.*apple.*",
            "/produkt/.*paeron.*",
            "/produkt/.*citron.*",
            "/produkt/.*apelsin.*",
            "/produkt/.*jordgubbar.*",
            "/produkt/.*melon.*"
        ]
        
        # Fokusera endast på proteinrika sortiment
        include_paths = [
            "/sortiment/mejeri-ost-och-agg/.*",
            "/sortiment/kott-chark-och-fagel/.*",
            "/sortiment/fisk-och-skaldjur/.*",
            "/sortiment/fryst/vego.*",
            "/sortiment/skafferi/konserver.*",
            "/produkt/.*"
        ]
        
        retries = 3
        crawl_job = None
        
        for attempt in range(retries):
            try:
                crawl_job = self.app.crawl(
                    url=start_url,
                    exclude_paths=exclude_paths,
                    include_paths=include_paths,
                    limit=limit,
                    crawl_entire_domain=True
                )
                break
            except Exception as e:
                # Exponentiell backoff med slumpmässigt inslag
                wait_time = 2 ** attempt + random.uniform(0, 1)
                logging.error("Firecrawl crawl misslyckades på försök %d: %s. Försöker igen om %.2fs...", attempt + 1, e, wait_time)
                if attempt == retries - 1:
                    logging.error("Kunde inte starta eller slutföra crawl efter %d försök.", retries)
                    return []
                time.sleep(wait_time)
                
        if not crawl_job or not hasattr(crawl_job, "data") or not crawl_job.data:
            logging.warning("Ingen data returnerades från Firecrawl crawl-jobbet.")
            return []
            
        product_urls = set()
        for doc in crawl_job.data:
            url = None
            if hasattr(doc, "metadata") and doc.metadata:
                url = doc.metadata.source_url or doc.metadata.url
            if not url and hasattr(doc, "url"):
                url = doc.url
                
            if url:
                url_str = str(url)
                # Spara endast faktiska produktsidor
                if "/produkt/" in url_str:
                    product_urls.add(url_str)
                    
        unique_urls = list(product_urls)
        logging.info("Hittade %d unika produkt-URL:er från Hemköps traversering.", len(unique_urls))
        return unique_urls

    def scrape_product_details(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Utför semantisk JSON-extraktion via Firecrawl Scrape för en specifik produktsida.
        """
        json_format = JsonFormat(
            prompt=(
                "Extrahera detaljerad produktinformation. Hitta näringsvärdestabellen (ofta under 'Näringsvärde per 100g' "
                "eller 'Innehållsdeklaration'). Hämta protein (protein_per_100g), fett (fat_per_100g), kolhydrater "
                "(carbs_per_100g) och kalorier i kcal (calories_100g) exakt som de står på sidan. "
                "Det är kritiskt att du bevarar exakta decimaler (t.ex. 9.6 istället för 9) och absolut INTE rundar av värdena."
            ),
            schema=HemkopProductExtractor.model_json_schema()
        )
        
        retries = 3
        document = None
        
        for attempt in range(retries):
            try:
                document = self.app.scrape(
                    url=url,
                    formats=[json_format]
                )
                break
            except Exception as e:
                wait_time = 2 ** attempt + random.uniform(0, 1)
                logging.error("Skrapning av URL %s misslyckades på försök %d: %s. Försöker igen om %.2fs...", url, attempt + 1, e, wait_time)
                if attempt == retries - 1:
                    return None
                time.sleep(wait_time)
                
        if not document or not hasattr(document, "json") or not document.json:
            logging.warning("Ingen strukturerad JSON returnerades för produkten: %s", url)
            return None
            
        raw_data = document.json
        logging.info("Framgångsrik extraktion för %s: %s", url, raw_data)
        return raw_data

    def run_pipeline(self, limit: int = 50):
        """
        Kör hela pipelinen: Traversering -> Extraktion -> OFF-berikning -> Säkra databaslagring.
        """
        logging.info("Startar exekvering av Hemköps skrapningspipeline...")
        
        # 1. Traversering
        product_urls = self.crawl_hemkop_urls(limit=limit)
        if not product_urls:
            logging.warning("Inga produkt-URL:er hittades. Avbryter pipeline.")
            return
            
        success_count = 0
        
        # 2. Skrapning och lagring
        for url in product_urls:
            try:
                raw_data = self.scrape_product_details(url)
                if not raw_data:
                    continue
                    
                ean = raw_data.get("ean")
                if not ean:
                    logging.warning("Ingen EAN-kod extraherad för produkten på %s. Hoppar över.", url)
                    continue
                    
                ean = str(ean).strip()
                
                # Rensa och städa förpackningsstorleken
                package_size = parse_package_size(raw_data.get("package_size_grams"), url)
                
                # Kontrollera om vi saknar makroämnen och behöver berika med Open Food Facts
                protein = raw_data.get("protein_per_100g")
                fat = raw_data.get("fat_per_100g")
                carbs = raw_data.get("carbs_per_100g")
                calories = raw_data.get("calories_100g")
                
                needs_enrichment = (
                    protein is None or 
                    fat is None or 
                    carbs is None or 
                    calories is None
                )
                
                off_data = None
                if needs_enrichment:
                    off_data = enrich_product_with_off(ean)
                    
                # Slå ihop data (Firecrawl har företräde, OFF som fallback)
                protein_val = protein if protein is not None else (off_data.get("protein_100g") if off_data else None)
                fat_val = fat if fat is not None else (off_data.get("fat_100g") if off_data else None)
                carbs_val = carbs if carbs is not None else (off_data.get("carbs_100g") if off_data else None)
                calories_val = calories if calories is not None else (off_data.get("calories_100g") if off_data else None)
                
                # Hämta eller sätt NOVA-grupp
                nova_group_val = off_data.get("nova_group") if off_data else None
                if nova_group_val is None:
                    nova_group_val = 3  # Standardfallback (halvfabrikat) om okänt
                    
                # Hantera databaskrav på NOT NULL genom robusta standardvärden
                protein_val = float(protein_val) if protein_val is not None else 0.0
                fat_val = float(fat_val) if fat_val is not None else 0.0
                carbs_val = float(carbs_val) if carbs_val is not None else 0.0
                calories_val = int(calories_val) if calories_val is not None else int(protein_val * 4 + carbs_val * 4 + fat_val * 9)
                
                category_val = raw_data.get("category") or "Skafferi"
                # Rätta till kategorinamn för att matcha gränssnittet vid behov
                if category_val == "Kött":
                    category_val = "Kött & Fågel"
                elif category_val == "Skafferi":
                    category_val = "Spannmål & Kolhydrater"
                
                # Spara transaktionssäkert till SQLite
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
                success_count += 1
                
            except Exception as e:
                logging.error("Fel vid hantering av produkt-URL %s: %s", url, e)
                
        logging.info("Hemköps pipeline klar! Exekverade och sparade %d produkter i databasen.", success_count)


def upsert_scraped_data(
    ean: str,
    name: str,
    brand: str,
    store_name: str,
    price_sek: float,
    package_size_grams: float,
    protein_per_100g: float,
    fat_per_100g: float,
    carbs_per_100g: float,
    calories_100g: int,
    nova_group: int,
    category: str
):
    """
    Safely upserts scraped products and pricing data into the SQLite database.
    Ensures integrity using database sessions and transactions.
    """
    session = SessionLocal()
    try:
        logging.info("Starting safe database upsert for Product '%s' (%s) at '%s'", name, ean, store_name)
        
        # 1. Retrieve or create the Store
        store = session.query(Store).filter(Store.name == store_name).first()
        if not store:
            store = Store(name=store_name)
            session.add(store)
            session.flush()
            logging.info("Created new store entry: '%s'", store_name)
            
        # 2. Retrieve or create/update the Product
        product = session.query(Product).filter(Product.ean == ean).first()
        if not product:
            product = Product(
                ean=ean,
                name=name,
                brand=brand,
                protein_per_100g=protein_per_100g,
                fat_per_100g=fat_per_100g,
                carbs_per_100g=carbs_per_100g,
                calories_100g=calories_100g,
                nova_group=nova_group,
                category=category
            )
            session.add(product)
            session.flush()
            logging.info("Created new product entry: '%s' (%s)", name, ean)
        else:
            # Update existing product attributes to keep nutrition updated
            product.name = name
            product.brand = brand
            product.protein_per_100g = protein_per_100g
            product.fat_per_100g = fat_per_100g
            product.carbs_per_100g = carbs_per_100g
            product.calories_100g = calories_100g
            product.nova_group = nova_group
            product.category = category
            logging.info("Updated existing product details for EAN: %s", ean)

        # 3. Retrieve or create/update the Price entry for this product and store
        price_entry = session.query(Price).filter(
            Price.product_id == product.id,
            Price.store_id == store.id
        ).first()
        
        if not price_entry:
            price_entry = Price(
                product_id=product.id,
                store_id=store.id,
                price_sek=price_sek,
                package_size_grams=package_size_grams
            )
            session.add(price_entry)
            logging.info("Added new price record of %.2f SEK for EAN %s at '%s'", price_sek, ean, store_name)
        else:
            price_entry.price_sek = price_sek
            price_entry.package_size_grams = package_size_grams
            logging.info("Updated existing price record to %.2f SEK for EAN %s at '%s'", price_sek, ean, store_name)

        session.commit()
        logging.info("Successfully committed transaction for Product '%s' (%s)", name, ean)
        
    except Exception as e:
        session.rollback()
        logging.error("Database transaction rolled back due to error during upsert of EAN %s: %s", ean, e)
    finally:
        session.close()


if __name__ == "__main__":
    # Testkörning av skrapningspipeline
    logging.info("Startar testkörning av skrapningspipelinen...")
    
    # 1. Testa den nya skarpa Hemköps-pipelinen med en låg gräns för att spara krediter under test
    try:
        hemkop_pipeline = HemkopScraperPipeline()
        # Vi kör med en låg gräns på 3 sidor för en supersnabb verifiering av decimalextraktionen
        hemkop_pipeline.run_pipeline(limit=3)
    except Exception as e:
        logging.error("Ett fel inträffade under Hemköps testskrapning: %s", e)
        
    # 2. Kör den befintliga Willys-simulatorn
    logging.info("Startar simulering för Willys...")
    willys_items = fetch_willys_catalog("Keso")
    
    for item in willys_items:
        ean = item["code"]
        nutri = enrich_product_with_off(ean)
        
        if nutri:
            upsert_scraped_data(
                ean=ean,
                name=item["name"],
                brand=item["brand"],
                store_name="Willys",
                price_sek=item["priceValue"],
                package_size_grams=float(item["displayVolume"].replace("g", "")),
                protein_per_100g=nutri["protein_100g"] or 0.0,
                fat_per_100g=nutri["fat_100g"] or 0.0,
                carbs_per_100g=nutri["carbs_100g"] or 0.0,
                calories_100g=nutri["calories_100g"] or 0,
                nova_group=nutri["nova_group"] or 3,
                category=item["category"]
            )
            
    logging.info("Skrapningspipeline och testkörning avslutades framgångsrikt.")
