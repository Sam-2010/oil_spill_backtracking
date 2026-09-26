import json
import math
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import folium
from folium import plugins
import geopandas as gpd
from shapely.geometry import Point, LineString, Polygon

from .models import (
    OriginMetadata,
    TimeWindow,
    VesselTrajectory,
    DarkShipCandidate,
    ScoredCandidate,
    ForensicVerdict
)
from .data_loader import InfrastructureIndex

def evaluate_forensic_attribution(
    scored_candidates: List[ScoredCandidate],
    trajectories: List[VesselTrajectory],
    infra_index: InfrastructureIndex,
    origin_meta: OriginMetadata,
    config: Dict[str, Any]
) -> ForensicVerdict:
    infra_cfg = config.get("infrastructure", {})
    alert_dist_m = float(infra_cfg.get("alert_distance_meters", 1000.0))
    oil_codes = infra_cfg.get("oil_product_codes", ["OIL", "CRUDE", "COND", "LQD", "BLKG"])
    
    origin_pt = origin_meta.primary_centroid
    nearest_pipe, pipe_dist = infra_index.query_nearest_pipeline(origin_pt)
    nearest_plat, plat_dist = infra_index.query_nearest_platform(origin_pt)
    
    infra_info = None
    if nearest_pipe:
        infra_info = {
            "type": "subsea_pipeline",
            "distance_meters": round(pipe_dist, 1),
            "segment_id": nearest_pipe.get("SEGMENT_NU"),
            "operator": nearest_pipe.get("SDE_COMPAN"),
            "diameter_inches": nearest_pipe.get("PPL_SIZE_C"),
            "product_code": nearest_pipe.get("PROD_CODE"),
            "status": nearest_pipe.get("STATUS_COD")
        }
    elif nearest_plat:
        infra_info = {
            "type": "offshore_platform",
            "distance_meters": round(plat_dist, 1),
            "structure_id": nearest_plat.get("STRUCTURE_"),
            "complex_id": nearest_plat.get("COMPLEX_ID"),
            "install_date": str(nearest_plat.get("INSTALL_DA")),
            "removal_date": str(nearest_plat.get("REMOVAL_DA"))
        }
        
    top_vessel = scored_candidates[0] if scored_candidates else None
    
    anchor_suspect = None
    if nearest_pipe and pipe_dist <= 1500.0:
        for traj in trajectories:
            if traj.loitering_detected or traj.min_speed < 1.0:
                for pt in traj.interpolated_points:
                    wgs_pt = Point(pt.longitude, pt.latitude)
                    _, d_pipe = infra_index.query_nearest_pipeline(wgs_pt)
                    if d_pipe <= 500.0:
                        anchor_suspect = {
                            "mmsi": traj.mmsi,
                            "vessel_name": traj.vessel_name,
                            "vessel_type": traj.vessel_type,
                            "distance_to_pipeline_meters": round(d_pipe, 1),
                            "timestamp": pt.timestamp.isoformat(),
                            "speed_knots": pt.speed_knots
                        }
                        break
            if anchor_suspect:
                break
                
    if anchor_suspect:
        return ForensicVerdict(
            primary_verdict="SUSPECTED_ANCHOR_STRIKE_ON_PIPELINE",
            confidence="HIGH",
            summary=(
                f"Vessel {anchor_suspect['vessel_name']} (MMSI: {anchor_suspect['mmsi']}) was observed loitering/anchoring "
                f"within {anchor_suspect['distance_to_pipeline_meters']:.0f}m of Pipeline Segment {nearest_pipe.get('SEGMENT_NU')} "
                f"operated by {nearest_pipe.get('SDE_COMPAN')} prior to release."
            ),
            top_vessel_candidate=top_vessel.__dict__ if top_vessel else None,
            nearest_infrastructure=infra_info,
            anchor_strike_suspect=anchor_suspect
        )
        
    if top_vessel and top_vessel.total_score >= 65.0:
        dark_str = "with an intentional transponder blackout" if top_vessel.is_dark_ship else "operating in corridor"
        return ForensicVerdict(
            primary_verdict="VESSEL_DISCHARGE",
            confidence="HIGH" if top_vessel.total_score >= 80.0 else "MEDIUM",
            summary=(
                f"Forensic evidence strongly points to vessel discharge by {top_vessel.vessel_name} (MMSI: {top_vessel.mmsi}, "
                f"Score: {top_vessel.total_score}%) {dark_str}. "
                f"Passed within {top_vessel.cpa_distance_meters:.0f}m of origin during estimated release window."
            ),
            top_vessel_candidate={
                "mmsi": top_vessel.mmsi,
                "vessel_name": top_vessel.vessel_name,
                "vessel_type": top_vessel.vessel_type,
                "is_dark_ship": top_vessel.is_dark_ship,
                "total_score": top_vessel.total_score,
                "suspicion_level": top_vessel.suspicion_level,
                "cpa_distance_meters": top_vessel.cpa_distance_meters,
                "audit_rationale": top_vessel.audit_rationale
            },
            nearest_infrastructure=infra_info
        )
        
    if (top_vessel is None or top_vessel.total_score < 45.0) and nearest_pipe and pipe_dist <= alert_dist_m:
        prod = str(nearest_pipe.get("PROD_CODE", "")).upper()
        return ForensicVerdict(
            primary_verdict="INFRASTRUCTURE_FAILURE",
            confidence="HIGH" if pipe_dist <= 300.0 else "MEDIUM",
            summary=(
                f"No culpable vessels detected in the corridor. Backtracked spill origin is located within "
                f"{pipe_dist:.0f}m of active Subsea Pipeline Segment {nearest_pipe.get('SEGMENT_NU')} "
                f"({nearest_pipe.get('PPL_SIZE_C')} inch {prod}) operated by {nearest_pipe.get('SDE_COMPAN')}."
            ),
            top_vessel_candidate=None,
            nearest_infrastructure=infra_info
        )
        
    if (top_vessel is None or top_vessel.total_score < 45.0) and nearest_plat and plat_dist <= alert_dist_m:
        return ForensicVerdict(
            primary_verdict="INFRASTRUCTURE_FAILURE",
            confidence="HIGH" if plat_dist <= 300.0 else "MEDIUM",
            summary=(
                f"No culpable vessels detected. Backtracked spill origin is located within "
                f"{plat_dist:.0f}m of Offshore Platform Structure {nearest_plat.get('STRUCTURE_')} "
                f"(Complex ID: {nearest_plat.get('COMPLEX_ID')})."
            ),
            top_vessel_candidate=None,
            nearest_infrastructure=infra_info
        )
        
    return ForensicVerdict(
        primary_verdict="UNRESOLVED_SEEP_OR_UNRECORDED_SOURCE",
        confidence="LOW",
        summary=(
            f"No vessel candidates scored above threshold (Top score: {top_vessel.total_score if top_vessel else 0}%), "
            f"and nearest pipeline is {pipe_dist:.0f}m away. Probable natural seabed seep, non-broadcasting craft, "
            f"or historical unmapped wellhead."
        ),
        top_vessel_candidate=top_vessel.__dict__ if top_vessel else None,
        nearest_infrastructure=infra_info
    )

