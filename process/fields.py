"""Wygładzanie pól, adwekcja temperatury, trasowanie i klasyfikacja linii prądu."""
import numpy as np
from scipy.ndimage import gaussian_filter
from scipy.interpolate import RegularGridInterpolator

R = 6.371e6


def _wygladz(a, sigma):
    """Filtr Gaussa odporny na NaN (np. poza obszarem ICON-EU)."""
    maska = np.isfinite(a)
    licznik = gaussian_filter(np.where(maska, a, 0.0), sigma)
    mianownik = gaussian_filter(maska.astype(float), sigma)
    with np.errstate(invalid="ignore", divide="ignore"):
        wynik = licznik / mianownik
    wynik[~maska] = np.nan
    return wynik


def advection(t, u, v, lat, lon):
    """-(u dT/dx + v dT/dy) w K/s; siatka regularna w stopniach, lat rosnąco."""
    dlat = np.radians(np.gradient(lat))
    dlon = np.radians(np.gradient(lon))
    dy = R * dlat[:, None]
    dx = R * np.cos(np.radians(lat))[:, None] * dlon[None, :]
    dTdy = np.gradient(t, axis=0) / dy
    dTdx = np.gradient(t, axis=1) / dx
    return -(u * dTdx + v * dTdy)


def prep(ds, sigma=6):                       # 6 pkt × 0,25° ≈ 150 km
    for v in ("t", "u", "v"):
        ds[v] = (("latitude", "longitude"), _wygladz(ds[v].values.astype(float), sigma))
    adv = advection(ds.t.values, ds.u.values, ds.v.values,
                    ds.latitude.values, ds.longitude.values) * 86400   # K/dobę
    ds["adv"] = (("latitude", "longitude"), adv)
    return ds


def trace(ds, seed, dt=3600, n=48, v_min=3.0):
    lat, lon = ds.latitude.values, ds.longitude.values          # lat rosnąco!
    f = {k: RegularGridInterpolator((lat, lon), ds[k].values,
                                    bounds_error=False, fill_value=np.nan)
         for k in ("u", "v", "adv")}
    pts, adv = [seed], []
    for _ in range(n):
        la, lo = pts[-1]
        u, v = float(f["u"]((la, lo))), float(f["v"]((la, lo)))
        if np.isnan(u) or np.isnan(v) or np.hypot(u, v) < v_min:
            break
        adv.append(float(f["adv"]((la, lo))))
        pts.append((la + np.degrees(v * dt / R),
                    lo + np.degrees(u * dt / (R * np.cos(np.radians(la))))))
    srednia = float(np.nanmean(adv)) if adv and np.isfinite(adv).any() else 0.0
    return np.array(pts), srednia


def classify(path, adv, min_km=800, thr=1.5):
    if len(path) < 2:
        return None
    km = np.sum(np.hypot(*np.diff(path, axis=0).T)) * 111
    if km < min_km or abs(adv) < thr:
        return None
    return "warm" if adv > 0 else "cold"
