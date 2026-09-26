# Maritime Oil Spill Backtracking & AIS Attribution Forensics Engine

An end-to-end, dual-engine maritime environmental forensics pipeline that takes satellite-detected oil slicks (SAR radar or optical imagery), reconstructs their reverse-time physical drift through ocean currents, winds, and waves, calculates their origin time window and bounding footprint, and cross-references historical Automatic Identification System (AIS) vessel traffic and offshore infrastructure (pipelines and platforms) to identify the responsible culprit.

---

## 1. System Architecture

The pipeline consists of two tightly coupled engines:

```
[Satellite SAR / Optical Detection]
               │
               ▼ (GeoJSON polygon or GPS coordinates)
┌──────────────────────────────────────────────────────────┐
│   UPSTREAM: Reverse-Lagrangian Hydrodynamic Backtrack    │
│  - Slick Morphology Analyzer (Fickian diffusion age)     │
│  - Copernicus Marine (CMEMS) Surface Currents & Waves    │
│  - OpenDrift 1.14 Reverse Particle Simulation (Leeway/Kh)│
│  - 2D Density Peak & Shoreline Grounding Solver          │
└──────────────────────────────────────────────────────────┘
               │
               ▼ Standardized Spatio-Temporal Corridor (`trajectory_corridor.geojson`)
┌──────────────────────────────────────────────────────────┐
│ DOWNSTREAM: AIS Vessel & Infrastructure Forensic Engine  │
│  - Pre-flight Temporal/Spatial Spatio-Temporal Validation│
│  - STRtree Spatial Indexing (Pipelines & Platforms)      │
│  - AIS Trajectory Reconstruction & Dark Ship Projection  │
│  - Closest Point of Approach (CPA) Minimization          │
│  - Multi-Criteria Decision Analysis (MCDA) Scoring       │
│  - Multi-Source Verdict Hierarchy & Legal Dossier Export │
└──────────────────────────────────────────────────────────┘
               │
               ▼
[Interactive HTML Maps, Culprit Dossiers, GeoJSON Visuals]
```

### Upstream: Reverse-Lagrangian Backtracking (`src/`)
1. **Slick Morphology Analyzer (`src/morphology.py`):**
   * Computes length, principal travel axis, and width profile ($W_{head}$ vs $W_{tail}$).
   * Estimates elapsed spill age using Fickian turbulent diffusion: $\Delta T \approx \frac{W_{tail}^2 - W_{head}^2}{8 K_h}$.
   * Fallback handler for circular point/radius inputs with unconstrained horizon tracking.
2. **Reverse Lagrangian Engine (`src/backtrack_engine.py`):**
   * Integrates negative time steps with 3% wind leeway and stochastic sub-grid diffusion ($K_h = 10\text{ m}^2/\text{s}$).
   * Powered by Copernicus Marine hourly surface currents (`uo`, `vo`), wave Stokes drift (`VSDX`, `VSDY`), and 10m wind fields.
3. **Adaptive Origin Solver & Output Formatter (`src/output_formatter.py`):**
   * **Coastal Stranding Convergence:** Detects when reverse particles converge onto shorelines or reefs (grounded vessels / reef collisions), reducing error by $>80\%$.
   * **2D Spatial Density Peak Solver:** Eliminates arithmetic mean offsets when currents bifurcate around islands or underwater features.
   * Generates standardized **GeoJSON query corridor**, structured **JSON metrics report**, and standalone **interactive Leaflet satellite HTML maps**.

### Downstream: AIS & Infrastructure Attribution Engine (`src/attribution/`)
1. **Pre-flight Validation (`src/attribution/preflight.py`):**
   * Validates spatial and temporal bounding boxes between the upstream query corridor and raw AIS broadcast feeds.
2. **Data Ingestion & Spatial Indexing (`src/attribution/data_loader.py`):**
   * Sanitizes AIS speeds (sentinel values 102.3 kt replaced with NaN), parses timestamps, and builds GEOS `STRtree` spatial indices for pipelines and platforms.
3. **Trajectory Interpolation & Loitering Analysis (`src/attribution/trajectory.py`):**
   * Resamples vessel tracks at 1-minute intervals using great-circle interpolation and angular bearing unrolling.
   * Calculates rate-of-turn (ROT) and loitering scores in reverse-time release envelopes.
4. **Dark-Ship Dead Reckoning (`src/attribution/dark_ship.py`):**
   * Detects AIS transponder shut-offs (gaps $>30$ minutes) inside the corridor and computes parallel dead-reckoning envelopes.
