from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, LineString, MultiLineString
from .models import InterpolatedPoint, TrajectoryGap, VesselTrajectory

def interpolate_angle(c1: float, c2: float, alpha: float) -> float:
    if np.isnan(c1) and np.isnan(c2):
        return 0.0
    if np.isnan(c1):
        return c2
    if np.isnan(c2):
        return c1
    diff = (c2 - c1 + 180.0) % 360.0 - 180.0
    return (c1 + alpha * diff) % 360.0

def interpolate_points(
    p1: Dict[str, Any],
    p2: Dict[str, Any],
    step_seconds: int = 60
) -> List[InterpolatedPoint]:
    t1 = p1["timestamp"]
    t2 = p2["timestamp"]
    total_seconds = (t2 - t1).total_seconds()
    
    if total_seconds <= step_seconds:
        return []
        
    num_steps = int(total_seconds // step_seconds)
    interp_points = []
    
    s1 = p1.get("speed_sanitized") or p1.get("speed_knots") or 0.0
    s2 = p2.get("speed_sanitized") or p2.get("speed_knots") or 0.0
    c1 = p1.get("course_sanitized") or p1.get("course_deg") or 0.0
    c2 = p2.get("course_sanitized") or p2.get("course_deg") or 0.0
    
    for i in range(1, num_steps + 1):
        step_dt = t1 + timedelta(seconds=i * step_seconds)
        if step_dt >= t2:
            break
        alpha = (step_dt - t1).total_seconds() / total_seconds
        
        lat = p1["latitude"] + alpha * (p2["latitude"] - p1["latitude"])
        lon = p1["longitude"] + alpha * (p2["longitude"] - p1["longitude"])
        speed = s1 + alpha * (s2 - s1) if not (np.isnan(s1) or np.isnan(s2)) else (s1 if not np.isnan(s1) else s2)
        course = interpolate_angle(c1, c2, alpha)
        
        interp_points.append(
            InterpolatedPoint(
                timestamp=step_dt,
                latitude=float(lat),
                longitude=float(lon),
                speed_knots=float(speed) if not np.isnan(speed) else 0.0,
                course_deg=float(course),
                is_interpolated=True
            )
        )
        
    return interp_points

def reconstruct_vessel_trajectories(
    sanitized_ais_gdf: gpd.GeoDataFrame,
    max_interpolation_gap_minutes: float = 15.0,
    gap_threshold_minutes: float = 30.0,
    interpolation_step_seconds: int = 60
) -> List[VesselTrajectory]:
    trajectories = []
    max_gap_seconds = max_interpolation_gap_minutes * 60.0
    gap_threshold_seconds = gap_threshold_minutes * 60.0
    
    grouped = sanitized_ais_gdf.groupby("mmsi")
    
    for mmsi, group in grouped:
        group = group.sort_values(by="timestamp").reset_index(drop=True)
        raw_count = len(group)
        
        vessel_name = str(group["vessel_name"].dropna().iloc[0]) if "vessel_name" in group.columns and not group["vessel_name"].dropna().empty else f"MMSI_{mmsi}"
        vessel_type = int(group["vessel_type"].dropna().iloc[0]) if "vessel_type" in group.columns and not group["vessel_type"].dropna().empty else None
        callsign = str(group["callsign"].dropna().iloc[0]) if "callsign" in group.columns and not group["callsign"].dropna().empty else None
        
        all_points: List[InterpolatedPoint] = []
        gaps: List[TrajectoryGap] = []
        coords = []
        
        rows = group.to_dict(orient="records")
        for i in range(len(rows)):
            cur = rows[i]
            cur_time = cur["timestamp"].to_pydatetime()
            cur_s = cur.get("speed_sanitized") or cur.get("speed_knots") or 0.0
            cur_c = cur.get("course_sanitized") or cur.get("course_deg") or 0.0
            
            pt_obj = InterpolatedPoint(
                timestamp=cur_time,
                latitude=float(cur["latitude"]),
                longitude=float(cur["longitude"]),
                speed_knots=float(cur_s) if not np.isnan(cur_s) else 0.0,
                course_deg=float(cur_c) if not np.isnan(cur_c) else 0.0,
                is_interpolated=False
            )
            all_points.append(pt_obj)
            coords.append((pt_obj.longitude, pt_obj.latitude))
            
            if i < len(rows) - 1:
                nxt = rows[i + 1]
                nxt_time = nxt["timestamp"].to_pydatetime()
                delta_sec = (nxt_time - cur_time).total_seconds()
                
                if delta_sec >= gap_threshold_seconds:
                    gaps.append(
                        TrajectoryGap(
                            start_time=cur_time,
                            end_time=nxt_time,
                            duration_minutes=delta_sec / 60.0,
                            start_point=Point(cur["longitude"], cur["latitude"]),
                            end_point=Point(nxt["longitude"], nxt["latitude"]),
                            last_speed=float(cur_s) if not np.isnan(cur_s) else 0.0,
                            last_course=float(cur_c) if not np.isnan(cur_c) else 0.0
                        )
                    )
                    
                if 0 < delta_sec <= max_gap_seconds:
                    interp = interpolate_points(cur, nxt, step_seconds=interpolation_step_seconds)
                    all_points.extend(interp)
                    for ip in interp:
                        coords.append((ip.longitude, ip.latitude))
                        
        all_points.sort(key=lambda p: p.timestamp)
        
        linestring = None
        if len(coords) >= 2:
            dedup_coords = [coords[0]]
            for c in coords[1:]:
                if c != dedup_coords[-1]:
                    dedup_coords.append(c)
            if len(dedup_coords) >= 2:
                linestring = LineString(dedup_coords)
            elif len(dedup_coords) == 1:
                linestring = None
                
        speeds = [p.speed_knots for p in all_points if not np.isnan(p.speed_knots)]
        if speeds:
            avg_speed = float(np.mean(speeds))
            min_speed = float(np.min(speeds))
            max_speed = float(np.max(speeds))
            speed_std = float(np.std(speeds))
        else:
            avg_speed = min_speed = max_speed = speed_std = 0.0
            
        loitering_detected = bool(avg_speed < 3.0 or (speed_std > 5.0 and min_speed < 1.0))
        
        trajectories.append(
            VesselTrajectory(
                mmsi=int(mmsi),
                vessel_name=vessel_name,
                vessel_type=vessel_type,
                callsign=callsign,
                raw_points_count=raw_count,
                interpolated_points=all_points,
                linestring=linestring,
                avg_speed=avg_speed,
                min_speed=min_speed,
                max_speed=max_speed,
                speed_std=speed_std,
                loitering_detected=loitering_detected,
                gaps=gaps
            )
        )
        
    return trajectories

def trajectories_to_geodataframe(trajectories: List[VesselTrajectory]) -> gpd.GeoDataFrame:
    records = []
    geometries = []
    
    for traj in trajectories:
        if traj.linestring is not None:
            geometries.append(traj.linestring)
            records.append({
                "mmsi": traj.mmsi,
                "vessel_name": traj.vessel_name,
                "vessel_type": traj.vessel_type,
                "callsign": traj.callsign,
                "raw_points_count": traj.raw_points_count,
                "total_points_count": len(traj.interpolated_points),
                "avg_speed_knots": round(traj.avg_speed, 2),
                "min_speed_knots": round(traj.min_speed, 2),
                "max_speed_knots": round(traj.max_speed, 2),
                "speed_std_knots": round(traj.speed_std, 2),
                "loitering_detected": traj.loitering_detected,
                "gaps_count": len(traj.gaps)
            })
            
    if not records:
        return gpd.GeoDataFrame(columns=[
            "mmsi", "vessel_name", "vessel_type", "callsign", "raw_points_count",
            "total_points_count", "avg_speed_knots", "min_speed_knots", "max_speed_knots",
            "speed_std_knots", "loitering_detected", "gaps_count", "geometry"
        ], crs="EPSG:4326")
        
    return gpd.GeoDataFrame(records, geometry=geometries, crs="EPSG:4326")
