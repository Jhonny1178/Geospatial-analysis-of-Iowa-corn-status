import rasterio
from rasterio.warp import reproject, Resampling
import numpy as np
import matplotlib.pyplot as plt
import os
import zipfile
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "Data")
RESULTS_DIR = os.path.join(BASE_DIR, "Charts_And_Analysis")

ZIP_FILENAME = os.path.join(DATA_DIR, "sentinel_image.zip")
# U need to download data from https://prism.oregonstate.edu/data/
PRISM_FILE_PATH = os.path.join(DATA_DIR, "your_file_name")
OUTPUT_FILENAME = os.path.join(RESULTS_DIR, "rainfall_correlation_august.png")

TEMP_FILES = ["red.jp2", "nir.jp2"]


def generate_rainfall_correlation_plot():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    print(f"START: Generating correlation plot using {PRISM_FILE_PATH}")

    if not os.path.exists(PRISM_FILE_PATH):
        print(f"ERROR: Prism file '{PRISM_FILE_PATH}' not found!")
        return

    if not os.path.exists(ZIP_FILENAME):
        print(f"ERROR: ZIP file '{ZIP_FILENAME}' not found!")
        return

    print("1/4 Extracting bands from ZIP...")
    found_paths = {"red": None, "nir": None}
    with zipfile.ZipFile(ZIP_FILENAME, 'r') as z:
        for f in z.namelist():
            if "IMG_DATA" in f and f.endswith(".jp2") and ("R10m" in f or "_10m" in f):
                if "B04" in f:
                    found_paths["red"] = f
                elif "B08" in f:
                    found_paths["nir"] = f

    if not all(found_paths.values()):
        print("ERROR: Missing B04 or B08 bands in ZIP!")
        return

    with zipfile.ZipFile(ZIP_FILENAME, 'r') as z:
        for name, path in found_paths.items():
            with z.open(path) as src, open(f"{name}.jp2", "wb") as dst:
                shutil.copyfileobj(src, dst)

    print("2/4 Loading NDVI data...")
    with rasterio.open("red.jp2") as src:
        red_data = src.read(1).astype('float32')
        height, width = red_data.shape
        dst_crs = src.crs
        dst_transform = src.transform

    with rasterio.open("nir.jp2") as src:
        nir_data = src.read(1, out_shape=(height, width), resampling=Resampling.nearest).astype('float32')

    ndvi_data = (nir_data - red_data) / (nir_data + red_data + 1e-8)

    print("3/4 Processing rainfall data (Reprojection)...")
    rainfall_map = np.zeros((height, width), dtype=np.float32)

    try:
        with rasterio.open(PRISM_FILE_PATH) as src_rain:
            reproject(
                source=rasterio.band(src_rain, 1),
                destination=rainfall_map,
                src_transform=src_rain.transform,
                src_crs=src_rain.crs,
                dst_transform=dst_transform,
                dst_crs=dst_crs,
                resampling=Resampling.bilinear
            )
    except Exception as e:
        print(f"TIF File Error: {e}")
        return

    print("4/4 Generating plot...")
    ndvi_mask = (ndvi_data > 0.3)
    sampling_step = 200

    x_sample = rainfall_map[ndvi_mask][::sampling_step]
    y_sample = ndvi_data[ndvi_mask][::sampling_step]

    std_dev = np.std(x_sample)

    plt.figure(figsize=(10, 7))
    plt.scatter(x_sample, y_sample, alpha=0.15, s=15, c='darkblue', edgecolors='none', label='Farmland pixels')

    if std_dev > 0.01 and len(x_sample) > 1:
        r_coeff = np.corrcoef(x_sample, y_sample)[0, 1]
        m_slope, b_intercept = np.polyfit(x_sample, y_sample, 1)
        plt.plot(x_sample, m_slope * x_sample + b_intercept, color='red', linewidth=3, label=f'Trend (r={r_coeff:.3f})')
    else:
        plt.legend(title='Constant rainfall (no trend)')

    plt.title("Actual Correlation: Rainfall vs NDVI (August 2024)", fontsize=16)
    plt.xlabel("Total Precipitation [mm]", fontsize=14)
    plt.ylabel("Plant Condition (NDVI)", fontsize=14)
    plt.legend(fontsize=12)
    plt.grid(True, alpha=0.3, linestyle='--')

    if len(x_sample) > 0:
        plt.xlim(min(x_sample) - 5, max(x_sample) + 5)

    plt.tight_layout()
    plt.savefig(OUTPUT_FILENAME, dpi=150)
    print(f"\n[SUCCESS] File generated: {OUTPUT_FILENAME}")

    print("Cleaning up temporary files...")
    for temp_file in TEMP_FILES:
        if os.path.exists(temp_file):
            os.remove(temp_file)

    plt.show()


if __name__ == "__main__":
    generate_rainfall_correlation_plot()