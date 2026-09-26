# Maritime Environmental Forensics & Oil Spill Origin Attribution System
**Comprehensive Engineering Report & Benchmark Incident Catalog**  
*Repository:* `https://github.com/Sam-2010/oil_spill_backtracking.git`  
*Branch:* `main` | *Environment:* Python 3.11 / OpenDrift 1.11 / CMEMS / GDAL

---

## Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [End-to-End System Architecture](#2-end-to-end-system-architecture)
3. [Core Engineering Modules](#3-core-engineering-modules)
   - [A. Upstream Physical Backtracking Engine](#a-upstream-physical-backtracking-engine)
   - [B. Downstream AIS & Infrastructure Attribution Engine](#b-downstream-ais--infrastructure-attribution-engine)
   - [C. Forensic Report Generator (Markdown & PDF)](#c-forensic-report-generator-markdown--pdf)
   - [D. Master Pipeline Orchestrator](#d-master-pipeline-orchestrator)
4. [Directory Restructuring & Dynamic Path Architecture](#4-directory-restructuring--dynamic-path-architecture)
5. [Validation & Performance Benchmarks](#5-validation--performance-benchmarks)
6. [CLI Execution Guide](#6-cli-execution-guide)
7. [Searchable Real-World Benchmark Incidents Catalog](#7-searchable-real-world-benchmark-incidents-catalog)
   - [1. Taylor Energy MC-20 (USA)](#1-taylor-energy-mc-20-usa---primary-e2e-benchmark)
   - [2. Main Pass MPOG Pipeline (USA)](#2-main-pass-mpog-pipeline-usa)
   - [3. MV Rubymar (Southern Red Sea)](#3-mv-rubymar-southern-red-sea)
   - [4. Barge Gulfstream (Tobago)](#4-barge-gulfstream-tobago)
   - [5. Vox Maxima & Marine Honour (Singapore)](#5-vox-maxima--marine-honour-singapore)
   - [6. MT Terra Nova (Manila Bay, Philippines)](#6-mt-terra-nova-manila-bay-philippines)
   - [7. MV Sounion (Central Red Sea)](#7-mv-sounion-central-red-sea)

---

## 1. Executive Summary

When marine oil slicks are detected by satellite Synthetic Aperture Radar (SAR) or aerial surveys, identifying the responsible polluter is traditionally complicated by ocean currents, wind drift, transponder gaps, and lack of integration between physical models and vessel tracking streams.

This project delivers an automated, court-admissible, end-to-end forensic attribution platform that connects:
1. **Physical Oceanographic Backtracking:** Solves slick diffusion kinetics ($W_{\text{tail}} > W_{\text{head}}$), estimates release age, and drives reverse-time Lagrangian particle trajectories through ocean hydrodynamic currents, wind, and wave drift.
2. **Maritime AIS Intelligence:** Reconstructs continuous vessel trajectories at 1-minute intervals, tracks transponder blackout gaps, solves Closest Point of Approach (CPA), and ranks suspect vessels via Multi-Criteria Decision Analysis (MCDA).
3. **Marine Infrastructure Correlation:** Assesses proximity to subsea pipelines and platforms to distinguish between illegal vessel discharges, anchor strikes, pipeline ruptures, and platform leaks.
4. **Court-Admissible Reporting:** Automatically compiles the investigation into publication-grade Markdown (`.md`), print-ready HTML (`.html`), and vector PDF (`.pdf`) reports with complete chain-of-custody verification.

---

## 2. End-to-End System Architecture

```
                      +----------------------------------------------------+
                      |    Satellite SAR Oil Slick Footprint (.geojson)    |
                      +----------------------------------------------------+
                                                 │
                                                 ▼
                      +----------------------------------------------------+
                      |            1. Slick Morphology Analyzer            |
                      |   - Computes head/tail width ratio                 |
                      |   - Solves diffusion age (t = W^2 / K)             |
                      +----------------------------------------------------+
                                                 │
                                                 ▼
                      +----------------------------------------------------+
                      |    2. Upstream OpenDrift Reverse-Time Engine       |
                      |   - CMEMS surface currents (uo, vo)                |
                      |   - ECMWF / CMEMS wind vectors (10m)               |
                      |   - Stokes wave drift (VSDX, VSDY)                 |
                      |   - Gaussian dispersion & reverse time stepping    |
                      +----------------------------------------------------+
                                                 │
                                                 ▼
                      +----------------------------------------------------+
                      |              Handover Contract Artifacts           |
                      |   - origin_report.json (Centroid & Time Window)    |
                      |   - trajectory_corridor.geojson (4D Query Bounds)  |
                      +----------------------------------------------------+
                                                 │
                                                 ▼
                      +----------------------------------------------------+
                      |       3. Downstream AIS Attribution Engine         |
                      |   - Ingests regional AIS broadcasts (.csv)         |
                      |   - Great-circle spherical interpolation (1-min)   |
                      |   - Dead-reckoning for transponder dark ships      |
                      |   - Closest Point of Approach (CPA) solver         |
                      |   - MCDA suspicion ranking with decay scoring      |
                      |   - Subsea pipeline & platform spatial indexing    |
                      +----------------------------------------------------+
                                                 │
                                                 ▼
                      +----------------------------------------------------+
                      |          4. Decision Tree & Verdict Resolver       |
                      |   - Resolves: Vessel, Pipeline, Platform, Seep     |
                      |   - Generates culprit_dossier.json                 |
                      |   - Renders interactive Leaflet culprit_map.html   |
                      +----------------------------------------------------+
                                                 │
                                                 ▼
                      +----------------------------------------------------+
                      |      5. Publication-Grade Forensic Report Engine   |
                      |   - forensic_investigation_report.md               |
                      |   - forensic_investigation_report.html             |
                      |   - forensic_investigation_report.pdf (via Edge)   |
                      +----------------------------------------------------+
```

---

## 3. Core Engineering Modules

### A. Upstream Physical Backtracking Engine
Located in `src/`:
* **`morphology.py` (`SlickMorphologyAnalyzer`):**
  Calculates slick geometric properties (length, perimeter, orientation, centroid). Compares the width at the leading head ($W_{\text{head}}$) against the trailing tail ($W_{\text{tail}}$). By applying the turbulent diffusion equation $W(t) \approx \sqrt{K \cdot t}$, it determines whether the spill was instantaneous or continuously drifting, providing the temporal simulation window.
* **`backtrack_engine.py` (`OilSpillBacktracker`):**
  Wraps the OpenDrift Lagrangian simulation framework in reverse-time mode (`time_step = -900s`). Ingests Copernicus Marine Service (CMEMS) surface current velocities, wind forcing, and wave Stokes drift. Simulates hundreds to thousands of particles backward from the detection time.
* **`output_formatter.py` (`TrajectoryOutputFormatter`):**
  Calculates origin centroids, 95% confidence intervals, and formats the trajectory history into a standardized GeoJSON corridor (`trajectory_corridor.geojson`) and origin summary (`origin_report.json`).

### B. Downstream AIS & Infrastructure Attribution Engine
Located in `src/attribution/`:
* **`preflight.py`:**
  Validates spatial bounding boxes and temporal limits to ensure the AIS dataset covers the required physical backtrack window before execution.
* **`data_loader.py`:**
  Parses raw NOAA Marine Cadastre and global AIS logs. Filters sentinel values (e.g., speed $> 45\text{ kn}$, invalid coordinates), filters non-vessel beacons (buoys, base stations), and indexes regional BOEM/BSEE pipeline and platform GeoJSON layers.
* **`trajectory.py`:**
  Resamples discrete vessel broadcasts to a continuous 1-minute path using spherical great-circle trigonometry (Haversine distance and initial bearing), deriving kinematic speed and course anomalies.
* **`dark_ship.py`:**
  Detects deliberate AIS transponder blackouts ($>30\text{ min}$ gaps) in the vicinity of the incident and performs kinematic dead-reckoning to compute virtual candidate positions.
* **`cpa.py`:**
  Calculates Closest Point of Approach (CPA) between vessel trajectories and the backtrack corridor, computing minimum spatial distance ($\text{CPA}_{\text{dist}}$), time delta ($\Delta t$), and trajectory alignment vector angles.
* **`scoring.py`:**
  Computes Multi-Criteria Decision Analysis (MCDA) suspicion scores (0–100%) using distance and time exponential decay functions:
  $$\text{Score} = w_{\text{prox}} S_{\text{prox}} + w_{\text{time}} S_{\text{time}} + w_{\text{type}} S_{\text{type}} + w_{\text{align}} S_{\text{align}} + w_{\text{gap}} S_{\text{gap}}$$
* **`decision_engine.py`:**
  Applies hierarchical evidentiary thresholds:
  1. *Subsea Platform Leak:* Origin within 500m of active platform and no vessel loitering.
  2. *Pipeline Anchor Strike:* Vessel loitered/anchored within 500m of a pipeline segment prior to release.
  3. *Pipeline Rupture:* Origin intersects active pipeline corridor with zero vessel traffic.
  4. *Illegal Vessel Discharge:* High-confidence vessel candidate (CPA $< 1.5\text{ nm}$, time aligned).
  5. *Natural Seep / Unresolved:* No infrastructure or vessel matches criteria.

### C. Forensic Report Generator (Markdown & PDF)
Located in `src/reporting/report_generator.py` and `generate_report.py`:
* Ingests upstream backtrack outputs and downstream attribution dossiers.
* Synthesizes 9 forensic sections:
  1. Incident Executive Summary & Final Verdict
  2. Spill Footprint & Observation Parameters
  3. Reverse Lagrangian Drift Reconstruction (hourly trajectory table)
  4. Maritime Traffic Analysis & Vessel Leaderboard (full candidate ranking)
  5. Top Suspect Forensic Profiles (deep-dive dossiers)
  6. Subsea Infrastructure Assessment (proximity audit)
  7. Multi-Criteria Scoring Formulation & Weights Table
  8. Chain of Custody & Environment
  9. Sign-off & Forensic Disclaimer
* Compiles `.md`, `.html` (print-styled), and `.pdf` (via headless Microsoft Edge).

### D. Master Pipeline Orchestrator
Located in `run_combined_forensics.py`:
* Unified CLI coordinating the entire pipeline end-to-end:
  ```bash
  python run_combined_forensics.py --incident taylor_energy
  ```
* Performs automated handoff verification, error handling, and generates complete outputs in under 20 seconds.

---

## 4. Directory Restructuring & Dynamic Path Architecture

To ensure professional code presentation, maintainability, and clean GitHub repository structure, the repository was reorganized:

```
oil_spill_backtracking/
├── README.md                          # Primary project documentation
├── config.yaml                        # Unified configuration & MCDA weights
├── .env.credentials.example           # CMEMS credentials template
├── .gitignore                         # Configured for clean git tracking
│
├── run_combined_forensics.py          # Master CLI: Backtrack + Attribution + Report
├── run_backtrack.py                   # Standalone CLI: Upstream Backtracking
├── run_attribution.py                 # Standalone CLI: Downstream AIS Attribution
├── generate_report.py                 # Standalone CLI: Forensic Report Generator
│
├── src/                               # Core engine source code
│   ├── morphology.py, backtrack_engine.py, output_formatter.py, data_fetcher.py
│   ├── attribution/                   # 8 attribution modules
│   └── reporting/                     # Report generation engine
│
├── scripts/                           # Data acquisition & utilities
│   ├── downloaders/                   # Resilient NOAA AIS & CMEMS downloaders
│   ├── extractors/                    # Regional AIS extraction tools
│   └── generate_demo_forcing.py       # Synthetic test data generator
│
├── tests/                             # Test suites & benchmark scripts
│   ├── run_all_benchmarks.py          # 7-incident automated benchmark suite
│   ├── test_downstream_ais.py         # Attribution pipeline test
│   └── test_phase[2-4].py             # Phase validation tests
│
├── docs/                              # Project documentation & handover records
│   ├── COMPREHENSIVE_PROJECT_REPORT.md# This document
│   └── HANDOVER_REPORT.md             # System architecture handover report
│
├── data/                              # Environmental & maritime datasets
│   ├── ais/                           # Cleaned benchmark AIS broadcasts (.csv)
│   ├── currents/, wind/, waves/       # CMEMS NetCDF files (.nc)
│   ├── infrastructure/                # Pipeline & platform GeoJSON layers
│   └── sar/                           # Sentinel-1 SAR imagery
│
├── inputs/                            # Satellite slick detection footprints (.geojson)
└── outputs/                           # Simulation results & generated reports
    └── taylor_energy/
        ├── origin_report.json
        ├── trajectory_corridor.geojson
        ├── trajectory_map.html
        ├── attribution/
        │   ├── culprit_dossier.json
        │   ├── culprit_map.html
        │   └── culprit_visual.geojson
        ├── forensic_investigation_report.md
        ├── forensic_investigation_report.html
        └── forensic_investigation_report.pdf
```

### Dynamic Path Resolution
All moved scripts in `scripts/` and `tests/` were injected with dynamic project root resolvers:
```python
import os
import sys
from pathlib import Path
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))  # or '..', '..'
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
os.chdir(_PROJECT_ROOT)
```
This guarantees that relative paths (`data/...`, `inputs/...`, `outputs/...`) and module imports (`from src...`) resolve consistently regardless of the user's working directory.

---

## 5. Validation & Performance Benchmarks

The system was validated against the **Taylor Energy MC-20** real-world incident:

| Metric | Result | Benchmark Standard |
|:---|:---:|:---:|
| **Ground Truth Latitude** | 28.93700° N | Verified Saratoga Platform coordinates |
| **Ground Truth Longitude** | -88.97100° W | Verified Saratoga Platform coordinates |
| **Solved Backtrack Centroid** | 28.93537° N, -88.96780° W | Calculated origin |
| **Origin Distance Error** | **~310 meters** | Outstanding ($< 1.0\text{ km}$ threshold) |
| **Backtrack Simulation Time** | **12.6 seconds** | 500 Lagrangian particles, 6-hr backtrack |
| **AIS Attribution Time** | **2.3 seconds** | 861 pings across 15 candidate vessels |
| **Report Generation Time** | **~3.5 seconds** | Markdown + HTML + Headless Edge PDF |
| **Total Pipeline Runtime** | **~18.5 seconds** | End-to-end execution |
| **False Accusation Rate** | **0%** | Accurately distinguished infrastructure leak |

---

## 6. CLI Execution Guide

### Option 1: Master Combined Pipeline (Recommended)
Runs physical backtracking, AIS attribution, and compiles PDF/MD reports:
```bash
python run_combined_forensics.py --incident taylor_energy
```

### Option 2: Standalone Upstream Backtracking
```bash
python run_backtrack.py --input inputs/taylor_energy_mc20_detection.geojson --hours 6.0 --particles 500 --output-dir outputs/taylor_energy --head-only
```

### Option 3: Standalone Downstream Attribution
```bash
python run_attribution.py \
  --origin outputs/taylor_energy/origin_report.json \
  --corridor outputs/taylor_energy/trajectory_corridor.geojson \
  --ais data/ais/taylor_energy_mc20_noaa_ais_2023_11_17.csv \
  --config config.yaml \
  --pipes data/infrastructure/regional_pipelines.geojson \
  --plats data/infrastructure/regional_platforms.geojson \
  --outdir outputs/taylor_energy/attribution
```

### Option 4: Standalone Forensic Report Generator
```bash
python generate_report.py --incident taylor_energy
```

### Option 5: Run Full Benchmark Suite (All 7 Incidents)
```bash
python tests/run_all_benchmarks.py
```

---

## 7. Searchable Real-World Benchmark Incidents Catalog

Use the following catalog to verify, search, and research the 7 historical maritime incidents configured in the platform:

---

### 1. Taylor Energy MC-20 (USA) - *Primary E2E Benchmark*
* **Official Name:** Taylor Energy Mississippi Canyon Block 20 Oil Discharge
* **Observation Date:** November 17, 2023 *(Spill active since September 2004)*
* **Location:** Mississippi Canyon Block 20, Gulf of Mexico (~10 miles off Louisiana coast)
* **Ground Truth Coordinates:** `28.93700° N, -88.97100° W` (Saratoga Platform wellhead cluster)
* **Incident Summary:** In September 2004, Hurricane Ivan triggered an underwater mudslide that toppled the Taylor Energy Saratoga production platform, burying 28 active wellheads under 100 feet of mud and creating the longest-running continuous oil spill in US history.
* **Search Keywords:** `"Taylor Energy" "MC-20" "Mississippi Canyon 20" "Hurricane Ivan mudslide" "Couvillion Group containment"`

---

### 2. Main Pass MPOG Pipeline (USA)
* **Official Name:** Main Pass Oil Gathering (MPOG) Pipeline Rupture
* **Observation Date:** November 16, 2023
* **Location:** East of Venice, Plaquemines Parish, Louisiana, Gulf of Mexico
* **Ground Truth Coordinates:** `29.29717° N, -88.71800° W` (Collet mechanical connector break)
* **Incident Summary:** A 16-inch underwater crude oil pipeline operated by Third Coast Midstream / MPOG ruptured in 40 feet of water, releasing an estimated 1.1 million gallons (~26,000 barrels) of crude oil into the Gulf of Mexico.
* **Search Keywords:** `"Main Pass Oil Gathering" "MPOG pipeline leak" "Third Coast Midstream November 2023" "Plaquemines oil spill"`

---

### 3. MV Rubymar (Southern Red Sea)
* **Official Name:** MV Rubymar Sinking & Fertilizer/Bunker Spill
* **Observation Date:** February 18 – March 2, 2024
* **Location:** Southern Red Sea / Bab el-Mandeb Strait, off Yemen
* **Ground Truth Coordinates:** `13.34400° N, 43.14500° E` (Missile strike & drift start location)
* **Incident Summary:** The UK-owned bulk carrier *MV Rubymar* was struck by Houthi anti-ship ballistic missiles while carrying 21,000 metric tons of ammonium phosphate fertilizer and heavy bunker fuel. The vessel drifted uncontrolled for 12 days leaving an 18-mile oil slick before sinking on March 2, 2024.
* **Search Keywords:** `"MV Rubymar" "Rubymar sinking Red Sea" "Houthi missile Rubymar" "Bab el-Mandeb fertilizer slick"`

---

### 4. Barge Gulfstream (Tobago)
* **Official Name:** Barge Gulfstream Capsizing & Mystery Spill
* **Observation Date:** February 7, 2024
* **Location:** Cove Eco-Industrial Park Reef, southwest coast of Tobago
* **Ground Truth Coordinates:** `11.14400° N, -60.77800° W` (Cove Reef capsizing site)
* **Incident Summary:** An uncrewed barge, later identified as the *Gulfstream*, capsized on a shallow coral reef off Tobago. It had been towed by the tug *Solo Creed* from Panama before breaking free. The spill released thousands of barrels of heavy fuel oil across the southern Caribbean Sea.
* **Search Keywords:** `"Barge Gulfstream" "Tobago oil spill February 2024" "Solo Creed tug" "Cove reef Tobago spill"`

---

### 5. Vox Maxima & Marine Honour (Singapore)
* **Official Name:** Pasir Panjang Port Allision & Fuel Oil Spill
* **Observation Date:** June 14, 2024
* **Location:** Pasir Panjang Terminal Berth 36, Singapore Strait
* **Ground Truth Coordinates:** `1.27200° N, 103.77400° E` (Berth allision site)
* **Incident Summary:** The Netherlands-flagged trailing suction hopper dredger *Vox Maxima* suffered an abrupt loss of steering and engine control, striking the stationary bunker tanker *Marine Honour*. A ruptured cargo tank released 400 metric tons of low-sulfur fuel oil, impacting Sentosa Island and Singapore's coastline.
* **Search Keywords:** `"Vox Maxima" "Marine Honour" "Pasir Panjang oil spill" "Singapore oil spill June 2024"`

---

### 6. MT Terra Nova (Manila Bay, Philippines)
* **Official Name:** MT Terra Nova Capsizing & Industrial Fuel Oil Spill
* **Observation Date:** July 25, 2024
* **Location:** Off Limay, Bataan, Manila Bay, Philippines
* **Ground Truth Coordinates:** `14.41700° N, 120.60000° E` (Sunken tanker wreck site)
* **Incident Summary:** The Philippine-flagged industrial fuel tanker *MT Terra Nova* was carrying 1.4 million liters (370,000 gallons) of industrial fuel oil when it capsized and sank in rough waters driven by Typhoon Gaemi (Carina), triggering international salvage operations.
* **Search Keywords:** `"MT Terra Nova" "Manila Bay oil spill July 2024" "Limay Bataan tanker sinking" "Typhoon Gaemi Terra Nova"`

---

### 7. MV Sounion (Central Red Sea)
* **Official Name:** MV Sounion Attack & Anchor Fire Incident
* **Observation Date:** August 21, 2024
* **Location:** Central Red Sea (~77 nautical miles west of Al Hudaydah, Yemen)
* **Ground Truth Coordinates:** `15.03500° N, 41.88500° E` (Anchored burning site)
* **Incident Summary:** The Greek-flagged crude oil tanker *MV Sounion*, carrying 150,000 metric tons (approx. 1 million barrels) of crude oil, was attacked and set ablaze by Houthi forces. The crew was evacuated by European naval forces (Operation ASPIDES) while salvage teams fought fires to avert a major environmental disaster.
* **Search Keywords:** `"MV Sounion" "Sounion tanker fire Red Sea" "Operation Aspides Sounion" "Houthi attack Sounion"`

---

## 8. Summary of Output Deliverables

After running the pipeline, the following files are produced under `outputs/<incident>/`:

| Artifact | Format | Purpose |
|:---|:---:|:---|
| `origin_report.json` | JSON | Machine-readable origin coordinates, confidence interval, and age |
| `trajectory_corridor.geojson` | GeoJSON | 4D polygon envelope used to query AIS transponder records |
| `trajectory_map.html` | HTML | Interactive Leaflet visualization of physical backtrack particles |
| `attribution/culprit_dossier.json` | JSON | Comprehensive legal audit trail with all vessel suspicion scores |
| `attribution/culprit_map.html` | HTML | Interactive map showing candidate vessel tracks and infrastructure |
| `attribution/culprit_visual.geojson` | GeoJSON | GIS vector layer of top suspect vessel tracks and CPA markers |
| `forensic_investigation_report.md` | Markdown | Comprehensive 9-section technical report |
| `forensic_investigation_report.pdf` | PDF | Court-admissible, publication-styled vector PDF report |
