"""
run_backtrack.py
----------------
Command-line interface (CLI) and main entry point for the Oil Spill Backtracking
and Origin Identification Module.

Usage:
  python run_backtrack.py --input inputs/rubymar_detection.geojson --hours 24 --particles 500
  python run_backtrack.py --input inputs/fallback_point.json --hours 24 --particles 500
"""

import argparse
import sys
from pathlib import Path

from src.morphology import SlickMorphologyAnalyzer
from src.backtrack_engine import OilSpillBacktracker
from src.output_formatter import TrajectoryOutputFormatter

def main():
    parser = argparse.ArgumentParser(
        description="Oil Spill Backtracking & Origin Identification Engine using OpenDrift and Copernicus Marine."
    )
    parser.add_argument(
        "--input", "-i",
        type=str,
        default="inputs/rubymar_detection.geojson",
        help="Path to input GeoJSON polygon or fallback point JSON (default: inputs/rubymar_detection.geojson)"
    )
    parser.add_argument(
        "--hours", "-H",
        type=float,
        default=24.0,
        help="Maximum backtrack duration in hours (default: 24.0)"
    )
    parser.add_argument(
        "--particles", "-p",
        type=int,
        default=500,
        help="Number of Lagrangian particles to simulate (default: 500)"
    )
    parser.add_argument(
        "--diffusivity", "-k",
        type=float,
        default=10.0,
        help="Turbulent horizontal diffusivity Kh in m^2/s (default: 10.0)"
    )
    parser.add_argument(
        "--leeway", "-l",
        type=float,
        default=0.03,
        help="Wind leeway factor (default: 0.03 = 3%)"
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default="outputs",
        help="Directory to save generated GeoJSON, report, and plot outputs (default: outputs)"
    )
    parser.add_argument(
        "--currents",
        type=str,
        default=None,
        help="Path to custom ocean currents NetCDF file"
    )
    parser.add_argument(
        "--wind",
        type=str,
        default=None,
        help="Path to custom 10m wind NetCDF file"
    )
    parser.add_argument(
        "--waves",
        type=str,
        default=None,
        help="Path to custom waves NetCDF file"
    )

    args = parser.parse_args()

    print("=" * 75)
    print("OIL SPILL BACKTRACKING & ORIGIN IDENTIFICATION MODULE")
    print("=" * 75)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}")
        sys.exit(1)

    # -------------------------------------------------------------
    # Step 1: Slick Morphology Analysis
    # -------------------------------------------------------------
    print(f"\n[1/3] Analyzing input slick geometry from: {input_path.name}")
    analyzer = SlickMorphologyAnalyzer(horizontal_diffusivity_m2s=args.diffusivity)
    detection = analyzer.analyze(str(input_path))

    if detection.get("warning"):
        print(f" -> {detection['warning']}")

    if detection.get("has_polygon"):
        morph = detection["morphology"]
        origin_win = detection["estimated_origin_window_utc"]
        print(f" -> Slick Length:       {morph['length_km']:.2f} km")
        print(f" -> Width Profile:      W_head = {morph['head_width_m']:.0f}m, W_tail = {morph['tail_width_m']:.0f}m")
        print(f" -> Calculated Age:     {morph['calculated_elapsed_hours']:.1f} hours prior to detection")
        print(f" -> Origin Time Window: {origin_win['start']} to {origin_win['end']} UTC")

    # Dynamic horizon adjustment: ensure simulation covers full morphology window
    sim_hours = args.hours
    if detection.get("has_polygon"):
        est_max = detection.get("estimated_origin_window_utc", {}).get("hours_prior_max", 0)
        if est_max > sim_hours:
            import math
            expanded_hours = float(math.ceil(est_max + 2.0))
            print(f" -> [AUTO-HORIZON] Morphology origin window extends to {est_max:.1f}h. Expanding backtrack duration from {sim_hours:.0f}h to {expanded_hours:.0f}h.")
            sim_hours = expanded_hours

    # -------------------------------------------------------------
    # Step 2: OpenDrift Reverse Hydrodynamic Simulation
    # -------------------------------------------------------------
    print(f"\n[2/3] Running OpenDrift reverse Lagrangian simulation ({args.particles} particles, {sim_hours:.0f} hours)...")
    backtracker = OilSpillBacktracker(
        horizontal_diffusivity=args.diffusivity,
        wind_drift_factor=args.leeway
    )

    sim_result = backtracker.run_backtrack(
        detection_data=detection,
        currents_file=Path(args.currents) if args.currents else None,
        wind_file=Path(args.wind) if args.wind else None,
        waves_file=Path(args.waves) if args.waves else None,
        backtrack_hours=sim_hours,
        num_particles=args.particles,
        time_step_minutes=15,
        output_step_minutes=60
    )

    # -------------------------------------------------------------
    # Step 3: Formatting & Exporting Results
    # -------------------------------------------------------------
    print(f"\n[3/3] Exporting standardized outputs to: {args.output_dir}/")
    formatter = TrajectoryOutputFormatter(output_dir=args.output_dir)
    exported_files = formatter.format_and_export(sim_result)

    print("\n" + "=" * 75)
    print("BACKTRACKING & ORIGIN ANALYSIS COMPLETE!")
    print("=" * 75)
    print(f" -> GeoJSON Corridor (AIS query envelope): {exported_files['geojson']}")
    print(f" -> Summary Origin Report:                 {exported_files['report']}")
    print(f" -> Interactive Leaflet Map:               {exported_files['map']}")
    print("=" * 75)

if __name__ == "__main__":
    main()
