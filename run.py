"""fetch -> process -> export -> render dla wszystkich kroków czasowych z config.yaml.

Użycie:
    python run.py                    # oba przebiegi (krótki + długi) — tak działa uruchom.bat
    python run.py --profil krotki    # tylko przebieg krótki (0-72h, GFS+ICON-EU)
    python run.py --profil dlugi     # tylko przebieg długi (0-168h, tylko GFS)
    python run.py --test             # szybka próba: tylko pierwszy krok każdego przebiegu
    python run.py --bez-png          # bez obrazków PNG (szybciej; tak działa aktualizacja na GitHubie)
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


def _arg(nazwa, domyslnie=None):
    if nazwa in sys.argv:
        i = sys.argv.index(nazwa)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return domyslnie


def wczytaj_config(sciezka="config.yaml"):
    return yaml.safe_load(Path(sciezka).read_text(encoding="utf-8"))


def _uzupelnij_wlasciwosci(geojson, start, krok_h, modele):
    geojson["properties"]["przebieg"] = start.strftime("%Y-%m-%d %H") + "UTC"
    geojson["properties"]["przebieg_iso"] = start.isoformat()
    geojson["properties"]["waznosc_iso"] = (start + timedelta(hours=krok_h)).isoformat()
    geojson["properties"]["modele"] = modele


def krok(cfg, profil, modele_profilu, krok_h, data, godzina):
    area = cfg["obszar"]
    progi = cfg["progi"]
    poziom = cfg["poziom"]["glowny"]
    start = datetime.strptime(data + godzina, "%Y%m%d%H").replace(tzinfo=timezone.utc)
    teraz_iso = datetime.now(timezone.utc).isoformat()

    wszystkie = {
        "gfs": lambda: gfs.fetch(krok_h, data, godzina),
        "icon_eu": lambda: icon_eu.fetch(krok_h, data, godzina),
        "ecmwf": lambda: _ecmwf().fetch(krok_h, data, godzina),
    }
    pobieranie = {n: f for n, f in wszystkie.items() if n in modele_profilu}

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

    web_root = Path(cfg["wyjscie"]["web_dir"]) / profil
    geojson_root = Path(cfg["wyjscie"]["geojson_dir"]) / profil

    ostatni = None
    for nazwa in linie_modele:
        gj = build_geojson(linie_modele[nazwa], centra_modele[nazwa], kontury=[],
                            krok_h=krok_h, timestamp=teraz_iso)
        _uzupelnij_wlasciwosci(gj, start, krok_h, [nazwa])
        write_geojson(gj, web_root / nazwa, krok_h)
        write_geojson(gj, geojson_root / nazwa, krok_h)
        ostatni = gj

    if len(linie_modele) >= 2:
        min_modeli = min(progi["konsensus_min_modeli"], len(linie_modele))
        linie = streams_consensus(linie_modele, min_modeli=min_modeli)
        centra = centers_consensus(centra_modele, min_modeli=min_modeli)
        gj = build_geojson(linie, centra, kontury=[], krok_h=krok_h, timestamp=teraz_iso)
        _uzupelnij_wlasciwosci(gj, start, krok_h, list(linie_modele))
        write_geojson(gj, web_root / "zgodnosc", krok_h)
        write_geojson(gj, geojson_root / "zgodnosc", krok_h)
        ostatni = gj

    if "--bez-png" not in sys.argv:
        try:
            from render.png import render as render_png
            render_png(ostatni, str(Path(cfg["wyjscie"]["png_dir"]) / profil), krok_h)
        except Exception as e:
            print(f"  PNG pominięty — {type(e).__name__}: {e}")

    return list(linie_modele)


def zapisz_meta(cfg, profil, data, godzina, kroki_ok, modele):
    """render/web/data/meta_<profil>.json — informacje dla mapy w przeglądarce."""
    start = datetime.strptime(data + godzina, "%Y%m%d%H").replace(tzinfo=timezone.utc)
    meta = {
        "przebieg_iso": start.isoformat(),
        "obliczono_iso": datetime.now(timezone.utc).isoformat(),
        "kroki": kroki_ok,
        "modele": modele,
        "ma_zgodnosc": len(modele) >= 2,
    }
    out = Path(cfg["wyjscie"]["web_dir"])
    out.mkdir(parents=True, exist_ok=True)
    (out / f"meta_{profil}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")


def policz_profil(cfg, profil, pcfg, globalnie_wlaczone):
    modele_profilu = [m for m in pcfg["modele"] if m in globalnie_wlaczone]
    if not modele_profilu:
        print(f"\nProfil '{profil}': żaden z jego modeli nie jest włączony w config.yaml — pomijam.")
        return

    print(f"\n=== Przebieg '{profil}' ({', '.join(modele_profilu)}) ===")
    kroki = list(range(pcfg["start_h"], pcfg["koniec_h"] + 1, pcfg["krok_h"]))
    if "--test" in sys.argv:
        kroki = kroki[:1]

    data, godzina = najnowszy_wspolny(modele_profilu, cykle_ograniczenie=pcfg.get("cykle_dziennie"))
    print(f"Przebieg modeli: {data} {godzina} UTC, kroków: {len(kroki)}")

    kroki_ok, modele_uzyte = [], set()
    for i, h in enumerate(kroki, 1):
        print(f"[{i}/{len(kroki)}] krok +{h:03d}h")
        try:
            wynik = krok(cfg, profil, modele_profilu, h, data, godzina)
            if wynik:
                kroki_ok.append(h)
                modele_uzyte.update(wynik)
                zapisz_meta(cfg, profil, data, godzina, kroki_ok, sorted(modele_uzyte))
        except Exception:
            traceback.print_exc()

    print(f"Profil '{profil}': {len(kroki_ok)}/{len(kroki)} kroków zapisanych.")


def policz_punkt(cfg, globalnie_wlaczone):
    if "punkt" not in cfg:
        return
    try:
        from fetch import punkt as punkt_mod
        modele_punktu = [m for m in ("gfs", "icon_eu") if m in globalnie_wlaczone] or ["gfs"]
        data, godzina = najnowszy_wspolny(modele_punktu)
        start = datetime.strptime(data + godzina, "%Y%m%d%H").replace(tzinfo=timezone.utc)
        p = cfg["punkt"]
        kroki_punktu = list(range(0, p.get("koniec_h", 72) + 1, 3))
        dane = punkt_mod.pobierz(p, start, kroki_punktu, model=p.get("model", "icon_eu"))
        punkt_mod.zapisz(dane, cfg["wyjscie"]["web_dir"])
        print(f"\nPrognoza punktowa dla {p['nazwa']}: OK ({len(kroki_punktu)} kroków)")
    except Exception as e:
        print(f"\nPrognoza punktowa pominięta — {type(e).__name__}: {e}")


def main():
    cfg = wczytaj_config()
    globalnie_wlaczone = {m for m in ("gfs", "icon_eu", "ecmwf")
                           if cfg.get("modele", {}).get(m, {}).get("wlaczony", True)}

    profile_cfg = cfg["przebiegi"]
    profil_arg = _arg("--profil")
    if profil_arg:
        if profil_arg not in profile_cfg:
            raise SystemExit(f"Nieznany profil '{profil_arg}'. Dostępne: {', '.join(profile_cfg)}")
        do_policzenia = {profil_arg: profile_cfg[profil_arg]}
    else:
        do_policzenia = profile_cfg   # bez --profil: liczymy wszystkie (tak działa uruchom.bat)

    for profil, pcfg in do_policzenia.items():
        policz_profil(cfg, profil, pcfg, globalnie_wlaczone)

    policz_punkt(cfg, globalnie_wlaczone)

    print(f"\nWyniki: {cfg['wyjscie']['png_dir']}, {cfg['wyjscie']['geojson_dir']}")
    print("Mapę w przeglądarce otworzysz plikiem pokaz_mape.bat")


if __name__ == "__main__":
    main()
