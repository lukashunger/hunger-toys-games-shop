# Hunger Toys & Games – Angebots-Website

Statische Website, die automatisch alle offenen Angebote von
[ricardo.ch/de/shop/Hunger-Toys-Games](https://www.ricardo.ch/de/shop/Hunger-Toys-Games/offers/)
anzeigt. Ein GitHub-Actions-Job liest die Angebote täglich neu aus und
aktualisiert `items.json` – die Seite selbst braucht dafür nichts weiter zu tun.

## Dateien

- `index.html` – die eigentliche Website (liest `items.json` und zeigt die Angebote als Karten)
- `items.json` – aktuelle Angebote (Titel, Preis, Bild, Link); wird automatisch überschrieben
- `scraper.py` – Python-Skript, das ricardo.ch ausliest
- `.github/workflows/update.yml` – GitHub-Actions-Job, der `scraper.py` täglich um 07:00 Uhr (CH-Zeit) laufen lässt

## Einrichtung auf GitHub (einmalig)

1. Gehe auf **github.com** und logge dich mit deinem Account (`lukashunger`) ein. Falls noch kein Account existiert: **Sign up**, E-Mail bestätigen.
2. Oben rechts auf **+** → **New repository**.
   - Name: z. B. `hunger-toys-games-shop`
   - Sichtbarkeit: **Public** (nötig für kostenloses GitHub Pages)
   - Sonst nichts ankreuzen → **Create repository**
3. Auf der leeren Repo-Seite auf **uploading an existing file** klicken.
4. Alle Dateien und Ordner aus diesem Ordner (`ricardo-shop-site/`) per Drag & Drop hineinziehen – **inklusive** des versteckten Ordners `.github/`.
   - Falls der `.github`-Ordner beim Drag & Drop nicht mitkommt: auf GitHub oben **Add file → Create new file**, als Dateiname exakt `.github/workflows/update.yml` eingeben (GitHub legt die Ordner automatisch an) und den Inhalt der Datei hineinkopieren.
5. Unten **Commit changes** klicken.
6. Im Repo auf **Settings → Pages**.
   - Bei **Source**: `Deploy from a branch`
   - Branch: `main`, Ordner: `/ (root)` → **Save**
   - Nach 1–2 Minuten ist die Seite live unter `https://lukashunger.github.io/hunger-toys-games-shop/`
7. Im Repo auf **Actions** klicken → falls gefragt, Actions aktivieren. Den Workflow **Update Ricardo Inventory** einmal manuell über **Run workflow** starten, damit sofort auch die Bilder geladen werden (die erste `items.json` hat noch keine Bilder).

Ab jetzt läuft alles automatisch: jeden Morgen liest der Job deine aktuellen
Ricardo-Angebote neu ein, aktualisiert `items.json` und die Website zeigt
den neuen Stand beim nächsten Aufruf.

## Lokal testen (optional)

```bash
pip install requests beautifulsoup4
python scraper.py
python -m http.server 8000
# dann im Browser: http://localhost:8000
```
