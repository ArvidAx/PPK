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
STORES = {
    "hemkop": {"name": "Hemköp", "base_url": "https://www.hemkop.se"},
    "willys": {"name": "Willys", "base_url": "https://www.willys.se"}
}
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

def fetch_category_page(session: requests.Session, base_url: str, category_slug: str, page: int) -> dict:
    """
    Hämtar en sida med produkter från kategorins REST-API.

    Endpoint: GET /c/{category_slug}?size={PAGE_SIZE}&page={page}

    Args:
        session: Aktiv requests.Session.
        base_url: Bas-URL för butiken (t.ex. https://www.hemkop.se).
        category_slug: Kategori-slug, t.ex. "kott-fagel-och-chark".
        page: Sidnummer (0-indexerat).

    Returns:
        Rå JSON-svar som dict, eller tomt dict vid fel.
    """
    url = urljoin(base_url, f"/c/{category_slug}")
    params = {"size": PAGE_SIZE, "page": page}
    log.info("Hämtar kategori '%s' från %s (sida %d)...", category_slug, base_url, page)

    resp = safe_get(session, url, params=params)
    if resp is None:
        return {}

    try:
        return resp.json()
    except (json.JSONDecodeError, ValueError) as exc:
        log.error("Kunde inte parsa JSON för kategori '%s' sida %d: %s",
                  category_slug, page, exc)
        return {}


def fetch_product_details(session: requests.Session, base_url: str, product_code: str) -> dict:
    """
    Hämtar fullständiga produktdetaljer inkl. näringsvärden.

    Endpoint: GET /axfood/rest/p/{product_code}

    Näringsvärden finns i:
      response["nutrientHeaders"][0]["nutrientDetails"]
      Varje element har: nutrientTypeCode, quantityContained, measurementUnitCode

    Args:
        session: En aktiv requests.Session.
        base_url: Bas-URL för butiken (t.ex. https://www.hemkop.se).
        product_code: Produktkod, t.ex. "101262973_ST".

    Returns:
        Rå JSON-svar som dict, eller tomt dict vid fel.
    """
    url = urljoin(base_url, f"/axfood/rest/p/{product_code}")

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


def is_prepared_yield_volume(display_volume: Optional[str], product_text: str = "") -> bool:
    """
    Identifierar volymer som beskriver färdig mängd efter tillagning, inte torr nettovikt.
    Exempel: buljong "8p/4l" betyder 8 tärningar ger 4 liter buljong.
    """
    if not display_volume:
        return False

    text = display_volume.lower().strip()
    product_l = (product_text or "").lower()
    prepared_keywords = (
        "buljong", "fond", "sås", "sas", "soppa", "potatismos", "pulver", "tärning", "tarning"
    )

    if not any(keyword in product_l for keyword in prepared_keywords):
        return False

    return bool(re.search(r"\d+\s*(?:p|st|port|portioner)\s*/\s*\d+[\.,]?\d*\s*(?:l|dl)\b", text))


