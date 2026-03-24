import requests
import rasterio
from rasterio.warp import transform_bounds, reproject, Resampling
import numpy as np
import matplotlib.pyplot as plt
import os
import re
import zipfile
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "Data")
RESULTS_DIR = os.path.join(BASE_DIR, "Charts_and_Analysis")
ZIP_FILENAME = os.path.join(DATA_DIR, "sentinel_image.zip")

MASK_TIF_PATH = os.path.join(DATA_DIR, "crop_mask_usda.tif")
TEMP_RED = "red_temp.jp2"
TEMP_NIR = "nir_temp.jp2"


CROP_YEAR = "2024"
CORN_CLASS_ID = 1

os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)


def extract_bands_from_zip():
    print("1/3 Extracting Red and NIR from ZIP...")
    found = {"red": False, "nir": False}

    if not os.path.exists(ZIP_FILENAME):
        print(f"ERROR ZIP file not found at {ZIP_FILENAME}")
        return False

    with zipfile.ZipFile(ZIP_FILENAME, 'r') as z:
        for file in z.namelist():
            if "IMG_DATA" in file and ("R10m" in file or "_10m" in file):
                if "B04" in file:  # Red Band
                    with z.open(file) as src, open(TEMP_RED, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    found["red"] = True
                elif "B08" in file:  # NIR Band
                    with z.open(file) as src, open(TEMP_NIR, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    found["nir"] = True

    return all(found.values())


def download_crop_mask(reference_file, output_path):
    if os.path.exists(output_path):
        print(f" Crop mask already exists at {output_path}. Skipping download.")
        return True




def generate_corn_ndvi_overlay(red_path, nir_path, mask_path):

    print("2/3 Processing NDVI and aligning crop mask...")

    with rasterio.open(red_path) as src_r:
        red_data = src_r.read(1).astype('float32')
        height, width = red_data.shape
        transform, crs = src_r.transform, src_r.crs

    with rasterio.open(nir_path) as src_n:
        nir_data = src_n.read(1, out_shape=(height, width), resampling=Resampling.nearest).astype('float32')

    ndvi = (nir_data - red_data) / (nir_data + red_data + 1e-8)

    with rasterio.open(mask_path) as src_mask:
        matched_mask = np.empty((height, width), dtype='uint8')
        reproject(
            source=rasterio.band(src_mask, 1),
            destination=matched_mask,
            src_transform=src_mask.transform,
            src_crs=src_mask.crs,
            dst_transform=transform,
            dst_crs=crs,
            resampling=Resampling.nearest
        )

    print("3/3 Generating corn-specific NDVI map...")

    corn_mask = (matched_mask == CORN_CLASS_ID)
    cloud_mask = (red_data > 2500)
    final_corn_ndvi = np.where(corn_mask & ~cloud_mask, ndvi, np.nan)


    plt.figure(figsize=(12, 10))

    plt.imshow(ndvi, cmap='gray', vmin=0, vmax=0.8, alpha=0.3)

    img = plt.imshow(final_corn_ndvi, cmap='RdYlGn', vmin=0.2, vmax=0.9)

    plt.colorbar(img, label='NDVI (Crop Condition)')
    avg_ndvi = np.nanmean(final_corn_ndvi)
    plt.title(f"Corn Condition Analysis Iowa {CROP_YEAR}\nMean Corn NDVI: {avg_ndvi:.2f}")
    plt.axis('off')

    output_png = os.path.join(RESULTS_DIR,"corn_ndvi_overlay.png")
    plt.savefig(output_png, bbox_inches='tight', dpi=300)
    print(f"   [SUCCESS] Map saved at: {output_png}")
    plt.show()


if __name__ == "__main__":
    if extract_bands_from_zip():
        if download_crop_mask(TEMP_RED, MASK_TIF_PATH):
            generate_corn_ndvi_overlay(TEMP_RED, TEMP_NIR, MASK_TIF_PATH)

        for f in [TEMP_RED, TEMP_NIR]:
            if os.path.exists(f):
                os.remove(f)
        print("Temporary files removed.")
    else:
        print("Process aborted: Could not extract bands.")