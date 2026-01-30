import zipfile
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject
import numpy as np
import matplotlib.pyplot as plt
import os
import shutil

ZIP_FILENAME = "sentinel_image.zip"
MASK_FILENAME = "crop_mask_usda.tif"


def analiza_woda_vs_zdrowie():
    print("[1/4] Wypakowywanie danych...")

    paths = {"red": None, "nir": None, "swir": None}
    if not os.path.exists(ZIP_FILENAME):
        print("Brak pliku ZIP!")
        return

    with zipfile.ZipFile(ZIP_FILENAME, 'r') as z:
        for f in z.namelist():
            if "IMG_DATA" in f and f.endswith(".jp2"):
                if "B04" in f and ("R10m" in f or "_B04" in f):
                    paths["red"] = f
                elif "B08" in f and ("R10m" in f or "_B08" in f):
                    paths["nir"] = f
                elif "B11" in f and ("R20m" in f or "R60m" in f or "_B11" in f):
                    paths["swir"] = f

    if not all(paths.values()):
        print(f"Brakuje plików! Znaleziono tylko: {paths}")
        return

    with zipfile.ZipFile(ZIP_FILENAME, 'r') as z:
        with z.open(paths["red"]) as s, open("red.jp2", "wb") as d: shutil.copyfileobj(s, d)
        with z.open(paths["nir"]) as s, open("nir.jp2", "wb") as d: shutil.copyfileobj(s, d)
        with z.open(paths["swir"]) as s, open("swir.jp2", "wb") as d: shutil.copyfileobj(s, d)

    print("[2/4] Wczytywanie i SKALOWANIE (Naprawa błędu wymiarów)...")

    with rasterio.open("red.jp2") as src:
        red = src.read(1).astype('float32')
        target_height = src.height
        target_width = src.width
        target_shape = (target_height, target_width)

        profile = src.profile
        print(f"   -> Wymiary docelowe: {target_shape} (10m)")

    with rasterio.open("nir.jp2") as src:
        nir = src.read(
            1,
            out_shape=target_shape,
            resampling=Resampling.nearest
        ).astype('float32')


    with rasterio.open("swir.jp2") as src:
        swir = src.read(
            1,
            out_shape=target_shape,
            resampling=Resampling.nearest
        ).astype('float32')
        print(f"   -> Przeskalowano SWIR z {src.shape} do {target_shape}")

    if os.path.exists(MASK_FILENAME):
        with rasterio.open(MASK_FILENAME) as src_mask:
            corn_raw = np.empty(target_shape, dtype='uint8')
            reproject(
                source=rasterio.band(src_mask, 1),
                destination=corn_raw,
                src_transform=src_mask.transform,
                src_crs=src_mask.crs,
                dst_transform=profile['transform'],
                dst_crs=profile['crs'],
                resampling=Resampling.nearest
            )
        maska_kukurydzy = (corn_raw == 1)
    else:
        maska_kukurydzy = np.ones(target_shape, dtype=bool)

    maska_chmur = (red > 2500)
    final_mask = maska_kukurydzy & ~maska_chmur

    print("[3/4] Obliczanie wskaźników...")

    ndmi = (nir - swir) / (nir + swir + 1e-8)
    ndvi = (nir - red) / (nir + red + 1e-8)

    ndmi_view = np.where(final_mask, ndmi, np.nan)

    plt.figure(figsize=(10, 8))
    cmap_water = plt.cm.RdBu
    cmap_water.set_bad('white')

    plt.imshow(ndmi_view, cmap=cmap_water, vmin=-0.2, vmax=0.4)
    plt.colorbar(label="Wskaźnik Wilgotności (NDMI)")
    plt.title("Mapa Nawodnienia Kukurydzy 2024-08-18 \n(Niebieski = Wilgotno, Czerwony = Sucho)")

    plt.savefig("tylko_woda_ndmi.png")
    print("   [SUKCES] Zapisano mapę: tylko_woda_ndmi.png")
    plt.show()

    print("[4/4] Rysowanie wykresu korelacji...")

    x_woda = ndmi[final_mask]
    y_zdrowie = ndvi[final_mask]

    if len(x_woda) > 10000:
        idx = np.random.choice(len(x_woda), 10000, replace=False)
        x_woda = x_woda[idx]
        y_zdrowie = y_zdrowie[idx]

    if len(x_woda) > 0:
        r = np.corrcoef(x_woda, y_zdrowie)[0, 1]
    else:
        r = 0

    plt.figure(figsize=(10, 7))
    plt.scatter(x_woda, y_zdrowie, alpha=0.15, s=3, c='purple', label='Pola kukurydzy')

    if len(x_woda) > 0:
        m, b = np.polyfit(x_woda, y_zdrowie, 1)
        plt.plot(x_woda, m * x_woda + b, color='red', linewidth=2, label=f'Trend')

    plt.xlabel("Wilgotność (NDMI)")
    plt.ylabel("Kondycja (NDVI)")
    plt.title(f"Czy woda wpływa na zdrowie 2024-08-18?\nKorelacja Pearsona: r = {r:.3f}")
    plt.grid(True, alpha=0.3)
    plt.legend()

    plt.savefig("korelacja_woda_vs_zdrowie.png")
    print("   [SUKCES] Zapisano wykres korelacji.")
    plt.show()


if __name__ == "__main__":
    analiza_woda_vs_zdrowie()