def parse_package_weight_g(display_volume: Optional[str], url: str = "", product_text: str = "") -> Optional[float]:
    """
    Tolkar förpackningsvikt/-volym till gram (eller ml).
    Hanterar: "500g", "1 kg", "1l", "5dl", "33cl", "250ml", multipack som "3x250ml", etc.
    """
    # Viktsbaserad produkt (säljs per kg) – defaulta till 1000g
    if url and re.search(r"[/_]KG$", url, re.IGNORECASE):
        return 1000.0

    if not display_volume:
        return None

    text = display_volume.lower().strip()

    if is_prepared_yield_volume(text, product_text):
        return None

    # Multipel förpackning med vikter/volymer, t.ex. "2x400g", "12x35g", "3p/25cl", "3x250ml"
    multi_match = re.search(r"(\d+)\s*(?:x|×|p/|st[x*])\s*(\d+[\.,]?\d*)\s*(kg|g|l|dl|cl|ml|gram)", text)
    if multi_match:
        count = float(multi_match.group(1))
        amount = float(multi_match.group(2).replace(",", "."))
        unit = multi_match.group(3)
        if unit in ("kg", "l"):
            return count * amount * 1000
        elif unit == "dl":
            return count * amount * 100
        elif unit == "cl":
            return count * amount * 10
        return count * amount

    # Kilogram / Liter (t.ex. "1,5kg", "1l", "1.5 liter")
    kg_l_match = re.search(r"(\d+[\.,]?\d*)\s*(kg|kilo|kilogram|l|lit|liter)\b", text)
    if kg_l_match:
        return float(kg_l_match.group(1).replace(",", ".")) * 1000

    # Deciliter (t.ex. "5dl")
    dl_match = re.search(r"(\d+[\.,]?\d*)\s*(dl|deciliter|desiliter)\b", text)
    if dl_match:
        return float(dl_match.group(1).replace(",", ".")) * 100

    # Centiliter (t.ex. "33cl")
    cl_match = re.search(r"(\d+[\.,]?\d*)\s*(cl|centiliter)\b", text)
    if cl_match:
        return float(cl_match.group(1).replace(",", ".")) * 10

    # Gram / Milliliter (t.ex. "500g", "250ml")
    g_ml_match = re.search(r"(\d+[\.,]?\d*)\s*(g|gram|gr|ml|milliliter)\b", text)
    if g_ml_match:
        return float(g_ml_match.group(1).replace(",", "."))

    # Rent numeriskt värde (tolkas som gram)
    num_match = re.search(r"(\d+[\.,]?\d*)", text)
    if num_match:
        val = float(num_match.group(1).replace(",", "."))
        # Siffror < 20 är troligen styck (t.ex. "6p"), inte gram
        if val >= 20:
            return val

    return None


def estimate_egg_package_weight(display_volume: Optional[str], name: str, description: str) -> Optional[float]:
    """
    Uppskattar vikten på en äggförpackning i gram.
    1. Hittar antal ägg i förpackningen.
    2. Letar efter viktintervall för ett ägg i beskrivningen (t.ex. '53-73 gram').
    3. Om inget intervall hittas, gissar vi baserat på storleksklass (S, M, L, XL, M/L).
    4. Returnerar antal_ägg * medelvikt.
    """
    is_egg = False
    name_l = name.lower()
    desc_l = description.lower() if description else ""
    
    if re.search(r"\bägg\b", name_l) or re.search(r"\bägg\b", desc_l):
        is_egg = True
        
    exclusions = ["nudlar", "pastej", "röra", "sallad", "smörgås", "skinka", "bacon", "paj", "glass", "våffla", "kakor", "bröd", "ost"]
    for excl in exclusions:
        if excl in name_l:
            is_egg = False
            break
            
    if not is_egg:
        return None

    # 1. Hitta antal ägg (t.ex. "15p", "6p", "10-pack", "15 stycken")
    egg_count = None
    for text in [display_volume, name, description]:
        if not text:
            continue
        count_match = re.search(r"(\d+)\s*(?:p|st|pack|stycken|packe)\b", text.lower())
        if count_match:
            egg_count = int(count_match.group(1))
            break
            
    if not egg_count or egg_count <= 0:
        return None

    # 2. Hitta viktintervall i beskrivningen, t.ex. "(53-73 gram)", "53-73g"
    if description:
        interval_match = re.search(r"(\d+)\s*[-–]\s*(\d+)\s*(?:g|gram)", desc_l)
        if interval_match:
            min_w = float(interval_match.group(1))
            max_w = float(interval_match.group(2))
            avg_weight = (min_w + max_w) / 2.0
            return egg_count * avg_weight

    # 3. Fallback till storleksklass i namn eller beskrivning
    text_to_search = (name_l + " " + desc_l)
    
    if "l/xl" in text_to_search or "large/x-large" in text_to_search or "l-xl" in text_to_search:
        avg_weight = 73.0
    elif "m/l" in text_to_search or "medium/large" in text_to_search or "m-l" in text_to_search or "mediumstora och stora" in text_to_search:
        avg_weight = 63.0
    elif "xl" in text_to_search or "extra large" in text_to_search:
        avg_weight = 78.0
    elif "large" in text_to_search or "stora ägg" in text_to_search or "storlek l" in text_to_search:
        avg_weight = 68.0
    elif "medium" in text_to_search or "mellan" in text_to_search or "mediumstora" in text_to_search or "storlek m" in text_to_search:
        avg_weight = 58.0
    elif "small" in text_to_search or "små ägg" in text_to_search or "storlek s" in text_to_search:
        avg_weight = 48.0
    else:
        avg_weight = 63.0

    return egg_count * avg_weight


