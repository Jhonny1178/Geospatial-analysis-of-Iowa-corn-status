import zipfile
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject
import numpy as np
import matplotlib.pyplot as plt
from scipy.ndimage import distance_transform_edt, binary_opening
import os
import shutil

ZIP_FILENAME = "sentinel_image.zip"
MASK_FILENAME = "crop_mask_usda.tif"
SAMPLE_SIZE = 15000


def analiza_krok_po_kroku_kropki():
    print("=== ROZPOCZYNAM ANALIZĘ (STYL: NIEBIESKIE KROPKI) ===")
    print("[1/6] Przygotowanie danych...")

    paths = {}
    if not os.path.exists(ZIP_FILENAME):
        print(f"[BŁĄD] Brak pliku {ZIP_FILENAME}!")
        return

    with zipfile.ZipFile(ZIP_FILENAME, 'r') as z:
        for f in z.namelist():
            if "IMG_DATA" in f and f.endswith(".jp2"):
                if "B04" in f and ("R10m" in f or "_B04" in f):
                    paths["red"] = f
                elif "B08" in f and ("R10m" in f or "_B08" in f):
                    paths["nir"] = f
                elif "B11" in f and ("R20m" in f or "_B11" in f):
                    paths["swir"] = f
                elif "SCL" in f and ("R20m" in f or "SCL" in f):
                    paths["scl"] = f

    if len(paths) < 4:
        print(f"[BŁĄD] Brakuje plików. Znaleziono: {list(paths.keys())}")
        return

    with zipfile.ZipFile(ZIP_FILENAME, 'r') as z:
        for n, p in paths.items():
            with z.open(p) as src, open(f"{n}.jp2", "wb") as dst: shutil.copyfileobj(src, dst)

    print("[2/6] Skalowanie map...")

    with rasterio.open("red.jp2") as src:
        red = src.read(1).astype('float32')
        profile = src.profile
        target_shape = (src.height, src.width)

    with rasterio.open("nir.jp2") as src:
        nir = src.read(1, out_shape=target_shape, resampling=Resampling.nearest).astype('float32')

    with rasterio.open("swir.jp2") as src:
        swir = src.read(1, out_shape=target_shape, resampling=Resampling.nearest).astype('float32')

    with rasterio.open("scl.jp2") as src:
        scl = src.read(1, out_shape=target_shape, resampling=Resampling.nearest)

    print("   -> Generowanie 'kropek' wodnych...")

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
        maska_kukurydzy = np.isin(scl, [4, 5])

    maska_chmur = (scl == 3) | (scl == 8) | (scl == 9) | (scl == 10)
    final_mask = maska_kukurydzy & ~maska_chmur

    maska_wody = (scl == 6)


    maska_wody = binary_opening(maska_wody, structure=np.ones((3, 3)))

    if np.sum(maska_wody) == 0:
        maska_wody[:, int(target_shape[1] / 2):int(target_shape[1] / 2) + 100] = True

    odleglosc = distance_transform_edt(~maska_wody) * 10


    ndvi = (nir - red) / (nir + red + 1e-8)
    ndmi = (nir - swir) / (nir + swir + 1e-8)

    x_dist = odleglosc[final_mask]
    y_ndmi = ndmi[final_mask]
    y_ndvi = ndvi[final_mask]

    if len(x_dist) > SAMPLE_SIZE:
        idx = np.random.choice(len(x_dist), SAMPLE_SIZE, replace=False)
        x_sample = x_dist[idx]
        y_ndmi_sample = y_ndmi[idx]
        y_ndvi_sample = y_ndvi[idx]
    else:
        x_sample = x_dist
        y_ndmi_sample = y_ndmi
        y_ndvi_sample = y_ndvi



    print("\n[3/6] Generowanie Mapy 1: Model Hydrologiczny (Kropki)...")
    plt.figure(figsize=(10, 8))


    plt.imshow(odleglosc, cmap='Blues_r', vmin=0, vmax=3000)

    plt.colorbar(label="Odległość od wody [m]")
    plt.title("1. Model Hydrologiczny Terenu\n(Ciemne punkty = Woda)")
    plt.axis('off')
    plt.savefig("1_mapa_wody_kropki.png")
    print("   -> Zapisano. Zamknij okno wykresu, aby kontynuować.")
    plt.show()

    print("\n[4/6] Generowanie Mapy 2: Kukurydza wg Dystansu...")
    plt.figure(figsize=(10, 8))
    tlo = np.full(target_shape, 0.2)
    plt.imshow(tlo, cmap='gray', vmin=0, vmax=1)

    dist_corn_view = np.where(final_mask, odleglosc, np.nan)
    plt.imshow(dist_corn_view, cmap='Spectral_r', vmin=0, vmax=5000)
    plt.colorbar(label="Odległość od wody [m]")
    plt.title("2. Pola Kukurydzy w zależności od wody")
    plt.axis('off')
    plt.savefig("2_mapa_kukurydzy_dystans.png")
    print("   -> Zapisano. Zamknij okno wykresu, aby kontynuować.")
    plt.show()

    print("\n[5/6] Generowanie Wykresu 3: Wpływ na Suszę...")
    plt.figure(figsize=(10, 6))
    if len(x_sample) > 0:
        r = np.corrcoef(x_sample, y_ndmi_sample)[0, 1]
        m, b = np.polyfit(x_sample, y_ndmi_sample, 1)
        plt.scatter(x_sample, y_ndmi_sample, alpha=0.15, s=5, c='blue', label='Pola')
        plt.plot(x_sample, m * x_sample + b, color='red', linewidth=3, label=f'Trend')
        plt.title(f"3. Czy odległość wpływa na wilgotność (NDMI) 2024-08-18?\nKorelacja Pearsona: r = {r:.3f}")

    plt.xlabel("Odległość od rzeki [m]")
    plt.ylabel("Wilgotność (NDMI)")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.savefig("3_wykres_susza.png")
    print("   -> Zapisano. Zamknij okno wykresu, aby kontynuować.")
    plt.show()

    print("\n[6/6] Generowanie Wykresu 4: Wpływ na Zdrowie...")
    plt.figure(figsize=(10, 6))
    if len(x_sample) > 0:
        r = np.corrcoef(x_sample, y_ndvi_sample)[0, 1]
        m, b = np.polyfit(x_sample, y_ndvi_sample, 1)
        plt.scatter(x_sample, y_ndvi_sample, alpha=0.15, s=5, c='green', label='Pola')
        plt.plot(x_sample, m * x_sample + b, color='red', linewidth=3, label=f'Trend')
        plt.title(f"4. Czy odległość wpływa na zdrowie (NDVI) 2024-08-18 ?\nKorelacja Pearsona: r = {r:.3f}")

    plt.xlabel("Odległość od rzeki [m]")
    plt.ylabel("Kondycja (NDVI)")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.savefig("4_wykres_zdrowie.png")
    print("   -> Zapisano. To był ostatni wykres.")
    plt.show()


if __name__ == "__main__":
    analiza_krok_po_kroku_kropki()