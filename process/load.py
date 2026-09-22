"""GRIB (cfgrib) -> xarray, wspólna siatka dla GFS/ICON/ECMWF, lat rosnąco, lon -180..180.

Każdy model zwraca inne nazwy zmiennych i poziomów, więc tu wszystko ujednolicamy do:
t, u, v (na 850 hPa) oraz msl (ciśnienie na poziomie morza, Pa).
"""
import warnings
import numpy as np
import xarray as xr
import cfgrib

# ostrzeżenie z wnętrza cfgrib o przyszłej zmianie w xarray — nieistotne dla nas
warnings.filterwarnings("ignore", category=FutureWarning, module="cfgrib")

NAZWY = {"prmsl": "msl", "pmsl": "msl", "mslp": "msl"}
POTRZEBNE = ("t", "u", "v", "msl")


def _jako_lista(sciezka):
    if isinstance(sciezka, (list, tuple)):
        return list(sciezka)
    return [sciezka]


def _porzadkuj(ds, poziom_hpa):
    # wybór poziomu 850 hPa, jeśli plik zawiera kilka poziomów
    if "isobaricInhPa" in ds.dims:
        ds = ds.sel(isobaricInhPa=poziom_hpa)
    ds = ds.rename({k: v for k, v in NAZWY.items() if k in ds.data_vars})
    ds = ds[[v for v in ds.data_vars if v in POTRZEBNE]]
    # usuwamy współrzędne skalarne (time, step, poziom...), które przeszkadzają w łączeniu
    ds = ds.drop_vars([c for c in ds.coords if c not in ("latitude", "longitude")])
    return ds


def open_grib(sciezki, poziom_hpa=850):
    czesci = []
    for sciezka in _jako_lista(sciezki):
        for ds in cfgrib.open_datasets(str(sciezka), backend_kwargs={"indexpath": ""}):
            ds = _porzadkuj(ds, poziom_hpa)
            if ds.data_vars:
                czesci.append(ds.load())
    if not czesci:
        raise ValueError(f"Brak potrzebnych pól w plikach: {sciezki}")
    ds = xr.merge(czesci, compat="override", join="outer")
    brak = [v for v in POTRZEBNE if v not in ds]
    if brak:
        raise ValueError(f"Brakuje pól {brak} w plikach: {sciezki}")
    return ds


def normalize_lon(ds):
    lon = ds.longitude.values
    if lon.max() > 180:
        ds = ds.assign_coords(longitude=((lon + 180) % 360) - 180).sortby("longitude")
    return ds


def ensure_lat_ascending(ds):
    if ds.latitude.values[0] > ds.latitude.values[-1]:
        ds = ds.isel(latitude=slice(None, None, -1))
    return ds


def to_common_grid(ds, area, rozdzielczosc):
    ds = ensure_lat_ascending(normalize_lon(ds))
    lat = np.arange(area["lat_min"], area["lat_max"] + rozdzielczosc / 2, rozdzielczosc)
    lon = np.arange(area["lon_min"], area["lon_max"] + rozdzielczosc / 2, rozdzielczosc)
    ds = ds.interp(latitude=lat, longitude=lon, method="linear")
    return ds.transpose("latitude", "longitude")


def load(sciezki, area, rozdzielczosc, poziom_hpa=850):
    return to_common_grid(open_grib(sciezki, poziom_hpa), area, rozdzielczosc)