def extract_nutrition_per_100g(product_detail: dict) -> dict:
    """
    Extraherar näringsvärden (protein, kalorier, fett, kolhydrater, salt) per 100g.
    """
    result = {
        "protein": None,
        "calories": None,
        "fat": None,
        "carbohydrates": None,
        "salt": None
    }
    
    nutrient_headers = product_detail.get("nutrientHeaders", [])
    if not nutrient_headers:
        return result

    def _parse_val(nutrient, convert_energy_to_kcal: bool = False):
        qty = nutrient.get("quantityContained")
        if qty is None:
            return None
        unit = (nutrient.get("measurementUnitCode") or "").lower()
        try:
            val = float(qty)
            if convert_energy_to_kcal and unit in ("kilojoule", "kj"):
                val /= 4.184
            elif unit in ("milligram", "mg"):
                val /= 1000.0
            elif unit in ("mikrogram", "microgram", "µg", "ug"):
                val /= 1000000.0
            return val
        except (ValueError, TypeError):
            return None

    for header in nutrient_headers:
        basis_qty = header.get("nutrientBasisQuantity")
        if basis_qty and float(basis_qty) != 100:
            continue

        for nutrient in header.get("nutrientDetails", []):
            type_code = (nutrient.get("nutrientTypeCode") or "").lower()
            unit = (nutrient.get("measurementUnitCode") or "").lower()
            val = _parse_val(nutrient, convert_energy_to_kcal="energi" in type_code)
            
            if val is not None:
                if "protein" in type_code:
                    result["protein"] = val
                elif "energi" in type_code and "kilokalori" in unit:
                    result["calories"] = val
                elif "energi" in type_code and result["calories"] is None and unit in ("kilojoule", "kj"):
                    result["calories"] = round(val, 1)
                elif type_code == "fett":
                    result["fat"] = val
                elif type_code == "kolhydrat":
                    result["carbohydrates"] = val
                elif "salt" in type_code:
                    result["salt"] = val
                    
        if result["protein"] is not None:
            break

    # Fallback om ingen 100g basis fanns
    if result["protein"] is None:
        for header in nutrient_headers:
            for nutrient in header.get("nutrientDetails", []):
                type_code = (nutrient.get("nutrientTypeCode") or "").lower()
                unit = (nutrient.get("measurementUnitCode") or "").lower()
                val = _parse_val(nutrient, convert_energy_to_kcal="energi" in type_code)
                if val is not None:
                    if "protein" in type_code:
                        result["protein"] = val
                    elif "energi" in type_code and "kilokalori" in unit:
                        result["calories"] = val
                    elif "energi" in type_code and result["calories"] is None and unit in ("kilojoule", "kj"):
                        result["calories"] = round(val, 1)
                    elif type_code == "fett":
                        result["fat"] = val
                    elif type_code == "kolhydrat":
                        result["carbohydrates"] = val
                    elif "salt" in type_code:
                        result["salt"] = val
            if result["protein"] is not None:
                break
                
    return result


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
    stores: list = None,
) -> list:
    """
    Huvud-skrapningsfunktion. Hämtar produkter från alla angivna kategorier och butiker
    och berikar varje produkt med näringsvärden från produktdetaljsidan.

    Args:
        category_slugs: Lista med kategori-slugs att skrapa.
        max_pages: Max sidor per kategori (0 = alla).
        fetch_nutrition: Om True, hämtas näringsvärden per produkt (långsammare).
        nutrition_delay: Sekunder att vänta mellan näringsdataanrop (None = slumpat).
        stores: Lista med butik-ID:n (t.ex. ["hemkop", "willys"]).

    Returns:
        Lista med produktdicts sorterade efter "protein_per_krona" (fallande).
    """
    if not stores:
        stores = ["hemkop", "willys"]

    session = make_session()
    all_products = []
    seen_keys = set()  # Deduplicering per butik – t.ex. "Hemköp_123"

    for store_key in stores:
        store_info = STORES.get(store_key)
        if not store_info:
            log.warning("Okänd butik: %s. Hoppar över.", store_key)
            continue
        store_name = store_info["name"]
        base_url = store_info["base_url"]

        log.info("Initierar session mot %s...", store_name)
        session.headers.update({"Referer": base_url + "/"})
        warmup_resp = safe_get(session, base_url, timeout=15)
        if warmup_resp:
            log.info("Session initierad för %s.", store_name)
        _polite_sleep()

        for slug in category_slugs:
            log.info("── Startar kategori: %s på %s ──", slug, store_name)
            page = 0
            total_pages = None

            while True:
                data = fetch_category_page(session, base_url, slug, page)
                if not data:
                    log.warning("Inga data för kategori '%s' på %s, sida %d. Hoppar.", slug, store_name, page)
                    break

                # Extrahera pagineringsinformation
                pagination = data.get("pagination", {})
                if total_pages is None:
                    total_pages = pagination.get("numberOfPages", 1)
                    total_items = pagination.get("totalNumberOfResults", "?")
                    log.info("Kategori '%s' på %s: %s produkter totalt, %d sidor.",
                             slug, store_name, total_items, total_pages)

                results = data.get("results", [])
                if not results:
                    log.info("Inga fler produkter för kategori '%s' på %s.", slug, store_name)
                    break

                log.info("Kategori '%s' på %s, sida %d/%d: %d produkter.",
                         slug, store_name, page + 1, total_pages, len(results))

                for raw in results:
                    code = raw.get("code", "")
                    if not code:
                        continue
                    seen_key = f"{store_name}_{code}"
                    if seen_key in seen_keys:
                        continue
                    seen_keys.add(seen_key)

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

                    # Jämförpris per KG (normalisera om enheten är "liter", "100ml" etc.)
                    compare_price_per_kg = None
                    if compare_price_sek is not None:
                        compare_unit_clean = compare_price_unit.replace(" ", "").strip()
                        if compare_unit_clean in ("kg", "kilo", "l", "lit", "liter"):
                            compare_price_per_kg = compare_price_sek
                        elif compare_unit_clean in ("100g", "100ml", "100 g", "100 ml", "dl", "deciliter"):
                            compare_price_per_kg = compare_price_sek * 10
                        elif compare_unit_clean in ("g", "gram", "ml", "milliliter"):
                            compare_price_per_kg = compare_price_sek * 1000
                        elif compare_unit_clean in ("cl", "centiliter"):
                            compare_price_per_kg = compare_price_sek * 100

                    # Förpackningsvikt
                    display_volume = raw.get("displayVolume", "")
                    package_weight_g = parse_package_weight_g(display_volume, code)
                    if not package_weight_g:
                        package_weight_g = parse_package_weight_g(name, code)

                    # Länk
                    url_path = raw.get("url")
                    if url_path:
                        product_url = base_url + url_path
                    else:
                        product_url = f"{base_url}/produkt/{code}"

                    product_entry = {
                        "name": name,
                        "brand": brand,
                        "code": code,
                        "store": store_name,
                        "category": slug,
                        "price_sek": price_sek,
                        "display_volume": display_volume,
                        "package_weight_g": package_weight_g,
                        "compare_price": compare_price_str,
                        "compare_price_per_kg": compare_price_per_kg,
                        "description": "",
                        "protein_per_100g": None,
                        "calories_per_100g": None,
                        "fat_per_100g": None,
                        "carbohydrates_per_100g": None,
                        "salt_per_100g": None,
                        "protein_per_krona": None,
                        "calculation_method": None,
                        "url": product_url,
                    }

                    # ── Hämta näringsvärden (om aktiverat) ──
                    if fetch_nutrition:
                        _polite_sleep()
                        detail = fetch_product_details(session, base_url, code)
                        
                        product_entry["description"] = detail.get("description", "")
                        
                        # Särskild hantering för ägg där vikt saknas men kan uppskattas från beskrivning/namn
                        if not package_weight_g:
                            egg_weight = estimate_egg_package_weight(
                                display_volume=display_volume,
                                name=name,
                                description=product_entry["description"]
                            )
                            if egg_weight:
                                package_weight_g = egg_weight
                                product_entry["package_weight_g"] = package_weight_g
                                
                                # Om jämförpris saknas för äggen, räkna ut det baserat på estimerad vikt
                                if not compare_price_per_kg and price_sek:
                                    compare_price_per_kg = (price_sek / package_weight_g) * 1000
                                    product_entry["compare_price_per_kg"] = compare_price_per_kg
                                    product_entry["compare_price"] = f"{compare_price_per_kg:.2f} kr/kg (beräknat)"
                        
                        nutrition = extract_nutrition_per_100g(detail)
                        protein = nutrition["protein"]
                        
                        product_entry["protein_per_100g"] = protein
                        product_entry["calories_per_100g"] = nutrition["calories"]
                        product_entry["fat_per_100g"] = nutrition["fat"]
                        product_entry["carbohydrates_per_100g"] = nutrition["carbohydrates"]
                        product_entry["salt_per_100g"] = nutrition["salt"]

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
                    log.info("Nådde max sidor (%d) för kategori '%s' på %s.", max_pages, slug, store_name)
                    break
                if total_pages is not None and page >= total_pages:
                    break

            log.info("Klar med kategori '%s' på %s. Totalt %d unika produkter hittills.",
                     slug, store_name, len(all_products))

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
    parser.add_argument(
        "--stores", nargs="*", default=["hemkop", "willys"],
        help="Specifika butiker att skrapa (t.ex. --stores hemkop willys)."
    )
    args = parser.parse_args()

    cats = args.categories if args.categories else CATEGORY_SLUGS
    stores_to_scrape = args.stores

    log.info("Startar skrapning av %d butiker och %d kategorier (max %d sidor/kategori)...",
             len(stores_to_scrape), len(cats), args.max_pages or 999)

    products = scrape_all_categories(
        category_slugs=cats,
        max_pages=args.max_pages,
        fetch_nutrition=not args.no_nutrition,
        stores=stores_to_scrape,
    )

    if args.output_json is None:
        args.output_json = "public/data.json"
        
    import json as _json
    import os
    from datetime import datetime
    os.makedirs(os.path.dirname(args.output_json) or ".", exist_ok=True)
    with open(args.output_json, "w", encoding="utf-8") as f:
        _json.dump(products, f, ensure_ascii=False, indent=2)
    log.info("Resultat sparade till '%s'.", args.output_json)

    last_updated_json = os.path.join(os.path.dirname(args.output_json) or ".", "last_updated.json")
    with open(last_updated_json, "w", encoding="utf-8") as f:
        _json.dump({"updated_at": datetime.now().astimezone().replace(hour=2, minute=0, second=0, microsecond=0).isoformat()}, f, ensure_ascii=False, indent=2)
    log.info("Uppdateringstid sparad till '%s'.", last_updated_json)

    ranked = display_results(products, top_n=args.top)

    # Returnera topp-20 som pandas DataFrame om tillgängligt
    if PANDAS_AVAILABLE and ranked:
        df_top = pd.DataFrame(ranked[:20])
        print("\nTopp-20 som pandas DataFrame:")
        print(df_top[[
            "name", "brand", "price_sek", "protein_per_100g",
            "protein_per_krona", "calculation_method"
        ]].to_string(index=False))
