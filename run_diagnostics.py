import json
import os
import sys

def run_tests():
    errors = 0
    print("=== STARTAR SYSTEMDIAGNOSTIK ===\n")

    # 1. Kontrollera Cachen (Steg 1)
    cache_path = "public/nutrition_cache.json"
    if not os.path.exists(cache_path):
        print(f"[FEL] Näringscachen saknas: {cache_path}")
        errors += 1
    else:
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cache = json.load(f)
            if not isinstance(cache, dict):
                print("[FEL] Näringscachen är inte en dictionary.")
                errors += 1
            elif len(cache) == 0:
                print("[VARNING] Näringscachen är tom. Har skrapan körts?")
            else:
                print(f"[OK] Näringscache hittad ({len(cache)} produkter).")
        except Exception as e:
            print(f"[FEL] Kunde inte läsa näringscachen: {e}")
            errors += 1

    # 2. Kontrollera Prishistoriken (Steg 2)
    data_path = "public/data.json"
    if not os.path.exists(data_path):
        print(f"[FEL] Huvuddatabasen saknas: {data_path}")
        errors += 1
    else:
        try:
            with open(data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                print("[FEL] data.json är inte en lista.")
                errors += 1
            elif len(data) == 0:
                print("[FEL] data.json är tom!")
                errors += 1
            else:
                missing_history = sum(1 for item in data if "price_history" not in item)
                if missing_history > 0:
                    print(f"[VARNING] {missing_history} produkter saknar 'price_history' i data.json.")
                else:
                    print(f"[OK] Prishistorik verifierad i {len(data)} produkter.")
        except Exception as e:
            print(f"[FEL] Kunde inte läsa data.json: {e}")
            errors += 1

    # 3. Kontrollera Delta-genereringen (Steg 3)
    out_dir = "public/produkter"
    hash_path = os.path.join(out_dir, "hash_state.json")
    if not os.path.exists(out_dir):
        print(f"[FEL] Mappen för SEO-sidor saknas: {out_dir}")
        errors += 1
    else:
        html_files = [f for f in os.listdir(out_dir) if f.endswith(".html")]
        if len(html_files) == 0:
            print("[VARNING] Inga HTML-filer har genererats i public/produkter/.")
        else:
            print(f"[OK] Hittade {len(html_files)} genererade HTML-filer.")

        if not os.path.exists(hash_path):
            print(f"[VARNING] Hash-state saknas: {hash_path}. Är detta första körningen?")
        else:
            try:
                with open(hash_path, "r", encoding="utf-8") as f:
                    hash_state = json.load(f)
                if not isinstance(hash_state, dict):
                    print("[FEL] hash_state.json är inte en dictionary.")
                    errors += 1
                else:
                    print(f"[OK] Hash-state verifierat ({len(hash_state)} hashar lagrade).")
            except Exception as e:
                print(f"[FEL] Kunde inte läsa hash_state.json: {e}")
                errors += 1

    print("\n=== DIAGNOSTIK AVSLUTAD ===")
    if errors > 0:
        print(f"\nHittade {errors} allvarliga fel i pipelinen. Kontrollera koden.")
        sys.exit(1)
    else:
        print("\nAlla strukturella tester passerade! Pipelinen är redo för produktion.")
        sys.exit(0)

if __name__ == "__main__":
    run_tests()
