# 🏡 Cherche Maison — Retraités près de Toulon

Script Python qui recherche automatiquement des **maisons à louer avec jardin** dans le Var (83) et les Alpes-de-Haute-Provence (04), triées par distance de Toulon.

Conçu pour des **retraités** qui cherchent un village calme, agréable et abordable à moins de 1h30 de Toulon.

---

## ✨ Ce que fait le script

- 🔍 Recherche sur **Bienici** (API JSON directe, sans blocage) — agrège les annonces de Century21, ERA, Hektor, ImmoFacile, Netty et bien d'autres agences
- 🌿 Filtre uniquement les **maisons avec jardin ou terrasse**
- 💶 Budget maximum configurable (défaut : **850 €/mois**)
- 📍 Trie les résultats du **plus proche au plus loin de Toulon** (calcul vol d'oiseau)
- 🖼️ Génère une **belle page HTML** avec photos, prix, distance, description
- 📊 Exporte un fichier **CSV** horodaté pour suivre les annonces

---

## 🗺️ Zones couvertes

| Département | Villages ciblés |
|-------------|----------------|
| **Var (83)** | Brignoles, Signes, Nans-les-Pins, Le Luc, Cuers, Lorgues, Draguignan, Trans-en-Provence... |
| **Alpes-de-Haute-Provence (04)** | Gréoux-les-Bains ★, Valensole, Manosque, Riez, Forcalquier, Oraison... |

---

## 📸 Aperçu du résultat

La page HTML générée affiche les annonces sous forme de cartes :

- Prix mensuel bien visible
- Distance de Toulon en km (vol d'oiseau)
- Photos de l'annonce avec miniatures cliquables
- Surface, nombre de pièces, agence source
- Lien direct vers l'annonce complète
- Triées automatiquement : **la plus proche de Toulon en premier**

---

## 🚀 Installation

```bash
# Cloner le projet
git clone https://github.com/stephanejob-web/cherche-maison-toulon.git
cd cherche-maison-toulon

# Installer les dépendances
pip3 install playwright --break-system-packages
python3 -m playwright install chromium
```

---

## ▶️ Utilisation

```bash
python3 cherche_maison.py
```

Le script :
1. Interroge l'API Bienici pour les deux départements
2. Filtre les maisons avec jardin/terrasse ≤ 850 €/mois
3. Calcule la distance de chaque annonce depuis Toulon
4. Affiche les résultats dans le terminal
5. Ouvre automatiquement la page HTML dans votre navigateur
6. Sauvegarde un fichier CSV horodaté

---

## ⚙️ Configuration

Dans `cherche_maison.py`, modifiez ces variables selon vos besoins :

```python
MAX_PRIX = 850        # Budget maximum en €/mois
HEADLESS  = False     # False = navigateur visible (recommandé)
```

Pour ajouter une ville, récupérez son identifiant Bienici :

```
https://res.bienici.com/place.json?q=NOM_VILLE&type=city&prefix=no
```

Puis ajoutez-la dans le dictionnaire `BIENICI_VILLES`.

---

## 📁 Fichiers générés

| Fichier | Description |
|---------|-------------|
| `maisons_toulon_YYYYMMDD_HHMM.html` | Page HTML avec photos et cartes |
| `maisons_toulon_YYYYMMDD_HHMM.csv` | Export tableau (LibreOffice / Excel) |

---

## ℹ️ Pourquoi seulement Bienici ?

| Site | État |
|------|------|
| ✅ **Bienici** | API publique, pas de blocage, données complètes |
| ❌ LeBonCoin | Bloqué par DataDome (anti-bot) |
| ❌ SeLoger | Bloqué côté serveur |
| ❌ PAP.fr | 0 résultats Var/04 à ce budget |
| ✅ Century21, ERA, Hektor... | **Déjà inclus dans Bienici** |

Bienici est un agrégateur : toutes les grandes agences y publient leurs annonces. Pas besoin de scraper les autres sites séparément.

---

## 📜 Licence

MIT — libre d'utilisation et de modification.
