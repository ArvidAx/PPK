"""
hemkop_protein_per_krona.py
============================
Skrapar produktdata från Hemköp och beräknar "Protein per Krona" (g protein / SEK).

Strategi:
  1. Kategorilista via intern REST-API: GET /c/{kategori}?size=30&page=N
     Returnerar JSON med produkter inkl. pris, vikt och streckkod/kod.
  2. Produktdetaljer via: GET /axfood/rest/p/{product_code}
     Returnerar JSON med näringsvärden under nutrientHeaders[].nutrientDetails.

Beräkningslogik (Alternativ A – via jämförpris per kg):
  Protein per Krona = (protein_per_100g * 10) / comparePrice_per_kg

Beräkningslogik (Alternativ B – via totalvikt):
  total_protein_g = (protein_per_100g / 100) * package_weight_g
  Protein per Krona = total_protein_g / product_price

Krav: requests, beautifulsoup4 (+ valfritt pandas)
"""

import json
import logging
import re
import time
import random
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# ── Försök importera pandas (ej obligatoriskt) ──────────────────────────────
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger(__name__)

# ── Konstanter ───────────────────────────────────────────────────────────────
BASE_URL = "https://www.hemkop.se"

# Realistisk User-Agent för att undvika blockering
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "sv-SE,sv;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.hemkop.se/",
    "X-Requested-With": "XMLHttpRequest",
}

# Kategorier att skrapa (slug används direkt i API-anropet)
CATEGORY_SLUGS = [
    "kott-fagel-och-chark",
    "frukt-och-gront",
    "mejeri-ost-och-agg",
    "skafferi",
    "fryst",
    "brod-och-kakor",
    "fisk-och-skaldjur",
    "vegetariskt",
    "fardigmat",
    "delikatessen",
    "godis-snacks-och-glass",
]

# Produkter per API-anrop (max 30 verkar fungera stabilt)
PAGE_SIZE = 30

# Fördröjning mellan anrop (sekunder) – respekterar servern
MIN_DELAY = 0.3
MAX_DELAY = 0.8

# Max antal produktsidor per kategori (0 = hämta alla)
MAX_PAGES_PER_CATEGORY = 0  # Sätt till t.ex. 3 för testning


# ── Hjälpfunktioner ──────────────────────────────────────────────────────────

def make_session() -> requests.Session:
    """
    Skapar en requests.Session med persistenta headers och cookie-hantering.
    Att använda en session sparar TCP-anslutningar och skickar cookies automatiskt.
    """
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def _polite_sleep():
    """Väntar en slumpmässig tid för att inte hammra servern."""
    time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))


def safe_get(session: requests.Session, url: str, params: Optional[dict] = None,
             retries: int = 3, timeout: int = 15) -> Optional[requests.Response]:
    """
    Utför en GET-förfrågan med automatiska omförsök vid nätverksfel eller 5xx.

    Args:
        session: En aktiv requests.Session.
        url: Mål-URL.
        params: Valfria query-parametrar.
        retries: Antal omförsök.
        timeout: Sekunder innan timeout.

    Returns:
        requests.Response om lyckat, annars None.
    """
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, params=params, timeout=timeout)
            if resp.status_code == 200:
                return resp
            elif resp.status_code == 429:
                # Rate limit – vänta länge
                wait = 10 * attempt
                log.warning("429 Rate Limit från %s. Väntar %ds...", url, wait)
                time.sleep(wait)
            elif resp.status_code >= 500:
                wait = 2 ** attempt
                log.warning("HTTP %d från %s. Försök %d/%d. Väntar %ds...",
                            resp.status_code, url, attempt, retries, wait)
                time.sleep(wait)
            else:
                log.warning("HTTP %d från %s. Hoppar över.", resp.status_code, url)
                return None
        except requests.exceptions.RequestException as exc:
            log.error("Nätverksfel vid %s (försök %d/%d): %s", url, attempt, retries, exc)
            time.sleep(2 ** attempt)
    return None


# ── Skrapningsfunktioner ─────────────────────────────────────────────────────

