#!/usr/bin/env python3
"""
cherche_maison.py — Script de recherche maison retraités
=========================================================
Objectif  : trouver maison à louer avec jardin/terrasse ≤850€/mois
Zone      : Var (83) + Alpes-de-Haute-Provence (04) — ≤1h30 Toulon
Public    : retraités → priorité calme, services, bon climat

Sources:
  [1] Bienici           — API JSON directe ✅ (agrège Century21, ERA, Hektor, ImmoFacile...)
  [2] Entreparticuliers  — particuliers à particuliers ✅
  [3] LeBonCoin         — ❌ bloqué DataDome (impossible sans proxy payant)
  [4] SeLoger           — ❌ bloqué côté serveur
  [5] PAP               — ❌ 0 résultats Var/04 à ce prix

Résultats : affichés + exportés CSV horodaté

Requis:
  pip3 install playwright --break-system-packages
  python3 -m playwright install chromium
"""

import asyncio, csv, json, math, re, time, urllib.request, urllib.parse, webbrowser, os
from datetime import datetime

# Toulon centre
TOULON_LAT = 43.1242
TOULON_LON = 5.9280

def distance_km(lat, lon):
    if lat is None or lon is None:
        return None
    R = 6371
    dlat = math.radians(lat - TOULON_LAT)
    dlon = math.radians(lon - TOULON_LON)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(TOULON_LAT)) * math.cos(math.radians(lat)) * math.sin(dlon/2)**2
    return round(R * 2 * math.asin(math.sqrt(a)), 1)

# ── CONFIG ────────────────────────────────────────────────────────────────────
MAX_PRIX    = 850
HEADLESS    = False   # False = navigateur visible (bypass DataDome mieux)
TIMEOUT_NAV = 25000   # ms

KEYWORDS_JARDIN = [
    "jardin", "terrain", "extérieur", "exterieur",
    "cour", "terrasse", "espace vert", "verdure", "parc",
    "clos", "enclos", "potager", "pelouse", "gazon", "patio",
    "outdoor", "plein air",
]

# ── BIENICI ZONE IDs (res.bienici.com/place.json) ────────────────────────────
# Niveau département = couvre TOUTES les communes
BIENICI_DEPTS = {
    "Var (83)":                    "-7390",
    "Alpes-de-Haute-Provence (04)": "-7380",
}

# Niveau commune = résultats plus précis pour villages ciblés retraités
BIENICI_VILLES = {
    # Var intérieur — calme, abordable
    "Brignoles (83)":          "-252749",
    "Signes (83)":             "-125420",
    "Nans-les-Pins (83)":      "-2694688",
    "Besse-sur-Issole (83)":   "-241355",
    "La Roquebrussanne (83)":  "-2690186",
    "Le Luc (83)":             "-225037",
    "Cuers (83)":              "-969748",
    "Lorgues (83)":            "-125337",
    "Trans-en-Provence (83)":  "-190815",
    "Draguignan (83)":         "-125329",
    # Alpes-de-Haute-Provence — TOP retraités, très abordable
    "Gréoux-les-Bains (04) ★": "-365374",
    "Valensole (04)":          "-1373073",
    "Manosque (04)":           "-365373",
    "Riez (04)":               "-364775",
    "Forcalquier (04)":        "-971007",
    "St-Martin-de-Brômes (04)":"-422649",
    "Allemagne-en-Provence (04)":"-364779",
}

# ── HELPERS ───────────────────────────────────────────────────────────────────

def a_jardin(txt: str) -> bool:
    t = txt.lower()
    return any(k in t for k in KEYWORDS_JARDIN)


def prix_int(txt: str) -> int:
    m = re.search(r'(\d[\d\s\.]{1,6})\s*€', txt)
    if not m:
        return 0
    try:
        return int(re.sub(r'[\s\.]', '', m.group(1)))
    except ValueError:
        return 0


def surface_str(txt: str) -> str:
    m = re.search(r'(\d+(?:[,.]\d+)?)\s*m[²2]', txt)
    return m.group(1) if m else ""


def pieces_str(txt: str) -> str:
    m = re.search(r'(\d+)\s*(?:pièce|piece|p\.)', txt, re.IGNORECASE)
    return m.group(1) if m else ""


def http_get(url: str) -> bytes | None:
    hdrs = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/122",
        "Accept": "application/json, */*",
        "Accept-Language": "fr-FR,fr;q=0.9",
    }
    try:
        req = urllib.request.Request(url, headers=hdrs)
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.read()
    except Exception:
        return None


