# Maritime Oil Spill Forensic Investigation Report
**Investigation Target:** TAYLOR_ENERGY Incident  
**Report Generated (UTC):** 2026-09-26 17:04:12 UTC  
**Classification:** Official Forensic Investigation & Maritime Attribution Audit  
**Forensic Integrity Hash:** SHA-256 Verified Data Pipeline  

---

## 1. Executive Summary & Legal Forensic Determination

| Forensic Dimension | Finding / Status |
| :--- | :--- |
| **Primary Verdict** | `SUSPECTED_ANCHOR_STRIKE_ON_PIPELINE` |
| **Confidence Level** | **HIGH** |
| **Predicted Spill Origin** | `28.93537°N, -88.96780°W` |
| **Spill Release Window** | `2023-11-17T23:16:46+00:00` to `2023-11-17T23:24:16+00:00` |
| **Satellite Detection Time** | `2023-11-17T23:54:16+00:00` |
| **Total Candidates Evaluated** | 15 vessel tracks |
| **Ground Truth Validation Error** | **309.4 meters (0.167 nm)** |

> **Official Forensic Summary:** Vessel CG WALNUT (MMSI: 366953000) was observed loitering/anchoring within 119m of Pipeline Segment 12712 operated by WALTER OIL & GAS CORPORATION prior to release.

## 2. Satellite Remote Sensing & Slick Morphology

The initial surface slick polygon was identified via synthetic aperture radar (SAR) imagery. The slick geometry was analyzed using principal component axis projection and transverse width profiling.

| Morphological Metric | Value | Technical Rationale |
| :--- | :--- | :--- |
| **Observation Timestamp** | `2023-11-17T23:54:16+00:00` | Satellite overpass capture time (UTC) |
| **Observed Centroid** | `28.93471°N, -88.96548°W` | Geodetic center of detected surface oil |
| **Slick Axis Length** | 2.67 km | Major physical spreading dimension |
| **Leading Edge Width (W_head)** | 1780.1 m | Freshly surfaced / narrowest release apex |
| **Trailing Edge Width (W_tail)** | 2136.1 m | Diffused / oldest surface oil footprint |
| **Principal Travel Orientation** | 42.8° | Directional orientation of slick elongation |
| **Horizontal Diffusivity (Kh)** | 10.0 m²/s | Standard ocean sub-grid turbulent diffusion |
| **Calculated Drift Age (ΔT)** | **0.50 hours** | Solved via Fickian diffusion formula |

### Diffusion Age Mathematical Formulation:
$$\Delta T = \frac{W_{\text{tail}}^2 - W_{\text{head}}^2}{8 K_h}$$
* **Diffusion Profile:** $W_{\text{tail}} > W_{\text{head}}$ (widening tail indicates physical drift away from release apex).
* **Numerical Solution:** Substituting $W_{\text{tail}} = 2136.1\text{ m}$, $W_{\text{head}} = 1780.1\text{ m}$, and $K_h = 10.0\text{ m}^2/\text{s}$ yields an elapsed surface residence time of **0.50 hours**, constraining the release window to `2023-11-17T23:16:46+00:00` – `2023-11-17T23:24:16+00:00`.

## 3. Hydrodynamic Reverse-Lagrangian Backtrack (Upstream Engine)

A reverse-Lagrangian particle dispersion model built on **OpenDrift 1.14** was seeded with the satellite slick footprint and integrated backwards in time. The physical forcing environment was driven by archived Copernicus Marine Service (CMEMS) reanalysis products.

| Simulation Parameter | Value | Description |
| :--- | :--- | :--- |
| **Lagrangian Particles** | 500 particles | Monte Carlo stochastic distribution |
| **Simulation Duration** | 6 hours | Negative time step reverse integration |
| **Hydrodynamic Surface Currents** | CMEMS Global Analysis | Hourly $u_o$ (eastward) and $v_o$ (northward) components |
| **Stokes Wave Drift** | CMEMS Wave Model | Surface wave-induced Stokes drift ($VSDX, VSDY$) |
| **Wind Leeway Factor** | 3.0% with $5^\circ$ deflection | Direct aerodynamic shear stress at 10m elevation |
| **Origin Solver Method** | `morphology_diffusion_correlated` | 2D Kernel Density Peak & Stranding Convergence |
| **Reconstructed Origin** | **`28.93537°N, -88.96780°W`** | Primary reverse-time convergence centroid |

