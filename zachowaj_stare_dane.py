"""Uruchamiane w CI po run.py, przed publikacją strony.

render/web/data/ jest w .gitignore — każdy przebieg workflow zaczyna od pustego
folderu. Jeśli w tym uruchomieniu policzony został tylko jeden profil (np. "krotki"
co 6h), drugi ("dlugi", liczony 2×/dobę) nie zostawił tu żadnych plików — bez tego
kroku publikacja skasowałaby jego ostatni wynik. Więc dla profilu, którego run.py
w tym uruchomieniu nie policzył (brak lokalnego meta_<profil>.json), dociągamy jego
ostatnią wersję z już opublikowanej strony.
"""
import argparse
import json
from pathlib import Path
import requests

WSZYSTKIE_PROFILE = ["krotki", "dlugi"]
WEB_DIR = Path("render/web/data")


def pobierz(url, cel):
    resp = requests.get(url, timeout=30)
    if resp.status_code != 200:
        return False
    cel.parent.mkdir(parents=True, exist_ok=True)
    cel.write_bytes(resp.content)
    return True


def zachowaj_profil(strona, profil):
    meta_cel = WEB_DIR / f"meta_{profil}.json"
    if meta_cel.exists():
        return  # ten profil został właśnie policzony w tym uruchomieniu — nic do roboty

    if not pobierz(f"{strona}/data/meta_{profil}.json", meta_cel):
        print(f"  {profil}: brak wcześniejszych danych na stronie (pierwsza publikacja?) — pomijam")
        return

    meta = json.loads(meta_cel.read_text(encoding="utf-8"))
    foldery = (["zgodnosc"] if meta.get("ma_zgodnosc") else []) + list(meta.get("modele", []))

    ok = 0
    for h in meta["kroki"]:
        for folder in foldery:
            nazwa = f"data/{profil}/{folder}/step_{h:03d}.geojson"
            if pobierz(f"{strona}/{nazwa}", Path("render/web") / nazwa):
                ok += 1
    print(f"  {profil}: zachowano {ok} plik(ów) z poprzedniej publikacji")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strona", required=True, help="np. https://TWOJA-NAZWA.github.io/airflow-map")
    args = ap.parse_args()
    strona = args.strona.rstrip("/")

    for profil in WSZYSTKIE_PROFILE:
        zachowaj_profil(strona, profil)


if __name__ == "__main__":
    main()