def fetch_category_page(session: requests.Session, category_slug: str, page: int) -> dict:
    """
    Hämtar en sida med produkter från kategorins REST-API.

    Endpoint: GET /c/{category_slug}?size={PAGE_SIZE}&page={page}

    Args:
        session: Aktiv requests.Session.
        category_slug: Kategori-slug, t.ex. "kott-fagel-och-chark".
        page: Sidnummer (0-indexerat).

    Returns:
        Rå JSON-svar som dict, eller tomt dict vid fel.
    """
    url = urljoin(BASE_URL, f"/c/{category_slug}")
    params = {"size": PAGE_SIZE, "page": page}
    log.info("Hämtar kategori '%s', sida %d...", category_slug, page)

    resp = safe_get(session, url, params=params)
    if resp is None:
        return {}

    try:
        return resp.json()
    except (json.JSONDecodeError, ValueError) as exc:
        log.error("Kunde inte parsa JSON för kategori '%s' sida %d: %s",
                  category_slug, page, exc)
        return {}


def fetch_product_details(session: requests.Session, product_code: str) -> dict:
    """
    Hämtar fullständiga produktdetaljer inkl. näringsvärden.

    Endpoint: GET /axfood/rest/p/{product_code}

    Näringsvärden finns i:
      response["nutrientHeaders"][0]["nutrientDetails"]
      Varje element har: nutrientTypeCode, quantityContained, measurementUnitCode

    Args:
        session: Aktiv requests.Session.
        product_code: Produktkod, t.ex. "101262973_ST".

    Returns:
        Rå JSON-svar som dict, eller tomt dict vid fel.
    """
    url = urljoin(BASE_URL, f"/axfood/rest/p/{product_code}")

    resp = safe_get(session, url)
    if resp is None:
        return {}

    try:
        return resp.json()
    except (json.JSONDecodeError, ValueError) as exc:
        log.error("Kunde inte parsa JSON för produkt '%s': %s", product_code, exc)
        return {}


# ── Extraktionsfunktioner ────────────────────────────────────────────────────

def parse_price(price_value) -> Optional[float]:
    """
    Konverterar ett prisvärde till float (SEK).
    Hanterar både strängar ("47,27 kr", "1 000,00") och numeriska värden.
    """
    if price_value is None:
        return None
    if isinstance(price_value, (int, float)):
        return float(price_value)
    if isinstance(price_value, str):
        # Ta bort "kr", alla mellanslag (inkl non-breaking) och byt komma mot punkt
        import re
        cleaned = price_value.replace("kr", "")
        cleaned = re.sub(r'\s+', '', cleaned) # Tar bort ALL whitespace (t.ex. i "1 000,00")
        cleaned = cleaned.replace(",", ".")
        match = re.search(r"[\d.]+", cleaned)
        if match:
            try:
                return float(match.group())
            except ValueError:
                pass
    return None


def parse_package_weight_g(display_volume: Optional[str], url: str = "") -> Optional[float]:
    """
    Tolkar förpackningsvikt/-volym till gram.
    Hanterar: "500g", "1 kg", "1,5 kg", "2x400g", "12x35g", "_KG" suffix i URL.

    Args:
        display_volume: Textsträng med vikt/volym, t.ex. "500g" eller "1 kg".
        url: Produkt-URL (används för att detektera viktsbaserade produkter).

    Returns:
        Vikt i gram som float, eller None om det inte gick att tolka.
    """
    # Viktsbaserad produkt (säljs per kg) – defaulta till 1000g
    if url and re.search(r"[/_]KG$", url, re.IGNORECASE):
        return 1000.0

    if not display_volume:
        return None

    text = display_volume.lower().strip()

    # Multipel förpackning: "2x400g" → 2 * 400 = 800g, "12x35g" → 420g
    multi_match = re.search(r"(\d+)\s*[xX×]\s*(\d+[\.,]?\d*)\s*(kg|g)", text)
    if multi_match:
        count = float(multi_match.group(1))
        amount = float(multi_match.group(2).replace(",", "."))
        unit = multi_match.group(3)
        if unit == "kg":
            return count * amount * 1000
        return count * amount

    # Kilogram
    kg_match = re.search(r"(\d+[\.,]?\d*)\s*(kg|kilo|kilogram)", text)
    if kg_match:
        return float(kg_match.group(1).replace(",", ".")) * 1000

    # Gram
    g_match = re.search(r"(\d+[\.,]?\d*)\s*(g|gram|gr)\b", text)
    if g_match:
        return float(g_match.group(1).replace(",", "."))

    # Rent numeriskt värde (tolkas som gram)
    num_match = re.search(r"(\d+[\.,]?\d*)", text)
    if num_match:
        val = float(num_match.group(1).replace(",", "."))
        # Siffror < 20 är troligen styck, inte gram
        if val >= 20:
            return val

    return None


