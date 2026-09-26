from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import geopandas as gpd
from shapely.geometry import Point, LineString, Polygon
from pyproj import Geod

from .models import (
    OriginMetadata,
    TimeWindow,
    VesselTrajectory,
    DarkShipCandidate,
    VesselCPA
)

geod = Geod(ellps="WGS84")
GOM_UTM_CRS = "EPSG:32616"

def calculate_slick_alignment_diff(vessel_course: float, slick_axis_deg: float) -> float:
    if np.isnan(vessel_course):
        return 45.0
    diff = abs(vessel_course - slick_axis_deg) % 360.0
    diff = min(diff, 360.0 - diff)
    folded = min(diff, abs(diff - 180.0))
    return float(min(folded, 90.0))

def compute_active_vessel_cpa(
    traj: VesselTrajectory,
    origin_meta: OriginMetadata,
    metric_crs: str = GOM_UTM_CRS
) -> Optional[VesselCPA]:
    if not traj.interpolated_points:
        return None
        
    origin_cent = origin_meta.primary_centroid
    origin_poly = origin_meta.origin_polygon
    win = origin_meta.time_window
    t_release_center = win.t0 - timedelta(hours=origin_meta.delta_t_hours)
    
    cent_utm = gpd.GeoSeries([origin_cent], crs="EPSG:4326").to_crs(metric_crs).iloc[0]
    poly_utm = gpd.GeoSeries([origin_poly], crs="EPSG:4326").to_crs(metric_crs).iloc[0] if origin_poly else None
    
    pts_wgs84 = [Point(p.longitude, p.latitude) for p in traj.interpolated_points]
    pts_utm = gpd.GeoSeries(pts_wgs84, crs="EPSG:4326").to_crs(metric_crs)
    
    distances = [float(cent_utm.distance(pt)) for pt in pts_utm]
    min_idx = int(np.argmin(distances))
    min_dist_m = distances[min_idx]
    
    cpa_pt_obj = traj.interpolated_points[min_idx]
    cpa_time = cpa_pt_obj.timestamp
    cpa_point = Point(cpa_pt_obj.longitude, cpa_pt_obj.latitude)
    cpa_speed = cpa_pt_obj.speed_knots
    cpa_course = cpa_pt_obj.course_deg
    
    intersects_poly = False
    if poly_utm and traj.linestring:
        line_utm = gpd.GeoSeries([traj.linestring], crs="EPSG:4326").to_crs(metric_crs).iloc[0]
        intersects_poly = bool(poly_utm.intersects(line_utm))
        
    time_offset_hours = abs((cpa_time - t_release_center).total_seconds()) / 3600.0
    within_window = bool(win.start_time <= cpa_time <= win.end_time)
    slick_diff = calculate_slick_alignment_diff(cpa_course, origin_meta.orientation_deg)
    
    return VesselCPA(
        mmsi=traj.mmsi,
        vessel_name=traj.vessel_name,
        vessel_type=traj.vessel_type,
        callsign=traj.callsign,
        is_dark_ship=False,
        cpa_timestamp=cpa_time,
        cpa_point=cpa_point,
        cpa_distance_meters=round(min_dist_m, 1),
        speed_at_cpa=round(cpa_speed, 2),
        course_at_cpa=round(cpa_course, 1),
        intersects_origin_polygon=intersects_poly,
        time_offset_from_release_hours=round(time_offset_hours, 2),
        is_within_release_window=within_window,
        slick_alignment_diff_deg=round(slick_diff, 1)
    )

