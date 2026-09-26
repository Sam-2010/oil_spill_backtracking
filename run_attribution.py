"""
run_attribution.py
------------------
CLI entry point for the AIS & Infrastructure Oil Spill Forensic Attribution Engine.
Ingests:
  - Upstream handover GeoJSON (trajectory_corridor.geojson)
  - Origin metadata report (origin_report.json)
  - Historical AIS data (CSV/Parquet)
  - Subsea infrastructure vector layers (Pipelines & Platforms)
Outputs:
  - culprit_dossier.json (Forensic audit report)
  - culprit_map.html (Interactive Folium Leaflet map)
  - culprit_visual.geojson (Vector GIS export)
"""

import os
import sys
import argparse
import yaml
import json

from src.attribution.preflight import extract_origin_metadata, validate_preflight
from src.attribution.data_loader import load_and_sanitize_ais, load_infrastructure
from src.attribution.trajectory import reconstruct_vessel_trajectories, trajectories_to_geodataframe
from src.attribution.dark_ship import detect_dark_ships, dark_candidates_to_geodataframe
from src.attribution.cpa import calculate_all_cpas, cpas_to_geodataframe
from src.attribution.scoring import score_all_candidates, scored_candidates_to_geodataframe
from src.attribution.decision_engine import evaluate_forensic_attribution, generate_forensic_dossier, generate_forensic_map

def run_attribution_pipeline(
    origin_report_path: str,
    corridor_path: str,
    ais_path: str,
    config_path: str = "config.yaml",
    pipes_path: str = "data/infrastructure/regional_pipelines.geojson",
    plats_path: str = "data/infrastructure/regional_platforms.geojson",
    output_dir: str = "outputs/attribution"
):
    print("=" * 80)
    print("AIS & INFRASTRUCTURE OIL SPILL FORENSIC ATTRIBUTION ENGINE")
    print("=" * 80)
    
    os.makedirs(output_dir, exist_ok=True)
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
        
    print("\n[PHASE 1] Extracting Origin & Validating Pre-Flight Coverage...")
    meta = extract_origin_metadata(origin_report_path, corridor_path)
    win = meta.time_window
    print(f"  Incident Time (T0):    {win.t0.isoformat()}")
    print(f"  Drift Elapsed Age:     {meta.delta_t_hours:.2f} hours")
    print(f"  Release Window:        {win.start_time.isoformat()} to {win.end_time.isoformat()}")
    
    preflight = validate_preflight(ais_path, meta)
    if not preflight.passed:
        print("\n  [ERROR] Pre-flight validation failed:")
        for err in preflight.errors:
            print(f"    - {err}")
        return None
    print("  Pre-flight Coverage:   PASSED")
    
    print("\n[PHASE 1.2] Sanitizing AIS Data & Loading Infrastructure...")
    minx, miny, maxx, maxy = meta.origin_polygon.bounds
    search_bbox = (minx - 0.25, miny - 0.25, maxx + 0.25, maxy + 0.25)
    ais_gdf = load_and_sanitize_ais(ais_path, win, spatial_bbox=search_bbox)
    infra = load_infrastructure(pipes_path, plats_path, meta.primary_centroid)
    print(f"  Corridor Pings:        {len(ais_gdf)} across {ais_gdf['mmsi'].nunique()} vessels.")
    
    print("\n[PHASE 2] Reconstructing Continuous Trajectories (1-min steps)...")
    trajectories = reconstruct_vessel_trajectories(ais_gdf)
    total_interp = sum(len(t.interpolated_points) for t in trajectories)
    print(f"  Traversed Vessels:     {len(trajectories)}")
    print(f"  Dense Pings (1-min):   {total_interp}")
    
    print("\n[PHASE 3] Detecting Transponder Blackout Gaps & Kinematic Dead-Reckoning...")
    dark_candidates = detect_dark_ships(trajectories, meta)
    print(f"  Dark Candidates:       {len(dark_candidates)}")
    
    print("\n[PHASE 4] Calculating Closest Point of Approach (CPA) & Slick Alignment...")
    cpas = calculate_all_cpas(trajectories, dark_candidates, meta)
    print(f"  Evaluated CPAs:        {len(cpas)} total paths")
    
    print("\n[PHASE 5] Computing Multi-Criteria Suspicion Scores...")
    scored = score_all_candidates(cpas, meta, config)
    
    print("\n  TOP 5 CANDIDATES LEADERBOARD:")
    print("  " + "-" * 75)
    print(f"  {'Rank':<5} {'MMSI':<12} {'Vessel Name':<18} {'Dark':<6} {'Dist (m)':<10} {'Score':<7} {'Level'}")
    print("  " + "-" * 75)
    for rank, s in enumerate(scored[:5], 1):
        dark_flag = "YES" if s.is_dark_ship else "no"
        print(f"  {rank:<5} {s.mmsi:<12} {s.vessel_name[:16]:<18} {dark_flag:<6} {s.cpa_distance_meters:<10.0f} {s.total_score:<7.1f} {s.suspicion_level}")
    print("  " + "-" * 75)
    
    print("\n[PHASE 6] Evaluating Forensic Attribution Decision Hierarchy...")
    verdict = evaluate_forensic_attribution(scored, trajectories, infra, meta, config)
    print(f"  Primary Verdict:       {verdict.primary_verdict}")
    print(f"  Confidence Level:      {verdict.confidence}")
    print(f"  Executive Summary:     {verdict.summary}")
    
    print("\n[PHASE 7] Generating Final Forensic Dossier & Interactive Map...")
    dossier_path = os.path.join(output_dir, "culprit_dossier.json")
    map_path = os.path.join(output_dir, "culprit_map.html")
    geojson_path = os.path.join(output_dir, "culprit_visual.geojson")
    
    generate_forensic_dossier(verdict, scored, meta, config, dossier_path)
    generate_forensic_map(meta, trajectories, dark_candidates, scored, infra, map_path)
    
    scored_gdf = scored_candidates_to_geodataframe(scored)
    scored_gdf.to_file(geojson_path, driver="GeoJSON")
    
    print(f"  [SAVED] Forensic Dossier:   {dossier_path}")
    print(f"  [SAVED] Interactive Map:    {map_path}")
    print(f"  [SAVED] Vector GeoJSON:     {geojson_path}")
    
    print("\n" + "=" * 80)
    print("PIPELINE EXECUTION COMPLETE - FORENSIC DOSSIER GENERATED")
    print("=" * 80)
    return verdict

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AIS & Infrastructure Oil Spill Forensic Attribution Engine")
    parser.add_argument("--origin", default="outputs/taylor_energy/origin_report.json", help="Path to origin_report.json")
    parser.add_argument("--corridor", default="outputs/taylor_energy/trajectory_corridor.geojson", help="Path to trajectory_corridor.geojson")
    parser.add_argument("--ais", default="data/ais/taylor_energy_mc20_noaa_ais_2023_11_17.csv", help="Path to AIS CSV/Parquet")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--pipes", default="data/infrastructure/regional_pipelines.geojson", help="Path to regional pipelines GeoJSON")
    parser.add_argument("--plats", default="data/infrastructure/regional_platforms.geojson", help="Path to regional platforms GeoJSON")
    parser.add_argument("--outdir", default="outputs/attribution", help="Output directory")
    
    args = parser.parse_args()
    run_attribution_pipeline(
        origin_report_path=args.origin,
        corridor_path=args.corridor,
        ais_path=args.ais,
        config_path=args.config,
        pipes_path=args.pipes,
        plats_path=args.plats,
        output_dir=args.outdir
    )
