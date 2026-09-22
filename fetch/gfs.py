"""Pobieranie GFS z NOMADS przez grib filter (tylko potrzebne pola/poziomy, cała kula ziemska)."""
from pathlib import Path
import requests

BASE = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"


def fetch(krok_h, data, godzina, out_dir="data/raw/gfs"):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    plik = out / f"gfs.{data}{godzina}.f{krok_h:03d}.grib2"
    if plik.exists() and plik.stat().st_size > 0:
        return plik

    params = {
        "file": f"gfs.t{godzina}z.pgrb2.0p25.f{krok_h:03d}",
        "dir": f"/gfs.{data}/{godzina}/atmos",
        "var_TMP": "on",
        "var_UGRD": "on",
        "var_VGRD": "on",
        "var_PRMSL": "on",
        "lev_850_mb": "on",
        "lev_mean_sea_level": "on",
    }
    resp = requests.get(BASE, params=params, timeout=180)
    resp.raise_for_status()
    if not resp.content.startswith(b"GRIB"):
        raise RuntimeError(f"GFS: serwer nie zwrócił pliku GRIB ({resp.url})")
    plik.write_bytes(resp.content)
    return plik
