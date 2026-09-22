"""Rzut ortograficzny (Cartopy) — statyczny widok "globusa" jak w TVN."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature

KOLOR = {"warm": "#e74c3c", "cold": "#3498db"}


def render(geojson, out_dir, krok_h, srodek=(50, 15)):
    fig = plt.figure(figsize=(8, 8), facecolor="black")
    proj = ccrs.Orthographic(central_longitude=srodek[1], central_latitude=srodek[0])
    ax = plt.axes(projection=proj)
    ax.set_global()
    ax.add_feature(cfeature.OCEAN, facecolor="#0b1e3d")
    ax.add_feature(cfeature.LAND, facecolor="#1c1c1c")
    ax.add_feature(cfeature.COASTLINE, edgecolor="#555555", linewidth=0.5)
    ax.add_feature(cfeature.BORDERS, edgecolor="#333333", linewidth=0.3)

    for f in geojson["features"]:
        geom = f["geometry"]
        props = f["properties"]
        if geom["type"] == "LineString" and "rodzaj" in props:
            lon, lat = zip(*geom["coordinates"])
            ax.plot(lon, lat, transform=ccrs.PlateCarree(),
                    color=KOLOR[props["rodzaj"]], linewidth=1.5)
            if len(lon) >= 2:   # grot na końcu linii = kierunek przepływu
                ax.annotate("", xy=(lon[-1], lat[-1]), xytext=(lon[-2], lat[-2]),
                            xycoords=ccrs.PlateCarree()._as_mpl_transform(ax),
                            arrowprops=dict(arrowstyle="-|>", color=KOLOR[props["rodzaj"]],
                                            lw=1.5, mutation_scale=12))
        elif geom["type"] == "LineString":  # izobara
            lon, lat = zip(*geom["coordinates"])
            ax.plot(lon, lat, transform=ccrs.PlateCarree(),
                    color="#888888", linewidth=0.4)
        elif geom["type"] == "Point":
            lon, lat = geom["coordinates"]
            ax.text(lon, lat, props["typ"], transform=ccrs.PlateCarree(),
                    color="white", fontsize=14, fontweight="bold",
                    ha="center", va="center")

    p = geojson.get("properties", {})
    if "waznosc_iso" in p:
        pl = ZoneInfo("Europe/Warsaw")
        t = datetime.fromisoformat(p["waznosc_iso"]).astimezone(pl)
        s0 = datetime.fromisoformat(p["przebieg_iso"]).astimezone(pl)
        fig.suptitle(f"{t:%d.%m.%Y %H:%M} (czas PL)   +{krok_h} h", color="white", fontsize=14, y=0.97)
        fig.text(0.5, 0.03, f"start prognozy {s0:%d.%m %H:%M} · modele: {', '.join(p.get('modele', []))}",
                 color="#9aa3b2", ha="center", fontsize=9)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    plik = out / f"step_{krok_h:03d}.png"
    fig.savefig(plik, dpi=150, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    return plik