def extract_protein_per_100g(product_detail: dict) -> Optional[float]:
    """
    Extraherar proteininnehåll per 100g från produktdetaljernas näringsvärden.
    Hanterar nu korrekt gram, milligram och mikrogram.
    """
    nutrient_headers = product_detail.get("nutrientHeaders", [])
    if not nutrient_headers:
        return None

    for header in nutrient_headers:
        basis_qty = header.get("nutrientBasisQuantity")
        if basis_qty and float(basis_qty) != 100:
            continue

        nutrient_details = header.get("nutrientDetails", [])
        for nutrient in nutrient_details:
            type_code = (nutrient.get("nutrientTypeCode") or "").lower()
            unit = (nutrient.get("measurementUnitCode") or "").lower()

            if "protein" in type_code:
                qty = nutrient.get("quantityContained")
                if qty is not None:
                    try:
                        val = float(qty)
                        if unit in ("milligram", "mg"):
                            val /= 1000.0
                        elif unit in ("mikrogram", "microgram", "µg", "ug"):
                            val /= 1000000.0
                        return val
                    except (ValueError, TypeError):
                        pass

    # Fallback: ta första bästa om 100g-block saknas
    for header in nutrient_headers:
        for nutrient in header.get("nutrientDetails", []):
            type_code = (nutrient.get("nutrientTypeCode") or "").lower()
            unit = (nutrient.get("measurementUnitCode") or "").lower()
            if "protein" in type_code:
                qty = nutrient.get("quantityContained")
                if qty is not None:
                    try:
                        val = float(qty)
                        if unit in ("milligram", "mg"):
                            val /= 1000.0
                        elif unit in ("mikrogram", "microgram", "µg", "ug"):
                            val /= 1000000.0
                        return val
                    except (ValueError, TypeError):
                        pass

    return None


# ── Beräkningsfunktioner ─────────────────────────────────────────────────────

def calculate_protein_per_krona(
    protein_per_100g: float,
    price_sek: float,
    compare_price_per_kg: Optional[float] = None,
    package_weight_g: Optional[float] = None
) -> Optional[float]:
    """
    Beräknar gram protein per SEK (Protein per Krona).

    Försöker Alternativ A (via jämförpris/kg) först, sedan Alternativ B (via totalvikt).

    Alt A: Protein per Krona = (protein_per_100g * 10) / compare_price_per_kg
    Alt B: Protein per Krona = (protein_per_100g / 100 * package_weight_g) / price_sek

    Args:
        protein_per_100g: Gram protein per 100g produkt.
        price_sek: Produktens konsumentpris i SEK.
        compare_price_per_kg: Jämförpris per kg (SEK/kg), om tillgängligt.
        package_weight_g: Förpackningens nettovikt i gram, om tillgängligt.

    Returns:
        Gram protein per SEK som float, eller None om beräkning ej möjlig.
    """
    if protein_per_100g <= 0:
        return None

    # Alternativ A: via jämförpris per kg (mest precis)
    if compare_price_per_kg and compare_price_per_kg > 0:
        ppk = (protein_per_100g * 10) / compare_price_per_kg
        return round(ppk, 4)

    # Alternativ B: via totalvikt och pris
    if package_weight_g and package_weight_g > 0 and price_sek and price_sek > 0:
        total_protein_g = (protein_per_100g / 100) * package_weight_g
        ppk = total_protein_g / price_sek
        return round(ppk, 4)

    return None


# ── Huvudlogik ───────────────────────────────────────────────────────────────

