import math
from typing import List, Dict, Any, Optional
import numpy as np
import geopandas as gpd
from .models import (
    OriginMetadata,
    VesselCPA,
    ScoredCandidate
)

def calculate_dynamic_weights(delta_t_hours: float, scoring_cfg: Dict[str, Any]) -> Dict[str, float]:
    mode = scoring_cfg.get("mode", "dynamic")
    if mode == "static":
        raw_weights = scoring_cfg.get("static_weights", {
            "proximity": 0.25, "time": 0.25, "vessel_type": 0.20, "alignment": 0.15, "ais_gap": 0.15
        })
        total = sum(raw_weights.values())
        return {k: v / total for k, v in raw_weights.items()}
        
    anchors = scoring_cfg.get("dynamic_anchors", {})
    t_min = float(anchors.get("t_min_hours", 1.5))
    t_max = float(anchors.get("t_max_hours", 28.0))
    
    fresh_p = anchors.get("fresh_profile", {
        "proximity": 0.30, "time": 0.30, "vessel_type": 0.15, "alignment": 0.15, "ais_gap": 0.10
    })
    weathered_p = anchors.get("weathered_profile", {
        "proximity": 0.15, "time": 0.10, "vessel_type": 0.30, "alignment": 0.15, "ais_gap": 0.30
    })
    
    if t_max <= t_min:
        alpha = 0.5
    else:
        alpha = max(0.0, min(1.0, (delta_t_hours - t_min) / (t_max - t_min)))
        
    interpolated = {}
    for key in ["proximity", "time", "vessel_type", "alignment", "ais_gap"]:
        w_f = float(fresh_p.get(key, 0.2))
        w_w = float(weathered_p.get(key, 0.2))
        interpolated[key] = (1.0 - alpha) * w_f + alpha * w_w
        
    total = sum(interpolated.values())
    return {k: round(v / total, 4) for k, v in interpolated.items()}

def score_vessel_type(vessel_type: Optional[int]) -> float:
    if vessel_type is None:
        return 25.0
    vt = int(vessel_type)
    if 80 <= vt <= 89:
        return 100.0
    elif 70 <= vt <= 79:
        return 65.0
    elif 90 <= vt <= 99:
        return 40.0
    elif vt in (31, 32, 52):
        return 30.0
    elif 60 <= vt <= 69:
        return 20.0
    elif vt in (30, 36, 37):
        return 15.0
    elif vt == 35:
        return 10.0
    return 25.0

def score_proximity(distance_meters: float, intersects_polygon: bool, origin_radius_m: float = 2000.0) -> float:
    if intersects_polygon or distance_meters <= origin_radius_m:
        return 100.0
    excess = distance_meters - origin_radius_m
    score = 100.0 * math.exp(-excess / 4000.0)
    return float(max(0.0, min(100.0, score)))

def score_time(is_within_window: bool, time_offset_hours: float, half_window_hours: float) -> float:
    if is_within_window:
        return 100.0
    excess = max(0.0, time_offset_hours - half_window_hours)
    score = 100.0 * math.exp(-excess / 2.5)
    return float(max(0.0, min(100.0, score)))

def score_alignment(diff_deg: float) -> float:
    clamped_diff = max(0.0, min(90.0, diff_deg))
    score = 100.0 - (90.0 * (clamped_diff / 90.0))
    return float(max(10.0, min(100.0, score)))

def score_ais_gap(is_dark_ship: bool, intersects_polygon: bool, distance_meters: float) -> float:
    if not is_dark_ship:
        return 0.0
    if intersects_polygon:
        return 100.0
    score = 100.0 * math.exp(-distance_meters / 6000.0)
    return float(max(30.0, min(100.0, score)))

def build_audit_rationale(cpa: VesselCPA, s_prox: float, s_time: float, s_type: float, s_gap: float, total: float) -> str:
    points = []
    if cpa.is_dark_ship:
        points.append(f"Exhibited intentional AIS transponder blackout (CPA ~{cpa.cpa_distance_meters:.0f}m)")
    else:
        points.append(f"Active AIS transit passing within {cpa.cpa_distance_meters:.0f}m of origin")
        
    if cpa.intersects_origin_polygon:
        points.append("Trajectory crossed directly through the backtracked origin polygon")
        
    if cpa.is_within_release_window:
        points.append(f"Passed inside estimated release window ({cpa.time_offset_from_release_hours:.1f}h from center)")
    else:
        points.append(f"Passed {cpa.time_offset_from_release_hours:.1f}h outside estimated release window")
        
    v_type_desc = "Tanker" if (cpa.vessel_type and 80 <= cpa.vessel_type <= 89) else ("Cargo" if (cpa.vessel_type and 70 <= cpa.vessel_type <= 79) else f"Type {cpa.vessel_type}")
    points.append(f"Vessel profile: {v_type_desc}")
    
    if cpa.slick_alignment_diff_deg <= 15.0:
        points.append(f"Course aligned parallel with slick trail ({cpa.slick_alignment_diff_deg:.1f}° diff)")
        
    return "; ".join(points) + f". Composite suspicion: {total:.1f}%."

