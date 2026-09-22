"""Strzałki (linie prądu), izobary i centra W/N -> GeoJSON dla jednego kroku czasowego."""
import json
from pathlib import Path

KOLOR = {"warm": "#e74c3c", "cold": "#3498db"}


def streams_to_features(linie):
    features = []
    for linia in linie:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [[float(lo), float(la)] for la, lo in linia["path"]],
            },
            "properties": {
                "rodzaj": linia["rodzaj"],
                "adv": linia["adv"],
                "kolor": KOLOR[linia["rodzaj"]],
                "pewne": linia.get("pewne", True),
                "modele": linia.get("modele", []),
            },
        })
    return features


def centers_to_features(centra):
    features = []
    for c in centra:
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [c["lon"], c["lat"]]},
            "properties": {
                "typ": c["typ"],
                "hpa": round(c["hpa"], 1),
                "pewne": c.get("pewne", True),
                "modele": c.get("modele", []),
            },
        })
    return features


def isobars_to_features(kontury):
    """kontury: lista [(hpa, [(lat, lon), ...]), ...] np. z matplotlib.contour"""
    features = []
    for hpa, punkty in kontury:
        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": [[lo, la] for la, lo in punkty]},
            "properties": {"hpa": hpa},
        })
    return features


def build_geojson(linie, centra, kontury, krok_h, timestamp):
    return {
        "type": "FeatureCollection",
        "properties": {"krok_h": krok_h, "timestamp": timestamp},
        "features": streams_to_features(linie) + centers_to_features(centra) + isobars_to_features(kontury),
    }


def write(geojson, out_dir, krok_h):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    plik = out / f"step_{krok_h:03d}.geojson"
    plik.write_text(json.dumps(geojson, ensure_ascii=False), encoding="utf-8")
    return plik
