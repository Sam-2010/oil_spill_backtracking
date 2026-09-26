import json
from datetime import datetime, timedelta
from typing import Union, Tuple, Dict, Any
import pandas as pd
import geopandas as gpd
from shapely.geometry import shape, Point, Polygon, box
from .models import TimeWindow, OriginMetadata, PreflightResult

def parse_iso_datetime(dt_str: str) -> datetime:
    """Robust ISO datetime parser converting to UTC timezone."""
    dt = pd.to_datetime(dt_str)
    if dt.tzinfo is None:
        dt = dt.tz_localize("UTC")
    else:
        dt = dt.tz_convert("UTC")
    return dt.to_pydatetime()

def calculate_release_window(t0: datetime, delta_t_hours: float, temporal_buffer_hours: float = 1.0) -> TimeWindow:
    """
    Applies the +/-25% uncertainty bracket around calculated elapsed age:
    Window = [T0 - 1.25 * delta_T, T0 - 0.75 * delta_T]
    """
    dt_delta = timedelta(hours=delta_t_hours)
    start_time = t0 - (1.25 * dt_delta)
    end_time = t0 - (0.75 * dt_delta)
    
    buf = timedelta(hours=temporal_buffer_hours)
    buffered_start = start_time - buf
    buffered_end = end_time + buf
    
    return TimeWindow(
        t0=t0,
        delta_t_hours=delta_t_hours,
        start_time=start_time,
        end_time=end_time,
        buffered_start=buffered_start,
        buffered_end=buffered_end
    )

def extract_origin_metadata(origin_report_path: str, corridor_geojson_path: str = None, temporal_buffer_hours: float = 1.0) -> OriginMetadata:
    """
    Extracts origin metadata, coordinates, and calculated release time window from report and corridor geojson.
    """
    with open(origin_report_path, "r", encoding="utf-8") as f:
        report = json.load(f)
        
    t0_str = report["detection_metadata"]["timestamp"]
    t0 = parse_iso_datetime(t0_str)
    delta_t = float(report["morphology_analysis"]["calculated_elapsed_hours"])
    orientation = float(report["morphology_analysis"].get("orientation_deg", 0.0))
    
    primary_cent = report["estimated_origin"]["primary_centroid"]
    centroid_pt = Point(primary_cent["longitude"], primary_cent["latitude"])
    
    time_win = calculate_release_window(t0, delta_t, temporal_buffer_hours)
    
    origin_poly = None
    if corridor_geojson_path:
        with open(corridor_geojson_path, "r", encoding="utf-8") as f:
            corridor = json.load(f)
            for feat in corridor.get("features", []):
                if feat.get("properties", {}).get("layer") == "primary_origin_candidate":
                    origin_poly = shape(feat["geometry"])
                    break
                    
    if origin_poly is None:
        origin_poly = centroid_pt.buffer(0.018)
        
    return OriginMetadata(
        t0=t0,
        delta_t_hours=delta_t,
        primary_centroid=centroid_pt,
        origin_polygon=origin_poly,
        orientation_deg=orientation,
        time_window=time_win
    )

def validate_preflight(ais_path: str, origin_meta: OriginMetadata, spatial_buffer_nm: float = 5.0) -> PreflightResult:
    """
    Validates temporal and spatial coverage of the AIS dataset against the incident release window.
    """
    errors = []
    warnings = []
    
    if ais_path.endswith(".parquet"):
        df_scan = pd.read_parquet(ais_path, columns=["timestamp", "latitude", "longitude"])
    else:
        df_scan = pd.read_csv(ais_path, usecols=["timestamp", "latitude", "longitude"])
        
    df_scan["timestamp"] = pd.to_datetime(df_scan["timestamp"], utc=True)
    
    ais_t_min = df_scan["timestamp"].min().to_pydatetime()
    ais_t_max = df_scan["timestamp"].max().to_pydatetime()
    
    ais_lat_min = df_scan["latitude"].min()
    ais_lat_max = df_scan["latitude"].max()
    ais_lon_min = df_scan["longitude"].min()
    ais_lon_max = df_scan["longitude"].max()
    
    win = origin_meta.time_window
    
    if ais_t_min > win.start_time:
        errors.append(
            f"Temporal Undercoverage: AIS dataset starts at {ais_t_min.isoformat()}, "
            f"which is after the estimated release window start ({win.start_time.isoformat()})."
        )
    elif ais_t_min > win.buffered_start:
        warnings.append(
            f"AIS data starts at {ais_t_min.isoformat()}, covering the release window but lacking the full 1-hour pre-buffer."
        )
        
    if ais_t_max < win.end_time:
        errors.append(
            f"Temporal Undercoverage: AIS dataset ends at {ais_t_max.isoformat()}, "
            f"which is before the estimated release window end ({win.end_time.isoformat()})."
        )
    elif ais_t_max < win.buffered_end:
        warnings.append(
            f"AIS data ends at {ais_t_max.isoformat()}, covering the release window but lacking the full 1-hour post-buffer."
        )
        
    buffer_deg = spatial_buffer_nm * 0.01666
    minx, miny, maxx, maxy = origin_meta.origin_polygon.bounds
    req_lat_min = miny - buffer_deg
    req_lat_max = maxy + buffer_deg
    req_lon_min = minx - buffer_deg
    req_lon_max = maxx + buffer_deg
    
    if ais_lat_min > req_lat_min or ais_lat_max < req_lat_max or ais_lon_min > req_lon_min or ais_lon_max < req_lon_max:
        errors.append(
            f"Spatial Undercoverage: AIS bounding box [{ais_lat_min:.4f}, {ais_lat_max:.4f}, {ais_lon_min:.4f}, {ais_lon_max:.4f}] "
            f"does not fully enclose required buffered release zone [{req_lat_min:.4f}, {req_lat_max:.4f}, {req_lon_min:.4f}, {req_lon_max:.4f}]."
        )
        
    passed = len(errors) == 0
    metadata = {
        "ais_time_range": {"min": ais_t_min.isoformat(), "max": ais_t_max.isoformat()},
        "release_window": {"start": win.start_time.isoformat(), "end": win.end_time.isoformat()},
        "ais_spatial_bbox": [float(ais_lat_min), float(ais_lat_max), float(ais_lon_min), float(ais_lon_max)],
        "required_spatial_bbox": [float(req_lat_min), float(req_lat_max), float(req_lon_min), float(req_lon_max)],
        "total_ais_records": len(df_scan)
    }
    
    return PreflightResult(passed=passed, warnings=warnings, errors=errors, metadata=metadata)