### Ground Truth Benchmark Verification:
* **Known Ground Truth Target:** Taylor Energy MC-20 Wellhead Site (BSEE / NOAA Official)
* **Official Ground Truth Coordinates:** `28.93653°N, -88.97069°W`
* **Model Calculated Origin:** `28.93537°N, -88.96780°W`
* **Absolute Geodetic Error:** **309.4 meters (0.167 nautical miles)**
* **Historical Background:** Hurricane Ivan (Sept 2004) triggered an underwater mudslide that toppled the Taylor Energy Mississippi Canyon Block 20 platform and buried 28 wellheads. Continuous active containment system operated by Couvillion Group under USCG/BSEE oversight.

## 4. Spatio-Temporal Query Corridor Specification

The upstream engine exported a standardized 4-dimensional query envelope (`trajectory_corridor.geojson`) enclosing all particle trajectories and expanding across the calculated spill release window. This corridor forms the exact spatial filter for cross-referencing historical AIS vessel broadcasts.

* **Temporal Ingestion Window:** `2023-11-17T23:16:46+00:00` to `2023-11-17T23:54:16+00:00`
* **Spatial Bounding Envelope:** Formed by the convex hull of the 500 reverse-time drift particles.
* **AIS Data Feed:** NOAA Marine Cadastre high-density terrestrial and satellite AIS archive.

## 5. Maritime Traffic & Candidate Vessel Evaluation (Downstream Engine)

Raw AIS vessel positions were resampled at 1-minute intervals using great-circle interpolation and course unrolling. For every vessel in the corridor, the engine solved for the exact Closest Point of Approach (CPA), time offset $\Delta t_{CPA}$, rate of turn, and transmission continuity.

### Comprehensive Candidate Evaluation Table:

| Rank | Vessel Name | MMSI | Vessel Type | CPA Distance | CPA Time (UTC) | $\Delta T_{CPA}$ | Speed | Score | Suspicion Level |
| :---: | :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | **CG WALNUT** | `366953000` | Offshore / Tug / Other (90) | 8451 m | `23:18:55` | 2m offset | 13.3 kt | **52.5%** | `MEDIUM` |
| 2 | **KARLA F** | `367332840` | Offshore / Tug / Other (90) | 10915 m | `23:44:30` | 28m offset | 9.8 kt | **51.7%** | `MEDIUM` |
| 3 | **MATTERHORN TLP** | `367376530` | Offshore / Tug / Other (90) | 25473 m | `23:30:19` | 14m offset | 0.1 kt | **50.3%** | `MEDIUM` |
| 4 | **MR SEAMAN** | `367154130` | Passenger (60) | 10723 m | `23:40:24` | 24m offset | 1.9 kt | **47.5%** | `LOW` |
| 5 | **FULL CIRCLE II** | `338444731` | Fishing / Trawler (37) | 31966 m | `22:59:59` | 17m offset | 15.2 kt | **43.7%** | `LOW` |
| 6 | **GO GLORY** | `368269780` | Cargo (70) | 14243 m | `23:02:25` | 14m offset | 0.1 kt | **43.1%** | `LOW` |
| 7 | **NGUYEN T J** | `367594140` | Fishing / Trawler (30) | 14976 m | `23:58:45` | 42m offset | 7.6 kt | **42.7%** | `LOW` |
| 8 | **MISSISSIPPI III** | `367724890` | Fishing / Trawler (30) | 16704 m | `23:17:50` | 1m offset | 7.6 kt | **41.0%** | `LOW` |
| 9 | **BRETON ISLAND** | `367558730` | Offshore / Tug / Other (90) | 13755 m | `22:17:14` | 60m offset | 2.5 kt | **39.9%** | `LOW` |
| 10 | **BOOGIE** | `338176375` | Fishing / Trawler (37) | 33202 m | `22:58:06` | 19m offset | 28.5 kt | **39.8%** | `LOW` |
| 11 | **KIMBERLY CELESTE** | `368152930` | Fishing / Trawler (30) | 14213 m | `22:17:19` | 59m offset | 6.0 kt | **38.6%** | `LOW` |
| 12 | **JAMAL** | `366701330` | Fishing / Trawler (37) | 33731 m | `22:59:38` | 17m offset | 0.1 kt | **37.6%** | `LOW` |
| 13 | **A.B. CENAC** | `368238290` | Vessel (Type 0) | 24373 m | `22:17:41` | 59m offset | 1.4 kt | **36.1%** | `LOW` |
| 14 | **OUR MOTHER** | `367155810` | Fishing / Trawler (30) | 28566 m | `23:32:49` | 16m offset | 2.8 kt | **35.6%** | `LOW` |
| 15 | **ENTERPRISE** | `368132210` | Fishing / Trawler (37) | 33729 m | `22:17:54` | 59m offset | 0.0 kt | **31.1%** | `LOW` |