def generate_forensic_dossier(
    verdict: ForensicVerdict,
    scored_candidates: List[ScoredCandidate],
    origin_meta: OriginMetadata,
    config: Dict[str, Any],
    output_path: str
) -> Dict[str, Any]:
    win = origin_meta.time_window
    dossier = {
        "report_metadata": {
            "generated_at_utc": datetime.utcnow().isoformat() + "Z",
            "observation_timestamp_utc": win.t0.isoformat(),
            "calculated_drift_age_hours": round(origin_meta.delta_t_hours, 2),
            "spill_origin_centroid": {
                "latitude": round(origin_meta.primary_centroid.y, 6),
                "longitude": round(origin_meta.primary_centroid.x, 6)
            },
            "release_window_utc": {
                "start": win.start_time.isoformat(),
                "end": win.end_time.isoformat(),
                "duration_hours": round((win.end_time - win.start_time).total_seconds() / 3600.0, 2)
            }
        },
        "forensic_verdict": {
            "primary_verdict": verdict.primary_verdict,
            "confidence_level": verdict.confidence,
            "executive_summary": verdict.summary,
            "nearest_infrastructure": verdict.nearest_infrastructure,
            "anchor_strike_suspect": verdict.anchor_strike_suspect
        },
        "scoring_weights_applied": scored_candidates[0].weights_applied if scored_candidates else {},
        "ranked_vessel_candidates": [
            {
                "rank": idx + 1,
                "mmsi": s.mmsi,
                "vessel_name": s.vessel_name,
                "vessel_type": s.vessel_type,
                "is_dark_ship": s.is_dark_ship,
                "composite_suspicion_score": s.total_score,
                "suspicion_level": s.suspicion_level,
                "cpa": {
                    "distance_meters": s.cpa_distance_meters,
                    "timestamp_utc": s.cpa_timestamp.isoformat(),
                    "speed_knots": s.speed_at_cpa,
                    "course_deg": s.course_at_cpa
                },
                "sub_scores": {
                    "proximity": s.s_prox,
                    "time_window": s.s_time,
                    "vessel_type_risk": s.s_type,
                    "slick_alignment": s.s_align,
                    "ais_transponder_gap": s.s_gap
                },
                "audit_rationale": s.audit_rationale
            }
            for idx, s in enumerate(scored_candidates)
        ]
    }
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(dossier, f, indent=2)
        
    return dossier