def annonce(source, ville, prix, surface, pieces, titre, lien, photos=None, description="", lat=None, lon=None):
    dist = distance_km(lat, lon)
    return {
        "source": source, "ville": ville, "prix": prix,
        "surface": surface, "pieces": pieces,
        "titre": titre[:100], "lien": lien,
        "photos": photos or [],
        "description": description[:500],
        "lat": lat, "lon": lon, "distance_km": dist,
    }


# ─────────────────────────────────────────────────────────────────────────────
# SOURCE 1 — BIENICI (API JSON directe — FIABLE)
# Pas de navigateur, pas de blocage, résultats réels
# ─────────────────────────────────────────────────────────────────────────────

def bienici_search(zone_ids: list[str], label: str, size=100) -> list:
    filtre = {
        "size": size, "from": 0,
        "filterType": "rent",
        "propertyType": ["house"],
        "maxPrice": MAX_PRIX,
        "onTheMarket": [True],
        "sortBy": "relevance", "sortOrder": "desc",
        "blurInfoType": ["disk", "exact"],
        "zoneIdsByTypes": {"zoneIds": zone_ids},
    }
    url = (
        "https://www.bienici.com/realEstateAds.json?filters="
        + urllib.parse.quote(json.dumps(filtre))
        + "&extensionType=extendedIfNoResult"
    )
    raw = http_get(url)
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data.get("realEstateAds", [])
    except Exception:
        return []


def scrape_bienici() -> list:
    print("\n[Bienici] API directe ...")
    resultats = []
    vus = set()

    # Recherche département entier d'abord
    for label, zid in BIENICI_DEPTS.items():
        ads = bienici_search([zid], label, size=100)
        total = len(ads)
        if total:
            print(f"  {label}: {total} annonces brutes")
        for a in ads:
            ad_id = a.get("id", "")
            if ad_id in vus:
                continue
            vus.add(ad_id)
            titre = (a.get("title") or "").strip()
            desc  = a.get("description") or ""
            prix  = a.get("price") or 0
            ville = a.get("city") or ""
            cp    = a.get("postalCode") or ""
            if not (0 < prix <= MAX_PRIX):
                continue
            if not a_jardin(titre + " " + desc):
                continue
            photos = [p.get("url", "") for p in (a.get("photos") or []) if p.get("url")]
            blur_pos = (a.get("blurInfo") or {}).get("position") or {}
            resultats.append(annonce(
                "Bienici", f"{ville} ({cp})", prix,
                str(a.get("surfaceArea") or ""),
                str(a.get("roomsQuantity") or ""),
                titre or desc[:80],
                "https://www.bienici.com/annonce/" + str(ad_id),
                photos=photos, description=desc,
                lat=blur_pos.get("lat"), lon=blur_pos.get("lon"),
            ))
        time.sleep(0.5)

    # Recherche par commune pour villages ciblés (complément)
    for label, zid in BIENICI_VILLES.items():
        ads = bienici_search([zid], label, size=50)
        for a in ads:
            ad_id = a.get("id", "")
            if ad_id in vus:
                continue
            vus.add(ad_id)
            titre = (a.get("title") or "").strip()
            desc  = a.get("description") or ""
            prix  = a.get("price") or 0
            ville = a.get("city") or label
            cp    = a.get("postalCode") or ""
            if not (0 < prix <= MAX_PRIX):
                continue
            if not a_jardin(titre + " " + desc):
                continue
            photos = [p.get("url", "") for p in (a.get("photos") or []) if p.get("url")]
            blur_pos = (a.get("blurInfo") or {}).get("position") or {}
            resultats.append(annonce(
                "Bienici", f"{ville} ({cp})", prix,
                str(a.get("surfaceArea") or ""),
                str(a.get("roomsQuantity") or ""),
                titre or desc[:80],
                "https://www.bienici.com/annonce/" + str(ad_id),
                photos=photos, description=desc,
                lat=blur_pos.get("lat"), lon=blur_pos.get("lon"),
            ))
        time.sleep(0.2)

    print(f"  → {len(resultats)} maisons avec jardin/terrasse ≤{MAX_PRIX}€")
    return resultats


# ─────────────────────────────────────────────────────────────────────────────
# PLAYWRIGHT helpers
# ─────────────────────────────────────────────────────────────────────────────

async def accept_cookies(page):
    for sel in [
        "#didomi-notice-agree-button", "button#acceptAll",
        "button[id*='accept']", "button[aria-label*='accepter' i]",
        ".didomi-continue-without-agreeing",
        "button[data-testid*='accept']",
    ]:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=1500):
                await btn.click()
                await asyncio.sleep(0.8)
                return
        except Exception:
            pass


