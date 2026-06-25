import json
import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(r"c:\Users\arvid\Documents\PPK\PPK")
from database import Base, Product, Store, Price, DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def import_data():
    session = SessionLocal()
    
    # 1. Clear old data
    print("Clearing old data from products and prices tables...")
    session.query(Price).delete()
    session.query(Product).delete()
    session.commit()
    print("Old data cleared.")
    
    # 2. Get or create Hemköp store
    hemkop = session.query(Store).filter(Store.name == "Hemköp").first()
    if not hemkop:
        hemkop = Store(name="Hemköp")
        session.add(hemkop)
        session.commit()

    # 3. Read both json files
    data = []
    for filename in ["resultat.json", "resultat_fler_kategorier.json"]:
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data.extend(json.load(f))
            print(f"Loaded {filename}")
        except Exception as e:
            print(f"Error loading {filename}: {e}")

    # 4. Insert data
    count = 0
    seen_eans = set()
    for item in data:
        if item.get("protein_per_100g") is None:
            continue
            
        ean = str(item.get("code") or f"NOCODE_{count}")
        if ean in seen_eans:
            continue
        seen_eans.add(ean)
            
        protein = float(item["protein_per_100g"])
        
        # Determine category based on the scraped category slug
        raw_cat = item.get("category", "")
        if "mejeri" in raw_cat:
            cat = "Mejeri"
        elif "kott" in raw_cat:
            cat = "Kött & Fågel"
        elif "fisk" in raw_cat:
            cat = "Fisk & Skaldjur"
        elif "vegetarisk" in raw_cat:
            cat = "Vegetabiliska Proteiner"
        elif "skafferi" in raw_cat:
            cat = "Spannmål & Kolhydrater"
        else:
            cat = "Övrigt"
            
        prod = Product(
            ean=ean,
            name=item.get("name") or "Okänd produkt",
            brand=item.get("brand") or "Okänt märke",
            protein_per_100g=protein,
            fat_per_100g=0.0,
            carbs_per_100g=0.0,
            calories_100g=int(protein * 4), 
            nova_group=1, # Default to un-processed for now, unless we fetch OFF
            category=cat,
            url=item.get("url")
        )
        session.add(prod)
        session.flush()

        package_size = item.get("package_weight_g") or 0.0
        price_val = item.get("price_sek") or 0.0
        
        price_entry = Price(
            product_id=prod.id,
            store_id=hemkop.id,
            price_sek=float(price_val),
            package_size_grams=float(package_size)
        )
        session.add(price_entry)
        count += 1

    session.commit()
    print(f"Imported {count} items from resultat.json into the database.")
    session.close()

if __name__ == "__main__":
    import_data()
