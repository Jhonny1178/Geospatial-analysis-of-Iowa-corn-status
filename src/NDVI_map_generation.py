import zipfile
import rasterio
from rasterio.enums import Resampling
import numpy as np
import matplotlib.pyplot as plt
import os
import shutil


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ZIP_FILENAME = os.path.join(BASE_DIR, "Data", "sentinel_image.zip")
RESULTS_DIR = os.path.join(BASE_DIR, "Charts_and_Analysis")

def ndvi():
    print("1/3 Extracting L2A data...")

    paths = {"red":None,"nir":None,"scl": None}
    temp_files = ["red.jp2", "nir.jp2", "scl.jp2"]

    with zipfile.ZipFile(ZIP_FILENAME, 'r') as z:
        for file in z.namelist():
            if "IMG_DATA" in file and file.endswith(".jp2"):
                if ("R10m" in file or "_10m" in file):
                    if "B04" in file:
                        paths["red"] = file
                    elif "B08" in file:
                        paths["nir"] = file

                if ("R20m" in file or "_20m" in file) and "SCL" in file:
                    paths["scl"] = file

    if not all(paths.values()):
        print(f"ERROR Not all files found! Found: {paths}")
        return

    with zipfile.ZipFile(ZIP_FILENAME, 'r') as z:
        for name, p in paths.items():
            with z.open(p) as src, open(f"{name}.jp2", "wb") as dst:
                shutil.copyfileobj(src, dst)

    print("2/3 Image processing...")

    with rasterio.open("red.jp2") as src:
        red = src.read(1).astype('float32')
        height, width = red.shape

    with rasterio.open("nir.jp2") as src:
        nir = src.read(1).astype('float32')

    print("Applying a cloud mask from an SCL file...")
    with rasterio.open("scl.jp2") as src:
        scl = src.read(
            1,
            out_shape=(height, width),
            resampling=Resampling.nearest
        )

    ndvi = (nir - red) / (nir + red + 1e-8)


    maska_zla=np.isin(scl, [0, 1, 3, 8, 9, 10, 11])

    ndvi_clean=np.where(maska_zla, np.nan, ndvi)

    print("3/3 Drawing a map...")
    plt.figure(figsize=(12, 10))


    valid_pixels=ndvi_clean[~np.isnan(ndvi_clean)]
    vmin=np.percentile(valid_pixels, 2)
    vmax=np.percentile(valid_pixels, 98)

    cmap=plt.cm.RdYlGn
    cmap.set_bad('white')

    plt.imshow(ndvi_clean,cmap=cmap,vmin=vmin,vmax=vmax)
    plt.colorbar(label="NDVI")
    plt.title(f"IOWA State NDVI Map 2024-08-18")
    if not os.path.exists(RESULTS_DIR):
        os.makedirs(RESULTS_DIR)
    final_save_path = os.path.join(RESULTS_DIR, "Ndvi_map_clean.png")


    plt.savefig(final_save_path)
    print(f"SUCCESS Saved plot to {final_save_path}")

    for f in temp_files:
        if os.path.exists(f):
            os.remove(f)
    print("Cleanup: Temporary .jp2 files removed from src.")
    plt.show()


if __name__ == "__main__":
    if os.path.exists(ZIP_FILENAME):
        ndvi()
    else:
        print("No ZIP file")