def generate_forensic_map(
    origin_meta: OriginMetadata,
    trajectories: List[VesselTrajectory],
    dark_candidates: List[DarkShipCandidate],
    scored_candidates: List[ScoredCandidate],
    infra_index: InfrastructureIndex,
    output_html_path: str
) -> folium.Map:
    cent = origin_meta.primary_centroid
    m = folium.Map(
        location=[cent.y, cent.x],
        zoom_start=11,
        tiles="OpenStreetMap"
    )
    
    poly_layer = folium.FeatureGroup(name="Estimated Spill Origin Zone", show=True)
    if origin_meta.origin_polygon:
        coords = [[lat, lon] for lon, lat in origin_meta.origin_polygon.exterior.coords]
        folium.Polygon(
            locations=coords,
            color="#FFD700",
            weight=3,
            fill=True,
            fill_color="#FFD700",
            fill_opacity=0.25,
            popup="Estimated Origin Search Zone (±25% drift uncertainty)"
        ).add_to(poly_layer)
        
    folium.Marker(
        location=[cent.y, cent.x],
        icon=folium.Icon(color="red", icon="crosshairs", prefix="fa"),
        popup=f"Origin Primary Centroid<br>Lat: {cent.y:.5f}<br>Lon: {cent.x:.5f}"
    ).add_to(poly_layer)
    poly_layer.add_to(m)
    
    infra_layer = folium.FeatureGroup(name="Offshore Infrastructure (Pipelines & Platforms)", show=True)
    if not infra_index.pipes_wgs84.empty:
        for _, pipe in infra_index.pipes_wgs84.iterrows():
            geom = pipe.geometry
            if geom and geom.geom_type == "LineString":
                pipe_coords = [[lat, lon] for lon, lat in geom.coords]
                popup_txt = f"Pipeline: Segment {pipe.get('SEGMENT_NU')}<br>Operator: {pipe.get('SDE_COMPAN')}<br>Size: {pipe.get('PPL_SIZE_C')} inch<br>Product: {pipe.get('PROD_CODE')}"
                folium.PolyLine(
                    locations=pipe_coords,
                    color="#00FFFF",
                    weight=2,
                    opacity=0.8,
                    popup=popup_txt
                ).add_to(infra_layer)
                
    if not infra_index.plats_wgs84.empty:
        for _, plat in infra_index.plats_wgs84.iterrows():
            pt = plat.geometry
            if pt and pt.geom_type == "Point":
                folium.CircleMarker(
                    location=[pt.y, pt.x],
                    radius=5,
                    color="#FFFF00",
                    fill=True,
                    fill_color="#FFFF00",
                    fill_opacity=0.9,
                    popup=f"Platform Structure: {plat.get('STRUCTURE_')}<br>Complex ID: {plat.get('COMPLEX_ID')}"
                ).add_to(infra_layer)
    infra_layer.add_to(m)
    
    traj_layer = folium.FeatureGroup(name="Active Vessel Trajectories", show=True)
    score_map = {s.mmsi: s.total_score for s in scored_candidates}
    
    for traj in trajectories:
        if traj.linestring and traj.linestring.geom_type == "LineString":
            coords = [[lat, lon] for lon, lat in traj.linestring.coords]
            v_score = score_map.get(traj.mmsi, 0.0)
            color = "#FF4500" if v_score >= 65.0 else ("#FFA500" if v_score >= 45.0 else "#1E90FF")
            folium.PolyLine(
                locations=coords,
                color=color,
                weight=2.5,
                opacity=0.7,
                popup=f"Vessel: {traj.vessel_name}<br>MMSI: {traj.mmsi}<br>Avg Speed: {traj.avg_speed:.1f} kn<br>Suspicion: {v_score:.1f}%"
            ).add_to(traj_layer)
    traj_layer.add_to(m)
    
    dark_layer = folium.FeatureGroup(name="Projected Dark Ship Blackout Vectors", show=True)
    for dark in dark_candidates:
        coords = [[lat, lon] for lon, lat in dark.projected_geometry.coords]
        folium.PolyLine(
            locations=coords,
            color="#FF0055",
            weight=3.5,
            dash_array="8, 8",
            popup=(
                f"DARK VESSEL BLACKOUT VECTOR<br>Vessel: {dark.vessel_name} (MMSI: {dark.mmsi})<br>"
                f"Gap: {dark.gap_duration_minutes:.1f} mins<br>Speed: {dark.connecting_speed_knots:.1f} kn<br>"
                f"Crosses Origin: {dark.intersects_origin_zone}"
            )
        ).add_to(dark_layer)
        folium.CircleMarker(
            location=[dark.drop_point.y, dark.drop_point.x],
            radius=6,
            color="#FF0000",
            fill=True,
            fill_color="#FF0000",
            popup=f"AIS Signal Terminated: {dark.vessel_name}"
        ).add_to(dark_layer)
        folium.CircleMarker(
            location=[dark.reemergence_point.y, dark.reemergence_point.x],
            radius=6,
            color="#00FF00",
            fill=True,
            fill_color="#00FF00",
            popup=f"AIS Signal Resumed: {dark.vessel_name}"
        ).add_to(dark_layer)
    dark_layer.add_to(m)
    
    cpa_layer = folium.FeatureGroup(name="Closest Point of Approach (CPA) Markers", show=True)
    for s in scored_candidates[:10]:
        color = "#FF0000" if s.total_score >= 70.0 else ("#FFA500" if s.total_score >= 50.0 else "#00BFFF")
        folium.CircleMarker(
            location=[s.cpa_point.y, s.cpa_point.x],
            radius=7,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.9,
            popup=(
                f"CPA Marker: {s.vessel_name} (MMSI: {s.mmsi})<br>"
                f"Suspicion Score: {s.total_score}% [{s.suspicion_level}]<br>"
                f"Distance: {s.cpa_distance_meters:.0f}m<br>"
                f"Time: {s.cpa_timestamp.strftime('%H:%M:%S UTC')}<br>"
                f"Dark Vessel: {s.is_dark_ship}"
            )
        ).add_to(cpa_layer)
    cpa_layer.add_to(m)
    
    folium.LayerControl(collapsed=False).add_to(m)
    m.save(output_html_path)
    return m