async def scroll_down(page, n=5):
    for _ in range(n):
        await page.keyboard.press("End")
        await asyncio.sleep(0.5)


async def extraire_blocs(annonces, source: str) -> list:
    resultats = []
    for a in annonces:
        try:
            txt = await a.inner_text()
            # Récupère href depuis l'élément ou son enfant <a>
            href = await a.get_attribute("href") or ""
            if not href:
                el = await a.query_selector("a[href]")
                href = (await el.get_attribute("href")) if el else ""

            prix = prix_int(txt)
            if not (0 < prix <= MAX_PRIX):
                continue
            if not a_jardin(txt):
                continue

            base = {
                "leboncoin": "https://www.leboncoin.fr",
                "Orpi": "https://www.orpi.com",
                "Century21": "https://www.century21.fr",
                "SeLoger": "https://www.seloger.com",
                "PAP": "https://www.pap.fr",
            }.get(source, "")

            lien = href if href.startswith("http") else base + href
            titre = txt.strip().split("\n")[0]
            vm = re.search(r'(\d{5})', txt)
            cp = vm.group(1) if vm else ""

            resultats.append(annonce(
                source, f"{source} ({cp})" if cp else source,
                prix, surface_str(txt), pieces_str(txt), titre, lien,
            ))
        except Exception:
            continue
    return resultats


async def new_page(ctx):
    return await ctx.new_page()


# ─────────────────────────────────────────────────────────────────────────────
# SOURCE 2 — ENTREPARTICULIERS.COM
# Particuliers → particuliers, souvent moins cher, moins protégé
# ─────────────────────────────────────────────────────────────────────────────

async def scrape_entreparticuliers(ctx) -> list:
    print("\n[Entreparticuliers] ...")
    resultats = []
    page = await new_page(ctx)

    ZONES = [
        (f"https://www.entreparticuliers.com/annonces-immobilieres/locations/maisons/var/?loyer_max={MAX_PRIX}", "Var"),
        (f"https://www.entreparticuliers.com/annonces-immobilieres/locations/maisons/alpes-de-haute-provence/?loyer_max={MAX_PRIX}", "04"),
    ]

    for url, label in ZONES:
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_NAV)
            await accept_cookies(page)
            await asyncio.sleep(3)
            await scroll_down(page)

            blocs = await page.query_selector_all(
                "article, .annonce, [class*='annonce'], "
                "[class*='listing-item'], [class*='property'], "
                "li[class*='result'], .ad-item"
            )
            print(f"  EP {label}: {len(blocs)} blocs")
            resultats += await extraire_blocs(blocs, "Entreparticuliers")
        except Exception as e:
            print(f"  EP {label}: {e}")

    await page.close()
    print(f"  → {len(resultats)} résultats")
    return resultats


# ─────────────────────────────────────────────────────────────────────────────
# AFFICHAGE + EXPORT
# ─────────────────────────────────────────────────────────────────────────────

