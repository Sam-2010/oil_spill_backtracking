# Marine Oil Spill Backtracking & Origin Identification Engine

An open-source, reverse-Lagrangian hydrodynamic simulation engine built on **OpenDrift** and **Copernicus Marine Service (CMEMS)**. Given a satellite-detected oil slick polygon or GPS coordinate, the engine backtracks ocean currents, winds, and Stokes wave drift in reverse time to pinpoint the **probable time window and geographic area of origin** for downstream AIS vessel matching.

---

## Key Features

1. **Slick Morphology Analyzer (`src/morphology.py`):**
   * Computes length, principal travel axis, and width profile ($W_{head}$ vs $W_{tail}$).
   * Estimates elapsed spill age using Fickian turbulent diffusion: $\Delta T \approx \frac{W_{tail}^2 - W_{head}^2}{8 K_h}$.
   * Fallback handler for circular point/radius inputs with unconstrained horizon tracking.
2. **Reverse Lagrangian Engine (`src/backtrack_engine.py`):**
   * Integrates negative time steps with 3% wind leeway and stochastic sub-grid diffusion ($K_h = 10\text{ m}^2/\text{s}$).
   * Powered by archived Copernicus Marine hourly surface currents (`uo`, `vo`), wave Stokes drift (`VSDX`, `VSDY`), and 10m wind fields.
3. **Adaptive Origin Solver & Output Formatter (`src/output_formatter.py`):**
   * **Coastal Stranding Convergence:** Detects when reverse particles converge onto shorelines or reefs (grounded vessels / reef collisions), reducing error by $>80\%$.
   * **2D Spatial Density Peak Solver:** Eliminates arithmetic mean offsets when currents bifurcate around islands.
   * Generates standardized **GeoJSON query corridor**, structured **JSON metrics report**, and standalone **interactive Leaflet satellite HTML maps**.

---

## Tested Benchmark Incidents (2024)

| Incident | Location | Date | Detection Sensor | Origin Error | Key Feature |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **MV *Rubymar*** | Southern Red Sea | March 1, 2024 | Sentinel-1 SAR | **$2.8\text{ km}$ ($1.5\text{ nm}$)** | Open-sea strait channel drift |
| **Barge *Gulfstream*** | Tobago, Caribbean | Feb 8, 2024 | Sentinel-1 SAR | **$7.6\text{ km}$ ($4.1\text{ nm}$)** | Reef grounding convergence |
| ***Vox Maxima*** | Singapore Strait | June 15, 2024 | Sentinel-1 SAR | **$7.9\text{ km}$ ($4.3\text{ nm}$)** | Tidal port allision & Sentosa beach stranding |
| **MT *Terra Nova*** | Manila Bay | July 26, 2024 | Sentinel-1 SAR | **$6.6\text{ km}$ ($3.5\text{ nm}$)** | Enclosed bay / Typhoon winds |
| **MV *Sounion*** | Central Red Sea | August 23, 2024 | Sentinel-1 SAR | **$13.9\text{ km}$ ($7.5\text{ nm}$)** | Burning tanker open-sea plume |

---

## Quick Start Guide

### 1. Installation (Using Conda or Miniforge)
```bash
# Clone or extract the repository
git clone https://github.com/your-username/OpenDrift2.git
cd OpenDrift2

# Create isolated Python 3.11 environment
conda create -n opendrift_env python=3.11 opendrift netcdf4 shapely geopandas folium scipy -c conda-forge -y
conda activate opendrift_env
```

### 2. Running Simulations

#### Run MV *Rubymar* (Red Sea Benchmark):
```bash
python run_backtrack.py --input inputs/rubymar_detection.geojson --currents data/currents/cmems_currents_rubymar.nc --wind data/wind/cmems_wind_rubymar.nc --waves data/waves/cmems_waves_rubymar.nc --hours 24 --particles 500
```

#### Run Singapore Strait Bunker Spill:
```bash
python run_backtrack.py --input inputs/singapore_detection.geojson --currents data/currents/cmems_currents_singapore.nc --wind data/wind/cmems_wind_singapore.nc --waves data/waves/cmems_waves_singapore.nc --particles 500
```

#### Run Tobago Mystery Barge Grounding:
```bash
python run_backtrack.py --input inputs/tobago_detection.geojson --currents data/currents/cmems_currents_tobago.nc --wind data/wind/cmems_wind_tobago.nc --waves data/waves/cmems_waves_tobago.nc --particles 500
```

#### Run Circular Fallback Point Mode:
```bash
python run_backtrack.py --input inputs/fallback_point.json --currents data/currents/cmems_currents_rubymar.nc --wind data/wind/cmems_wind_rubymar.nc --waves data/waves/cmems_waves_rubymar.nc --hours 24 --particles 500
```

---

## Generated Outputs (`outputs/`)

* **`outputs/trajectory_map.html`:** Open in any web browser to view the interactive high-resolution satellite map, slick footprint (red), origin zone (green), and hourly backtrack corridor (blue).
* **`outputs/origin_report.json`:** JSON summary report containing calculated slick age, time window $[T_{start}, T_{end}]$ UTC, primary centroid coordinates, and confidence levels.
* **`outputs/trajectory_corridor.geojson`:** Standardized GeoJSON FeatureCollection ready for direct ingestion by downstream AIS vessel attribution algorithms.
