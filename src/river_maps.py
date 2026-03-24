import zipfile
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject
import numpy as np
import matplotlib.pyplot as plt
from scipy.ndimage import distance_transform_edt, binary_opening
import os
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "Data")
RESULTS_DIR = os.path.join(BASE_DIR, "Charts_And_Analysis")

ZIP_FILENAME = os.path.join(DATA_DIR, "sentinel_image.zip")
MASK_FILENAME = os.path.join(DATA_DIR, "crop_mask_usda.tif")
SAMPLE_SIZE = 15000
TEMP_FILES = ["red.jp2", "nir.jp2", "swir.jp2", "scl.jp2"]


def analyze_distance_impact():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    print("1/6 Preparing data and extracting bands...")

    band_paths = {}
    if not os.path.exists(ZIP_FILENAME):
        print(f"ERROR: {ZIP_FILENAME} not found!")
        return

    with zipfile.ZipFile(ZIP_FILENAME, 'r') as z:
        for filename in z.namelist():
            if "IMG_DATA" in filename and filename.endswith(".jp2"):
                if "B04" in filename and ("R10m" in filename or "_B04" in filename):
                    band_paths["red"] = filename
                elif "B08" in filename and ("R10m" in filename or "_B08" in filename):
                    band_paths["nir"] = filename
                elif "B11" in filename and ("R20m" in filename or "_B11" in filename):
                    band_paths["swir"] = filename
                elif "SCL" in filename and ("R20m" in filename or "SCL" in filename):
                    band_paths["scl"] = filename

    if len(band_paths) < 4:
        print(f"ERROR: Missing bands! Found: {list(band_paths.keys())}")
        return

    with zipfile.ZipFile(ZIP_FILENAME, 'r') as z:
        for name, path in band_paths.items():
            with z.open(path) as src, open(f"{name}.jp2", "wb") as dst:
                shutil.copyfileobj(src, dst)

    print("2/6 Loading and resampling bands...")

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

    print("Generating water proximity model...")

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
        corn_mask = np.isin(scl, [4, 5])

    cloud_mask = np.isin(scl, [3, 8, 9, 10])
    final_mask = corn_mask & ~cloud_mask

    water_mask = (scl == 6)
    water_mask = binary_opening(water_mask, structure=np.ones((3, 3)))

    if np.sum(water_mask) == 0:
        water_mask[:, int(target_shape[1] / 2):int(target_shape[1] / 2) + 100] = True

    distance_map = distance_transform_edt(~water_mask) * 10

    ndvi = (nir - red) / (nir + red + 1e-8)
    ndmi = (nir - swir) / (nir + swir + 1e-8)

    x_dist = distance_map[final_mask]
    y_ndmi = ndmi[final_mask]
    y_ndvi = ndvi[final_mask]

    if len(x_dist) > SAMPLE_SIZE:
        indices = np.random.choice(len(x_dist), SAMPLE_SIZE, replace=False)
        x_sample = x_dist[indices]
        y_ndmi_sample = y_ndmi[indices]
        y_ndvi_sample = y_ndvi[indices]
    else:
        x_sample, y_ndmi_sample, y_ndvi_sample = x_dist, y_ndmi, y_ndvi

    print("3/6 Saving Map 1: Hydrological Proximity...")
    plt.figure(figsize=(10, 8))
    plt.imshow(distance_map, cmap='Blues_r', vmin=0, vmax=3000)
    plt.colorbar(label="Distance from water [m]")
    plt.title("1. Hydrological Terrain Model\n(Dark Blue = Water Source)")
    plt.axis('off')
    plt.savefig(os.path.join(RESULTS_DIR, "1_water_proximity_model.png"))
    plt.show()

    print("4/6 Saving Map 2: Corn Fields Distance...")
    plt.figure(figsize=(10, 8))
    background = np.full(target_shape, 0.2)
    plt.imshow(background, cmap='gray', vmin=0, vmax=1)
    dist_corn_view = np.where(final_mask, distance_map, np.nan)
    plt.imshow(dist_corn_view, cmap='Spectral_r', vmin=0, vmax=5000)
    plt.colorbar(label="Distance from water [m]")
    plt.title("2. Corn Fields vs. Water Proximity")
    plt.axis('off')
    plt.savefig(os.path.join(RESULTS_DIR, "2_corn_distance_map.png"))
    plt.show()

    print("5/6 Saving Plot 3: Moisture vs. Distance...")
    plt.figure(figsize=(10, 6))
    if len(x_sample) > 0:
        r_val = np.corrcoef(x_sample, y_ndmi_sample)[0, 1]
        m, b = np.polyfit(x_sample, y_ndmi_sample, 1)
        plt.scatter(x_sample, y_ndmi_sample, alpha=0.15, s=5, c='blue', label='Corn Pixels')
        plt.plot(x_sample, m * x_sample + b, color='red', linewidth=3, label='Trend')
        plt.title(f"3. Impact of Distance on Moisture (NDMI)\nPearson Correlation: r = {r_val:.3f}")

    plt.xlabel("Distance from water [m]")
    plt.ylabel("Moisture Index (NDMI)")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.savefig(os.path.join(RESULTS_DIR, "3_moisture_correlation.png"))
    plt.show()

    print("6/6 Saving Plot 4: Health vs. Distance...")
    plt.figure(figsize=(10, 6))
    if len(x_sample) > 0:
        r_val = np.corrcoef(x_sample, y_ndvi_sample)[0, 1]
        m, b = np.polyfit(x_sample, y_ndvi_sample, 1)
        plt.scatter(x_sample, y_ndvi_sample, alpha=0.15, s=5, c='green', label='Corn Pixels')
        plt.plot(x_sample, m * x_sample + b, color='red', linewidth=3, label='Trend')
        plt.title(f"4. Impact of Distance on Health (NDVI)\nPearson Correlation: r = {r_val:.3f}")

    plt.xlabel("Distance from water [m]")
    plt.ylabel("Health Index (NDVI)")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.savefig(os.path.join(RESULTS_DIR, "4_health_correlation.png"))
    plt.show()

    print("Cleaning up temporary files...")
    for temp_file in TEMP_FILES:
        if os.path.exists(temp_file):
            os.remove(temp_file)
    print("Done.")


if __name__ == "__main__":
    analyze_distance_impact()