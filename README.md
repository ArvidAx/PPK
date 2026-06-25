# PPK – Protein per Krona

En webbaserad kalkylator som hittar de mest kostnadseffektiva proteinkällorna på Hemköp, mätt i gram protein per spenderad krona (PPK).

## Arkitektur

```
PPK/
├── hemkop_protein_per_krona.py   # Skrapan som genererar data.json
├── daily_automation.py            # Automatiserar daglig skrapning och Git-push
├── requirements.txt               # Python-beroenden
└── public/                        # Statisk webbplats (deployas på Cloudflare Pages)
    ├── index.html                 # Kalkylator-sidan
    ├── recept.html                # Receptsidan
    ├── kunskap.html               # Kunskapsbanken (artikelindex)
    ├── artikel-*.html             # Individuella artiklar
    ├── style.css
    ├── app.js
    └── data.json                  # Genereras av skrapan
```

## Kom igång

```bash
pip install -r requirements.txt

# Skrapa hela Hemköp (tar 30-60 min)
python hemkop_protein_per_krona.py

# Eller testa med 1 kategori, 2 sidor
python hemkop_protein_per_krona.py --categories mejeri-ost-och-agg --max-pages 2

# Visa hemsidan lokalt
cd public && python -m http.server
```

## Daglig automation (server)

Kör `daily_automation.py` via crontab (Linux) eller Schemaläggaren (Windows):

```cron
0 4 * * * /usr/bin/python3 /path/to/PPK/daily_automation.py >> /path/to/PPK/cron_log.txt 2>&1
```

Skriptet skrapar, committar ny `data.json` och pushar till GitHub. Cloudflare Pages sätter igång automatiskt.

## Hosting på Cloudflare Pages

1. Koppla GitHub-repot till Cloudflare Pages
2. Sätt **Build output directory** till `public`
3. Lämna build command tomt
4. Deploy!