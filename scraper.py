#!/usr/bin/env python3
"""
Scraper fuer den Hunger-Toys-Games Ricardo-Shop.

Liest alle offenen Angebote von der oeffentlichen Ricardo-Verkaeuferseite
(https://www.ricardo.ch/de/shop/Hunger-Toys-Games/offers/) und schreibt sie
als items.json (fuer index.html) ins Repo-Root.

Laeuft normalerweise automatisch ueber GitHub Actions
(.github/workflows/update.yml), kann aber auch lokal ausgefuehrt werden:

    pip install curl_cffi beautifulsoup4
    python scraper.py

Wichtig: ricardo.ch blockt Anfragen ohne echten Browser-"Fingerprint" (403
Forbidden). Deshalb wird ueber curl_cffi mit impersonate="chrome" ein echter
Chrome-TLS-Fingerprint nachgeahmt. Falls curl_cffi nicht installiert ist,
faellt das Skript auf das normale requests-Modul zurueck (kann dann von
ricardo.ch geblockt werden).

Sicherheitsnetz: Wenn beim Einlesen 0 Angebote gefunden werden (z.B. weil
ricardo.ch die Anfrage blockiert oder das Seiten-Layout sich geaendert hat),
wird items.json NICHT ueberschrieben -> die zuletzt bekannten Angebote
bleiben online sichtbar, statt durch eine leere Liste ersetzt zu werden.
"""

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

try:
    from curl_cffi import requests as http  # echter Browser-TLS-Fingerprint
    IMPERSONATE = "chrome124"
except ImportError:  # Fallback fuer lokale Umgebungen ohne curl_cffi
    import requests as http  # type: ignore
    IMPERSONATE = None

SHOP_URL = "https://www.ricardo.ch/de/shop/Hunger-Toys-Games/offers/"
OUTPUT_FILE = Path(__file__).parent / "items.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "de-CH,de;q=0.9,en;q=0.8",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

REQUEST_DELAY = 0.8  # Sekunden zwischen Requests, um freundlich zu bleiben
MAX_PAGES = 15  # Sicherheitslimit gegen Endlosschleifen
MIN_EXPECTED_RATIO = 0.5  # bricht ab, wenn <50% der bisherigen Angebote gefunden werden


def _session():
    if IMPERSONATE:
        return http.Session(impersonate=IMPERSONATE, headers=HEADERS)
    s = http.Session()
    s.headers.update(HEADERS)
    return s


SESSION = _session()


def fetch(url: str) -> str:
    resp = SESSION.get(url, timeout=25)
    resp.raise_for_status()
    return resp.text


def collect_product_urls() -> list[str]:
    """Sammelt alle eindeutigen Produkt-URLs von der Shop-Seite (inkl. Paginierung)."""
    urls: list[str] = []
    seen = set()

    for page in range(1, MAX_PAGES + 1):
        page_url = SHOP_URL if page == 1 else f"{SHOP_URL}?page={page}"
        try:
            html = fetch(page_url)
        except Exception as e:
            print(f"[warn] konnte Seite {page} nicht laden: {e}", file=sys.stderr)
            break

        found = re.findall(r'href="(/de/a/[^"]+?-\d+/)"', html)
        new_on_page = [u for u in found if u not in seen]

        if not new_on_page:
            # keine neuen Artikel mehr -> letzte Seite erreicht
            break

        for u in new_on_page:
            seen.add(u)
            urls.append("https://www.ricardo.ch" + u)

        time.sleep(REQUEST_DELAY)

    return urls


def parse_product(url: str) -> dict | None:
    try:
        html = fetch(url)
    except Exception as e:
        print(f"[warn] konnte {url} nicht laden: {e}", file=sys.stderr)
        return None

    soup = BeautifulSoup(html, "html.parser")

    def meta(name_or_prop: str, attr: str = "property") -> str | None:
        tag = soup.find("meta", attrs={attr: name_or_prop})
        return tag["content"].strip() if tag and tag.get("content") else None

    title = meta("og:title") or (soup.title.string if soup.title else None) or ""
    title = re.sub(r"\s*\|\s*Kaufen auf Ricardo.*$", "", title).strip()

    image = meta("og:image")

    description = meta("og:description") or ""
    price = None
    m = re.search(r"Preis:\s*CHF\s*([\d.,'’]+)", description)
    if m:
        price_str = m.group(1).replace("'", "").replace("’", "").replace(",", ".")
        try:
            price = float(price_str)
        except ValueError:
            price = None

    condition = None
    m = re.search(r"Zustand:\s*([^|]+)", description)
    if m:
        condition = m.group(1).strip()

    id_match = re.search(r"-(\d+)/?$", url)
    item_id = id_match.group(1) if id_match else url

    # Marke best-effort aus Titel ableiten (Fallback wenn og-Daten nichts hergeben)
    brand = None
    for candidate in ["Lego", "LEGO", "Pokémon", "Pokemon", "Nintendo", "Sony"]:
        if candidate.lower() in title.lower():
            brand = "Pokémon" if "pok" in candidate.lower() else candidate.capitalize()
            break
    if brand is None:
        brand = "Sonstige"

    return {
        "id": item_id,
        "title": title,
        "brand": brand,
        "price": price,
        "condition": condition,
        "image": image,
        "url": url,
    }


def load_existing() -> dict:
    if OUTPUT_FILE.exists():
        try:
            return json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"items": []}


def main() -> None:
    existing = load_existing()
    existing_items = existing.get("items", [])
    existing_by_id = {i["id"]: i for i in existing_items}

    product_urls = collect_product_urls()
    print(f"[info] {len(product_urls)} Angebote gefunden (vorher: {len(existing_items)}).")

    # Sicherheitsnetz: nichts kaputt schreiben, wenn ricardo.ch blockiert hat
    # oder aus anderem Grund fast nichts zurueckkam.
    if existing_items and len(product_urls) < len(existing_items) * MIN_EXPECTED_RATIO:
        print(
            f"[error] Nur {len(product_urls)} von vorher {len(existing_items)} Angeboten "
            "gefunden - vermutlich von ricardo.ch blockiert. Breche ab, items.json bleibt "
            "unveraendert.",
            file=sys.stderr,
        )
        sys.exit(1)

    items = []
    for url in product_urls:
        item = parse_product(url)
        time.sleep(REQUEST_DELAY)

        id_match = re.search(r"-(\d+)/?$", url)
        item_id = id_match.group(1) if id_match else url

        if item is None:
            # Fetch fehlgeschlagen -> alten Eintrag behalten, falls vorhanden
            if item_id in existing_by_id:
                print(f"[info] behalte gecachten Eintrag fuer {item_id}")
                items.append(existing_by_id[item_id])
            continue

        items.append(item)

    data = {
        "shop": "Hunger-Toys-Games",
        "shop_url": SHOP_URL,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "items": items,
    }

    OUTPUT_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[info] {len(items)} Angebote nach {OUTPUT_FILE} geschrieben.")


if __name__ == "__main__":
    main()
