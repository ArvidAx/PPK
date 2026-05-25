import sys
import os
import re
import logging
import sqlite3
import openfoodfacts

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def run_cleanup():
    db_path = r"c:\Users\arvid\Documents\PPK\PPK\ppk_database.db"
    if not os.path.exists(db_path):
        logging.error(f"Database not found at {db_path}")
        return
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Delete non-food items
    non_food_keywords = [
        "tvättmedel", "sköljmedel", "maskindisk", "diskmedel", "blöja", "blöjor", 
        "tvål", "schampo", "balsam", "tampong", "binda", "bindor", "tandkräm", 
        "tandborste", "rakhyvel", "hundmat", "kattmat", "tvätt", "disk", "tvål",
        "snus", "portionssnus", "lössnus", "oil", "tallrik", "spray", "allrengöring", "party"
    ]
    logging.info("Step 1: Removing non-food items...")
    deleted_non_food = 0
    for kw in non_food_keywords:
        cursor.execute("SELECT id, name FROM products WHERE name LIKE ?", (f"%{kw}%",))
        for row in cursor.fetchall():
            pid, name = row
            logging.info(f"Deleting non-food item: {name} (ID: {pid})")
            cursor.execute("DELETE FROM prices WHERE product_id = ?", (pid,))
            cursor.execute("DELETE FROM products WHERE id = ?", (pid,))
            deleted_non_food += 1
            
    # Also delete anything in the 'Övrigt' category as it contains miscellaneous non-food scrapes
    cursor.execute("SELECT id, name FROM products WHERE category = 'Övrigt'")
    for row in cursor.fetchall():
        pid, name = row
        logging.info(f"Deleting non-food item from category 'Övrigt': {name} (ID: {pid})")
        cursor.execute("DELETE FROM prices WHERE product_id = ?", (pid,))
        cursor.execute("DELETE FROM products WHERE id = ?", (pid,))
        deleted_non_food += 1
            
    conn.commit()
    logging.info(f"Deleted {deleted_non_food} non-food items.")
    
    # 2. Recategorize vegetables/fruits misclassified as 'Spannmål & Kolhydrater' or others
    logging.info("Step 2: Recategorizing vegetables/fruits...")
    # Map category 'Frukt' to 'Vegetabiliskt'
    cursor.execute("UPDATE products SET category = 'Vegetabiliskt' WHERE category = 'Frukt'")
    
    vegetable_keywords = [
        "tomat", "potatis", "lök", "morot", "paprika", "vitlök", "sallad", "gurka", 
        "citron", "äpple", "banan", "apelsin", "päron", "ingefära", "radis", "zucchini", "purjo", "mango"
    ]
    recategorized = 0
    for kw in vegetable_keywords:
        cursor.execute("SELECT id, name, category FROM products WHERE name LIKE ? AND category != 'Vegetabiliskt'", (f"%{kw}%",))
        for row in cursor.fetchall():
            pid, name, cat = row
            logging.info(f"Recategorizing '{name}' from '{cat}' to 'Vegetabiliskt'")
            cursor.execute("UPDATE products SET category = 'Vegetabiliskt' WHERE id = ?", (pid,))
            recategorized += 1
    conn.commit()
    logging.info(f"Recategorized {recategorized} items.")
    
    # 3. Smarter deduplication based on Name, Brand, and Package Size
    logging.info("Step 3: Deduplicating products...")
    # Fetch all products and their price details
    cursor.execute("""
        SELECT p.id, p.ean, p.name, p.brand, pr.package_size_grams, pr.price_sek, pr.store_id 
        FROM products p
        LEFT JOIN prices pr ON p.id = pr.product_id
    """)
    products = cursor.fetchall()
    
    # Group products by (name, brand, package_size)
    groups = {}
    for row in products:
        pid, ean, name, brand, size, price, store_id = row
        if not size:
            size = 0.0
        # Normalize keys
        key = (name.lower().strip(), brand.lower().strip(), size)
        if key not in groups:
            groups[key] = []
        groups[key].append({
            "id": pid,
            "ean": ean,
            "name": name,
            "brand": brand,
            "size": size,
            "price": price,
            "store_id": store_id
        })
        
    def ean_quality(ean: str) -> int:
        ean = str(ean).strip()
        if '_' in ean:
            return 0  # SKU with suffix like _ST
        if not ean.isdigit():
            return 1  # Contains non-digits
        if len(ean) == 9 and ean.startswith("10"):
            return 2  # Hemköp SKU
        if len(ean) in [8, 12, 13, 14]:
            return 4  # Standard EAN-8, EAN-12, EAN-13, EAN-14
        return 3  # Other numeric
        
    deleted_duplicates = 0
    for key, prods in groups.items():
        if len(prods) > 1:
            # We have duplicates!
            # Sort by EAN quality descending so the best EAN is first
            prods.sort(key=lambda x: ean_quality(x["ean"]), reverse=True)
            to_keep = prods[0]
            to_delete = prods[1:]
            
            logging.info(f"Deduplicating group: '{to_keep['name']}' ({to_keep['brand']}, {to_keep['size']}g)")
            logging.info(f"  Keeping: EAN {to_keep['ean']} (ID: {to_keep['id']})")
            
            # Keep track of store prices for to_keep
            cursor.execute("SELECT store_id FROM prices WHERE product_id = ?", (to_keep["id"],))
            kept_store_ids = {r[0] for r in cursor.fetchall()}
            
            for p_del in to_delete:
                # If deleted product has a price at a store we don't have, transfer it
                if p_del["store_id"] and p_del["store_id"] not in kept_store_ids:
                    logging.info(f"  Transferring price from duplicate EAN {p_del['ean']} for store {p_del['store_id']} to kept product")
                    cursor.execute("UPDATE prices SET product_id = ? WHERE product_id = ? AND store_id = ?", 
                                   (to_keep["id"], p_del["id"], p_del["store_id"]))
                    kept_store_ids.add(p_del["store_id"])
                
                # Delete the duplicate product and any remaining prices
                logging.info(f"  Deleting duplicate: EAN {p_del['ean']} (ID: {p_del['id']})")
                cursor.execute("DELETE FROM prices WHERE product_id = ?", (p_del["id"],))
                cursor.execute("DELETE FROM products WHERE id = ?", (p_del["id"],))
                deleted_duplicates += 1
                
    conn.commit()
    logging.info(f"Deleted {deleted_duplicates} duplicate records.")
    
    # 4. Open Food Facts enrichment for zero-protein products
    logging.info("Step 4: Enriching zero-protein products from Open Food Facts...")
    cursor.execute("SELECT id, ean, name, category FROM products WHERE protein_per_100g = 0.0")
    zero_p_prods = cursor.fetchall()
    logging.info(f"Found {len(zero_p_prods)} products with 0.0g protein.")
    
    api = openfoodfacts.API(user_agent="PPK_Swedish_Grocery_App/1.0 (arvid@example.com)")
    
    def clean_ean(ean: str) -> str:
        s = str(ean).strip()
        s = re.sub(r'_(st|kg|st|kg)$', '', s, flags=re.IGNORECASE)
        if len(s) == 14 and s.startswith("0"):
            s = s[1:]
        return s
        
    enriched_count = 0
    for row in zero_p_prods:
        pid, ean, name, cat = row
        cleaned = clean_ean(ean)
        
        # Only query OFF if cleaned EAN is numeric and at least 8 digits
        if not cleaned.isdigit() or len(cleaned) < 8:
            continue
            
        try:
            logging.info(f"Querying OFF for: '{name}' (EAN: {ean} -> {cleaned})")
            res = api.product.get(cleaned, fields=["product_name", "nutriments", "nova_groups"])
            
            if res and ("nutriments" in res or "product_name" in res):
                nutri = res.get("nutriments", {})
                protein = nutri.get("proteins_100g") or nutri.get("proteins")
                fat = nutri.get("fat_100g") or nutri.get("fat")
                carbs = nutri.get("carbohydrates_100g") or nutri.get("carbohydrates")
                calories = nutri.get("energy-kcal_100g") or nutri.get("energy-kcal")
                
                updates = []
                params = []
                
                if protein is not None:
                    updates.append("protein_per_100g = ?")
                    params.append(float(protein))
                if fat is not None:
                    updates.append("fat_per_100g = ?")
                    params.append(float(fat))
                if carbs is not None:
                    updates.append("carbs_per_100g = ?")
                    params.append(float(carbs))
                if calories is not None:
                    updates.append("calories_100g = ?")
                    params.append(int(calories))
                else:
                    energy_kj = nutri.get("energy_100g") or nutri.get("energy")
                    if energy_kj is not None:
                        updates.append("calories_100g = ?")
                        params.append(int(float(energy_kj) * 0.239006))
                        
                nova = res.get("nova_groups") or res.get("nova_group")
                if nova is not None:
                    updates.append("nova_group = ?")
                    params.append(int(nova))
                    
                if updates:
                    params.append(pid)
                    sql = f"UPDATE products SET {', '.join(updates)} WHERE id = ?"
                    cursor.execute(sql, params)
                    enriched_count += 1
                    logging.info(f"  Successfully enriched '{name}' from OFF: protein={protein}g")
                    
            import time
            time.sleep(0.5) # Prevent rate limits
        except Exception as e:
            logging.error(f"  Error enriching '{name}' from OFF: {e}")
            
    conn.commit()
    logging.info(f"Enriched {enriched_count} products using Open Food Facts.")
    
    # 5. Smart Name-Based Fallback for remaining zero-protein items in key categories
    logging.info("Step 5: Applying smart fallbacks for remaining zero-protein items...")
    cursor.execute("SELECT id, name, category FROM products WHERE protein_per_100g = 0.0")
    remaining_zero_p = cursor.fetchall()
    
    fallback_count = 0
    for row in remaining_zero_p:
        pid, name, cat = row
        name_lower = name.lower()
        
        protein, fat, carbs, calories, nova = None, None, None, None, 1
        
        # Meat & Poultry
        if cat == "Kött & Fågel":
            if "kyckling" in name_lower:
                protein, fat, carbs, calories, nova = 22.0, 1.5, 0.0, 105, 1
            elif "nötfärs" in name_lower or "nöt" in name_lower:
                protein, fat, carbs, calories, nova = 20.0, 10.0, 0.0, 170, 1
            elif "karré" in name_lower or "fläsk" in name_lower or "gris" in name_lower:
                protein, fat, carbs, calories, nova = 18.0, 14.0, 0.0, 200, 1
            elif "blandfärs" in name_lower:
                protein, fat, carbs, calories, nova = 19.0, 15.0, 0.0, 210, 1
            else:
                protein, fat, carbs, calories, nova = 20.0, 8.0, 0.0, 150, 1
                
        # Dairy
        elif cat == "Mejeri":
            if "kvarg" in name_lower:
                protein, fat, carbs, calories, nova = 11.0, 0.2, 3.0, 60, 1
            elif "keso" in name_lower or "cottage" in name_lower:
                protein, fat, carbs, calories, nova = 12.0, 4.0, 2.0, 93, 3
            elif "ost" in name_lower:
                protein, fat, carbs, calories, nova = 25.0, 28.0, 0.0, 350, 3
            elif "mjölk" in name_lower or "mellanmjölk" in name_lower:
                protein, fat, carbs, calories, nova = 3.4, 1.5, 4.8, 45, 1
            elif "yoghurt" in name_lower:
                protein, fat, carbs, calories, nova = 3.4, 3.0, 3.8, 60, 1
            else:
                protein, fat, carbs, calories, nova = 5.0, 4.0, 4.0, 70, 1
                
        # Fish & Seafood
        elif cat == "Fisk & Skaldjur":
            if "lax" in name_lower:
                protein, fat, carbs, calories, nova = 20.0, 13.0, 0.0, 200, 1
            elif "torsk" in name_lower or "sej" in name_lower:
                protein, fat, carbs, calories, nova = 18.0, 1.0, 0.0, 80, 1
            elif "tonfisk" in name_lower:
                protein, fat, carbs, calories, nova = 24.0, 1.0, 0.0, 110, 3
            else:
                protein, fat, carbs, calories, nova = 19.0, 5.0, 0.0, 120, 1
                
        # Grains / Carbs
        elif cat == "Spannmål & Kolhydrater":
            if "bröd" in name_lower or "limpa" in name_lower:
                protein, fat, carbs, calories, nova = 8.0, 2.0, 50.0, 250, 3
            elif "havre" in name_lower or "gryn" in name_lower:
                protein, fat, carbs, calories, nova = 13.0, 7.0, 58.0, 370, 1
            elif "pasta" in name_lower:
                protein, fat, carbs, calories, nova = 12.0, 1.5, 70.0, 350, 1
            elif "ris" in name_lower:
                protein, fat, carbs, calories, nova = 7.0, 0.5, 78.0, 350, 1
            elif "knäcke" in name_lower or "hårt" in name_lower:
                protein, fat, carbs, calories, nova = 10.0, 2.5, 65.0, 330, 3
            else:
                protein, fat, carbs, calories, nova = 8.0, 2.0, 60.0, 300, 3
                
        # Vegetables
        elif cat == "Vegetabiliskt":
            if "potatis" in name_lower:
                protein, fat, carbs, calories, nova = 2.0, 0.1, 16.0, 75, 1
            elif "morot" in name_lower or "morötter" in name_lower:
                protein, fat, carbs, calories, nova = 0.9, 0.1, 9.0, 40, 1
            elif "tomat" in name_lower:
                protein, fat, carbs, calories, nova = 0.9, 0.2, 3.9, 18, 1
            elif "paprika" in name_lower:
                protein, fat, carbs, calories, nova = 1.0, 0.3, 6.0, 30, 1
            elif "lök" in name_lower:
                protein, fat, carbs, calories, nova = 1.1, 0.1, 9.0, 40, 1
            elif "banan" in name_lower:
                protein, fat, carbs, calories, nova = 1.1, 0.3, 23.0, 89, 1
            elif "gurka" in name_lower:
                protein, fat, carbs, calories, nova = 0.7, 0.1, 3.0, 15, 1
            elif "mango" in name_lower:
                protein, fat, carbs, calories, nova = 0.8, 0.4, 15.0, 60, 1
            else:
                protein, fat, carbs, calories, nova = 1.0, 0.2, 5.0, 25, 1

        if protein is not None:
            logging.info(f"Applying name-based fallback for '{name}' ({cat}): protein={protein}g, fat={fat}g, carbs={carbs}g")
            cursor.execute("""
                UPDATE products 
                SET protein_per_100g = ?, fat_per_100g = ?, carbs_per_100g = ?, calories_100g = ?, nova_group = ?
                WHERE id = ?
            """, (protein, fat, carbs, calories, nova, pid))
            fallback_count += 1
            
    conn.commit()
    logging.info(f"Applied name-based fallbacks to {fallback_count} products.")
    
    # 6. Final safety check for 0.0g protein in protein-rich categories
    logging.info("Step 6: Final safety check for remaining 0.0g protein in protein-rich categories...")
    cursor.execute("""
        SELECT id, name, category FROM products 
        WHERE protein_per_100g = 0.0 
        AND category IN ('Mejeri', 'Kött & Fågel', 'Fisk & Skaldjur', 'Vegetabiliska Proteiner')
    """)
    bad_scrapes = cursor.fetchall()
    deleted_bad = 0
    for row in bad_scrapes:
        pid, name, cat = row
        logging.info(f"Removing remaining bad scrape: '{name}' in '{cat}' with 0.0g protein")
        cursor.execute("DELETE FROM prices WHERE product_id = ?", (pid,))
        cursor.execute("DELETE FROM products WHERE id = ?", (pid,))
        deleted_bad += 1
        
    conn.commit()
    logging.info(f"Deleted {deleted_bad} bad scrapes.")
    
    # Summary
    cursor.execute("SELECT count(*) FROM products")
    total_after = cursor.fetchone()[0]
    cursor.execute("SELECT count(*) FROM products WHERE protein_per_100g = 0.0")
    zero_after = cursor.fetchone()[0]
    
    print("\n================ CLEANUP SUMMARY ================")
    print("Total products before: 78")
    print(f"Total products after:  {total_after}")
    print("Zero protein products before: 40")
    print(f"Zero protein products after:  {zero_after}")
    print(f"Deleted duplicates:    {deleted_duplicates}")
    print(f"Deleted non-food items: {deleted_non_food}")
    print(f"Enriched via OFF:      {enriched_count}")
    print(f"Enriched via Fallback: {fallback_count}")
    print(f"Recategorized items:   {recategorized}")
    print("=================================================\n")
    
    conn.close()

if __name__ == "__main__":
    run_cleanup()