5. **Closest Point of Approach (CPA) Engine (`src/attribution/cpa.py`):**
   * Computes exact spatio-temporal distance $d_{CPA}$ and timestamp offset $\Delta t_{CPA}$ to the reconstructed spill origin, plus alignment against the slick's major axis.
6. **MCDA Scoring Engine (`src/attribution/scoring.py`):**
   * Multi-criteria evaluation: Spatial proximity ($W_s$), Temporal alignment ($W_t$), Vessel type hazard ($W_v$), Maneuvering/Loitering ($W_m$), Dark-ship bonus ($W_d$), Infrastructure proximity ($W_i$).
7. **Verdict Hierarchy & Dossier Generation (`src/attribution/decision_engine.py`):**
   * Categorizes incidents into:
     - `VESSEL_DISCHARGE`
     - `INFRASTRUCTURE_FAILURE`
     - `SUSPECTED_ANCHOR_STRIKE_ON_PIPELINE`
     - `UNRESOLVED_SEEP_OR_UNRECORDED_SOURCE`
   * Exports an auditable JSON dossier and interactive Folium forensic map.

---

## 2. Tested Scientific Benchmarks & Ground Truth

| Incident | Location | Date | Detection Sensor | Origin Error | Attribution Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Taylor Energy MC-20** | Gulf of Mexico | Nov 17, 2023 | Sentinel-1 SAR | **$310\text{ m}$ ($0.17\text{ nm}$)** | `INFRASTRUCTURE_FAILURE` / Persistent Seep (Cleared 100% of passing vessels) |
| **MV *Rubymar*** | Southern Red Sea | March 1, 2024 | Sentinel-1 SAR | **$2.8\text{ km}$ ($1.5\text{ nm}$)** | Sinking bulk carrier trailing fuel oil plume |
| **Barge *Gulfstream*** | Tobago, Caribbean | Feb 8, 2024 | Sentinel-1 SAR | **$7.6\text{ km}$ ($4.1\text{ nm}$)** | Reef grounding convergence / Dark unflagged barge |
| ***Vox Maxima*** | Singapore Strait | June 15, 2024 | Sentinel-1 SAR | **$7.9\text{ km}$ ($4.3\text{ nm}$)** | Bunker spill from dredger allision with *Marine Honour* |
| **MT *Terra Nova*** | Manila Bay | July 26, 2024 | Sentinel-1 SAR | **$6.6\text{ km}$ ($3.5\text{ nm}$)** | Sunken product tanker under Typhoon Gaemi conditions |
| **MV *Sounion*** | Central Red Sea | August 23, 2024 | Sentinel-1 SAR | **$13.9\text{ km}$ ($7.5\text{ nm}$)** | Burning crude tanker drifting off Hodeidah |

### Highlight: Taylor Energy MC-20 Ground Truth Validation
* **Predicted Backtrack Origin:** Lat `28.93537°N`, Lon `-88.96780°W`
* **Official BSEE / NOAA Wellhead Site:** Lat `28.93653°N`, Lon `-88.97069°W`
* **Absolute Geodetic Error:** **$310.0\text{ meters}$ ($0.167\text{ nautical miles}$)**
* **Downstream Forensic Evaluation:** Evaluated 1,328 vessel records (including OSVs *HOS WARSELLER*, *MS CLAUDIA*, *MR CHARLIE*). Zero commercial vessels were falsely flagged, cleanly passing the negative control test.

---

## 3. Repository Structure

```
.
├── config.yaml                     # Unified configuration (paths, weights, thresholds)
├── run_combined_forensics.py       # Master CLI: runs Upstream + Downstream in one command
├── run_backtrack.py                # Standalone Upstream Backtracking CLI
├── run_attribution.py              # Standalone Downstream AIS Attribution CLI
├── src/
│   ├── morphology.py               # Satellite slick geometry & diffusion age
│   ├── backtrack_engine.py         # OpenDrift reverse-time Lagrangian engine
│   ├── output_formatter.py         # Origin solver & GeoJSON corridor generator
│   └── attribution/                # Downstream AIS & Infrastructure Engine
│       ├── models.py               # Typed dataclasses (Corridors, Vessels, CPAs, Dossiers)
│       ├── preflight.py            # Spatial and temporal boundary validator
│       ├── data_loader.py          # AIS ingestion & GeoJSON infrastructure indexing
│       ├── trajectory.py           # Spherical interpolation & loitering metrics
│       ├── dark_ship.py            # AIS gap dead-reckoning extrapolation
│       ├── cpa.py                  # Closest Point of Approach solver
│       ├── scoring.py              # MCDA ranking engine with distance/time decay
│       └── decision_engine.py      # Forensic verdict resolver, dossier & HTML generator
├── data/
│   ├── ais/                        # Cleaned benchmark AIS broadcasts (.csv)
│   ├── currents/                   # Copernicus Marine hydrodynamic netCDF files (.nc)
│   ├── wind/                       # Copernicus Marine wind vector netCDF files (.nc)
│   ├── waves/                      # Copernicus Marine Stokes drift netCDF files (.nc)
│   └── infrastructure/             # Regional marine infrastructure
│       ├── regional_pipelines.geojson
│       └── regional_platforms.geojson
├── inputs/                         # Satellite slick detection footprints (.geojson / .json)
└── outputs/                        # Forensic dossiers, HTML maps, and query corridors
```

