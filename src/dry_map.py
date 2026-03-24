import zipfile
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject
import numpy as np
import matplotlib.pyplot as plt
import os
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "Data")
RESULTS_DIR = os.path.join(BASE_DIR, "Charts_And_Analysis")

ZIP_FILENAME = os.path.join(DATA_DIR, "sentinel_image.zip")
MASK_FILENAME = os.path.join(DATA_DIR, "crop_mask_usda.tif")

TEMP_FILES = ["red.jp2","nir.jp2","swir.jp2"]

def analyze_water_vs_health():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    print("1/4 Extracting data...")

    band_paths = {"red": None, "nir": None, "swir": None}
    if not os.path.exists(ZIP_FILENAME):
        print(f"ERROR: ZIP file not found at {ZIP_FILENAME}!")
        return

    with zipfile.ZipFile(ZIP_FILENAME, 'r') as z:
        for f in z.namelist():
            if "IMG_DATA" in f and f.endswith(".jp2"):
                if "B04" in f and ("R10m" in f or "_B04" in f):
                    band_paths["red"] = f
                elif "B08" in f and ("R10m" in f or "_B08" in f):
                    band_paths["nir"] = f
                elif "B11" in f and ("R20m" in f or "R60m" in f or "_B11" in f):
                    band_paths["swir"] = f

    if not all(band_paths.values()):
        print(f"ERROR: Missing bands! Found: {band_paths}")
        return

    with zipfile.ZipFile(ZIP_FILENAME, 'r') as z:
        with z.open(band_paths["red"]) as s, open("red.jp2", "wb") as d: shutil.copyfileobj(s, d)
        with z.open(band_paths["nir"]) as s, open("nir.jp2", "wb") as d: shutil.copyfileobj(s, d)
        with z.open(band_paths["swir"]) as s, open("swir.jp2", "wb") as d: shutil.copyfileobj(s, d)

    print("2/4 Loading and resampling...")

    with rasterio.open("red.jp2") as src:
        red = src.read(1).astype('float32')
        target_height = src.height
        target_width = src.width
        target_shape = (target_height, target_width)
        profile = src.profile
        print(f"Target dimensions: {target_shape} (10m)")

    with rasterio.open("nir.jp2") as src:
        nir = src.read(1, out_shape=target_shape, resampling=Resampling.nearest).astype('float32')

    with rasterio.open("swir.jp2") as src:
        swir = src.read(1, out_shape=target_shape, resampling=Resampling.nearest).astype('float32')
        print(f"   -> Resampled SWIR from {src.shape} to {target_shape}")

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
        corn_mask = (corn_raw == 1)
    else:
        corn_mask = np.ones(target_shape, dtype=bool)

    cloud_mask = (red > 2500)
    final_mask = corn_mask & ~cloud_mask

    print("3/4 Calculating indices...")

    ndmi = (nir - swir) / (nir + swir + 1e-8)
    ndvi = (nir - red) / (nir + red + 1e-8)

    ndmi_filtered = np.where(final_mask, ndmi, np.nan)

    plt.figure(figsize=(10, 8))
    cmap_water = plt.cm.RdBu
    cmap_water.set_bad('white')

    plt.imshow(ndmi_filtered, cmap=cmap_water, vmin=-0.2, vmax=0.4)
    plt.colorbar(label="Moisture Index (NDMI)")
    plt.title("Corn Hydration Map\n(Blue = Moist, Red = Dry)")

    map_save_path = os.path.join(RESULTS_DIR, "corn_hydration_ndmi.png")
    plt.savefig(map_save_path)
    print(f"Map saved: {map_save_path}")
    plt.show()

    print("4/4 Generating correlation plot...")

    x_water = ndmi[final_mask]
    y_health = ndvi[final_mask]

    if len(x_water) > 10000:
        idx = np.random.choice(len(x_water), 10000, replace=False)
        x_water = x_water[idx]
        y_health = y_health[idx]

    if len(x_water) > 0:
        r_coefficient = np.corrcoef(x_water, y_health)[0, 1]
    else:
        r_coefficient = 0

    plt.figure(figsize=(10, 7))
    plt.scatter(x_water, y_health, alpha=0.15, s=3, c='purple', label='Corn Fields')

    if len(x_water) > 0:
        m, b = np.polyfit(x_water, y_health, 1)
        plt.plot(x_water, m * x_water + b, color='red', linewidth=2, label='Trendline')

    plt.xlabel("Moisture (NDMI)")
    plt.ylabel("Condition (NDVI)")
    plt.title(f"Does water affect plant health? (2024-08-18)\nPearson Correlation: r = {r_coefficient:.3f}")
    plt.grid(True, alpha=0.3)
    plt.legend()

    correlation_save_path = os.path.join(RESULTS_DIR, "water_vs_health_correlation.png")
    plt.savefig(correlation_save_path)
    print(f"   [SUCCESS] Correlation plot saved: {correlation_save_path}")
    plt.show()

    print("Cleaning up temporary files...")
    for file in TEMP_FILES:
        if os.path.exists(file):
            os.remove(file)
    print("Done.")

if __name__ == "__main__":
    analyze_water_vs_health()