"""Siatka punktów startowych, trasowanie linii prądu i filtrowanie nakładających się."""
import numpy as np
from .fields import trace, classify


def seed_grid(area, odstep=2.0):
    lat = np.arange(area["lat_min"], area["lat_max"], odstep)
    lon = np.arange(area["lon_min"], area["lon_max"], odstep)
    return [(la, lo) for la in lat for lo in lon]


def build_streams(ds, area, odstep=2.0, min_km=800, thr=1.5, **trace_kw):
    linie = []
    for seed in seed_grid(area, odstep):
        path, adv = trace(ds, seed, **trace_kw)
        rodzaj = classify(path, adv, min_km=min_km, thr=thr)
        if rodzaj:
            linie.append({"path": path, "adv": float(adv), "rodzaj": rodzaj})
    return dedupe(linie)


def dedupe(linie, min_odleglosc_deg=1.0):
    """Odrzuca linie, których punkt startowy leży zbyt blisko już zaakceptowanej."""
    zaakceptowane = []
    for linia in sorted(linie, key=lambda l: -len(l["path"])):
        start = linia["path"][0]
        if all(np.hypot(*(start - inna["path"][0])) > min_odleglosc_deg for inna in zaakceptowane):
            zaakceptowane.append(linia)
    return zaakceptowane