---

## 4. Installation & Environment Setup

### 1. Prerequisites
* **Operating System:** Linux, macOS, or Windows x64.
* **Environment Manager:** Conda or Mamba (recommended for C-extension geospatial libraries).

### 2. Conda Environment
```bash
# Clone the repository
git clone https://github.com/Sam-2010/oil_spill_backtracking.git
cd oil_spill_backtracking

# Create and activate the environment
conda create -n opendrift_env python=3.11 -c conda-forge -y
conda activate opendrift_env

# Install core dependencies from conda-forge
conda install -c conda-forge opendrift netcdf4 shapely geopandas folium scipy pyproj pyyaml -y
```

---

## 5. Usage & CLI Commands

### Option A: Run the Unified End-to-End Forensics Pipeline (Recommended)
Execute both upstream backtracking and downstream attribution in a single call:

```bash
# Run the Taylor Energy benchmark
python run_combined_forensics.py --incident taylor_energy

# Run with custom parameters
python run_combined_forensics.py \
  --input inputs/taylor_energy_detection.geojson \
  --currents data/currents/cmems_currents_taylor.nc \
  --wind data/wind/cmems_wind_taylor.nc \
  --waves data/waves/cmems_waves_taylor.nc \
  --ais data/ais/taylor_energy_mc20_noaa_ais_2023_11_17.csv \
  --pipelines data/infrastructure/regional_pipelines.geojson \
  --platforms data/infrastructure/regional_platforms.geojson \
  --output outputs/my_investigation \
  --particles 500
```

### Option B: Standalone Upstream Backtracking
If you only need to backtrack the slick to find the origin corridor:

```bash
python run_backtrack.py \
  --input inputs/rubymar_detection.geojson \
  --currents data/currents/cmems_currents_rubymar.nc \
  --wind data/wind/cmems_wind_rubymar.nc \
  --waves data/waves/cmems_waves_rubymar.nc \
  --hours 24 \
  --particles 500
```

### Option C: Standalone Downstream AIS Attribution
If you already have a `trajectory_corridor.geojson` from upstream:

```bash
python run_attribution.py \
  --corridor outputs/taylor_energy/trajectory_corridor.geojson \
  --ais data/ais/taylor_energy_mc20_noaa_ais_2023_11_17.csv \
  --pipelines data/infrastructure/regional_pipelines.geojson \
  --platforms data/infrastructure/regional_platforms.geojson \
  --output-dir outputs/taylor_energy/attribution
```

---

## 6. Generated Forensic Outputs

Every investigation produces an auditable evidence package:

1. **`outputs/.../origin_report.json`**: Physical backtracking summary, containing estimated spill release time $[T_{start}, T_{end}]$ UTC, coordinates, and dispersion variance.
2. **`outputs/.../trajectory_corridor.geojson`**: Standardized GeoJSON spatio-temporal query polygon encompassing the reverse particle drift history.
3. **`outputs/.../trajectory_map.html`**: Interactive satellite map showing slick polygon, particle trajectories, and resolved origin zone.
4. **`outputs/.../attribution/culprit_dossier.json`**: Comprehensive forensic breakdown of all candidates, MCDA scores, CPAs, loitering analysis, dark-ship gaps, and final verdict.
5. **`outputs/.../attribution/culprit_map.html`**: Interactive forensic visualization rendering vessel tracks, AIS points, infrastructure layers, CPA lines, and confidence overlays.
6. **`outputs/.../attribution/culprit_visual.geojson`**: Standalone GeoJSON of vessel trajectories and infrastructure for GIS tools (QGIS, ArcGIS).

---

## 7. License & Citations
* OpenDrift framework: [OpenDrift on GitHub](https://github.com/OpenDrift/opendrift)
* Oceanographic Data: [Copernicus Marine Service (CMEMS)](https://marine.copernicus.eu/)
* AIS Data: [NOAA Marine Cadastre](https://marinecadastre.gov/ais/)
