"""Pobieranie ICON-EU z DWD opendata (pliki .grib2.bz2 -> rozpakowane .grib2)."""
import bz2
from pathlib import Path
import requests

BASE = "https://opendata.dwd.de/weather/nwp/icon-eu/grib"

# katalog na serwerze -> (rodzaj poziomu, końcówka nazwy pliku)
PARAMY = {
    "t": ("pressure-level", "850_T"),
    "u": ("pressure-level", "850_U"),
    "v": ("pressure-level", "850_V"),
    "pmsl": ("single-level", "PMSL"),
}


def _url(data, godzina, krok_h, katalog, rodzaj, koncowka):
    nazwa = f"icon-eu_europe_regular-lat-lon_{rodzaj}_{data}{godzina}_{krok_h:03d}_{koncowka}.grib2.bz2"
    return f"{BASE}/{godzina}/{katalog}/{nazwa}"


def fetch(krok_h, data, godzina, out_dir="data/raw/icon_eu"):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pliki = []
    for katalog, (rodzaj, koncowka) in PARAMY.items():
        plik = out / f"icon_eu.{data}{godzina}.f{krok_h:03d}.{katalog}.grib2"
        if not (plik.exists() and plik.stat().st_size > 0):
            resp = requests.get(_url(data, godzina, krok_h, katalog, rodzaj, koncowka), timeout=180)
            resp.raise_for_status()
            plik.write_bytes(bz2.decompress(resp.content))
        pliki.append(plik)
    return pliki