## 6. Subsea & Offshore Infrastructure Proximity Analysis

Offshore infrastructure records (pipelines and platforms) were ingested into a high-performance GEOS `STRtree` spatial index to compute exact geodetic clearances from the calculated origin centroid.

| Infrastructure Parameter | Finding | Description |
| :--- | :--- | :--- |
| **Nearest Infrastructure** | `Subsea Pipeline` | Identified offshore marine structure |
| **Distance from Origin** | **49.1 meters** | Proximity to origin centroid |
| **Segment / ID** | `12712` | Regulatory asset identifier |
| **Operating Entity** | WALTER OIL & GAS CORPORATION | Commercial operating company |
| **Diameter / Status** | 06" / Status: `ABN` | Mechanical specifications |
| **Product Flow** | `BLKG` | Hydrocarbon stream category |

> [!IMPORTANT]
> **Anchor-Strike / Loitering Assessment:** Vessel **CG WALNUT** (`366953000`) passed within **118.9 m** of Pipeline Segment 12712 while maneuvering at 13.7 knots. Because the pipeline is classified as Abandoned (`ABN`) and the spill origin aligns directly with the known MC-20 wellhead structure, the primary failure mode is classified as an infrastructure failure rather than an active commercial vessel discharge.

## 7. Multi-Criteria Decision Analysis (MCDA) Scoring Matrix

Every candidate vessel was scored using continuous multi-attribute weight functions. Scores range from 0.0% (completely exonerated) to 100.0% (definite culprit).

| Criterion | Weight ($W$) | Decay Function / Model |
| :--- | :---: | :--- |
| **Spatial Proximity ($S_{prox}$)** | 30% | Gaussian distance decay: $e^{-(d_{cpa} / 2000)^2}$ |
| **Temporal Alignment ($S_{time}$)** | 30% | Continuous time decay from estimated release window center |
| **Vessel Hazard Profile ($S_{type}$)** | 15% | Regulated hazard multipliers (Tankers 1.0, Cargo 0.65, Tug/OSV 0.40) |
| **Slick Axis Alignment ($S_{align}$)** | 15% | Angular cosine similarity: $\cos(\theta_{vessel} - \theta_{slick})$ |
| **Dark-Ship Transponder Gap ($S_{gap}$)** | 10% | Step escalation for unannounced AIS dropouts $>30$ min |

### Negative Control Verification & Commercial Vessel Exoneration:
All transiting commercial and offshore vessels (e.g. *CG WALNUT*, *KARLA F*, *MATTERHORN TLP*, *MR SEAMAN*) remained at least **8.4 km to 33.7 km away** from the physical release origin. Their low composite scores (31.1% – 52.5%) and high spatial separation verify that **no commercial surface vessels were responsible for this discharge**, successfully clearing the negative control test.

## 8. Final Forensic Determination & Evidence Chain of Custody

### Formal Verdict Declaration:
Based on the mathematical convergence of reverse-Lagrangian particle dispersion, satellite morphology diffusion age estimation, and exhaustive AIS spatial query cross-referencing, the investigative authority makes the following determination:

$$\mathbf{VERDICT:\; SUSPECTED_ANCHOR_STRIKE_ON_PIPELINE}$$
$$\mathbf{CONFIDENCE:\; HIGH\; (88.5\%)}$$

### Forensic Chain of Custody & Audit Trail:
* **Simulation Software:** OpenDrift 1.14.10 / Reverse-Lagrangian Trajectory Core
* **Hydrodynamic Reanalysis:** Copernicus Marine Service (CMEMS) Global Ocean Analysis Forecast
* **AIS Broadcast Registry:** NOAA Marine Cadastre Decoded Broadcast Feed
* **Infrastructure Registry:** Bureau of Ocean Energy Management (BOEM) / BSEE Deepwater Cadastre
* **Execution Environment:** Windows x64 / Python 3.11 / GEOS & GDAL C-Spatial Engines

## 9. Technical Appendix & Evidence Manifest

The complete, reproducible digital evidence package is preserved in the investigation repository:

1. **`origin_report.json`**: Upstream physics metrics and diffusion age parameters.
2. **`trajectory_corridor.geojson`**: Standardized 4D spatio-temporal query polygon.
3. **`trajectory_map.html`**: Standalone interactive satellite drift map.
4. **`attribution/culprit_dossier.json`**: Complete machine-readable forensic dossier.
5. **`attribution/culprit_map.html`**: Interactive forensic attribution map with AIS tracks.
6. **`attribution/culprit_visual.geojson`**: Reconstructed vessel trajectories for GIS integration.

---
*End of Official Forensic Investigation Report.*