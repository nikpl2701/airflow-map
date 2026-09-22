"""fetch -> process -> export -> render dla wszystkich kroków czasowych z config.yaml.

Użycie:
    python run.py          # pełny przebieg (wszystkie kroki z config.yaml)
    python run.py --test   # szybka próba: tylko pierwszy krok
    python run.py --bez-png  # bez obrazków PNG (szybciej; tak działa aktualizacja na GitHubie)
"""
import sys
import os
import traceback
import json
import yaml
from pathlib import Path
from datetime import datetime, timedelta, timezone

# zawsze pracujemy w folderze projektu (ważne przy uruchamianiu dwuklikiem / z crona)
os.chdir(Path(__file__).resolve().parent)

from fetch import gfs, icon_eu
from fetch.cykl import najnowszy_wspolny
from process.load import load
from process.fields import prep
from process.streams import build_streams
from process.centers import find_centers
from process.consensus import streams_consensus, centers_consensus
from export.geojson import build_geojson, write as write_geojson


def _ecmwf():
    from fetch import ecmwf   # import tylko gdy model jest włączony
    return ecmwf


def wczytaj_config(sciezka="config.yaml"):
    return yaml.safe_load(Path(sciezka).read_text(encoding="utf-8"))


def krok(cfg, krok_h, data, godzina):
    area = cfg["obszar"]
    progi = cfg["progi"]
    poziom = cfg["poziom"]["glowny"]

    wszystkie = {
        "gfs": lambda: gfs.fetch(krok_h, data, godzina),
        "icon_eu": lambda: icon_eu.fetch(krok_h, data, godzina),
        "ecmwf": lambda: _ecmwf().fetch(krok_h, data, godzina),
    }
    modele_cfg = cfg.get("modele", {})
    pobieranie = {n: f for n, f in wszystkie.items()
                  if modele_cfg.get(n, {}).get("wlaczony", True)}

    linie_modele, centra_modele = {}, {}
    for nazwa, pobierz in pobieranie.items():
        try:
            print(f"  {nazwa}: pobieranie...", flush=True)
            pliki = pobierz()
            print(f"  {nazwa}: przeliczanie...", flush=True)
            ds = load(pliki, area, area["rozdzielczosc"], poziom_hpa=poziom)
            ds = prep(ds, sigma=progi["wygladzanie_sigma"])
            linie_modele[nazwa] = build_streams(
                ds, area,
                min_km=progi["trasa_min_km"],
                thr=progi["adwekcja_min"],
                v_min=progi["predkosc_min_ms"],
            )
            centra_modele[nazwa] = find_centers(ds)
            print(f"  {nazwa}: OK ({len(linie_modele[nazwa])} linii, {len(centra_modele[nazwa])} centrów)")
        except Exception as e:
            print(f"  {nazwa}: POMINIĘTY — {type(e).__name__}: {e}")

    if not linie_modele:
        print("  Żaden model się nie udał — pomijam ten krok.")
        return None

    min_modeli = min(progi["konsensus_min_modeli"], len(linie_modele))
    linie = streams_consensus(linie_modele, min_modeli=min_modeli)
    centra = centers_consensus(centra_modele, min_modeli=min_modeli)

    geojson = build_geojson(linie, centra, kontury=[], krok_h=krok_h,
                            timestamp=datetime.now(timezone.utc).isoformat())
    start = datetime.strptime(data + godzina, "%Y%m%d%H").replace(tzinfo=timezone.utc)
    geojson["properties"]["przebieg"] = f"{data} {godzina}UTC"
    geojson["properties"]["przebieg_iso"] = start.isoformat()
    geojson["properties"]["waznosc_iso"] = (start + timedelta(hours=krok_h)).isoformat()
    geojson["properties"]["modele"] = list(linie_modele)

    write_geojson(geojson, cfg["wyjscie"]["geojson_dir"], krok_h)
    write_geojson(geojson, cfg["wyjscie"]["web_dir"], krok_h)
    if "--bez-png" in sys.argv:
        return list(linie_modele)
    try:
        from render.png import render as render_png
        render_png(geojson, cfg["wyjscie"]["png_dir"], krok_h)
    except Exception as e:
        print(f"  PNG pominięty — {type(e).__name__}: {e}")
    return list(linie_modele)


def zapisz_meta(cfg, data, godzina, kroki_ok, modele):
    """render/web/data/meta.json — informacje dla mapy w przeglądarce (czas przebiegu, lista kroków)."""
    start = datetime.strptime(data + godzina, "%Y%m%d%H").replace(tzinfo=timezone.utc)
    meta = {
        "przebieg_iso": start.isoformat(),
        "obliczono_iso": datetime.now(timezone.utc).isoformat(),
        "kroki": kroki_ok,
        "modele": modele,
    }
    out = Path(cfg["wyjscie"]["web_dir"])
    out.mkdir(parents=True, exist_ok=True)
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    cfg = wczytaj_config()
    kroki_cfg = cfg["kroki_czasowe"]
    kroki = list(range(kroki_cfg["start_h"], kroki_cfg["koniec_h"] + 1, kroki_cfg["krok_h"]))
    if "--test" in sys.argv:
        kroki = kroki[:1]

    wlaczone = [m for m in ("gfs", "icon_eu", "ecmwf")
                if cfg.get("modele", {}).get(m, {}).get("wlaczony", True)]
    data, godzina = najnowszy_wspolny(wlaczone)
    print(f"Przebieg modeli: {data} {godzina} UTC, kroków: {len(kroki)}")

    kroki_ok, modele = [], set()
    for i, h in enumerate(kroki, 1):
        print(f"[{i}/{len(kroki)}] krok +{h:03d}h")
        try:
            wynik = krok(cfg, h, data, godzina)
            if wynik:
                kroki_ok.append(h)
                modele.update(wynik)
                zapisz_meta(cfg, data, godzina, kroki_ok, sorted(modele))
        except Exception:
            traceback.print_exc()

    if "punkt" in cfg and kroki_ok:
        try:
            from fetch import punkt as punkt_mod
            start = datetime.strptime(data + godzina, "%Y%m%d%H").replace(tzinfo=timezone.utc)
            p = cfg["punkt"]
            dane = punkt_mod.pobierz(p, start, kroki_ok, model=p.get("model", "icon_eu"))
            punkt_mod.zapisz(dane, cfg["wyjscie"]["web_dir"])
            print(f"Prognoza punktowa dla {p['nazwa']}: OK")
        except Exception as e:
            print(f"Prognoza punktowa pominięta — {type(e).__name__}: {e}")

    print(f"\nGotowe: {len(kroki_ok)}/{len(kroki)} kroków zapisanych.")
    print(f"Wyniki: {cfg['wyjscie']['png_dir']}, {cfg['wyjscie']['geojson_dir']}")
    print("Mapę w przeglądarce otworzysz plikiem pokaz_mape.bat")


if __name__ == "__main__":
    main()
