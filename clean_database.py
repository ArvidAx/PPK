import json
import re

def extract_weight_in_grams(item):
    weight = item.get("package_weight_g")
    if weight and float(weight) > 0:
        return float(weight)
    
    display_volume = item.get("display_volume", "")
    if display_volume:
        g_match = re.search(r"(\d+[\.,]?\d*)\s*g\b", display_volume.lower())
        if g_match:
            return float(g_match.group(1).replace(",", "."))
        
        kg_match = re.search(r"(\d+[\.,]?\d*)\s*kg\b", display_volume.lower())
        if kg_match:
            return float(kg_match.group(1).replace(",", ".")) * 1000.0

    return None

def clean_data_file(filepath):
    with open(filepath, encoding='utf-8') as f:
        data = json.load(f)

    cleaned_data = []

    for item in data:
        name = item.get("name", "")
        category = item.get("category", "")
        desc = item.get("description", "")
        price = item.get("price_sek")
        display_volume = item.get("display_volume", "")
        protein_100g = item.get("protein_per_100g")
        
        if price is None or price <= 0:
            continue

        name_lower = name.lower()
        brand_lower = (item.get("brand") or "").lower()
        
        # 1. Permanent Blocklist for invalid names and brands
        blacklisted_names = ["vanilj syrup sockerfri", "grönt te", "fänkålsfrön hela burk", "shirataki nudlar", "mintblad"]
        blacklisted_brands = ["touch of taste", "dotetorp", "borekulla gård", "clipper", "lipton"]
        
        if any(b_name in name_lower for b_name in blacklisted_names) or any(b_brand in brand_lower for b_brand in blacklisted_brands):
            continue

        # 2. Exclude products without nutrition values (both missing or 0)
        raw_kcal = item.get('calories_per_100g')
        
        try:
            p_val = float(protein_100g) if protein_100g is not None else 0.0
        except (ValueError, TypeError):
            p_val = 0.0
        try:
            k_val = float(raw_kcal) if raw_kcal is not None else 0.0
        except (ValueError, TypeError):
            k_val = 0.0

        if (protein_100g is None and raw_kcal is None) or (p_val == 0.0 and k_val == 0.0):
            continue

        full_text = " ".join([name, category, desc or ""]).lower()
        
        # Check if egg
        underkategori = item.get("underkategori", [])
        if isinstance(underkategori, list):
            has_egg_sub = any(str(sub).lower() == "ägg" for sub in underkategori)
        else:
            has_egg_sub = str(underkategori).lower() == "ägg"
        
        is_egg = (category == "mejeri-ost-och-agg" and (has_egg_sub or "ägg" in name_lower))
        
        if is_egg:
            egg_count = None
            for text in [display_volume, name, desc]:
                if not text:
                    continue
                count_match = re.search(r"(\d+)\s*(?:p|st|pack|stycken|packe)\b", text.lower())
                if count_match:
                    egg_count = int(count_match.group(1))
                    break
            
            if egg_count and egg_count > 0:
                item["package_weight_g"] = egg_count * 55.0
                item["protein_per_100g"] = 12.5
                protein_100g = 12.5
            else:
                continue # Unknown egg count, skip

        # Check if dry powder or soup
        dry_keywords = ["soppa", "soppor", "buljong", "torrsoppa", "såsmix", "sasmix", "pulver", "dipp", "dressingmix", "potatismos", "fond", "fonder", "touch of taste", "buljongkoncentrat"]
        is_dry = any(kw in full_text for kw in dry_keywords)

        if is_dry:
            dry_weight = None
            for source in [display_volume, name, desc]:
                if not source:
                    continue
                g_match = re.search(r"(\d+[\.,]?\d*)\s*g\b", source.lower())
                if g_match:
                    dry_weight = float(g_match.group(1).replace(",", "."))
                    break
            
            if not dry_weight and display_volume and (display_volume.lower().endswith("g") or "gram" in display_volume.lower()):
                num_match = re.search(r"(\d+[\.,]?\d*)", display_volume)
                if num_match:
                    dry_weight = float(num_match.group(1).replace(",", "."))

            if dry_weight:
                item["package_weight_g"] = dry_weight
            else:
                # If we can't determine dry weight, and it's a dry powder, we check if PPK is too high
                if (item.get("protein_per_krona") or 0) > 8:
                    continue

        # 1. Strikt viktextraktion och fallback
        weight_g = extract_weight_in_grams(item)
        if not weight_g or weight_g <= 0:
            continue # Om vikten är okänd, exkludera produkten helt

        # 2. Beräkna PPK (Protein Per Krona)
        total_protein = (protein_100g / 100.0) * weight_g
        ppk = total_protein / price

        # 3. Beräkna Protein per 100 kcal (Strikt matematisk spärr)
        try:
            kcal = float(raw_kcal) if raw_kcal is not None else 0.0
        except (ValueError, TypeError):
            kcal = 0.0

        parsed_raw_kcal = kcal
        if kcal <= 0:
            kcal = 4.0 * protein_100g # Fallback: proteinet självt sätter minimikalorivärdet

        p_per_100kcal = 0.0
        if kcal > 0:
            p_per_100kcal = (protein_100g / kcal) * 100.0

        # Defensiv max-spärr: Inget livsmedel i universum kan överstiga dessa naturlagar
        if p_per_100kcal > 25.0: 
            if parsed_raw_kcal <= 0.0 or "syrup" in name_lower or "sirap" in name_lower or "vatten" in name_lower or "dryck" in name_lower:
                continue # Skip zero-calorie products showing high protein/kcal anomalies
            else:
                p_per_100kcal = 0.0 # Rounding anomaly fallback
            
        if ppk > 15.0: # Ingen vanlig matvara ger mer än 15g protein per krona live
            continue # Kassera anomalin
            
        if is_dry and ppk > 8.0:
            continue

        item['protein_per_krona'] = round(ppk, 4)
        item['p_per_100kcal'] = round(p_per_100kcal, 2)
        item['package_weight_g'] = weight_g
        item['kcal_per_100g'] = kcal

        cleaned_data.append(item)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, ensure_ascii=False, indent=4)

    print(f"Cleaned database saved to {filepath}. Total items: {len(cleaned_data)} (original: {len(data)})")

if __name__ == "__main__":
    clean_data_file('public/data.json')
