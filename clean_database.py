import json
import re

def clean_data_file(filepath):
    with open(filepath, encoding='utf-8') as f:
        data = json.load(f)

    cleaned_data = []
    
    # Exclude keywords for egg validation
    exclusions = ["nudlar", "pastej", "röra", "sallad", "smörgås", "skinka", "bacon", "paj", "glass", "våffla", "kakor", "bröd", "ost"]

    for item in data:
        name = item.get("name", "")
        brand = item.get("brand", "")
        category = item.get("category", "")
        desc = item.get("description", "")
        price = item.get("price_sek")
        display_volume = item.get("display_volume", "")
        protein_100g = item.get("protein_per_100g")
        
        if price is None or price <= 0:
            continue

        # Check if egg
        is_egg = False
        full_text = " ".join([name, category, desc or ""]).lower()
        if "ägg" in full_text and not any(excl in name.lower() for excl in exclusions):
            is_egg = True

        if is_egg:
            # 1. Hitta antal ägg (t.ex. "15p", "6p", "10-pack", "15 stycken", "12-pack")
            egg_count = None
            for text in [display_volume, name, desc]:
                if not text:
                    continue
                count_match = re.search(r"(\d+)\s*(?:p|st|pack|stycken|packe)\b", text.lower())
                if count_match:
                    egg_count = int(count_match.group(1))
                    break
            
            if egg_count and egg_count > 0:
                total_protein_g = egg_count * 6.875
                ppk = total_protein_g / price
                item["protein_per_krona"] = round(ppk, 4)
                item["protein_per_100g"] = 12.5
                item["package_weight_g"] = egg_count * 55.0
                item["calculation_method"] = "C (ägg-specifik)"
            else:
                # If egg count not found but it's eggs, let's estimate or skip to avoid anomalies
                continue

        # Check if dry powder or soup
        is_dry = False
        dry_keywords = ["soppa", "soppor", "buljong", "torrsoppa", "såsmix", "sasmix", "pulver", "dipp", "dressingmix", "potatismos"]
        if any(kw in full_text for kw in dry_keywords):
            is_dry = True

        if is_dry:
            # Parse dry weight in grams from display_volume or description
            dry_weight = None
            # e.g. "62g/1l" -> 62
            for source in [display_volume, name, desc]:
                if not source:
                    continue
                # Try pattern Xg/Yl or X g / Y l
                g_match = re.search(r"(\d+[\.,]?\d*)\s*g\b", source.lower())
                if g_match:
                    dry_weight = float(g_match.group(1).replace(",", "."))
                    break
            
            if not dry_weight:
                # Try to parse standard numbers in display volume if it ends with "g"
                if display_volume and (display_volume.lower().endswith("g") or "gram" in display_volume.lower()):
                    num_match = re.search(r"(\d+[\.,]?\d*)", display_volume)
                    if num_match:
                        dry_weight = float(num_match.group(1).replace(",", "."))

            if dry_weight and protein_100g is not None:
                total_protein = (protein_100g / 100.0) * dry_weight
                ppk = total_protein / price
                item["protein_per_krona"] = round(ppk, 4)
                item["package_weight_g"] = dry_weight
                item["calculation_method"] = "B (torrvikt/pris)"
            else:
                # If we can't determine the actual dry weight and PPK is high, exclude it
                if (item.get("protein_per_krona") or 0) > 15:
                    continue

        # Final sanity check: if PPK is still unreasonably high (> 15), exclude it
        if (item.get("protein_per_krona") or 0) > 15:
            # Exclude
            continue

        cleaned_data.append(item)

    # Save cleaned data
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, ensure_ascii=False, indent=4)

    print(f"Cleaned database saved to {filepath}. Total items: {len(cleaned_data)} (original: {len(data)})")

if __name__ == "__main__":
    clean_data_file('public/data.json')
