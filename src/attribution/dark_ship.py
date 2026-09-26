from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any
import numpy as np
import geopandas as gpd
from pyproj import Geod
from shapely.geometry import Point, LineString, Polygon
from .models import (
    TimeWindow,
    OriginMetadata,
    TrajectoryGap,
    VesselTrajectory,
    DarkShipCandidate
)

geod = Geod(ellps="WGS84")
GOM_UTM_CRS = "EPSG:32616"

def calculate_geodesic_distance_nm(p1: Point, p2: Point) -> float:
    _, _, dist_meters = geod.inv(p1.x, p1.y, p2.x, p2.y)
    return dist_meters / 1852.0

def calculate_geodesic_distance_meters(p1: Point, p2: Point) -> float:
    _, _, dist_meters = geod.inv(p1.x, p1.y, p2.x, p2.y)
    return dist_meters

def project_dead_reckoning_point(start_pt: Point, speed_knots: float, course_deg: float, duration_hours: float) -> Point:
    dist_meters = (speed_knots * 1852.0) * duration_hours
    lon_proj, lat_proj, _ = geod.fwd(start_pt.x, start_pt.y, course_deg, dist_meters)
    return Point(lon_proj, lat_proj)

def detect_dark_ships(
    trajectories: List[VesselTrajectory],
    origin_meta: OriginMetadata,
    max_plausible_transit_speed: float = 35.0,
    proximity_alert_radius_meters: float = 10000.0,
    metric_crs: str = GOM_UTM_CRS
) -> List[DarkShipCandidate]:
    dark_candidates: List[DarkShipCandidate] = []
    win = origin_meta.time_window
    origin_poly = origin_meta.origin_polygon
    origin_cent = origin_meta.primary_centroid
    
    cent_utm = gpd.GeoSeries([origin_cent], crs="EPSG:4326").to_crs(metric_crs).iloc[0]
    poly_utm = gpd.GeoSeries([origin_poly], crs="EPSG:4326").to_crs(metric_crs).iloc[0] if origin_poly else None
    
    for traj in trajectories:
        if not traj.gaps:
            continue
            
        for gap in traj.gaps:
            temporal_overlap = bool(gap.start_time <= win.buffered_end and gap.end_time >= win.buffered_start)
            
            gap_hours = gap.duration_minutes / 60.0
            dist_nm = calculate_geodesic_distance_nm(gap.start_point, gap.end_point)
            connecting_speed = dist_nm / gap_hours if gap_hours > 0 else 0.0
            
            is_plausible = bool(connecting_speed <= max_plausible_transit_speed)
            
            projected_geom = LineString([
                (gap.start_point.x, gap.start_point.y),
                (gap.end_point.x, gap.end_point.y)
            ])
            
            proj_gdf = gpd.GeoSeries([projected_geom], crs="EPSG:4326").to_crs(metric_crs)
            proj_utm = proj_gdf.iloc[0]
            
            min_dist_m = float(cent_utm.distance(proj_utm))
            intersects_poly = bool(poly_utm.intersects(proj_utm)) if poly_utm else False
            
            is_relevant_suspect = temporal_overlap and (intersects_poly or min_dist_m <= proximity_alert_radius_meters)
            
            if is_relevant_suspect or temporal_overlap:
                candidate = DarkShipCandidate(
                    mmsi=traj.mmsi,
                    vessel_name=traj.vessel_name,
                    vessel_type=traj.vessel_type,
                    callsign=traj.callsign,
                    gap_start_time=gap.start_time,
                    gap_end_time=gap.end_time,
                    gap_duration_minutes=round(gap.duration_minutes, 1),
                    drop_point=gap.start_point,
                    reemergence_point=gap.end_point,
                    last_speed_knots=round(gap.last_speed, 2),
                    last_course_deg=round(gap.last_course, 1),
                    connecting_speed_knots=round(connecting_speed, 2),
                    is_kinematically_plausible=is_plausible,
                    temporal_overlap=temporal_overlap,
                    intersects_origin_zone=intersects_poly,
                    min_distance_to_centroid_meters=round(min_dist_m, 1),
                    projected_geometry=projected_geom
                )
                dark_candidates.append(candidate)
                
    dark_candidates.sort(key=lambda c: c.min_distance_to_centroid_meters)
    return dark_candidates

def dark_candidates_to_geodataframe(dark_candidates: List[DarkShipCandidate]) -> gpd.GeoDataFrame:
    records = []
    geometries = []
    
    for c in dark_candidates:
        geometries.append(c.projected_geometry)
        records.append({
            "mmsi": c.mmsi,
            "vessel_name": c.vessel_name,
            "vessel_type": c.vessel_type,
            "callsign": c.callsign,
            "gap_start_utc": c.gap_start_time.isoformat(),
            "gap_end_utc": c.gap_end_time.isoformat(),
            "gap_duration_minutes": c.gap_duration_minutes,
            "last_speed_knots": c.last_speed_knots,
            "connecting_speed_knots": c.connecting_speed_knots,
            "kinematically_plausible": c.is_kinematically_plausible,
            "temporal_overlap": c.temporal_overlap,
            "intersects_origin_zone": c.intersects_origin_zone,
            "min_distance_meters": c.min_distance_to_centroid_meters
        })
        
    if not records:
        return gpd.GeoDataFrame(columns=[
            "mmsi", "vessel_name", "vessel_type", "callsign", "gap_start_utc",
            "gap_end_utc", "gap_duration_minutes", "last_speed_knots",
            "connecting_speed_knots", "kinematically_plausible", "temporal_overlap",
            "intersects_origin_zone", "min_distance_meters", "geometry"
        ], crs="EPSG:4326")
        
    return gpd.GeoDataFrame(records, geometry=geometries, crs="EPSG:4326")
