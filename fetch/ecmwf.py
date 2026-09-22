"""Pobieranie ECMWF open-data (HRES 0.25°) przez ecmwf-opendata Client.

Główny portal data.ecmwf.int bywa przeciążony (HTTP 429), więc pobieramy z kopii w chmurze:
AWS, potem Azure, potem Google.
"""
from pathlib import Path
from ecmwf.opendata import Client

ZRODLA = ("aws", "azure", "google")
_klienci = {}


def _klient(zrodlo):
    if zrodlo not in _klienci:
        _klienci[zrodlo] = Client(source=zrodlo)
    return _klienci[zrodlo]


def _pobierz(plik, **zapytanie):
    if plik.exists() and plik.stat().st_size > 0:
        return
    bledy = []
    for zrodlo in ZRODLA:
        try:
            _klient(zrodlo).retrieve(target=str(plik), **zapytanie)
            if plik.exists() and plik.stat().st_size > 0:
                return
        except Exception as e:
            bledy.append(f"{zrodlo}: {type(e).__name__}: {e}")
            if plik.exists():
                plik.unlink()
    raise RuntimeError("ECMWF niedostępny ze wszystkich źródeł — " + " | ".join(bledy))


def fetch(krok_h, data, godzina, out_dir="data/raw/ecmwf"):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    plik_pl = out / f"ecmwf.{data}{godzina}.f{krok_h:03d}.pl.grib2"
    plik_sfc = out / f"ecmwf.{data}{godzina}.f{krok_h:03d}.msl.grib2"
    wspolne = dict(date=int(data), time=int(godzina), step=krok_h, stream="oper", type="fc")

    _pobierz(plik_pl, levtype="pl", levelist=[850], param=["t", "u", "v"], **wspolne)
    _pobierz(plik_sfc, levtype="sfc", param=["msl"], **wspolne)
    return [plik_pl, plik_sfc]
