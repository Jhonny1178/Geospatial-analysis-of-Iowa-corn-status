import requests
import rasterio
from rasterio.warp import transform_bounds, reproject, Resampling
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import os
import re
import zipfile
import shutil
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ZIP_FILENAME = os.path.join(BASE_DIR, "Data", "sentinel_image.zip")
RESULTS_DIR = os.path.join(BASE_DIR, "Charts_and_Analysis","Corn_soy_map_USA.png")
MASK_FILENAME = os.path.join(BASE_DIR, "Data", "crop_mask_usda.tif")
SENTINEL_REF = "red.jp2"
# make sure that the year is the same that your downloaded satellites photo
CROP_YEAR = "2024"

def download_mask_from_api(template_file, output_file):
    print(f"1/3 Download USDA crop map for the year : {CROP_YEAR}...")

    if not os.path.exists(template_file):
        print(f"ERROR {template_file} not finde")
        return False

    with rasterio.open(template_file) as src:
        left, bottom, right, top = src.bounds
        src_crs = src.crs
        dst_crs = 'EPSG:5070'
        minx, miny, maxx, maxy = transform_bounds(src_crs, dst_crs, left, bottom, right, top)
        bbox = f"{minx},{miny},{maxx},{maxy}"

    url = "https://nassgeodata.gmu.edu/axis2/services/CDLService/GetCDLFile"
    params = {'year': CROP_YEAR, 'bbox': bbox}

    try:
        response = requests.get(url, params=params)
        file_link = re.search(r'(https?://[^"]+\.tif)', response.text)

        if not file_link:
            print("API USDA Failed")
            return False

        download_url = file_link.group(1)
        print(f"Map found: {download_url}")

        with requests.get(download_url, stream=True) as r:
            with open(output_file, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024):
                    f.write(chunk)
        print("OK Map saved in Charts_and_Analysis Folder")
        return True

    except Exception as e:
        print(f"USDA connection failed {e}")
        return False


def visualize_mask(sentinel_path, mask_path):
    print("2/3 USDA Map Matching...")

    with rasterio.open(sentinel_path) as src_sentinel:
        with rasterio.open(mask_path) as src_mask:
            mask_matched = np.empty(src_sentinel.shape, dtype='uint8')

            reproject(
                source=rasterio.band(src_mask, 1),
                destination=mask_matched,
                src_transform=src_mask.transform,
                src_crs=src_mask.crs,
                dst_transform=src_sentinel.transform,
                dst_crs=src_sentinel.crs,
                resampling=Resampling.nearest
            )

    print("3/3 Generating a color map...")


    height, width = mask_matched.shape
    colorful_image = np.zeros((height, width, 3), dtype=np.float32)

    colorful_image[:, :] = [0.8, 0.8, 0.8]


    colorful_image[mask_matched == 1] = [1.0, 0.8, 0.0]

    colorful_image[mask_matched == 5] = [0.0, 0.3, 0.8]

    plt.figure(figsize=(12, 10))
    plt.imshow(colorful_image)

    corn_color = mpatches.Patch(color=(1.0, 0.8, 0.0), label='Kukurydza')
    soy_color = mpatches.Patch(color=(0.0, 0.3, 0.8), label='Soja')
    background_color = mpatches.Patch(color=(0.8, 0.8, 0.8), label='Inne / Tło')

    plt.legend(handles=[corn_color, soy_color, background_color], loc='upper right')
    plt.title(f"Crop Distribution in Iowa ({CROP_YEAR})\n(Dane: USDA CDL)")
    plt.axis('off')
    plt.savefig(RESULTS_DIR)
    print(f"Chart saved to: {RESULTS_DIR}")

    plt.show()


if __name__ == "__main__":
    if os.path.exists(ZIP_FILENAME):
        path_in_zip = None

        with zipfile.ZipFile(ZIP_FILENAME, 'r') as z:
            for file in z.namelist():
                if "IMG_DATA" in file and "B04" in file and ("R10m" in file or "_10m" in file):
                    path_in_zip = file
                    break

        if path_in_zip:
            with zipfile.ZipFile(ZIP_FILENAME, 'r') as z:
                with z.open(path_in_zip) as src, open(SENTINEL_REF, "wb") as dst:
                    shutil.copyfileobj(src, dst)

            if download_mask_from_api(SENTINEL_REF, MASK_FILENAME):
                visualize_mask(SENTINEL_REF, MASK_FILENAME)

            if os.path.exists(SENTINEL_REF):
                os.remove(SENTINEL_REF)
                print(" Temporary reference file removed")
        else:
            print("ERROR Could not find B04 in zip file")
    else:
        print(f"ERROR Could not found zip at {ZIP_FILENAME}")
