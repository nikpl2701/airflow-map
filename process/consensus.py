"""Zgodność GFS/ICON/ECMWF dla linii prądu i centrów W/N w tym samym kroku czasowym."""
import numpy as np


def _blisko(a, b, tol_deg=1.5):
    return np.hypot(a[0] - b[0], a[1] - b[1]) <= tol_deg


def streams_consensus(modele_linie, min_modeli=2, tol_deg=1.5):
    """modele_linie: {"gfs": [...], "icon_eu": [...], "ecmwf": [...]}"""
    wszystkie = [(nazwa, linia) for nazwa, linie in modele_linie.items() for linia in linie]
    wynik = []
    uzyte = set()
    for i, (nazwa_a, linia_a) in enumerate(wszystkie):
        if i in uzyte:
            continue
        zgodne = [nazwa_a]
        for j, (nazwa_b, linia_b) in enumerate(wszystkie):
            if j <= i or nazwa_b in zgodne:
                continue
            if linia_a["rodzaj"] == linia_b["rodzaj"] and _blisko(linia_a["path"][0], linia_b["path"][0], tol_deg):
                zgodne.append(nazwa_b)
                uzyte.add(j)
        if len(zgodne) >= min_modeli:
            wynik.append({**linia_a, "modele": zgodne, "pewne": True})
        else:
            wynik.append({**linia_a, "modele": zgodne, "pewne": False})
    return wynik


def centers_consensus(modele_centra, min_modeli=2, tol_deg=1.5):
    wszystkie = [(nazwa, c) for nazwa, centra in modele_centra.items() for c in centra]
    wynik = []
    uzyte = set()
    for i, (nazwa_a, c_a) in enumerate(wszystkie):
        if i in uzyte:
            continue
        zgodne = [nazwa_a]
        for j, (nazwa_b, c_b) in enumerate(wszystkie):
            if j <= i or nazwa_b in zgodne:
                continue
            if c_a["typ"] == c_b["typ"] and _blisko((c_a["lat"], c_a["lon"]), (c_b["lat"], c_b["lon"]), tol_deg):
                zgodne.append(nazwa_b)
                uzyte.add(j)
        wynik.append({**c_a, "modele": zgodne, "pewne": len(zgodne) >= min_modeli})
    return wynik
