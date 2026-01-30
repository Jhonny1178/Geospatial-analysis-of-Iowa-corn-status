import requests
import rasterio
from rasterio.warp import transform_bounds, reproject, Resampling
import numpy as np
import matplotlib.pyplot as plt
import os
import re

SENTINEL_REF = "red.jp2"
NIR_FILE = "nir.jp2"
MASK_FILENAME = "crop_mask_usda.tif"
CROP_YEAR = "2024"


def pobierz_maske_z_api(plik_wzorcowy, plik_wynikowy):
    if os.path.exists(plik_wynikowy):
        print("[INFO] Maska USDA już istnieje. Pomijam pobieranie.")
        return True

    print(f"[1/4] Pobieranie mapy upraw z USDA dla roku {CROP_YEAR}...")
    if not os.path.exists(plik_wzorcowy):
        print("BŁĄD: Brak pliku red.jp2.")
        return False

    with rasterio.open(plik_wzorcowy) as src:
        left, bottom, right, top = src.bounds
        src_crs = src.crs
        dst_crs = 'EPSG:5070'
        minx, miny, maxx, maxy = transform_bounds(src_crs, dst_crs, left, bottom, right, top)
        bbox = f"{minx},{miny},{maxx},{maxy}"

    url = "https://nassgeodata.gmu.edu/axis2/services/CDLService/GetCDLFile"
    try:
        response = requests.get(url, params={'year': CROP_YEAR, 'bbox': bbox})
        link_do_pliku = re.search(r'(https?://[^"]+\.tif)', response.text)

        if link_do_pliku:
            with requests.get(link_do_pliku.group(1), stream=True) as r, open(plik_wynikowy, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024):
                    f.write(chunk)
            print("   [OK] Mapa pobrana.")
            return True
        else:
            print("   [BŁĄD] API nie zwróciło linku.")
            return False
    except Exception as e:
        print(f"   [BŁĄD] {e}")
        return False


def naloz_ndvi_na_kukurydze(sentinel_path, mask_path):
    print("[2/4] Wczytywanie i dopasowywanie danych...")


    with rasterio.open("red.jp2") as src:
        red = src.read(1).astype('float32')
        height, width = red.shape

    with rasterio.open("nir.jp2") as src:
        nir = src.read(
            1,
            out_shape=(height, width),
            resampling=Resampling.nearest
        ).astype('float32')

    print(f"   -> Wymiary wyrównane do: {red.shape}")

    with rasterio.open(sentinel_path) as src_sentinel:
        with rasterio.open(mask_path) as src_mask:
            maska_dopasowana = np.empty(src_sentinel.shape, dtype='uint8')
            reproject(
                source=rasterio.band(src_mask, 1),
                destination=maska_dopasowana,
                src_transform=src_mask.transform,
                src_crs=src_mask.crs,
                dst_transform=src_sentinel.transform,
                dst_crs=src_sentinel.crs,
                resampling=Resampling.nearest
            )

    print("[3/4] Obliczanie NDVI i filtrowanie...")

    ndvi = (nir - red) / (nir + red + 1e-8)

    tylko_kukurydza = (maska_dopasowana == 1)
    maska_chmur = (red > 2500)
    maska_finalna = (tylko_kukurydza & ~maska_chmur)

    ndvi_widok = np.where(maska_finalna, ndvi, np.nan)

    print("[4/4] Rysowanie mapy warstwowej...")

    plt.figure(figsize=(12, 10))

    # Tło szare
    plt.imshow(ndvi, cmap='gray', vmin=0, vmax=0.8, alpha=0.4)

    # Kolorowa kukurydza
    obraz = plt.imshow(ndvi_widok, cmap='RdYlGn', vmin=0.2, vmax=0.8)

    cbar = plt.colorbar(obraz, label='NDVI (Kondycja Roślin)')
    srednie_ndvi = np.nanmean(ndvi_widok)
    plt.title(f"Kondycja Kukurydzy - IOWA 2024-08-18\nŚrednie NDVI dla kukurydzy: {srednie_ndvi:.2f}")

    plt.xlabel("Piksele (x)")
    plt.ylabel("Piksele (y)")

    plt.savefig("kukurydza_ndvi_full.png")
    print("   [SUKCES] Mapa zapisana jako kukurydza_ndvi_full.png")
    plt.show()


if __name__ == "__main__":
    if pobierz_maske_z_api(SENTINEL_REF, MASK_FILENAME):
        naloz_ndvi_na_kukurydze(SENTINEL_REF, MASK_FILENAME)