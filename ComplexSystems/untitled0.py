import re
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE = "https://www.driving-distances.com"
INDEX_URL = f"{BASE}/road-distances-between-american-cities.php"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; DataExtractionBot/1.0; +https://example.com/bot)"
}

session = requests.Session()
session.headers.update(HEADERS)

def get_html(url, timeout=30):
    r = session.get(url, timeout=timeout)
    r.raise_for_status()
    return r.text

def extract_city_pages(index_html):
    soup = BeautifulSoup(index_html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "road-distances-from-city.php?city=" in href:
            full = urljoin(BASE, href)
            if full not in links:
                links.append(full)
    return links

def extract_origin_from_h1(text):
    # Exemple: "How far from Albany, New York to other US Cities by Road"
    m = re.search(r"How far from\s+(.+?),\s+(.+?)\s+to other US Cities by Road", text, flags=re.I)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return None, None

def parse_distance_lines(page_text):
    """
    Extrait les lignes du bloc 'tabular format' :
    'Albany, New York, 12201 0 miles'
    'Annapolis, Maryland, 21401 349.9 miles'
    """
    rows = []

    # Normaliser le texte (enlevant espaces multiples)
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in page_text.splitlines()]
    lines = [ln for ln in lines if ln]

    # Récupérer origine via H1 (si possible)
    origin_city = origin_state = None
    for ln in lines:
        if ln.lower().startswith("how far from ") and "to other us cities by road" in ln.lower():
            origin_city, origin_state = extract_origin_from_h1(ln)
            break

    in_block = False
    for ln in lines:
        if "US Capital City, State and Zip Distance from" in ln:
            in_block = True
            continue
        if in_block and (ln.startswith("We hope you have found this information useful") or ln.startswith("## ")):
            break
        if not in_block:
            continue

        # Format attendu: City, State, ZIP DIST miles
        m = re.match(
            r"^(?P<dest_city>.+?),\s+(?P<dest_state>.+?),\s+(?P<zip>\d{5})\s+(?P<miles>\d+(?:\.\d+)?)\s+miles$",
            ln
        )
        if m:
            rows.append({
                "origin_city": origin_city,
                "origin_state": origin_state,
                "dest_city": m.group("dest_city").strip(),
                "dest_state": m.group("dest_state").strip(),
                "dest_zip": m.group("zip"),
                "distance_miles": float(m.group("miles")),
            })

    return rows

def main():
    index_html = get_html(INDEX_URL)
    city_pages = extract_city_pages(index_html)
    print(f"{len(city_pages)} pages villes trouvées")

    all_rows = []
    for i, url in enumerate(city_pages, 1):
        try:
            html = get_html(url)
            # Extraire texte brut de la page
            soup = BeautifulSoup(html, "html.parser")
            text = soup.get_text("\n", strip=True)
            rows = parse_distance_lines(text)

            for r in rows:
                r["source_url"] = url

            all_rows.extend(rows)
            print(f"[{i}/{len(city_pages)}] {url} -> {len(rows)} lignes")
        except Exception as e:
            print(f"[ERREUR] {url}: {e}")
        time.sleep(1.0)  # politesse envers le site

    df = pd.DataFrame(all_rows)

    # Nettoyage de base
    if not df.empty:
        # Retirer doublons exacts
        df = df.drop_duplicates()

        # Créer une clé non orientée pour pairwise unique (A-B == B-A)
        def pair_key(row):
            a = (row["origin_city"], row["origin_state"])
            b = (row["dest_city"], row["dest_state"])
            return tuple(sorted([a, b]))

        df["pair_key"] = df.apply(pair_key, axis=1)

        # Option 1: dataset orienté (origine -> destination)
        df.to_csv("us_capitals_distances_directed.csv", index=False)

        # Option 2: dataset pairwise unique (une seule ligne par paire)
        # on garde la première occurrence non nulle
        df_unique = (
            df.sort_values(["distance_miles"])
              .drop_duplicates(subset=["pair_key"])
              .drop(columns=["pair_key"])
        )
        df_unique.to_csv("us_capitals_distances_undirected_unique.csv", index=False)

        print("\nFichiers créés :")
        print("- us_capitals_distances_directed.csv")
        print("- us_capitals_distances_undirected_unique.csv")
        print(f"Lignes (orienté): {len(df)}")
        print(f"Lignes (paires uniques): {len(df_unique)}")
    else:
        print("Aucune donnée extraite.")

if __name__ == "__main__":
    main()