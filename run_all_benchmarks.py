"""
run_all_benchmarks.py
---------------------
Executes backtracking across all 7 real-world benchmark incidents and calculates
the precise geographic origin error against authoritative ground truth coordinates.
"""

import sys
import json
import math
from pathlib import Path
from datetime import datetime

# Add project root
sys.path.insert(0, str(Path(".").resolve()))

from src.morphology import SlickMorphologyAnalyzer
from src.backtrack_engine import OilSpillBacktracker
from src.output_formatter import TrajectoryOutputFormatter

# Haversine distance formula in kilometers and nautical miles
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0 # Earth's radius in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

BENCHMARKS = [
    {
        "id": "rubymar",
        "name": "MV Rubymar (Red Sea)",
        "input": "inputs/rubymar_detection.geojson",
        "currents": "data/currents/cmems_currents_rubymar.nc",
        "wind": "data/wind/cmems_wind_rubymar.nc",
        "waves": "data/waves/cmems_waves_rubymar.nc",
        "hours": 72.0,
        "head_only": False,
        "ground_truth": {"lat": 13.3440, "lon": 43.1450, "description": "Houthi missile strike location"}
    },
    {
        "id": "tobago",
        "name": "Barge Gulfstream (Tobago)",
        "input": "inputs/tobago_detection.geojson",
        "currents": "data/currents/cmems_currents_tobago.nc",
        "wind": "data/wind/cmems_wind_tobago.nc",
        "waves": "data/waves/cmems_waves_tobago.nc",
        "hours": 37.0,
        "head_only": False,
        "ground_truth": {"lat": 11.1440, "lon": -60.7780, "description": "Cove Reef grounding site"}
    },
    {
        "id": "singapore",
        "name": "Vox Maxima (Singapore Strait)",
        "input": "inputs/singapore_detection.geojson",
        "currents": "data/currents/cmems_currents_singapore.nc",
        "wind": "data/wind/cmems_wind_singapore.nc",
        "waves": "data/waves/cmems_waves_singapore.nc",
        "hours": 24.0,
        "head_only": False,
        "ground_truth": {"lat": 1.2720, "lon": 103.7740, "description": "Pasir Panjang Terminal berth allision"}
    },
    {
        "id": "manila",
        "name": "MT Terra Nova (Manila Bay)",
        "input": "inputs/manila_detection.geojson",
        "currents": "data/currents/cmems_currents_manila.nc",
        "wind": "data/wind/cmems_wind_manila.nc",
        "waves": "data/waves/cmems_waves_manila.nc",
        "hours": 24.0,
        "head_only": False,
        "ground_truth": {"lat": 14.4170, "lon": 120.6000, "description": "Sunken tanker wreck site"}
    },
    {
        "id": "sounion",
        "name": "MV Sounion (Central Red Sea)",
        "input": "inputs/sounion_detection.geojson",
        "currents": "data/currents/cmems_currents_sounion.nc",
        "wind": "data/wind/cmems_wind_sounion.nc",
        "waves": "data/waves/cmems_waves_sounion.nc",
        "hours": 24.0,
        "head_only": False,
        "ground_truth": {"lat": 15.0350, "lon": 41.8850, "description": "Burning anchored tanker site"}
    },
    {
        "id": "main_pass",
        "name": "Main Pass MPOG Pipeline (USA)",
        "input": "inputs/main_pass_detection.geojson",
        "currents": "data/currents/cmems_currents_main_pass.nc",
        "wind": "data/wind/cmems_wind_main_pass.nc",
        "waves": "data/waves/cmems_waves_main_pass.nc",
        "hours": 24.0,
        "head_only": False,
        "ground_truth": {"lat": 29.29717, "lon": -88.71800, "description": "MPOG pipeline collet fitting break"}
    },
    {
        "id": "taylor_energy",
        "name": "Taylor Energy MC-20 (USA)",
        "input": "inputs/taylor_energy_mc20_clustered.geojson",
        "currents": "data/currents/cmems_currents_mc20.nc",
        "wind": "data/wind/cmems_wind_mc20.nc",
        "waves": "data/waves/cmems_waves_mc20.nc",
        "hours": 6.0,
        "head_only": False,
        "ground_truth": {"lat": 28.93700, "lon": -88.97100, "description": "Saratoga platform wellhead cluster"}
    }
]

def main():
    print("=" * 80)
    print("EXECUTING ALL REAL-WORLD OIL SPILL BENCHMARKS (7 INCIDENTS)")
    print("=" * 80)

    results = []

    for b in BENCHMARKS:
        print(f"\n---> Running Benchmark: {b['name']} ...")
        out_dir = Path("outputs") / b["id"]
        out_dir.mkdir(parents=True, exist_ok=True)

        analyzer = SlickMorphologyAnalyzer(horizontal_diffusivity_m2s=10.0)
        detection = analyzer.analyze(b["input"], head_only=b["head_only"])

        sim_hours = b["hours"]
        if detection.get("has_polygon") and not b["head_only"]:
            est_max = detection.get("estimated_origin_window_utc", {}).get("hours_prior_max", 0)
            if est_max > sim_hours:
                sim_hours = float(math.ceil(est_max + 2.0))

        backtracker = OilSpillBacktracker(horizontal_diffusivity=10.0, wind_drift_factor=0.03)
        sim_result = backtracker.run_backtrack(
            detection_data=detection,
            currents_file=Path(b["currents"]),
            wind_file=Path(b["wind"]),
            waves_file=Path(b["waves"]),
            backtrack_hours=sim_hours,
            num_particles=400,
            time_step_minutes=15,
            output_step_minutes=60
        )

        formatter = TrajectoryOutputFormatter(output_dir=str(out_dir))
        formatter.format_and_export(sim_result)

        # Ingest generated report
        with open(out_dir / "origin_report.json", "r", encoding="utf-8") as f:
            rep = json.load(f)

        est_lat = rep["estimated_origin"]["primary_centroid"]["latitude"]
        est_lon = rep["estimated_origin"]["primary_centroid"]["longitude"]
        gt_lat = b["ground_truth"]["lat"]
        gt_lon = b["ground_truth"]["lon"]

        err_km = haversine_km(est_lat, est_lon, gt_lat, gt_lon)
        err_nm = err_km / 1.852

        results.append({
            "name": b["name"],
            "gt_lat": gt_lat,
            "gt_lon": gt_lon,
            "est_lat": est_lat,
            "est_lon": est_lon,
            "err_km": err_km,
            "err_nm": err_nm,
            "method": rep["estimated_origin"]["solver_method"],
            "conf": rep["estimated_origin"]["confidence"]
        })
        print(f"     [Result] Error: {err_km:.2f} km ({err_nm:.2f} nm) | Solver: {rep['estimated_origin']['solver_method']}")

    # Print summary table
    print("\n" + "=" * 90)
    print(f"{'Incident':<30} | {'Ground Truth':<20} | {'Estimated Origin':<20} | {'Error (km)':<10} | {'Error (nm)':<10}")
    print("-" * 90)
    for r in results:
        gt_str = f"{r['gt_lat']:.3f}, {r['gt_lon']:.3f}"
        est_str = f"{r['est_lat']:.3f}, {r['est_lon']:.3f}"
        print(f"{r['name']:<30} | {gt_str:<20} | {est_str:<20} | {r['err_km']:<10.2f} | {r['err_nm']:<10.2f}")
    print("=" * 90)

if __name__ == "__main__":
    main()
