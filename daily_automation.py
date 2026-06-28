import subprocess
import logging
from datetime import datetime
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def run_cmd(cmd):
    logging.info(f"Kör: {cmd}")
    # Kör med Popen och slå samman stderr/stdout för att strömma loggar direkt till terminalen
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    
    stdout_lines = []
    for line in process.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        stdout_lines.append(line)
        
    process.wait()
    if process.returncode != 0:
        logging.error(f"Kommando misslyckades med returkod {process.returncode}: {cmd}")
        sys.exit(1)
    return "".join(stdout_lines)

def main():
    # 1. Byt katalog till repot så att scriptet kan köras varifrån som helst
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(repo_dir)

    # 2. Dra ner eventuella uppdateringar från Github för att undvika konflikter
    logging.info("Uppdaterar lokalt repo...")
    run_cmd("git pull origin main")

    # 3. Kör skrapan. Skicka vidare eventuella argument (t.ex. för snabbtestning).
    args_str = " ".join(sys.argv[1:])
    logging.info(f"Startar Hemköp-skrapan med argument: {args_str if args_str else 'inga (full skrapning)'}...")
    run_cmd(f"{sys.executable} -u hemkop_protein_per_krona.py {args_str}")

    # 3.5 Kör tvättskriptet för att sanera eventuella anomalier (matematiska gränsvärden etc.)
    logging.info("Kör datatvätt för att filtrera bort anomalier (clean_database.py)...")
    run_cmd(f"{sys.executable} -u clean_database.py")

    # 4. Kontrollera om data.json faktiskt har ändrats
    status = subprocess.run("git status --porcelain public/data.json public/nutrition_cache.json", shell=True, capture_output=True, text=True)
    if not status.stdout.strip():
        logging.info("Inga förändringar i data.json eller cachen sedan igår. Inget att pusha.")
        return

    # 5. Lägg till och committa
    logging.info("Sparar nya data och uppdateringstid till Git...")
    run_cmd("git add public/data.json public/last_updated.json public/nutrition_cache.json")
    
    date_str = datetime.now().strftime("%Y-%m-%d")
    # Lägg märke till [skip ci] ifall du inte vill att github actions ska bygga, men Cloudflare Pages sköter sig självt.
    run_cmd(f'git commit -m "Automatisk databasuppdatering {date_str}"')

    # 6. Push upp till GitHub (Detta säger automatiskt åt Cloudflare att uppdatera hemsidan!)
    logging.info("Pushar till GitHub...")
    run_cmd("git push origin main")
    
    logging.info("Allt klart! Hemsidan är nu uppdaterad med dagens priser.")

if __name__ == "__main__":
    main()