def scrape_all_categories(
    category_slugs: list = CATEGORY_SLUGS,
    max_pages: int = MAX_PAGES_PER_CATEGORY,
    fetch_nutrition: bool = True,
    nutrition_delay: float = None,
) -> list:
    """
    Huvud-skrapningsfunktion. Hämtar produkter från alla angivna kategorier
    och berikar varje produkt med näringsvärden från produktdetaljsidan.

    Args:
        category_slugs: Lista med kategori-slugs att skrapa.
        max_pages: Max sidor per kategori (0 = alla).
        fetch_nutrition: Om True, hämtas näringsvärden per produkt (långsammare).
        nutrition_delay: Sekunder att vänta mellan näringsdataanrop (None = slumpat).

    Returns:
        Lista med produktdicts sorterade efter "protein_per_krona" (fallande).
    """
    session = make_session()

    # Initialt anrop för att sätta cookies (t.ex. cookie consent)
    log.info("Initierar session mot Hemköp...")
    warmup_resp = safe_get(session, BASE_URL, timeout=15)
    if warmup_resp:
        log.info("Session initierad. Cookie-hantering aktiv.")
    _polite_sleep()

    all_products = []
    seen_codes = set()  # Deduplicering – samma produkt kan finnas i flera kategorier

    for slug in category_slugs:
        log.info("── Startar kategori: %s ──", slug)
        page = 0
        total_pages = None

        while True:
            data = fetch_category_page(session, slug, page)
            if not data:
                log.warning("Inga data för kategori '%s' sida %d. Hoppar.", slug, page)
                break

            # Extrahera pagineringsinformation
            pagination = data.get("pagination", {})
            if total_pages is None:
                total_pages = pagination.get("numberOfPages", 1)
                total_items = pagination.get("totalNumberOfResults", "?")
                log.info("Kategori '%s': %s produkter totalt, %d sidor.",
                         slug, total_items, total_pages)

            results = data.get("results", [])
            if not results:
                log.info("Inga fler produkter för kategori '%s'.", slug)
                break

            log.info("Kategori '%s' sida %d/%d: %d produkter.",
                     slug, page + 1, total_pages, len(results))

            for raw in results:
                code = raw.get("code", "")
                if not code or code in seen_codes:
                    continue
                seen_codes.add(code)

                # ── Extrakt grunddata från kategorilistan ──
                name = raw.get("name", "Okänd produkt")
                brand = raw.get("manufacturer", "Okänt märke")

                # Pris: "priceValue" är numeriskt (float), "price" är sträng som "47,27 kr"
                price_sek = None
                if raw.get("priceValue") is not None:
                    price_sek = float(raw["priceValue"])
                else:
                    price_sek = parse_price(raw.get("price"))

                # Jämförpris
                compare_price_str = raw.get("comparePrice", "")
                compare_price_sek = parse_price(compare_price_str)
                compare_price_unit = (raw.get("comparePriceUnit") or "").lower()

                # Jämförpris per KG (normalisera om enheten är "liter" eller "100g" etc.)
                compare_price_per_kg = None
                if compare_price_sek is not None:
                    if compare_price_unit in ("kg", "kilo"):
                        compare_price_per_kg = compare_price_sek
                    elif compare_price_unit in ("100g", "100 g"):
                        compare_price_per_kg = compare_price_sek * 10
                    elif compare_price_unit in ("g", "gram"):
                        compare_price_per_kg = compare_price_sek * 1000

                # Förpackningsvikt
                display_volume = raw.get("displayVolume", "")
                package_weight_g = parse_package_weight_g(display_volume, code)

                # Länk
                url_path = raw.get("url")
                if url_path:
                    product_url = "https://www.hemkop.se" + url_path
                else:
                    product_url = f"https://www.hemkop.se/produkt/{code}"

                product_entry = {
                    "name": name,
                    "brand": brand,
                    "code": code,
                    "category": slug,
                    "price_sek": price_sek,
                    "display_volume": display_volume,
                    "package_weight_g": package_weight_g,
                    "compare_price": compare_price_str,
                    "compare_price_per_kg": compare_price_per_kg,
                    "protein_per_100g": None,
                    "protein_per_krona": None,
                    "calculation_method": None,
                    "url": product_url,
                }

                # ── Hämta näringsvärden (om aktiverat) ──
                if fetch_nutrition:
                    _polite_sleep()
                    detail = fetch_product_details(session, code)
                    protein = extract_protein_per_100g(detail)
                    product_entry["protein_per_100g"] = protein

                    if protein is not None:
                        ppk = calculate_protein_per_krona(
                            protein_per_100g=protein,
                            price_sek=price_sek or 0,
                            compare_price_per_kg=compare_price_per_kg,
                            package_weight_g=package_weight_g,
                        )
                        product_entry["protein_per_krona"] = ppk
                        if compare_price_per_kg:
                            product_entry["calculation_method"] = "A (jämförpris/kg)"
                        elif package_weight_g and price_sek:
                            product_entry["calculation_method"] = "B (totalvikt/pris)"

                all_products.append(product_entry)

            _polite_sleep()
            page += 1

            # Avbryt om vi nått max antal sidor eller sista sidan
            if max_pages > 0 and page >= max_pages:
                log.info("Nådde max sidor (%d) för kategori '%s'.", max_pages, slug)
                break
            if total_pages is not None and page >= total_pages:
                break

        log.info("Klar med kategori '%s'. Totalt %d unika produkter hittills.",
                 slug, len(all_products))

    return all_products


