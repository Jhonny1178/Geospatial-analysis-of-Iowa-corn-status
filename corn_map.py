import requests
import rasterio
from rasterio.warp import transform_bounds, reproject, Resampling
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import os
import re

SENTINEL_REF = "red.jp2"
MASK_FILENAME = "crop_mask_usda.tif"
CROP_YEAR = "2024"

def pobierz_maske_z_api(plik_wzorcowy, plik_wynikowy):
    print(f"[1/3] Pobieranie mapy upraw (CDL) z USDA dla roku {CROP_YEAR}...")

    if not os.path.exists(plik_wzorcowy):
        print("BŁĄD: Brak pliku red.jp2. Uruchom najpierw wypakowywanie ZIPa.")
        return False

    with rasterio.open(plik_wzorcowy) as src:
        left, bottom, right, top = src.bounds
        src_crs = src.crs
        dst_crs = 'EPSG:5070'
        minx, miny, maxx, maxy = transform_bounds(src_crs, dst_crs, left, bottom, right, top)
        bbox = f"{minx},{miny},{maxx},{maxy}"

    url = "https://nassgeodata.gmu.edu/axis2/services/CDLService/GetCDLFile"
    params = {'year': CROP_YEAR, 'bbox': bbox}

    try:
        response = requests.get(url, params=params)
        link_do_pliku = re.search(r'(https?://[^"]+\.tif)', response.text)

        if not link_do_pliku:
            print("   [!] API USDA nie zwróciło linku.")
            return False

        download_url = link_do_pliku.group(1)
        print(f"   Znaleziono mapę: {download_url}")

        with requests.get(download_url, stream=True) as r:
            with open(plik_wynikowy, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024):
                    f.write(chunk)
        print("   [OK] Mapa upraw zapisana na dysku.")
        return True

    except Exception as e:
        print(f"   [!] Błąd połączenia z USDA: {e}")
        return False


def wizualizuj_tylko_maske(sentinel_path, mask_path):
    print("[2/3] Dopasowywanie (reprojekcja) mapy USDA...")

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

    print("[3/3] Generowanie mapy kolorów (Kukurydza vs Reszta)...")


    height, width = maska_dopasowana.shape
    obraz_kolorowy = np.zeros((height, width, 3), dtype=np.float32)

    obraz_kolorowy[:, :] = [0.8, 0.8, 0.8]


    obraz_kolorowy[maska_dopasowana == 1] = [1.0, 0.8, 0.0]

    obraz_kolorowy[maska_dopasowana == 5] = [0.0, 0.3, 0.8]

    plt.figure(figsize=(12, 10))
    plt.imshow(obraz_kolorowy)

    kolor_kukurydza = mpatches.Patch(color=(1.0, 0.8, 0.0), label='Kukurydza')
    kolor_soja = mpatches.Patch(color=(0.0, 0.3, 0.8), label='Soja')
    kolor_tlo = mpatches.Patch(color=(0.8, 0.8, 0.8), label='Inne / Tło')

    plt.legend(handles=[kolor_kukurydza, kolor_soja, kolor_tlo], loc='upper right')
    plt.title(f"Rozkład Upraw w Iowa ({CROP_YEAR})\n(Dane: USDA CDL)")
    plt.axis('off')
    plt.savefig("corn_soy_map.png")

    plt.show()


if __name__ == "__main__":
    if pobierz_maske_z_api(SENTINEL_REF, MASK_FILENAME):
        wizualizuj_tylko_maske(SENTINEL_REF, MASK_FILENAME)