def compute_dark_candidate_cpa(
    dark_cand: DarkShipCandidate,
    origin_meta: OriginMetadata,
    metric_crs: str = GOM_UTM_CRS
) -> VesselCPA:
    origin_cent = origin_meta.primary_centroid
    win = origin_meta.time_window
    t_release_center = win.t0 - timedelta(hours=origin_meta.delta_t_hours)
    
    cent_utm = gpd.GeoSeries([origin_cent], crs="EPSG:4326").to_crs(metric_crs).iloc[0]
    line_utm = gpd.GeoSeries([dark_cand.projected_geometry], crs="EPSG:4326").to_crs(metric_crs).iloc[0]
    
    proj_dist = line_utm.project(cent_utm)
    total_len = line_utm.length
    alpha = proj_dist / total_len if total_len > 0 else 0.5
    alpha = max(0.0, min(1.0, alpha))
    
    total_gap_sec = (dark_cand.gap_end_time - dark_cand.gap_start_time).total_seconds()
    cpa_time = dark_cand.gap_start_time + timedelta(seconds=alpha * total_gap_sec)
    
    cpa_point_utm = line_utm.interpolate(proj_dist)
    cpa_point_wgs = gpd.GeoSeries([cpa_point_utm], crs=metric_crs).to_crs("EPSG:4326").iloc[0]
    
    min_dist_m = float(cent_utm.distance(cpa_point_utm))
    time_offset_hours = abs((cpa_time - t_release_center).total_seconds()) / 3600.0
    within_window = bool(win.start_time <= cpa_time <= win.end_time)
    
    _, _, course_between = geod.inv(
        dark_cand.drop_point.x, dark_cand.drop_point.y,
        dark_cand.reemergence_point.x, dark_cand.reemergence_point.y
    )
    course_between = (course_between + 360.0) % 360.0
    course_to_use = dark_cand.last_course_deg if not np.isnan(dark_cand.last_course_deg) else course_between
    slick_diff = calculate_slick_alignment_diff(course_to_use, origin_meta.orientation_deg)
    
    return VesselCPA(
        mmsi=dark_cand.mmsi,
        vessel_name=dark_cand.vessel_name,
        vessel_type=dark_cand.vessel_type,
        callsign=dark_cand.callsign,
        is_dark_ship=True,
        cpa_timestamp=cpa_time,
        cpa_point=cpa_point_wgs,
        cpa_distance_meters=round(min_dist_m, 1),
        speed_at_cpa=round(dark_cand.connecting_speed_knots, 2),
        course_at_cpa=round(course_to_use, 1),
        intersects_origin_polygon=dark_cand.intersects_origin_zone,
        time_offset_from_release_hours=round(time_offset_hours, 2),
        is_within_release_window=within_window,
        slick_alignment_diff_deg=round(slick_diff, 1)
    )

def calculate_all_cpas(
    active_trajectories: List[VesselTrajectory],
    dark_candidates: List[DarkShipCandidate],
    origin_meta: OriginMetadata,
    metric_crs: str = GOM_UTM_CRS
) -> List[VesselCPA]:
    cpas: List[VesselCPA] = []
    
    for traj in active_trajectories:
        cpa = compute_active_vessel_cpa(traj, origin_meta, metric_crs=metric_crs)
        if cpa:
            cpas.append(cpa)
            
    for dark in dark_candidates:
        cpa = compute_dark_candidate_cpa(dark, origin_meta, metric_crs=metric_crs)
        cpas.append(cpa)
        
    cpas.sort(key=lambda x: x.cpa_distance_meters)
    return cpas

def cpas_to_geodataframe(cpas: List[VesselCPA]) -> gpd.GeoDataFrame:
    records = []
    geometries = []
    
    for c in cpas:
        geometries.append(c.cpa_point)
        records.append({
            "mmsi": c.mmsi,
            "vessel_name": c.vessel_name,
            "vessel_type": c.vessel_type,
            "callsign": c.callsign,
            "is_dark_ship": c.is_dark_ship,
            "cpa_timestamp_utc": c.cpa_timestamp.isoformat(),
            "cpa_distance_meters": c.cpa_distance_meters,
            "speed_at_cpa_knots": c.speed_at_cpa,
            "course_at_cpa_deg": c.course_at_cpa,
            "intersects_origin_polygon": c.intersects_origin_polygon,
            "time_offset_hours": c.time_offset_from_release_hours,
            "within_release_window": c.is_within_release_window,
            "slick_alignment_diff_deg": c.slick_alignment_diff_deg
        })
        
    if not records:
        return gpd.GeoDataFrame(columns=[
            "mmsi", "vessel_name", "vessel_type", "callsign", "is_dark_ship",
            "cpa_timestamp_utc", "cpa_distance_meters", "speed_at_cpa_knots",
            "course_at_cpa_deg", "intersects_origin_polygon", "time_offset_hours",
            "within_release_window", "slick_alignment_diff_deg", "geometry"
        ], crs="EPSG:4326")
        
    return gpd.GeoDataFrame(records, geometry=geometries, crs="EPSG:4326")
