"""Prognoza punktowa (np. dla Łomży) z Open-Meteo — tabela obok mapy.

Open-Meteo udostępnia wyniki tych samych modeli (ICON, GFS) dla pojedynczego punktu,
razem z temperaturą odczuwalną i opadem. Wynik zapisujemy do render/web/data/punkt.json.
"""
import json
from datetime import timedelta
from pathlib import Path
import requests

URL = "https://api.open-meteo.com/v1/forecast"
POLA = ["temperature_2m", "apparent_temperature", "precipitation", "pressure_msl",
        "wind_speed_10m", "wind_gusts_10m", "wind_direction_10m", "cloud_cover"]
MODELE_OPEN_METEO = {"icon_eu": "icon_seamless", "gfs": "gfs_seamless"}


def _r(x, n=1):
    if x is None:
        return None
    return round(float(x), n) if n else int(round(float(x)))


def pobierz(punkt, start, kroki, model="icon_eu"):
    """start: datetime UTC startu przebiegu; kroki: lista godzin [0, 3, ...]."""
    koniec = start + timedelta(hours=max(kroki))
    params = {
        "latitude": punkt["lat"],
        "longitude": punkt["lon"],
        "hourly": ",".join(POLA),
        "models": MODELE_OPEN_METEO.get(model, model),
        "wind_speed_unit": "ms",
        "timezone": "GMT",
        "timeformat": "unixtime",
        "start_hour": start.strftime("%Y-%m-%dT%H:%M"),
        "end_hour": koniec.strftime("%Y-%m-%dT%H:%M"),
    }
    resp = requests.get(URL, params=params, timeout=60)
    resp.raise_for_status()
    hourly = resp.json()["hourly"]
    idx = {int(t): i for i, t in enumerate(hourly["time"])}

    def wartosc(pole, t):
        i = idx.get(int(t.timestamp()))
        return None if i is None else hourly[pole][i]

    def opad_miedzy(t0, t1):
        """Suma opadu w przedziale (t0, t1]; wartość godzinowa dotyczy godziny poprzedzającej."""
        suma, t = 0.0, t0 + timedelta(hours=1)
        while t <= t1:
            suma += wartosc("precipitation", t) or 0.0
            t += timedelta(hours=1)
        return suma

    wynik, poprzedni = [], None
    for h in kroki:
        t = start + timedelta(hours=h)
        wynik.append({
            "h": h,
            "czas_iso": t.isoformat(),
            "temp": _r(wartosc("temperature_2m", t)),
            "odczuwalna": _r(wartosc("apparent_temperature", t)),
            "opad": _r(opad_miedzy(poprzedni, t) if poprzedni is not None else 0.0),
            "opad_suma": _r(opad_miedzy(start, t)),
            "cisnienie": _r(wartosc("pressure_msl", t), 0),
            "wiatr": _r(wartosc("wind_speed_10m", t)),
            "porywy": _r(wartosc("wind_gusts_10m", t)),
            "kierunek": _r(wartosc("wind_direction_10m", t), 0),
            "chmury": _r(wartosc("cloud_cover", t), 0),
        })
        poprzedni = t
    return {
        "nazwa": punkt["nazwa"],
        "lat": punkt["lat"],
        "lon": punkt["lon"],
        "model": model,
        "zrodlo": "Open-Meteo",
        "przebieg_iso": start.isoformat(),
        "kroki": wynik,
    }


def zapisz(dane, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "punkt.json").write_text(json.dumps(dane, ensure_ascii=False, indent=1), encoding="utf-8")
