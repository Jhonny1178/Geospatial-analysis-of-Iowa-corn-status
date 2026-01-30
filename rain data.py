import rasterio
from rasterio.warp import reproject, Resampling
import numpy as np
import matplotlib.pyplot as plt
import os

SENTINEL_RED = "red.jp2"
SENTINEL_NIR = "nir.jp2"
PLIK_PRISM = "prism_ppt_us_30s_202408.tif"
# Dane trzeba pobrać z https://prism.oregonstate.edu/data/ aby dostać cały miesiąć
OUTPUT_FILENAME = "wykres_korelacji_real_sierpien.png"


def generuj_tylko_wykres_real():
    print(f"START: Generowanie wykresu z pliku {PLIK_PRISM} ")

    if not os.path.exists(PLIK_PRISM):
        print(f"BŁĄD: Nie widzę pliku '{PLIK_PRISM}'!")
        print("Upewnij się, że skopiowałeś go do folderu projektu.")
        return

    print("[1/3] Wczytywanie danych NDVI...")
    with rasterio.open(SENTINEL_RED) as src:
        red = src.read(1).astype('float32')
        height, width = red.shape
        dst_crs = src.crs
        dst_transform = src.transform

    with rasterio.open(SENTINEL_NIR) as src:
        nir = src.read(1, out_shape=(height, width), resampling=Resampling.nearest).astype('float32')

    ndvi = (nir - red) / (nir + red + 1e-8)

    print(f"[2/3] Przetwarzanie danych opadowych...")
    mapa_deszczu = np.zeros((height, width), dtype=np.float32)

    try:
        with rasterio.open(PLIK_PRISM) as src_rain:
            reproject(
                source=rasterio.band(src_rain, 1),
                destination=mapa_deszczu,
                src_transform=src_rain.transform,
                src_crs=src_rain.crs,
                dst_transform=dst_transform,
                dst_crs=dst_crs,
                resampling=Resampling.bilinear
            )
    except Exception as e:
        print(f"Błąd pliku TIF: {e}")
        return

    print("[3/3] Rysowanie wykresu...")

    maska = (ndvi > 0.3)
    step = 200

    x_samp = mapa_deszczu[maska][::step]
    y_samp = ndvi[maska][::step]

    std_dev = np.std(x_samp)

    if std_dev > 0.01:
        r = np.corrcoef(x_samp, y_samp)[0, 1]
        trend_label = f'Trend (r={r:.3f})'
    else:
        r = 0
        trend_label = 'Opad stały (brak trendu)'

    plt.figure(figsize=(10, 7))

    plt.scatter(x_samp, y_samp, alpha=0.15, s=15, c='darkblue', edgecolors='none', label='Pola uprawne')

    if std_dev > 0.01 and len(x_samp) > 1:
        m, b = np.polyfit(x_samp, y_samp, 1)
        plt.plot(x_samp, m * x_samp + b, color='red', linewidth=3, label=trend_label)

    plt.title(f"Rzeczywista korelacja: Opad vs NDVI (Sierpien 2024)", fontsize=16)
    plt.xlabel("Suma opadów [mm]", fontsize=14)
    plt.ylabel("Kondycja roślin (NDVI)", fontsize=14)
    plt.legend(fontsize=12)
    plt.grid(True, alpha=0.3, linestyle='--')

    if len(x_samp) > 0:
        plt.xlim(min(x_samp) - 5, max(x_samp) + 5)

    plt.tight_layout()
    plt.savefig(OUTPUT_FILENAME, dpi=150)
    print(f"\n[SUKCES] Wygenerowano plik: {OUTPUT_FILENAME}")
    plt.show()


if __name__ == "__main__":
    generuj_tylko_wykres_real()