def display_results(products: list, top_n: int = 50):
    """
    Presenterar resultaten sorterade efter Protein per Krona (fallande).
    Visar de produkter som HAR proteindata.

    Args:
        products: Lista med produktdicts.
        top_n: Antal toppprodukter att visa.
    """
    # Filtrera produkter med giltig PPK
    valid = [p for p in products if p.get("protein_per_krona") is not None]
    no_data = [p for p in products if p.get("protein_per_100g") is None]

    # Sortera fallande efter protein per krona
    sorted_products = sorted(valid, key=lambda x: x["protein_per_krona"], reverse=True)

    print("\n" + "=" * 90)
    print(f"  HEMKÖP - PROTEIN PER KRONA (g protein / SEK)  -  TOP {top_n}")
    print("=" * 90)
    print(f"  Totalt analyserade produkter: {len(products)}")
    print(f"  Produkter med proteindata:    {len(valid)}")
    print(f"  Produkter utan proteindata:   {len(no_data)}")
    print("-" * 90)

    if PANDAS_AVAILABLE:
        df = pd.DataFrame(sorted_products[:top_n])
        display_cols = [
            "rank", "name", "brand", "category",
            "price_sek", "display_volume", "protein_per_100g",
            "protein_per_krona", "calculation_method"
        ]
        df.insert(0, "rank", range(1, len(df) + 1))
        print(df[[c for c in display_cols if c in df.columns]].to_string(index=False))
    else:
        # Fallback: plain text-utskrift
        header = (
            f"{'#':>3}  {'Produkt':<40}  {'Märke':<18}  "
            f"{'Pris':>7}  {'Vikt':>7}  {'P/100g':>6}  {'P/kr':>7}  Metod"
        )
        print(header)
        print("-" * 90)
        for i, p in enumerate(sorted_products[:top_n], 1):
            name_trunc = (p["name"] or "")[:38]
            brand_trunc = (p["brand"] or "")[:16]
            price_str = f"{p['price_sek']:.2f}" if p["price_sek"] else "N/A"
            weight_str = f"{p['package_weight_g']:.0f}g" if p["package_weight_g"] else "?"
            protein_str = f"{p['protein_per_100g']:.1f}g" if p["protein_per_100g"] else "?"
            ppk_str = f"{p['protein_per_krona']:.4f}" if p["protein_per_krona"] else "N/A"
            method = p.get("calculation_method", "")
            print(
                f"{i:>3}. {name_trunc:<40}  {brand_trunc:<18}  "
                f"{price_str:>7}  {weight_str:>7}  {protein_str:>6}  {ppk_str:>7}  {method}"
            )

    print("-" * 90)
    if no_data:
        print(f"\n  [!] {len(no_data)} produkter saknade näringsvärden och exkluderades.")
    print()

    return sorted_products


# ── Körbara exempel ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Skrapar Hemköp och beräknar Protein per Krona."
    )
    parser.add_argument(
        "--max-pages", type=int, default=0,
        help="Max antal sidor per kategori (0 = alla). Använd t.ex. 2 för snabb test."
    )
    parser.add_argument(
        "--top", type=int, default=50,
        help="Antal topprodukter att visa i resultatlistan."
    )
    parser.add_argument(
        "--categories", nargs="*", default=None,
        help="Specifika kategorier att skrapa (t.ex. kott-fagel-och-chark mejeri-ost-och-agg)."
    )
    parser.add_argument(
        "--no-nutrition", action="store_true",
        help="Hämta INTE näringsvärden (snabbt men PPK beräknas ej)."
    )
    parser.add_argument(
        "--output-json", type=str, default=None,
        help="Spara alla produkter som JSON-fil (t.ex. --output-json results.json)."
    )
    args = parser.parse_args()

    cats = args.categories if args.categories else CATEGORY_SLUGS

    log.info("Startar skrapning av %d kategorier (max %d sidor/kategori)...",
             len(cats), args.max_pages or 999)

    products = scrape_all_categories(
        category_slugs=cats,
        max_pages=args.max_pages,
        fetch_nutrition=not args.no_nutrition,
    )

    if args.output_json:
        import json as _json
        with open(args.output_json, "w", encoding="utf-8") as f:
            _json.dump(products, f, ensure_ascii=False, indent=2)
        log.info("Resultat sparade till '%s'.", args.output_json)

    ranked = display_results(products, top_n=args.top)

    # Returnera topp-20 som pandas DataFrame om tillgängligt
    if PANDAS_AVAILABLE and ranked:
        df_top = pd.DataFrame(ranked[:20])
        print("\nTopp-20 som pandas DataFrame:")
        print(df_top[[
            "name", "brand", "price_sek", "protein_per_100g",
            "protein_per_krona", "calculation_method"
        ]].to_string(index=False))
