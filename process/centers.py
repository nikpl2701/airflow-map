"""Wyże (W) i niże (N) wyznaczone z lokalnych ekstremów MSLP."""
import numpy as np
from scipy.ndimage import minimum_filter, maximum_filter


def find_centers(ds, rozmiar=15, prog_hpa=None):
    mslp = ds["msl"].values / 100.0  # Pa -> hPa
    lat, lon = ds.latitude.values, ds.longitude.values

    # NaN (poza zasięgiem modelu) zastępujemy tak, żeby nie tworzyły fałszywych ekstremów
    dla_min = np.where(np.isnan(mslp), np.inf, mslp)
    dla_max = np.where(np.isnan(mslp), -np.inf, mslp)
    minima = (dla_min == minimum_filter(dla_min, size=rozmiar)) & np.isfinite(mslp)
    maxima = (dla_max == maximum_filter(dla_max, size=rozmiar)) & np.isfinite(mslp)

    # pomijamy brzegi — tam "ekstremum" to zwykle tylko koniec mapy
    brzeg = rozmiar // 2
    ramka = np.zeros_like(minima)
    ramka[brzeg:-brzeg, brzeg:-brzeg] = True
    minima &= ramka
    maxima &= ramka

    centra = []
    for mask, etykieta in ((minima, "N"), (maxima, "W")):
        for j, i in zip(*np.where(mask)):
            wartosc = mslp[j, i]
            if prog_hpa and etykieta == "N" and wartosc > prog_hpa:
                continue
            if prog_hpa and etykieta == "W" and wartosc < prog_hpa:
                continue
            centra.append({
                "lat": float(lat[j]),
                "lon": float(lon[i]),
                "typ": etykieta,
                "hpa": float(wartosc),
            })
    return centra
