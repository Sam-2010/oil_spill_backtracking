"""
test_phase4.py
--------------
Unit and verification test for Phase 4:
1. Performs morphology analysis on the benchmark MV Rubymar detection GeoJSON.
2. Executes a full 24-hour backward simulation using real Copernicus Marine hourly currents,
   wind, and wave Stokes drift.
3. Verifies that the particle ensemble backtracks south-southeast toward the original strike zone.
"""

import os
import sys
from pathlib import Path
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
os.chdir(_PROJECT_ROOT)

from src.morphology import SlickMorphologyAnalyzer
from src.backtrack_engine import OilSpillBacktracker

def run_tests():
    print("=" * 70)
    print("RUNNING PHASE 4 TESTS: FULL OPENDRIFT BACKTRACKING SIMULATION")
    print("=" * 70)

    # 1. Analyze morphology
    print("\n[STEP 1] Ingesting & analyzing benchmark Rubymar GeoJSON...")
    analyzer = SlickMorphologyAnalyzer(horizontal_diffusivity_m2s=10.0)
    detection = analyzer.analyze("inputs/rubymar_detection.geojson")

    print(f" -> Detection Time: {detection['detection_timestamp']}")
    print(f" -> Estimated Elapsed Age: {detection['morphology']['calculated_elapsed_hours']:.1f} hours")
    print(f" -> Origin Time Window: {detection['estimated_origin_window_utc']['start']} to {detection['estimated_origin_window_utc']['end']}")

    # 2. Run Backtrack Simulation
    print("\n[STEP 2] Running 24-hour backward Lagrangian simulation (500 particles)...")
    backtracker = OilSpillBacktracker(
        horizontal_diffusivity=10.0,
        wind_drift_factor=0.03
    )

    sim_result = backtracker.run_backtrack(
        detection_data=detection,
        backtrack_hours=24.0,
        num_particles=500,
        time_step_minutes=15,
        output_step_minutes=60
    )

    assert sim_result["status"] == "success", "Simulation failed"
    traj = sim_result["trajectory"]
    print(f"\n[STEP 3] Verifying trajectory history...")
    print(f" -> Total hourly output steps: {traj['num_steps']}")
    print(f" -> Start time (detection):   {traj['times'][0]}")
    print(f" -> Final backtracked time:    {traj['times'][-1]}")

    import numpy as np

    # Inspect initial vs final positions using nanmean (ignoring stranded elements)
    initial_mean_lon = float(np.nanmean(traj['lons'][:, 0]))
    initial_mean_lat = float(np.nanmean(traj['lats'][:, 0]))
    final_mean_lon = float(np.nanmean(traj['lons'][:, -1]))
    final_mean_lat = float(np.nanmean(traj['lats'][:, -1]))

    active_count = int(np.sum(~np.isnan(traj['lons'][:, -1])))
    stranded_count = traj['lons'].shape[0] - active_count

    print(f" -> Initial centroid (at detection): {initial_mean_lat:.4f}N, {initial_mean_lon:.4f}E")
    print(f" -> Final backtracked centroid (-24h): {final_mean_lat:.4f}N, {final_mean_lon:.4f}E")
    print(f" -> Active floating particles: {active_count} | Stranded/coastal: {stranded_count}")

    # In forward time, water flowed northward. In reverse time, particles should drift southward!
    delta_lat = final_mean_lat - initial_mean_lat
    print(f" -> Net reverse latitude displacement: {delta_lat:+.4f} deg")
    assert delta_lat < 0, f"Expected southward reverse drift (delta_lat < 0), got {delta_lat:+.4f}"
    print(" -> Particles correctly backtracked southward along the channel toward the source! [OK]")

    print("\n" + "=" * 70)
    print("ALL PHASE 4 TESTS COMPLETED SUCCESSFULLY! [OK]")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()