def generer_html(resultats: list) -> str:
    fname = f"maisons_toulon_{datetime.now().strftime('%Y%m%d_%H%M')}.html"

    cartes = ""
    for r in resultats:
        photos = r.get("photos", [])
        # Galerie photos
        if photos:
            imgs = "".join(
                f'<img src="{p}" alt="photo" loading="lazy" '
                f'onclick="this.parentElement.querySelector(\'.main-img\').src=\'{p}\'">'
                for p in photos[1:6]
            )
            galerie = f"""
            <div class="gallery">
                <img class="main-img" src="{photos[0]}" alt="{r['titre']}" onerror="this.src='https://via.placeholder.com/600x400?text=Pas+de+photo'">
                <div class="thumbs">{imgs}</div>
            </div>"""
        else:
            galerie = '<div class="no-photo">📷 Pas de photo disponible</div>'

        # Badges infos
        badges = ""
        dist = r.get("distance_km")
        if dist is not None:
            badges += f'<span class="badge dist">📍 {dist} km de Toulon</span>'
        if r.get("surface"):
            badges += f'<span class="badge">📐 {r["surface"]} m²</span>'
        if r.get("pieces"):
            badges += f'<span class="badge">🚪 {r["pieces"]} pièces</span>'
        badges += f'<span class="badge source">{r["source"]}</span>'

        desc_html = r.get("description", "").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
        dist_label = f'<div class="dist-banner">🚗 {dist} km de Toulon (vol d\'oiseau)</div>' if dist is not None else ""

        cartes += f"""
        <div class="card" id="card-{id(r)}">
            {galerie}
            <div class="card-body">
                <div class="prix">{r['prix']} €<span>/mois</span></div>
                {dist_label}
                <div class="ville">📍 {r['ville']}</div>
                <h2 class="titre">{r['titre']}</h2>
                <div class="badges">{badges}</div>
                {"<p class='desc'>" + desc_html + "</p>" if desc_html else ""}
                <a href="{r['lien']}" target="_blank" class="btn-voir">
                    Voir l'annonce complète →
                </a>
            </div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Maisons à louer — {len(resultats)} résultats ≤{MAX_PRIX}€/mois</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Segoe UI', Arial, sans-serif;
    background: #f0f2f5;
    color: #222;
  }}
  header {{
    background: linear-gradient(135deg, #1a6f3c, #2ecc71);
    color: white;
    padding: 2rem;
    text-align: center;
    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
  }}
  header h1 {{ font-size: 2rem; margin-bottom: .5rem; }}
  header p  {{ opacity: .85; font-size: 1.1rem; }}
  .stats {{
    display: flex; gap: 2rem; justify-content: center;
    padding: 1.5rem; background: white;
    border-bottom: 2px solid #e0e0e0;
    flex-wrap: wrap;
  }}
  .stat {{ text-align: center; }}
  .stat strong {{ display: block; font-size: 2rem; color: #1a6f3c; }}
  .stat span {{ font-size: .85rem; color: #666; }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
    gap: 1.5rem;
    padding: 2rem;
    max-width: 1400px;
    margin: 0 auto;
  }}
  .card {{
    background: white;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 2px 12px rgba(0,0,0,0.1);
    transition: transform .2s, box-shadow .2s;
  }}
  .card:hover {{
    transform: translateY(-4px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.15);
  }}
  .gallery {{ position: relative; background: #111; }}
  .gallery .main-img {{
    width: 100%; height: 240px; object-fit: cover;
    display: block; cursor: zoom-in;
    transition: opacity .2s;
  }}
  .gallery .thumbs {{
    display: flex; gap: 4px; padding: 4px;
    background: #222; overflow-x: auto;
  }}
  .gallery .thumbs img {{
    height: 56px; width: 80px; object-fit: cover;
    border-radius: 4px; cursor: pointer; opacity: .7;
    transition: opacity .2s; flex-shrink: 0;
  }}
  .gallery .thumbs img:hover {{ opacity: 1; }}
  .no-photo {{
    height: 180px; display: flex; align-items: center;
    justify-content: center; background: #f5f5f5;
    color: #999; font-size: 1.2rem;
  }}
  .card-body {{ padding: 1.2rem; }}
  .prix {{
    font-size: 1.8rem; font-weight: 700; color: #1a6f3c;
    margin-bottom: .3rem;
  }}
  .prix span {{ font-size: 1rem; font-weight: 400; color: #666; }}
  .ville {{ color: #555; margin-bottom: .5rem; font-size: .95rem; }}
  .titre {{
    font-size: 1rem; font-weight: 600; margin-bottom: .8rem;
    color: #222; line-height: 1.4;
  }}
  .badges {{ display: flex; flex-wrap: wrap; gap: .4rem; margin-bottom: .8rem; }}
  .badge {{
    background: #e8f5e9; color: #1a6f3c;
    padding: .25rem .6rem; border-radius: 20px;
    font-size: .8rem; font-weight: 600;
  }}
  .badge.source {{ background: #e3f2fd; color: #1565c0; }}
  .badge.dist {{ background: #fff3e0; color: #e65100; font-weight: 700; }}
  .dist-banner {{
    font-size: .85rem; font-weight: 700; color: #e65100;
    background: #fff3e0; border-radius: 6px;
    padding: .3rem .6rem; margin-bottom: .5rem; display: inline-block;
  }}
  .desc {{
    font-size: .85rem; color: #555; line-height: 1.5;
    margin-bottom: 1rem; max-height: 100px;
    overflow: hidden; position: relative;
  }}
  .desc::after {{
    content: ''; position: absolute; bottom: 0; left: 0; right: 0;
    height: 30px;
    background: linear-gradient(transparent, white);
  }}
  .btn-voir {{
    display: block; text-align: center;
    background: #1a6f3c; color: white;
    padding: .75rem 1rem; border-radius: 8px;
    text-decoration: none; font-weight: 600;
    transition: background .2s;
  }}
  .btn-voir:hover {{ background: #155c30; }}
  .aucun {{
    text-align: center; padding: 4rem 2rem; color: #666;
  }}
  .aucun h2 {{ font-size: 1.5rem; margin-bottom: 1rem; color: #c0392b; }}
  footer {{
    text-align: center; padding: 2rem; color: #999;
    font-size: .85rem; border-top: 1px solid #e0e0e0;
    margin-top: 2rem;
  }}
</style>
</head>
<body>

<header>
  <h1>🏡 Maisons à louer — Retraités</h1>
  <p>Var (83) + Alpes-de-Haute-Provence (04) · ≤ {MAX_PRIX} €/mois · Jardin/Terrasse</p>
  <p style="font-size:.9rem;opacity:.8">📍 Triées du plus proche au plus loin de Toulon</p>
</header>

<div class="stats">
  <div class="stat"><strong>{len(resultats)}</strong><span>annonces trouvées</span></div>
  <div class="stat"><strong>{min((r['prix'] for r in resultats), default=0)} €</strong><span>prix min</span></div>
  <div class="stat"><strong>{max((r['prix'] for r in resultats), default=0)} €</strong><span>prix max</span></div>
  <div class="stat"><strong>{datetime.now().strftime('%d/%m/%Y %H:%M')}</strong><span>dernière mise à jour</span></div>
</div>

<div class="grid">
{"  " + cartes if cartes else '<div class="aucun"><h2>Aucun résultat trouvé</h2><p>Relancez le script demain — les annonces changent quotidiennement.</p></div>'}
</div>

<footer>
  Généré par cherche_maison.py · Sources: Bienici (Century21+ERA+Hektor+ImmoFacile...) + Entreparticuliers<br>
  Relancer: <code>python3 cherche_maison.py</code>
</footer>

</body>
</html>"""

    with open(fname, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n✓ HTML: {fname}")
    return fname


def afficher(resultats: list):
    print(f"\n{'='*70}")
    if not resultats:
        print("  AUCUN RÉSULTAT TROUVÉ")
        print("="*70)
        print("\nConseils: chercher manuellement sur")
        print("  https://www.leboncoin.fr → Immobilier → Maison → Var → ≤850€")
        print("  https://www.pap.fr → Locations → Maison → Var")
        print("  https://www.bienici.com → Location maison Var ≤850€")
        return

    resultats.sort(key=lambda x: (x["distance_km"] is None, x["distance_km"] or 0))
    print(f"  {len(resultats)} MAISONS AVEC JARDIN/TERRASSE ≤{MAX_PRIX}€/mois")
    print(f"  Var (83) + Alpes-de-Haute-Provence (04) — idéal retraités")
    print("="*70)

    for r in resultats:
        infos = [f"\n[{r['source']}]", r["ville"], "—", f"{r['prix']}€/mois"]
        if r.get("surface"):
            infos += ["|", f"{r['surface']}m²"]
        if r.get("pieces"):
            infos += ["|", f"{r['pieces']} pièces"]
        print(" ".join(infos))
        print(f"  {r['titre']}")
        print(f"  {r['lien']}")


def exporter_csv(resultats: list):
    if not resultats:
        return
    fname = f"maisons_toulon_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    champs = ["source", "ville", "prix", "surface", "pieces", "titre", "lien"]
    with open(fname, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=champs, extrasaction="ignore")
        w.writeheader()
        w.writerows(resultats)
    print(f"\n✓ CSV: {fname}")
    print(f"  libreoffice --calc {fname}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    from playwright.async_api import async_playwright

    print("=" * 70)
    print(f"RECHERCHE MAISON+JARDIN ≤{MAX_PRIX}€/mois — RETRAITÉS")
    print(f"Zones: Var (83) + Alpes-de-Haute-Provence (04)")
    print(f"Mode navigateur: {'visible' if not HEADLESS else 'headless'}")
    print("=" * 70)

    tous = []

    # Bienici sans navigateur (API directe)
    tous += scrape_bienici()

    # Autres sources avec Playwright
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=HEADLESS,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        ctx = await browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            locale="fr-FR",
            timezone_id="Europe/Paris",
        )
        # Masque webdriver flag
        await ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        for scraper in [
            scrape_entreparticuliers,
        ]:
            try:
                tous += await scraper(ctx)
            except Exception as e:
                print(f"  ERREUR {scraper.__name__}: {e}")
            await asyncio.sleep(1)

        await browser.close()

    # Dédoublonner par lien
    seen, uniq = set(), []
    for r in tous:
        k = r.get("lien") or r.get("titre", "")
        if k and k not in seen:
            seen.add(k)
            uniq.append(r)

    afficher(uniq)
    exporter_csv(uniq)

    # Génère page HTML + ouvre dans le navigateur
    html_file = generer_html(uniq)
    webbrowser.open(f"file://{os.path.abspath(html_file)}")

    print(f"\nTOTAL: {len(uniq)} annonces uniques trouvées")
    print(f"Page HTML ouverte dans votre navigateur.")


if __name__ == "__main__":
    asyncio.run(main())
