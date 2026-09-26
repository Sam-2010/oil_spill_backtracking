"""
run_combined_forensics.py
-------------------------
Master orchestration runner executing the complete end-to-end maritime environmental forensics pipeline:
1. Upstream Physical Backtracking (OpenDrift reverse Lagrangian trajectory modeling)
2. Contract Handover Verification (origin_report.json & trajectory_corridor.geojson)
3. Downstream AIS & Infrastructure Attribution (CPA, dead reckoning, MCDA scoring, infrastructure cross-referencing)
4. Forensic Dossier & Interactive Leaflet Map generation
"""

import os
import sys
import subprocess
import json
import time
import argparse

def run_step(cmd, description=""):
    print(f"\n>>> [RUNNING] {description}")
    print(f"Command: {' '.join(cmd)}\n")
    start = time.time()
    result = subprocess.run(cmd, text=True, capture_output=False)
    elapsed = time.time() - start
    if result.returncode != 0:
        print(f"\n[ERROR] Step failed with exit code {result.returncode} ({description})")
        sys.exit(result.returncode)
    print(f"\n>>> [SUCCESS] {description} completed in {elapsed:.1f}s.")

def main():
    parser = argparse.ArgumentParser(description="Master End-to-End Maritime Forensics Pipeline")
    parser.add_argument("--incident", choices=["taylor_energy", "main_pass"], default="taylor_energy", help="Preset incident benchmark")
    parser.add_argument("--input", default=None, help="Custom detection GeoJSON input")
    parser.add_argument("--ais", default=None, help="Custom AIS CSV/Parquet path")
    parser.add_argument("--hours", type=float, default=6.0, help="Simulation backtrack hours")
    parser.add_argument("--particles", type=int, default=500, help="Particle count")
    args = parser.parse_args()

    python_bin = sys.executable

    print("=" * 80)
    print("MASTER MARITIME ENVIRONMENTAL FORENSICS PIPELINE")
    print(f"Incident Target: {args.incident.upper()}")
    print("=" * 80)

    # 1. Setup paths based on incident preset
    if args.incident == "taylor_energy":
        input_geojson = args.input or "inputs/taylor_energy_mc20_detection.geojson"
        ais_csv = args.ais or "data/ais/taylor_energy_mc20_noaa_ais_2023_11_17.csv"
        upstream_out = "outputs/taylor_energy"
        attribution_out = "outputs/taylor_energy/attribution"
        head_only = True
    else:
        input_geojson = args.input or "inputs/main_pass_detection.geojson"
        ais_csv = args.ais or "data/ais/main_pass_noaa_ais_2023_11_16.csv"
        upstream_out = "outputs/main_pass"
        attribution_out = "outputs/main_pass/attribution"
        head_only = False

    # -------------------------------------------------------------
    # Step 1: Upstream Physical Reverse Lagrangian Backtracking
    # -------------------------------------------------------------
    backtrack_cmd = [
        python_bin, "run_backtrack.py",
        "--input", input_geojson,
        "--hours", str(args.hours),
        "--particles", str(args.particles),
        "--output-dir", upstream_out
    ]
    if head_only:
        backtrack_cmd.append("--head-only")

    run_step(backtrack_cmd, description=f"Upstream Physical Reverse-Drift Simulation ({args.incident})")

    # -------------------------------------------------------------
    # Step 2: Handover Contract Verification
    # -------------------------------------------------------------
    corridor_geojson = os.path.join(upstream_out, "trajectory_corridor.geojson")
    origin_report = os.path.join(upstream_out, "origin_report.json")

    print("\n[VERIFY] Validating Handover Contract Artifacts...")
    assert os.path.exists(corridor_geojson), f"Missing handover corridor: {corridor_geojson}"
    assert os.path.exists(origin_report), f"Missing handover report: {origin_report}"

    with open(origin_report, "r", encoding="utf-8") as f:
        rep = json.load(f)
    elapsed_hours = rep["morphology_analysis"]["calculated_elapsed_hours"]
    origin_cent = rep["estimated_origin"]["primary_centroid"]
    print(f" -> Handover Verified: Calculated Elapsed Drift = {elapsed_hours:.2f} hours")
    print(f" -> Origin Centroid:   Lat {origin_cent['latitude']:.5f}, Lon {origin_cent['longitude']:.5f}")

    # -------------------------------------------------------------
    # Step 3: Downstream AIS & Infrastructure Forensic Attribution
    # -------------------------------------------------------------
    attribution_cmd = [
        python_bin, "run_attribution.py",
        "--origin", origin_report,
        "--corridor", corridor_geojson,
        "--ais", ais_csv,
        "--config", "config.yaml",
        "--pipes", "data/infrastructure/regional_pipelines.geojson",
        "--plats", "data/infrastructure/regional_platforms.geojson",
        "--outdir", attribution_out
    ]
    run_step(attribution_cmd, description=f"Downstream AIS & Infrastructure Attribution Engine ({args.incident})")

    # -------------------------------------------------------------
    # Step 4: Executive Forensic Dossier Summary
    # -------------------------------------------------------------
    dossier_path = os.path.join(attribution_out, "culprit_dossier.json")
    map_path = os.path.join(attribution_out, "culprit_map.html")

    with open(dossier_path, "r", encoding="utf-8") as f:
        dossier = json.load(f)

    verdict = dossier["forensic_verdict"]
    top_candidates = dossier["ranked_vessel_candidates"]

    print("\n" + "=" * 80)
    print("FINAL COMBINED FORENSIC DOSSIER SUMMARY")
    print("=" * 80)
    print(f"Primary Verdict:    {verdict['primary_verdict']}")
    print(f"Confidence Level:   {verdict['confidence_level']}")
    print(f"Executive Summary:  {verdict['executive_summary']}")
    print("-" * 80)
    print("Top Vessel Suspects:")
    for v in top_candidates[:3]:
        print(f"  Rank {v['rank']}: {v['vessel_name']} (MMSI: {v['mmsi']}) -> Score: {v['composite_suspicion_score']}% [{v['suspicion_level']}], CPA: {v['cpa']['distance_meters']:.0f}m")
    print("-" * 80)
    print(f"Interactive Forensic Map: file:///{os.path.abspath(map_path).replace(os.sep, '/')}")
    print(f"Complete Audit Dossier:   file:///{os.path.abspath(dossier_path).replace(os.sep, '/')}")
    print("=" * 80)

if __name__ == "__main__":
    main()