def score_all_candidates(
    cpas: List[VesselCPA],
    origin_meta: OriginMetadata,
    config: Dict[str, Any]
) -> List[ScoredCandidate]:
    scoring_cfg = config.get("scoring", {})
    weights = calculate_dynamic_weights(origin_meta.delta_t_hours, scoring_cfg)
    
    win = origin_meta.time_window
    half_window_hours = ((win.end_time - win.start_time).total_seconds() / 3600.0) / 2.0
    
    scored: List[ScoredCandidate] = []
    
    for c in cpas:
        s_prox = score_proximity(c.cpa_distance_meters, c.intersects_origin_polygon)
        s_time = score_time(c.is_within_release_window, c.time_offset_from_release_hours, half_window_hours)
        s_type = score_vessel_type(c.vessel_type)
        s_align = score_alignment(c.slick_alignment_diff_deg)
        s_gap = score_ais_gap(c.is_dark_ship, c.intersects_origin_polygon, c.cpa_distance_meters)
        
        total = (
            weights["proximity"] * s_prox +
            weights["time"] * s_time +
            weights["vessel_type"] * s_type +
            weights["alignment"] * s_align +
            weights["ais_gap"] * s_gap
        )
        total = round(total, 1)
        
        if total >= 70.0:
            level = "HIGH"
        elif total >= 50.0:
            level = "MEDIUM"
        elif total >= 30.0:
            level = "LOW"
        else:
            level = "NEGLIGIBLE"
            
        rationale = build_audit_rationale(c, s_prox, s_time, s_type, s_gap, total)
        
        scored.append(
            ScoredCandidate(
                mmsi=c.mmsi,
                vessel_name=c.vessel_name,
                vessel_type=c.vessel_type,
                callsign=c.callsign,
                is_dark_ship=c.is_dark_ship,
                cpa_distance_meters=c.cpa_distance_meters,
                cpa_timestamp=c.cpa_timestamp,
                speed_at_cpa=c.speed_at_cpa,
                course_at_cpa=c.course_at_cpa,
                s_prox=round(s_prox, 1),
                s_time=round(s_time, 1),
                s_type=round(s_type, 1),
                s_align=round(s_align, 1),
                s_gap=round(s_gap, 1),
                total_score=total,
                suspicion_level=level,
                weights_applied=weights,
                audit_rationale=rationale,
                cpa_point=c.cpa_point
            )
        )
        
    scored.sort(key=lambda s: s.total_score, reverse=True)
    return scored

def scored_candidates_to_geodataframe(scored_candidates: List[ScoredCandidate]) -> gpd.GeoDataFrame:
    records = []
    geometries = []
    
    for s in scored_candidates:
        geometries.append(s.cpa_point)
        records.append({
            "mmsi": s.mmsi,
            "vessel_name": s.vessel_name,
            "vessel_type": s.vessel_type,
            "callsign": s.callsign,
            "is_dark_ship": s.is_dark_ship,
            "cpa_timestamp_utc": s.cpa_timestamp.isoformat(),
            "cpa_distance_meters": s.cpa_distance_meters,
            "speed_knots": s.speed_at_cpa,
            "course_deg": s.course_at_cpa,
            "s_prox": s.s_prox,
            "s_time": s.s_time,
            "s_type": s.s_type,
            "s_align": s.s_align,
            "s_gap": s.s_gap,
            "total_score": s.total_score,
            "suspicion_level": s.suspicion_level,
            "audit_rationale": s.audit_rationale
        })
        
    if not records:
        return gpd.GeoDataFrame(columns=[
            "mmsi", "vessel_name", "vessel_type", "callsign", "is_dark_ship",
            "cpa_timestamp_utc", "cpa_distance_meters", "speed_knots", "course_deg",
            "s_prox", "s_time", "s_type", "s_align", "s_gap", "total_score",
            "suspicion_level", "audit_rationale", "geometry"
        ], crs="EPSG:4326")
        
    return gpd.GeoDataFrame(records, geometry=geometries, crs="EPSG:4326")
