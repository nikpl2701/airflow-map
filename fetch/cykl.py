"""Wybór wspólnego przebiegu (data + godzina UTC), który jest już opublikowany dla wszystkich modeli."""
from datetime import datetime, timedelta, timezone

# Ile godzin po starcie przebiegu dane są już dostępne do +72 h:
# GFS ~4,5 h, ICON-EU ~4 h, ECMWF open-data ~8 h (i tylko przebiegi 00/12).
OPOZNIENIE_H = {"gfs": 5, "icon_eu": 5, "ecmwf": 9}
CYKLE = {"gfs": ("00", "06", "12", "18"), "icon_eu": ("00", "06", "12", "18"), "ecmwf": ("00", "12")}


def najnowszy_wspolny(modele=("gfs", "icon_eu")):
    opoznienie = max(OPOZNIENIE_H[m] for m in modele)
    cykle = set.intersection(*(set(CYKLE[m]) for m in modele))
    t = datetime.now(timezone.utc) - timedelta(hours=opoznienie)
    for dzien in (t, t - timedelta(days=1)):
        for c in sorted(cykle, reverse=True):
            start = dzien.replace(hour=int(c), minute=0, second=0, microsecond=0)
            if start <= t:
                return start.strftime("%Y%m%d"), c
    raise RuntimeError("Nie udało się wyznaczyć przebiegu")
