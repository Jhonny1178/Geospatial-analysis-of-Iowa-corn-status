# Geospatial Analysis of Iowa Corn Status

This project provides a comprehensive geospatial and statistical analysis of corn crop health in Iowa. It integrates **Sentinel-2 satellite imagery** with **USDA Cropland Data** and **PRISM precipitation data** to analyze the impact of water proximity and rainfall on vegetation condition.

---

## Crop Classification & Vegetation Index
Initial processing involves classifying crops and generating a clean Normalized Difference Vegetation Index (NDVI) to assess overall biomass.

| Crop Distribution (USDA) | Clean NDVI Map |
|:---:|:---:|
| ![Corn Soy Map](./Charts_and_Analysis/corn_soy_map_USA.png) | ![NDVI Clean](./Charts_and_Analysis/Ndvi_map_clean.png) |

---

## Hydrological Proximity Model
Analyzing how the distance to the nearest water sources (rivers/lakes) correlates with crop distribution.

| Water Proximity Model | Corn Fields vs. Water Distance |
|:---:|:---:|
| ![Water Proximity](./Charts_and_Analysis/1_water_proximity_model.png) | ![Corn Distance](./Charts_and_Analysis/2_corn_distance_map.png) |

---

## Focused Crop Analysis
By applying the USDA mask to the satellite data, we can observe the condition (NDVI) and moisture (NDMI) specifically for corn fields, ignoring surrounding vegetation.

<p align="center">
  <img src="./Charts_and_Analysis/corn_ndvi_overlay.png" width="45%" />
  <img src="./Charts_and_Analysis/corn_hydration_ndmi.png" width="45%" />
  <br>
  <em>Corn NDVI Overlay (Health) &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Corn NDMI Map (Moisture)</em>
</p>

---

## Statistical Correlations
These charts analyze how environmental factors (distance to water and rainfall) actually affect the biological status of the plants.

### 1. Distance from Water vs. Plant Status
| Moisture (NDMI) vs. Distance | Health (NDVI) vs. Distance |
|:---:|:---:|
| ![Moisture/Dist](./Charts_and_Analysis/3_moisture_correlation.png) | ![Health/Dist](./Charts_and_Analysis/4_health_correlation.png) |

### 2. Precipitation Impact
Relationship between actual monthly rainfall totals and corn health.

<p align="center">
  <img src="./Charts_and_Analysis/water_vs_health_correlation.png" width="800">
  <br>
  <em>Correlation between cumulative rainfall and NDVI condition.</em>
</p>

---

## Technologies
* **Python 3.13**
* **Rasterio & GDAL** (Geospatial data processing)
* **NumPy** (Numerical analysis)
* **Matplotlib** (Data visualization)
* **Sentinel-2 L2A Data** (Satellite imagery)